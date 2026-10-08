import uuid
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app import repositories
from app.models import AnalysisRun, Finding
from app.schemas import AnalysisRunRead, ClaimType
from app.config import get_settings
from app.services.media_storage import MediaStorage, StorageNotConfigured
from app.services.video_analysis import VideoAnalysisError, VideoAnalyzer, contains_causal_language

WORKFLOW = [
    ("load_incident", "Loaded incident metadata."),
    ("read_drive_logs", "Read available synthetic vehicle log events."),
    ("sample_video_metadata", "Read synthetic video metadata only; no frames were interpreted."),
    ("align_timeline", "Aligned available events and evidence by UTC timestamp."),
    ("draft_report", "Created deterministic findings from available evidence."),
]


def run_analysis(db: Session, incident_id: uuid.UUID, storage: MediaStorage | None = None, analyzer: VideoAnalyzer | None = None) -> AnalysisRunRead:
    started = datetime.now(UTC)
    incident = repositories.get_incident(db, incident_id)
    if incident is None:
        raise LookupError("Incident not found")
    run = AnalysisRun(
        incident_id=incident_id, status="running", steps=[], warning=None,
        started_at=started,
    )
    try:
        events = repositories.incident_events(db, incident_id)
        evidence = repositories.incident_evidence(db, incident_id)
        clips = [item for item in evidence if item.evidence_type == "video_clip" and item.metadata_json.get("storage_path")]
        if clips:
            clip = clips[-1]
            settings = get_settings()
            if not settings.google_api_key:
                run.status = "completed"
                run.warning = "Video chưa được phân tích: chưa cấu hình nhà cung cấp Gemini."
                run.steps = [{"name": "video_analysis", "status": "skipped", "started_at": started.isoformat(), "finished_at": datetime.now(UTC).isoformat(), "message": "Clip thật được lưu nhưng chưa được model phân tích."}]
                run.finished_at = datetime.now(UTC)
                db.add(run); db.commit()
                return AnalysisRunRead.model_validate(run)
            try:
                storage = storage or MediaStorage()
                analyzer = analyzer or VideoAnalyzer()
                media_bytes = storage.download(clip.metadata_json["storage_path"])
                import os
                fd, video_path = tempfile.mkstemp(suffix=Path(clip.metadata_json.get("storage_path", "clip.mp4")).suffix)
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(media_bytes)
                    drafts = analyzer.analyze(video_path, [{"id": str(e.id), "type": e.event_type, "timestamp": e.timestamp.isoformat(), "message": e.message} for e in events], [str(e.id) for e in evidence], settings.video_analysis_timeout_seconds)
                finally:
                    Path(video_path).unlink(missing_ok=True)
                duration = float(clip.metadata_json.get("duration_seconds", 0))
                allowed = {str(item.id) for item in evidence}
                findings = []
                for draft in drafts:
                    citations = {str(value) for value in draft.evidence_ids}
                    if (not citations or not citations <= allowed or draft.timestamp_seconds > duration
                            or draft.claim_type != ClaimType.observation
                            or contains_causal_language(draft.title + " " + draft.description)):
                        continue
                    findings.append(Finding(title=draft.title, description=draft.description, confidence=draft.confidence,
                        evidence_ids=sorted(citations), timestamp=clip.timestamp + timedelta(seconds=draft.timestamp_seconds)))
                run.steps = [{"name": "gemini_video_analysis", "status": "completed", "started_at": started.isoformat(), "finished_at": datetime.now(UTC).isoformat(), "message": f"Analyzed clip with {settings.gemini_model}; findings grounded to incident evidence."}]
                run.warning = None if findings else "Chưa đủ bằng chứng hợp lệ để tạo finding từ video."
                run.status = "awaiting_review" if findings else "completed"
                run.finished_at = datetime.now(UTC)
                db.add(run); db.flush()
                for finding in findings: finding.run = run
                repositories.add_findings(db, findings)
                db.commit()
                return AnalysisRunRead.model_validate(run)
            except (VideoAnalysisError, StorageNotConfigured, Exception) as exc:
                db.rollback()
                failed = AnalysisRun(incident_id=incident_id, status="failed", steps=[{"name": "gemini_video_analysis", "status": "failed", "started_at": started.isoformat(), "finished_at": datetime.now(UTC).isoformat(), "message": "Video analysis failed; no video findings were created."}], warning="Video chưa được phân tích do lỗi provider hoặc storage.", started_at=started, finished_at=datetime.now(UTC))
                db.add(failed); db.commit()
                return AnalysisRunRead.model_validate(failed)
        trace = []
        for step_name, message in WORKFLOW:
            now = datetime.now(UTC)
            trace.append({"name": step_name, "status": "completed", "started_at": now.isoformat(), "finished_at": datetime.now(UTC).isoformat(), "message": message})
        usable = [item for item in evidence if item.evidence_type in {"log", "video_metadata", "keyframe_metadata"}]
        findings: list[Finding] = []
        if events and usable:
            event = events[0]
            matched_evidence = [item for item in usable if abs((item.timestamp - event.timestamp).total_seconds()) <= 15]
            if matched_evidence:
                findings.append(Finding(
                    title="Vehicle event coincides with recorded scene evidence",
                    description=f"The synthetic event '{event.event_type}' is temporally close to available evidence. This is a correlation for reviewer inspection, not a causal conclusion.",
                    confidence=0.62,
                    evidence_ids=[str(item.id) for item in matched_evidence],
                    timestamp=event.timestamp,
                ))
        run.steps = trace
        run.finished_at = datetime.now(UTC)
        run.warning = None if findings else "Insufficient aligned log and evidence data; no finding was created."
        run.status = "awaiting_review" if findings else "completed"
        db.add(run)
        db.flush()
        for finding in findings:
            finding.run = run
        repositories.add_findings(db, findings)
        db.commit()
        return AnalysisRunRead.model_validate(run)
    except Exception as exc:
        db.rollback()
        failed = AnalysisRun(
            incident_id=incident_id, status="failed",
            steps=[{"name": "analysis", "status": "failed", "started_at": started.isoformat(), "finished_at": datetime.now(UTC).isoformat(), "message": "Analysis failed; see server logs."}],
            warning="Analysis could not be completed.", started_at=started, finished_at=datetime.now(UTC),
        )
        db.add(failed)
        db.commit()
        raise RuntimeError("Analysis failed") from exc
