"""
Diagnose stage — classify root cause for each risk signal.

- Payments: deterministic rule-based lookup from failure_code → root cause
- Checkout: rule-based heuristic with optional LLM fallback for ambiguous cases
"""

import os
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import Payment, CheckoutSession, RiskSignal
from app.pipeline.audit import write_audit


# ── Payment Failure Cause Map ────────────────────────────────────────

FAILURE_CAUSE_MAP = {
    "insufficient_funds": {"root_cause": "insufficient_funds", "retry_strategy": "retry_after_hours", "delay_hours": 6},
    "card_expired":       {"root_cause": "card_expired",       "retry_strategy": "request_new_method", "delay_hours": 0},
    "bank_timeout":       {"root_cause": "bank_timeout",       "retry_strategy": "retry_soon",         "delay_hours": 0.25},
    "otp_failed":         {"root_cause": "otp_failed",         "retry_strategy": "retry_soon",         "delay_hours": 0.5},
    "network_error":      {"root_cause": "network_error",      "retry_strategy": "retry_soon",         "delay_hours": 0.1},
}


# ── Checkout Abandonment Reasons ─────────────────────────────────────

CHECKOUT_STAGE_HEURISTICS = {
    "otp": {
        "root_cause": "payment_friction",
        "confidence": 0.90,
        "reasoning": "Abandoned at OTP stage — likely payment friction or OTP delivery issue.",
    },
    "payment_selection": {
        "root_cause": "price_hesitation",
        "confidence": 0.70,
        "reasoning": "Abandoned at payment selection — likely price hesitation or preferred method unavailable.",
    },
    "address": {
        "root_cause": "shipping_cost_surprise",
        "confidence": 0.55,
        "reasoning": "Abandoned at address stage — likely encountered unexpected shipping costs.",
    },
    "cart": {
        "root_cause": "distraction_timeout",
        "confidence": 0.40,
        "reasoning": "Abandoned at cart stage — likely distraction or browsing, low intent signal.",
    },
}


