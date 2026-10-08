import uuid
from datetime import UTC, datetime, timedelta

from app.models import Evidence, Incident, LogEvent


def make_incident(session_factory, *, with_evidence=True, offset_seconds=3):
    incident_id = uuid.uuid4()
    occurred = datetime(2026, 1, 1, 12, tzinfo=UTC)
    with session_factory() as session:
        incident = Incident(
            id=incident_id,
            title="Synthetic braking event",
            severity="high",
            status="open",
            occurred_at=occurred,
            vehicle_id="demo-01",
            summary="Synthetic incident for behavior testing.",
            metadata_json={"source": "test"},
        )
        incident.events.append(LogEvent(
            timestamp=occurred, source="vehicle", event_type="hard_brake",
            message="Hard braking detected", details={"speed": 12},
        ))
        if with_evidence:
            incident.evidence.append(Evidence(
                timestamp=occurred + timedelta(seconds=offset_seconds),
                evidence_type="video_metadata", label="Synthetic clip metadata",
                description="Metadata only; no video frames were interpreted.",
                metadata_json={"synthetic": True},
            ))
        session.add(incident)
        session.commit()
    return incident_id


def test_list_and_detail_sort_timeline_and_filter(client):
    api, sessions = client
    first_id = make_incident(sessions)
    second_id = make_incident(sessions, with_evidence=False)

    response = api.get("/api/incidents?severity=high&status=open")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 2

    detail = api.get(f"/api/incidents/{first_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["metadata"] == {"source": "test"}
    assert body["events"][0]["event_type"] == "hard_brake"
    assert body["evidence"][0]["metadata"] == {"synthetic": True}
    assert api.get("/api/incidents?severity=not-a-severity").json()["items"] == []
    assert api.get(f"/api/incidents/{second_id}").status_code == 200


def test_invalid_or_missing_incident_is_not_found_or_validation_error(client):
    api, _ = client
    assert api.get(f"/api/incidents/{uuid.uuid4()}").status_code == 404
    assert api.get("/api/incidents/not-a-uuid").status_code == 422
    assert api.post(f"/api/incidents/{uuid.uuid4()}/analyze").status_code == 404


def test_analysis_only_creates_finding_with_temporally_aligned_evidence(client):
    api, sessions = client
    incident_id = make_incident(sessions, offset_seconds=15)

    detail = api.get(f"/api/incidents/{incident_id}")
    assert detail.status_code == 200
    evidence_id = detail.json()["evidence"][0]["id"]

    response = api.post(f"/api/incidents/{incident_id}/analyze")
    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "awaiting_review"
    assert [step["name"] for step in run["steps"]] == [
        "load_incident", "read_drive_logs", "sample_video_metadata",
        "align_timeline", "draft_report",
    ]
    assert len(run["findings"]) == 1
    evidence_ids = run["findings"][0]["evidence_ids"]
    assert evidence_ids == [evidence_id]
    assert all(str(uuid.UUID(value)) == value for value in evidence_ids)


def test_analysis_without_evidence_or_outside_time_window_has_warning_and_no_finding(client):
    api, sessions = client
    missing_id = make_incident(sessions, with_evidence=False)
    outside_id = make_incident(sessions, offset_seconds=16)

    for incident_id in (missing_id, outside_id):
        response = api.post(f"/api/incidents/{incident_id}/analyze")
        assert response.status_code == 200
        run = response.json()
        assert run["status"] == "completed"
        assert run["findings"] == []
        assert "Insufficient" in run["warning"]
