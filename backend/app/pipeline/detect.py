"""
Detect stage — scan synthetic batch, flag at-risk records with a risk score.

Two detectors share the same interface:
  - detect_payment_signals: failed payments eligible for retry
  - detect_checkout_signals: abandoned sessions past a meaningful stage
"""

import uuid
import math
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import Payment, CheckoutSession, RiskSignal, RecoveryAction
from app.pipeline.audit import write_audit


# ── Risk Scoring ─────────────────────────────────────────────────────

def _time_decay(created_at: datetime, half_life_hours: float = 24.0) -> float:
    """Exponential decay: recent records score higher. Returns 0-1."""
    now = datetime.utcnow()
    hours_elapsed = (now - created_at).total_seconds() / 3600
    return math.exp(-0.693 * hours_elapsed / half_life_hours)  # ln(2) ≈ 0.693


def _normalize(value: float, max_value: float) -> float:
    """Normalize value to 0-1 range."""
    return min(value / max_value, 1.0) if max_value > 0 else 0.0


# ── Payment Detection ───────────────────────────────────────────────

STAGE_PROXIMITY = {
    "cart": 0.25,
    "address": 0.50,
    "payment_selection": 0.75,
    "otp": 1.0,
}


def detect_payment_signals(db: Session) -> list[RiskSignal]:
    """
    Flag failed payments eligible for recovery:
      - status = 'failed'
      - attempt_number <= 3
      - no prior successful recovery action for this payment
    """
    failed_payments = (
        db.query(Payment)
        .filter(Payment.status == "failed", Payment.attempt_number <= 3)
        .all()
    )

    # Find max amount for normalization
    max_amount = max((p.amount for p in failed_payments), default=1.0)

    signals = []
    for payment in failed_payments:
        # Check: no prior successful recovery for this payment
        prior_success = (
            db.query(RecoveryAction)
            .join(RiskSignal, RecoveryAction.signal_id == RiskSignal.id)
            .filter(
                RiskSignal.source_id == payment.id,
                RecoveryAction.outcome == "recovered",
            )
            .first()
        )
        if prior_success:
            continue

        # Check: signal already generated for this payment
        existing = db.query(RiskSignal).filter(RiskSignal.source_id == payment.id).first()
        if existing:
            signals.append(existing)
            continue

        # Compute risk score
        amount_norm = _normalize(payment.amount, max_amount)
        attempt_proximity = _normalize(payment.attempt_number, 3.0)
        time_factor = _time_decay(payment.created_at)

        risk_score = round(
            0.4 * amount_norm + 0.3 * attempt_proximity + 0.3 * time_factor,
            4,
        )

        signal = RiskSignal(
            id=f"sig_{payment.id}",
            source_type="payment",
            source_id=payment.id,
            risk_score=risk_score,
        )
        db.add(signal)
        signals.append(signal)

        write_audit(
            db,
            entity_id=payment.id,
            stage="detect",
            explanation=(
                f"Flagged failed payment: amount=₹{payment.amount:.2f}, "
                f"failure_code={payment.failure_code}, "
                f"attempt #{payment.attempt_number}, "
                f"risk_score={risk_score}"
            ),
            metadata={
                "amount": payment.amount,
                "failure_code": payment.failure_code,
                "attempt_number": payment.attempt_number,
                "risk_score": risk_score,
                "payment_method": payment.payment_method,
            },
        )

    db.flush()
    return signals


# ── Checkout Detection ──────────────────────────────────────────────

CART_VALUE_THRESHOLD = 2000.0  # ₹ — flag abandoned sessions above this even at early stages


def detect_checkout_signals(db: Session) -> list[RiskSignal]:
    """
    Flag abandoned checkouts worth recovering:
      - status = 'abandoned'
      - stage_reached >= 'payment_selection' OR cart_value >= threshold
    """
    abandoned_sessions = (
        db.query(CheckoutSession)
        .filter(CheckoutSession.status == "abandoned")
        .all()
    )

    qualifying = [
        s for s in abandoned_sessions
        if s.stage_reached in ("payment_selection", "otp") or s.cart_value >= CART_VALUE_THRESHOLD
    ]

    max_cart = max((s.cart_value for s in qualifying), default=1.0)

    signals = []
    for session in qualifying:
        # Check: signal already generated for this session
        existing = db.query(RiskSignal).filter(RiskSignal.source_id == session.id).first()
        if existing:
            signals.append(existing)
            continue

        cart_norm = _normalize(session.cart_value, max_cart)
        stage_prox = STAGE_PROXIMITY.get(session.stage_reached, 0.25)
        time_factor = _time_decay(session.last_activity_at, half_life_hours=12.0)

        risk_score = round(
            0.4 * cart_norm + 0.3 * stage_prox + 0.3 * time_factor,
            4,
        )

        signal = RiskSignal(
            id=f"sig_{session.id}",
            source_type="checkout",
            source_id=session.id,
            risk_score=risk_score,
        )
        db.add(signal)
        signals.append(signal)

        write_audit(
            db,
            entity_id=session.id,
            stage="detect",
            explanation=(
                f"Flagged abandoned checkout: cart=₹{session.cart_value:.2f}, "
                f"stage={session.stage_reached}, "
                f"risk_score={risk_score}"
            ),
            metadata={
                "cart_value": session.cart_value,
                "stage_reached": session.stage_reached,
                "risk_score": risk_score,
                "minutes_since_activity": round(
                    (datetime.utcnow() - session.last_activity_at).total_seconds() / 60, 1
                ),
            },
        )

    db.flush()
    return signals
