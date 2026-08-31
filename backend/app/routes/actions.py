"""GET /actions — list all recovery actions with outcomes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RecoveryAction, RiskSignal

router = APIRouter()


@router.get("/actions")
def list_actions(
    outcome: str | None = Query(None, description="Filter by outcome: recovered, failed, still_pending"),
    db: Session = Depends(get_db),
):
    """Return all recovery actions with their outcomes and linked signal info."""
    query = db.query(RecoveryAction)
    if outcome:
        query = query.filter(RecoveryAction.outcome == outcome)

    actions = query.order_by(RecoveryAction.scheduled_at.desc()).all()

    results = []
    for act in actions:
        signal = db.query(RiskSignal).filter(RiskSignal.id == act.signal_id).first()
        results.append({
            "id": act.id,
            "signal_id": act.signal_id,
            "action_type": act.action_type,
            "attempt_number": act.attempt_number,
            "scheduled_at": act.scheduled_at.isoformat() if act.scheduled_at else None,
            "executed_at": act.executed_at.isoformat() if act.executed_at else None,
            "outcome": act.outcome,
            "amount_recovered": act.amount_recovered,
            "stopped_reason": act.stopped_reason,
            "source_type": signal.source_type if signal else None,
            "source_id": signal.source_id if signal else None,
            "root_cause": signal.root_cause if signal else None,
        })

    return results
