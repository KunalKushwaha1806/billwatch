"""GET /metrics/summary — aggregate recovery metrics computed from actual batch run."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from collections import defaultdict

from app.database import get_db
from app.models import RecoveryAction, RiskSignal, Payment, CheckoutSession

router = APIRouter()


@router.get("/metrics/summary")
def get_metrics_summary(db: Session = Depends(get_db)):
    """
    Compute and return aggregate recovery metrics.
    All numbers are derived from actual DB rows — nothing is hard-coded.
    """
    # Get all signals
    signals = db.query(RiskSignal).all()
    signal_map = {s.id: s for s in signals}

    # Get all actions
    actions = db.query(RecoveryAction).all()

    # ── Compute total at-risk amount ────────────────────────────────
    total_at_risk = 0.0
    seen_sources = set()
    for sig in signals:
        if sig.source_id in seen_sources:
            continue
        seen_sources.add(sig.source_id)

        if sig.source_type == "payment":
            payment = db.query(Payment).filter(Payment.id == sig.source_id).first()
            if payment:
                total_at_risk += payment.amount
        elif sig.source_type == "checkout":
            session = db.query(CheckoutSession).filter(CheckoutSession.id == sig.source_id).first()
            if session:
                total_at_risk += session.cart_value

    # ── Compute recovered amount and breakdowns ─────────────────────
    total_recovered = 0.0
    actions_taken = 0
    actions_blocked = 0
    escalated_to_human = 0
    by_root_cause = defaultdict(lambda: {"attempted": 0, "recovered": 0})

    for action in actions:
        signal = signal_map.get(action.signal_id)
        root_cause = signal.root_cause if signal else "unknown"

        if action.action_type == "no_action_policy_block":
            actions_blocked += 1
        elif action.action_type == "escalate_human":
            escalated_to_human += 1
            actions_taken += 1
            by_root_cause[root_cause]["attempted"] += 1
        else:
            actions_taken += 1
            by_root_cause[root_cause]["attempted"] += 1

            if action.outcome == "recovered" and action.amount_recovered:
                total_recovered += action.amount_recovered
                by_root_cause[root_cause]["recovered"] += 1

    recovery_rate = round(total_recovered / total_at_risk, 4) if total_at_risk > 0 else 0.0

    # ── Stopped-reason breakdown ────────────────────────────────────
    stopped_reasons = defaultdict(int)
    for action in actions:
        if action.stopped_reason:
            stopped_reasons[action.stopped_reason] += 1

    return {
        "total_at_risk": round(total_at_risk, 2),
        "total_recovered": round(total_recovered, 2),
        "recovery_rate": recovery_rate,
        "actions_taken": actions_taken,
        "actions_blocked_by_policy": actions_blocked,
        "escalated_to_human": escalated_to_human,
        "by_root_cause": dict(by_root_cause),
        "stopped_reasons": dict(stopped_reasons),
    }
