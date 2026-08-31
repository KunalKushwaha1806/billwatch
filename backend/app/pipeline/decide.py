"""
Decide stage — policy engine with explicit stopping rules.

This is the core deliverable: every branch must be inspectable and must
write an AuditEntry explaining which rule fired and why.

Stopping rules (checked in order):
  1. Max attempts: 3+ prior actions → stop
  2. Cooldown: last action < 15 min ago → stop
  3. Low confidence: diagnosis_confidence < 0.5 → escalate to human
  4. Fraud block: customer in fraud list → hard stop
  5. Otherwise: map root cause → bounded action
"""

import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models import RiskSignal, RecoveryAction, Payment, CheckoutSession
from app.pipeline.audit import write_audit


# ── Action Mapping ───────────────────────────────────────────────────

# Payment root cause → recovery action
PAYMENT_ACTION_MAP = {
    "bank_timeout":       "retry_payment",
    "otp_failed":         "retry_payment",
    "network_error":      "retry_payment",
    "insufficient_funds": "retry_payment",
    "card_expired":       "send_nudge",  # can't retry — ask for new method
}

# Checkout root cause → recovery action
CHECKOUT_ACTION_MAP = {
    "payment_friction":       "send_nudge",
    "price_hesitation":       "send_nudge",
    "shipping_cost_surprise": "send_nudge",
    "distraction_timeout":    "send_nudge",
}

# Simulated fraud-flagged customers (for demo — shows the policy block rule firing)
FRAUD_FLAGGED_CUSTOMERS = {"cust_007", "cust_013"}

MAX_ATTEMPTS = 3
COOLDOWN_MINUTES = 15


# ── Policy Engine ────────────────────────────────────────────────────

def decide_action(db: Session, signal: RiskSignal) -> RecoveryAction | None:
    """
    Apply stopping rules in order, then map to a bounded action.
    Returns a RecoveryAction (possibly with stopped_reason set), or None.
    """
    source_entity_id = signal.source_id

    # Resolve customer_id for fraud check
    customer_id = _get_customer_id(db, signal)

    # Count prior actions for this signal
    prior_actions = (
        db.query(RecoveryAction)
        .filter(RecoveryAction.signal_id == signal.id)
        .order_by(RecoveryAction.scheduled_at.desc())
        .all()
    )
    prior_count = len(prior_actions)

    now = datetime.utcnow()

    # ── Rule 1: Max attempts ────────────────────────────────────────
    if prior_count >= MAX_ATTEMPTS:
        action = _create_blocked_action(
            db, signal, prior_count + 1,
            action_type="no_action_policy_block",
            stopped_reason="max_attempts_reached",
        )
        write_audit(
            db, entity_id=source_entity_id,
            stage="decide",
            explanation=(
                f"STOPPED: max attempts reached ({prior_count} prior actions ≥ {MAX_ATTEMPTS}). "
                f"No further recovery attempts will be made for signal {signal.id}."
            ),
            metadata={
                "rule": "max_attempts",
                "prior_attempts": prior_count,
                "threshold": MAX_ATTEMPTS,
            },
        )
        return action

    # ── Rule 2: Cooldown ────────────────────────────────────────────
    if prior_actions:
        last_action = prior_actions[0]
        time_since = (now - last_action.scheduled_at).total_seconds() / 60
        if time_since < COOLDOWN_MINUTES:
            action = _create_blocked_action(
                db, signal, prior_count + 1,
                action_type="no_action_policy_block",
                stopped_reason="cooldown_active",
            )
            write_audit(
                db, entity_id=source_entity_id,
                stage="decide",
                explanation=(
                    f"STOPPED: cooldown active. Last action was {time_since:.1f} min ago "
                    f"(< {COOLDOWN_MINUTES} min threshold). Will not retry yet."
                ),
                metadata={
                    "rule": "cooldown",
                    "minutes_since_last": round(time_since, 1),
                    "cooldown_minutes": COOLDOWN_MINUTES,
                },
            )
            return action

    # ── Rule 3: Low-confidence diagnosis → escalate ─────────────────
    if signal.diagnosis_confidence is not None and signal.diagnosis_confidence < 0.5:
        action = _create_action(
            db, signal, prior_count + 1,
            action_type="escalate_human",
            stopped_reason="low_confidence_diagnosis",
        )
        write_audit(
            db, entity_id=source_entity_id,
            stage="decide",
            explanation=(
                f"ESCALATED TO HUMAN: diagnosis confidence={signal.diagnosis_confidence:.2f} "
                f"(< 0.5 threshold). Root cause '{signal.root_cause}' is uncertain — "
                f"will not auto-act. Routing to human review."
            ),
            metadata={
                "rule": "low_confidence",
                "confidence": signal.diagnosis_confidence,
                "root_cause": signal.root_cause,
                "threshold": 0.5,
            },
        )
        return action

    # ── Rule 4: Fraud block ─────────────────────────────────────────
    if customer_id and customer_id in FRAUD_FLAGGED_CUSTOMERS:
        action = _create_blocked_action(
            db, signal, prior_count + 1,
            action_type="no_action_policy_block",
            stopped_reason="fraud_policy_block",
        )
        write_audit(
            db, entity_id=source_entity_id,
            stage="decide",
            explanation=(
                f"STOPPED: fraud policy block. Customer {customer_id} is flagged — "
                f"automatic recovery is prohibited. No action taken."
            ),
            metadata={
                "rule": "fraud_block",
                "customer_id": customer_id,
            },
        )
        return action

    # ── Rule 5: Map to bounded action ───────────────────────────────
    action_type = _resolve_action_type(signal)
    action = _create_action(
        db, signal, prior_count + 1,
        action_type=action_type,
    )

    write_audit(
        db, entity_id=source_entity_id,
        stage="decide",
        explanation=(
            f"ACTION APPROVED: {action_type} for root_cause='{signal.root_cause}', "
            f"risk_score={signal.risk_score:.4f}, confidence={signal.diagnosis_confidence}, "
            f"attempt #{prior_count + 1}. No stopping rules triggered."
        ),
        metadata={
            "rule": "action_approved",
            "action_type": action_type,
            "root_cause": signal.root_cause,
            "risk_score": signal.risk_score,
            "attempt_number": prior_count + 1,
        },
    )

    db.flush()
    return action


