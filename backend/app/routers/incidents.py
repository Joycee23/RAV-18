import uuid
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app import repositories
from app.db import get_db
from app.schemas import AnalysisRunRead, EvidenceRead, IncidentDetail, IncidentList, ReviewActionCreate, ReviewActionRead, SignedMediaUrl
from app.services.analysis import run_analysis
from app.services.media_storage import MediaStorage, optional_media_storage
from app.services.video_analysis import inspect_video
from app.config import get_settings
from app.models import Evidence
from app.services.review import ReviewConflict, review_analysis

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("", response_model=IncidentList)
def incidents(status: str | None = Query(default=None), severity: str | None = Query(default=None), db: Session = Depends(get_db)) -> IncidentList:
    return IncidentList(items=repositories.list_incidents(db, status=status, severity=severity))


@router.get("/{incident_id}", response_model=IncidentDetail)
def incident_detail(incident_id: uuid.UUID, db: Session = Depends(get_db)) -> IncidentDetail:
    incident = repositories.get_incident(db, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return IncidentDetail.model_validate(incident)


@router.post("/{incident_id}/analyze", response_model=AnalysisRunRead)
def analyze(incident_id: uuid.UUID, db: Session = Depends(get_db), storage: MediaStorage | None = Depends(optional_media_storage)) -> AnalysisRunRead:
    try:
        return run_analysis(db, incident_id, storage=storage)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Incident not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail="Analysis failed") from exc


@router.post("/{incident_id}/media", response_model=EvidenceRead)
async def upload_media(incident_id: uuid.UUID, file: UploadFile, recorded_at: datetime | None = Form(default=None), db: Session = Depends(get_db), storage: MediaStorage | None = Depends(optional_media_storage)) -> EvidenceRead:
    incident = repositories.get_incident(db, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    if recorded_at is not None and recorded_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="recorded_at must include a timezone")
    if storage is None:
        raise HTTPException(status_code=503, detail="Private media storage is not configured")
    settings = get_settings()
    accepted_mimes = {"video/mp4", "video/quicktime", "video/webm"}
    if file.content_type not in accepted_mimes:
        raise HTTPException(status_code=415, detail="Only MP4, MOV, or WebM video is supported")
    try:
        data = await file.read(settings.max_video_bytes + 1)
        if not data or len(data) > settings.max_video_bytes:
            raise ValueError("Video is empty or exceeds the configured size limit")
        detected_mime, duration = inspect_video(data, settings.max_video_duration_seconds)
        if detected_mime != file.content_type:
            raise ValueError("Video content does not match its declared MIME type")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()
    suffix = {"video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm"}[detected_mime]
    object_path = f"{incident_id}/{uuid4()}{suffix}"
    clip_recorded_at = (recorded_at or incident.occurred_at).astimezone(UTC)
    try:
        storage.upload(incident_id, data, object_path, detected_mime)
        evidence = Evidence(incident_id=incident_id, timestamp=clip_recorded_at, evidence_type="video_clip", label="Uploaded video clip", description="User-provided clip stored in private Supabase Storage.", metadata_json={"storage_path": object_path, "mime_type": detected_mime, "size_bytes": len(data), "duration_seconds": duration, "source": "user_upload", "mode": "real_video", "recorded_at": clip_recorded_at.isoformat()})
        db.add(evidence); db.commit(); db.refresh(evidence)
        return EvidenceRead.model_validate(evidence)
    except Exception as exc:
        db.rollback()
        try:
            storage.delete(object_path)
        except Exception:
            pass
        raise HTTPException(status_code=503, detail="Could not store uploaded video") from exc


@router.get("/{incident_id}/media/{evidence_id}/url", response_model=SignedMediaUrl)
def media_url(incident_id: uuid.UUID, evidence_id: uuid.UUID, db: Session = Depends(get_db), storage: MediaStorage | None = Depends(optional_media_storage)) -> SignedMediaUrl:
    evidence = next((item for item in repositories.incident_evidence(db, incident_id) if item.id == evidence_id), None)
    if evidence is None or evidence.evidence_type != "video_clip":
        raise HTTPException(status_code=404, detail="Video evidence not found")
    if storage is None:
        raise HTTPException(status_code=503, detail="Private media storage is not configured")
    expires = 300
    try:
        url = storage.signed_url(evidence.metadata_json["storage_path"], expires)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not access private video") from exc
    return SignedMediaUrl(url=url, expires_at=datetime.now(UTC) + timedelta(seconds=expires))


@router.post("/{incident_id}/actions/{action_id}/review", response_model=ReviewActionRead)
def review(incident_id: uuid.UUID, action_id: uuid.UUID, action: ReviewActionCreate, db: Session = Depends(get_db)) -> ReviewActionRead:
    try:
        return review_analysis(db, incident_id, action_id, action)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Analysis run not found") from exc
    except ReviewConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