def _try_llm_diagnosis(session_data: dict) -> dict | None:
    """
    Attempt LLM-based diagnosis for checkout abandonment.
    Returns {"root_cause": str, "confidence": float, "reasoning": str} or None on failure.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""Analyze this abandoned checkout session and classify the most likely abandonment reason.

Session data:
- Cart value: ₹{session_data['cart_value']:.2f}
- Stage reached: {session_data['stage_reached']}
- Time spent (minutes): {session_data['minutes_active']}

Classify as exactly ONE of:
1. "price_hesitation" — customer hesitated due to total cost
2. "shipping_cost_surprise" — unexpected shipping/additional charges
3. "payment_friction" — issue with payment method or OTP
4. "distraction_timeout" — customer got distracted or session timed out

Respond with ONLY a JSON object: {{"reason": "...", "confidence": 0.0-1.0, "explanation": "..."}}"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )

        import json
        result = json.loads(response.content[0].text)
        return {
            "root_cause": result["reason"],
            "confidence": float(result["confidence"]),
            "reasoning": result["explanation"],
        }
    except Exception as e:
        # LLM call failed — fall back gracefully
        return None


# ── Public API ───────────────────────────────────────────────────────

def diagnose_payment(db: Session, signal: RiskSignal) -> None:
    """Diagnose a payment risk signal using deterministic rule lookup."""
    payment = db.query(Payment).filter(Payment.id == signal.source_id).first()
    if not payment or not payment.failure_code:
        signal.root_cause = "unknown"
        signal.diagnosis_confidence = 0.3
        signal.diagnosed_at = datetime.utcnow()
        write_audit(
            db, entity_id=payment.id if payment else signal.source_id,
            stage="diagnose",
            explanation="No failure code found — classified as unknown (confidence: 0.3).",
            metadata={"root_cause": "unknown", "confidence": 0.3},
        )
        return

    cause_info = FAILURE_CAUSE_MAP.get(payment.failure_code, {})
    root_cause = cause_info.get("root_cause", payment.failure_code)

    signal.root_cause = root_cause
    signal.diagnosis_confidence = 1.0  # rule-based = fully deterministic
    signal.diagnosed_at = datetime.utcnow()

    write_audit(
        db, entity_id=payment.id,
        stage="diagnose",
        explanation=(
            f"Diagnosed payment failure: code={payment.failure_code}, "
            f"root_cause={root_cause}, "
            f"strategy={cause_info.get('retry_strategy', 'n/a')}, "
            f"delay={cause_info.get('delay_hours', 0)}h. "
            f"Confidence: 1.0 (deterministic rule match)."
        ),
        metadata={
            "failure_code": payment.failure_code,
            "root_cause": root_cause,
            "retry_strategy": cause_info.get("retry_strategy"),
            "delay_hours": cause_info.get("delay_hours"),
            "confidence": 1.0,
            "method": "rule_lookup",
        },
    )


def diagnose_checkout(db: Session, signal: RiskSignal) -> None:
    """
    Diagnose a checkout risk signal.
    Uses rule-based heuristic first; falls back to LLM for ambiguous cases.
    """
    session = db.query(CheckoutSession).filter(CheckoutSession.id == signal.source_id).first()
    if not session:
        signal.root_cause = "unknown"
        signal.diagnosis_confidence = 0.3
        signal.diagnosed_at = datetime.utcnow()
        return

    heuristic = CHECKOUT_STAGE_HEURISTICS.get(session.stage_reached)

    # For stages with lower heuristic confidence, attempt LLM diagnosis
    use_llm = heuristic and heuristic["confidence"] < 0.80
    llm_result = None

    if use_llm:
        minutes_active = (session.last_activity_at - session.created_at).total_seconds() / 60
        llm_result = _try_llm_diagnosis({
            "cart_value": session.cart_value,
            "stage_reached": session.stage_reached,
            "minutes_active": round(minutes_active, 1),
        })

    if llm_result:
        # LLM succeeded — use its diagnosis
        signal.root_cause = llm_result["root_cause"]
        signal.diagnosis_confidence = llm_result["confidence"]
        signal.diagnosed_at = datetime.utcnow()

        write_audit(
            db, entity_id=session.id,
            stage="diagnose",
            explanation=(
                f"LLM diagnosis for checkout abandonment: "
                f"reason={llm_result['root_cause']}, "
                f"confidence={llm_result['confidence']:.2f}. "
                f"LLM reasoning: {llm_result['reasoning']}"
            ),
            metadata={
                "root_cause": llm_result["root_cause"],
                "confidence": llm_result["confidence"],
                "method": "llm_classification",
                "stage_reached": session.stage_reached,
                "cart_value": session.cart_value,
            },
        )
    elif heuristic:
        # Use rule-based heuristic
        signal.root_cause = heuristic["root_cause"]
        signal.diagnosis_confidence = heuristic["confidence"]
        signal.diagnosed_at = datetime.utcnow()

        write_audit(
            db, entity_id=session.id,
            stage="diagnose",
            explanation=(
                f"Rule-based checkout diagnosis: "
                f"stage={session.stage_reached}, "
                f"cause={heuristic['root_cause']}, "
                f"confidence={heuristic['confidence']:.2f}. "
                f"{heuristic['reasoning']}"
            ),
            metadata={
                "root_cause": heuristic["root_cause"],
                "confidence": heuristic["confidence"],
                "method": "rule_heuristic",
                "stage_reached": session.stage_reached,
                "cart_value": session.cart_value,
            },
        )
    else:
        # Unknown stage
        signal.root_cause = "unknown"
        signal.diagnosis_confidence = 0.3
        signal.diagnosed_at = datetime.utcnow()

        write_audit(
            db, entity_id=session.id,
            stage="diagnose",
            explanation=f"Unknown checkout stage '{session.stage_reached}' — classified as unknown (confidence: 0.3).",
            metadata={"root_cause": "unknown", "confidence": 0.3},
        )

    db.flush()
