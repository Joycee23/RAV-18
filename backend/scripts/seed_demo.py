"""Seed deterministic, entirely synthetic incident data."""
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.models import Evidence, Incident, LogEvent

INCIDENTS = [
    {
        "id": UUID("18000000-0000-4000-8000-000000000001"),
        "title": "Unexpected hard braking near a crossing",
        "severity": "high", "status": "open", "occurred_at": "2026-09-14T08:32:10+00:00",
        "vehicle_id": "SIM-AV-021", "summary": "Synthetic test event: a hard-brake signal appeared near a marked crossing.",
        "events": [("2026-09-14T08:32:10+00:00", "vehicle_control", "hard_brake", "Deceleration exceeded the synthetic review threshold.")],
        "evidence": [("2026-09-14T08:32:12+00:00", "video_metadata", "Synthetic clip metadata", "Metadata placeholder for a simulated forward-camera clip.")],
    },
    {
        "id": UUID("18000000-0000-4000-8000-000000000002"),
        "title": "Localization warning without supporting media",
        "severity": "medium", "status": "investigating", "occurred_at": "2026-09-18T14:05:00+00:00",
        "vehicle_id": "SIM-AV-008", "summary": "Synthetic failure case: available logs have no matching evidence.",
        "events": [("2026-09-18T14:05:00+00:00", "localization", "pose_uncertain", "Synthetic localization confidence dropped below threshold.")],
        "evidence": [],
    },
    {
        "id": UUID("18000000-0000-4000-8000-000000000003"),
        "title": "Lane departure alert during a turn",
        "severity": "low", "status": "closed", "occurred_at": "2026-09-22T11:17:42+00:00",
        "vehicle_id": "SIM-AV-034", "summary": "Synthetic event with log and metadata evidence for timeline review.",
        "events": [("2026-09-22T11:17:42+00:00", "perception", "lane_departure_alert", "Synthetic lane alert recorded during a low-speed turn.")],
        "evidence": [("2026-09-22T11:17:45+00:00", "keyframe_metadata", "Synthetic keyframe metadata", "Metadata-only keyframe record; no visual understanding is represented.")],
    },
]


def seed(db: Session) -> None:
    for row in INCIDENTS:
        incident = db.get(Incident, row["id"])
        if incident is None:
            incident = Incident(
                id=row["id"], title=row["title"], severity=row["severity"], status=row["status"],
                occurred_at=datetime.fromisoformat(row["occurred_at"]).astimezone(UTC),
                vehicle_id=row["vehicle_id"], summary=row["summary"], metadata_json={"dataset": "synthetic", "label": "SIMULATED"},
            )
            db.add(incident)
            db.flush()
        if not incident.events and row["events"]:
            db.add_all([
                LogEvent(incident_id=incident.id, timestamp=datetime.fromisoformat(ts).astimezone(UTC), source=source,
                         event_type=kind, message=message, details={"dataset": "synthetic"})
                for ts, source, kind, message in row["events"]
            ])
        if not incident.evidence and row["evidence"]:
            db.add_all([
                Evidence(incident_id=incident.id, timestamp=datetime.fromisoformat(ts).astimezone(UTC), evidence_type=kind,
                         label=label, description=description,
                         metadata_json={"label": "SIMULATED", "media_interpretation": "metadata_only"})
                for ts, kind, label, description in row["evidence"]
            ])
    db.commit()


if __name__ == "__main__":
    if engine is None or SessionLocal is None:
        raise SystemExit("Set DATABASE_URL to your Supabase PostgreSQL connection string first.")
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed(session)
    print("Seeded 3 synthetic IncidentLens incidents.")
