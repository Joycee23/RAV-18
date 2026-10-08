import uuid
from types import SimpleNamespace

from app.routers import incidents as incident_routes
from app.services.media_storage import optional_media_storage


class FakeStorage:
    def __init__(self):
        self.uploads = []
        self.deletes = []
        self.urls = []

    def upload(self, incident_id, data, path, mime):
        self.uploads.append((incident_id, data, path, mime))

    def delete(self, path):
        self.deletes.append(path)

    def signed_url(self, path, ttl):
        self.urls.append((path, ttl))
        return "https://private.example/signed"


def _incident(sessions):
    from test_incidents import make_incident
    return make_incident(sessions, with_evidence=False)


def _install_storage(monkeypatch, storage):
    from app.main import app
    app.dependency_overrides[optional_media_storage] = lambda: storage
    monkeypatch.setattr(incident_routes, "get_settings", lambda: SimpleNamespace(
        max_video_bytes=100, max_video_duration_seconds=30,
    ))


def test_upload_accepts_valid_clip_and_records_private_metadata(client, monkeypatch):
    api, sessions = client
    incident_id = _incident(sessions)
    storage = FakeStorage()
    _install_storage(monkeypatch, storage)
    monkeypatch.setattr(incident_routes, "inspect_video", lambda data, maximum: ("video/mp4", 4.5))
    payload = b"video bytes"

    response = api.post(f"/api/incidents/{incident_id}/media", files={"file": ("clip.mp4", payload, "video/mp4")})

    assert response.status_code == 200
    evidence = response.json()
    assert evidence["evidence_type"] == "video_clip"
    assert evidence["metadata"]["source"] == "user_upload"
    assert evidence["metadata"]["duration_seconds"] == 4.5
    assert evidence["metadata"]["size_bytes"] == len(payload)
    assert evidence["metadata"]["storage_path"].startswith(f"{incident_id}/")
    assert storage.uploads[0][1:] == (payload, evidence["metadata"]["storage_path"], "video/mp4")
    assert storage.deletes == []


def test_upload_normalizes_recorded_at_to_utc_and_persists_it(client, monkeypatch):
    from datetime import datetime, UTC
    from app.models import Evidence

    api, sessions = client
    incident_id = _incident(sessions)
    storage = FakeStorage()
    _install_storage(monkeypatch, storage)
    monkeypatch.setattr(incident_routes, "inspect_video", lambda data, maximum: ("video/mp4", 4.5))
    recorded = "2026-10-08T20:30:00+05:30"

    response = api.post(f"/api/incidents/{incident_id}/media", data={"recorded_at": recorded},
                        files={"file": ("clip.mp4", b"video bytes", "video/mp4")})

    assert response.status_code == 200
    evidence_id = response.json()["id"]
    assert response.json()["timestamp"] == "2026-10-08T15:00:00"
    assert response.json()["metadata"]["recorded_at"] == "2026-10-08T15:00:00+00:00"
    with sessions() as session:
        evidence = session.get(Evidence, uuid.UUID(evidence_id))
        assert evidence.timestamp.replace(tzinfo=UTC) == datetime(2026, 10, 8, 15, 0, tzinfo=UTC)


def test_upload_defaults_recorded_at_to_incident_time(client, monkeypatch):
    from datetime import UTC
    from app.models import Incident

    api, sessions = client
    incident_id = _incident(sessions)
    with sessions() as session:
        incident_time = session.get(Incident, incident_id).occurred_at.replace(tzinfo=UTC)
    storage = FakeStorage()
    _install_storage(monkeypatch, storage)
    monkeypatch.setattr(incident_routes, "inspect_video", lambda data, maximum: ("video/mp4", 4.5))

    response = api.post(f"/api/incidents/{incident_id}/media", files={"file": ("clip.mp4", b"video bytes", "video/mp4")})

    assert response.status_code == 200
    assert response.json()["metadata"]["recorded_at"] == "2026-01-01T12:00:00+00:00"
    assert response.json()["timestamp"] == "2026-01-01T12:00:00"


