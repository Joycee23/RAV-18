import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import AnalysisRun, Evidence, Finding, Incident, LogEvent, ReviewAction


def list_incidents(db: Session, status: str | None = None, severity: str | None = None) -> list[Incident]:
    query = select(Incident).order_by(Incident.occurred_at.desc())
    if status:
        query = query.where(Incident.status == status)
    if severity:
        query = query.where(Incident.severity == severity)
    return list(db.scalars(query).all())


def get_incident(db: Session, incident_id: uuid.UUID) -> Incident | None:
    query = (
        select(Incident)
        .where(Incident.id == incident_id)
        .options(
            selectinload(Incident.events), selectinload(Incident.evidence),
            selectinload(Incident.runs).selectinload(AnalysisRun.findings),
            selectinload(Incident.runs).selectinload(AnalysisRun.reviews),
        )
    )
    incident = db.scalar(query)
    if incident:
        incident.events.sort(key=lambda event: event.timestamp)
        incident.evidence.sort(key=lambda evidence: evidence.timestamp)
        incident.runs.sort(key=lambda run: run.started_at)
    return incident


def get_run_for_incident(db: Session, incident_id: uuid.UUID, run_id: uuid.UUID) -> AnalysisRun | None:
    return db.scalar(
        select(AnalysisRun).where(AnalysisRun.id == run_id, AnalysisRun.incident_id == incident_id)
        .options(selectinload(AnalysisRun.findings), selectinload(AnalysisRun.reviews))
    )


def add_run(db: Session, run: AnalysisRun) -> AnalysisRun:
    db.add(run)
    db.flush()
    return run


def add_findings(db: Session, findings: list[Finding]) -> None:
    db.add_all(findings)
    db.flush()


def add_review(db: Session, action: ReviewAction) -> ReviewAction:
    db.add(action)
    db.flush()
    return action


def incident_evidence(db: Session, incident_id: uuid.UUID) -> list[Evidence]:
    return list(db.scalars(select(Evidence).where(Evidence.incident_id == incident_id).order_by(Evidence.timestamp)).all())


def incident_events(db: Session, incident_id: uuid.UUID) -> list[LogEvent]:
    return list(db.scalars(select(LogEvent).where(LogEvent.incident_id == incident_id).order_by(LogEvent.timestamp)).all())