# ── Helpers ──────────────────────────────────────────────────────────

def _get_customer_id(db: Session, signal: RiskSignal) -> str | None:
    """Resolve customer_id from the source entity."""
    if signal.source_type == "payment":
        payment = db.query(Payment).filter(Payment.id == signal.source_id).first()
        return payment.customer_id if payment else None
    elif signal.source_type == "checkout":
        session = db.query(CheckoutSession).filter(CheckoutSession.id == signal.source_id).first()
        return session.customer_id if session else None
    return None


def _resolve_action_type(signal: RiskSignal) -> str:
    """Map root cause to an action type."""
    if signal.source_type == "payment":
        return PAYMENT_ACTION_MAP.get(signal.root_cause, "retry_payment")
    else:
        return CHECKOUT_ACTION_MAP.get(signal.root_cause, "send_nudge")


def _create_action(
    db: Session, signal: RiskSignal, attempt: int,
    action_type: str, stopped_reason: str | None = None,
) -> RecoveryAction:
    """Create a RecoveryAction that may or may not proceed to execution."""
    action = RecoveryAction(
        id=f"act_{signal.source_id}_{attempt}",
        signal_id=signal.id,
        action_type=action_type,
        attempt_number=attempt,
        scheduled_at=datetime.utcnow(),
        stopped_reason=stopped_reason,
    )
    db.add(action)
    db.flush()
    return action


def _create_blocked_action(
    db: Session, signal: RiskSignal, attempt: int,
    action_type: str, stopped_reason: str,
) -> RecoveryAction:
    """Create a RecoveryAction that is immediately blocked (no execution)."""
    action = RecoveryAction(
        id=f"act_{signal.source_id}_{attempt}",
        signal_id=signal.id,
        action_type=action_type,
        attempt_number=attempt,
        scheduled_at=datetime.utcnow(),
        executed_at=datetime.utcnow(),
        outcome="failed",
        stopped_reason=stopped_reason,
    )
    db.add(action)
    db.flush()
    return action

