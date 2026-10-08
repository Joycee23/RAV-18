import uuid

from sqlalchemy.orm import Session

from app import repositories
from app.models import ReviewAction
from app.schemas import ReviewActionCreate, ReviewActionRead


class ReviewConflict(Exception):
    pass


def review_analysis(db: Session, incident_id: uuid.UUID, run_id: uuid.UUID, action: ReviewActionCreate) -> ReviewActionRead:
    run = repositories.get_run_for_incident(db, incident_id, run_id)
    if run is None:
        raise LookupError("Analysis run not found")
    if action.actor_role != "reviewer":
        raise ValueError("Only the reviewer demo role can review an analysis")
    if run.status != "awaiting_review" or run.reviews:
        raise ReviewConflict("Analysis is not awaiting review")
    result = ReviewAction(
        run_id=run.id, decision=action.decision.value, actor_role=action.actor_role,
        actor_name=action.actor_name, note=action.note,
    )
    repositories.add_review(db, result)
    run.status = "approved" if action.decision.value == "approve" else "rejected"
    db.commit()
    db.refresh(result)
    return ReviewActionRead.model_validate(result)