def test_upload_rejects_naive_recorded_at_before_storage_or_evidence_write(client, monkeypatch):
    from app.models import Evidence

    api, sessions = client
    incident_id = _incident(sessions)
    storage = FakeStorage()
    _install_storage(monkeypatch, storage)
    monkeypatch.setattr(incident_routes, "inspect_video", lambda data, maximum: ("video/mp4", 4.5))

    response = api.post(f"/api/incidents/{incident_id}/media", data={"recorded_at": "2026-10-08T20:30:00"},
                        files={"file": ("clip.mp4", b"video bytes", "video/mp4")})

    assert response.status_code == 422
    assert storage.uploads == []
    with sessions() as session:
        assert session.query(Evidence).filter(Evidence.incident_id == incident_id).count() == 0


def test_upload_rejects_mime_size_and_duration(client, monkeypatch):
    api, sessions = client
    incident_id = _incident(sessions)
    storage = FakeStorage()
    _install_storage(monkeypatch, storage)
    assert api.post(f"/api/incidents/{incident_id}/media", files={"file": ("x.txt", b"x", "text/plain")}).status_code == 415
    assert api.post(f"/api/incidents/{incident_id}/media", files={"file": ("x.mp4", b"x" * 101, "video/mp4")}).status_code == 422
    import cv2
    class LongClip:
        def isOpened(self): return True
        def read(self): return True, object()
        def get(self, prop): return 31.0 if prop == cv2.CAP_PROP_FRAME_COUNT else 1.0
        def release(self): pass
    monkeypatch.setattr(cv2, "VideoCapture", lambda _path: LongClip())
    monkeypatch.setattr(incident_routes, "inspect_video", __import__("app.services.video_analysis", fromlist=["inspect_video"]).inspect_video)
    mp4 = b"\x00\x00\x00\x18ftypisomxxxx"
    assert api.post(f"/api/incidents/{incident_id}/media", files={"file": ("x.mp4", mp4, "video/mp4")}).status_code == 422
    assert storage.uploads == []


def test_upload_rejects_container_mime_mismatch_and_empty_file(client, monkeypatch):
    api, sessions = client
    incident_id = _incident(sessions)
    storage = FakeStorage()
    _install_storage(monkeypatch, storage)
    monkeypatch.setattr(incident_routes, "inspect_video", lambda data, maximum: ("video/quicktime", 2.0))
    mismatch = api.post(f"/api/incidents/{incident_id}/media", files={"file": ("x.mp4", b"bytes", "video/mp4")})
    empty = api.post(f"/api/incidents/{incident_id}/media", files={"file": ("x.mp4", b"", "video/mp4")})
    assert mismatch.status_code == 422
    assert empty.status_code == 422
    assert storage.uploads == []


def test_signed_url_is_scoped_to_incident_and_uses_five_minute_ttl(client, monkeypatch):
    api, sessions = client
    incident_id = _incident(sessions)
    storage = FakeStorage()
    _install_storage(monkeypatch, storage)
    monkeypatch.setattr(incident_routes, "inspect_video", lambda data, maximum: ("video/mp4", 4.0))
    upload = api.post(f"/api/incidents/{incident_id}/media", files={"file": ("clip.mp4", b"bytes", "video/mp4")})
    evidence_id = upload.json()["id"]
    result = api.get(f"/api/incidents/{incident_id}/media/{evidence_id}/url")
    assert result.status_code == 200
    assert result.json()["url"] == "https://private.example/signed"
    assert storage.urls[0][1] == 300
    assert api.get(f"/api/incidents/{uuid.uuid4()}/media/{evidence_id}/url").status_code == 404


def test_upload_deletes_object_if_database_insert_fails(client, monkeypatch):
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    from app.models import Evidence

    api, sessions = client
    incident_id = _incident(sessions)
    storage = FakeStorage()
    _install_storage(monkeypatch, storage)
    monkeypatch.setattr(incident_routes, "inspect_video", lambda data, maximum: ("video/mp4", 4.0))

    def fail_evidence_flush(session, flush_context, instances):
        if any(isinstance(item, Evidence) for item in session.new):
            raise RuntimeError("simulated database failure")

    event.listen(Session, "before_flush", fail_evidence_flush)
    try:
        response = api.post(f"/api/incidents/{incident_id}/media", files={"file": ("clip.mp4", b"bytes", "video/mp4")})
    finally:
        event.remove(Session, "before_flush", fail_evidence_flush)
    assert response.status_code == 503
    assert len(storage.uploads) == len(storage.deletes) == 1
    assert storage.deletes[0] == storage.uploads[0][2]
