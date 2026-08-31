"""
Execute stage — simulated recovery action with probabilistic outcome.

Clearly labeled as simulated: no real payment retries or SMS sends.
Outcome is determined by root-cause-specific success rates with a
seeded random for reproducibility.
"""

import hashlib
import random
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import RiskSignal, RecoveryAction, Payment, CheckoutSession
from app.pipeline.audit import write_audit


# ── Simulated Success Rates by Root Cause ────────────────────────────

SIMULATED_SUCCESS_RATES = {
    "bank_timeout":           0.70,
    "otp_failed":             0.65,
    "network_error":          0.80,
    "insufficient_funds":     0.40,
    "card_expired":           0.05,
    "payment_friction":       0.55,
    "price_hesitation":       0.35,
    "shipping_cost_surprise": 0.30,
    "distraction_timeout":    0.20,
    "unknown":                0.15,
}


def _deterministic_seed(action_id: str) -> int:
    """Generate a reproducible seed from the action ID."""
    return int(hashlib.sha256(action_id.encode()).hexdigest()[:8], 16)


def execute_action(db: Session, action: RecoveryAction, signal: RiskSignal) -> None:
    """
    Simulate execution of a recovery action.

    SIMULATION NOTE: This does not make real payment retries or send real
    messages. Outcome is probabilistic based on root cause success rates,
    seeded by action ID for reproducibility.
    """
    # Skip if already executed or blocked
    if action.executed_at is not None:
        return

    # Skip non-executable actions
    if action.action_type == "no_action_policy_block":
        return
    if action.action_type == "escalate_human":
        action.executed_at = datetime.utcnow()
        action.outcome = "still_pending"
        write_audit(
            db, entity_id=signal.source_id,
            stage="execute",
            explanation=(
                f"[SIMULATED] Escalated to human review. Action {action.id} "
                f"routed to support queue — no automated recovery attempted. "
                f"Root cause: {signal.root_cause}, confidence: {signal.diagnosis_confidence}."
            ),
            metadata={
                "action_id": action.id,
                "action_type": action.action_type,
                "outcome": "still_pending",
                "simulated": True,
            },
        )
        db.flush()
        return

    # Determine outcome probabilistically
    success_rate = SIMULATED_SUCCESS_RATES.get(signal.root_cause, 0.30)
    rng = random.Random(_deterministic_seed(action.id))
    is_recovered = rng.random() < success_rate

    # Resolve the amount at stake
    amount = _get_amount(db, signal)

    action.executed_at = datetime.utcnow()
    if is_recovered:
        action.outcome = "recovered"
        action.amount_recovered = amount
    else:
        action.outcome = "failed"
        action.amount_recovered = 0.0

    action_label = "retry_payment" if action.action_type == "retry_payment" else "send_nudge"
    outcome_emoji = "✅" if is_recovered else "❌"

    write_audit(
        db, entity_id=signal.source_id,
        stage="execute",
        explanation=(
            f"[SIMULATED] {outcome_emoji} {action_label}: "
            f"outcome={'RECOVERED' if is_recovered else 'FAILED'}, "
            f"amount={'₹' + f'{amount:.2f}' if is_recovered else '₹0.00'}, "
            f"success_rate={success_rate:.0%} for cause='{signal.root_cause}'. "
            f"(Simulated — no real {'payment retry' if action.action_type == 'retry_payment' else 'message sent'}.)"
        ),
        metadata={
            "action_id": action.id,
            "action_type": action.action_type,
            "outcome": action.outcome,
            "amount_recovered": action.amount_recovered,
            "success_rate": success_rate,
            "root_cause": signal.root_cause,
            "simulated": True,
        },
    )

    db.flush()


def _get_amount(db: Session, signal: RiskSignal) -> float:
    """Get the monetary amount at stake for this signal."""
    if signal.source_type == "payment":
        payment = db.query(Payment).filter(Payment.id == signal.source_id).first()
        return payment.amount if payment else 0.0
    elif signal.source_type == "checkout":
        session = db.query(CheckoutSession).filter(CheckoutSession.id == signal.source_id).first()
        return session.cart_value if session else 0.0
    return 0.0
