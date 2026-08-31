"""GET /signals — list all flagged risk signals."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RiskSignal, Payment, CheckoutSession
from app.schemas import RiskSignalSchema

router = APIRouter()


@router.get("/signals")
def list_signals(
    source_type: str | None = Query(None, description="Filter by 'payment' or 'checkout'"),
    db: Session = Depends(get_db),
):
    """Return all risk signals with joined source info."""
    query = db.query(RiskSignal)
    if source_type:
        query = query.filter(RiskSignal.source_type == source_type)

    signals = query.order_by(RiskSignal.risk_score.desc()).all()

    results = []
    for sig in signals:
        sig_dict = {
            "id": sig.id,
            "source_type": sig.source_type,
            "source_id": sig.source_id,
            "risk_score": sig.risk_score,
            "root_cause": sig.root_cause,
            "diagnosis_confidence": sig.diagnosis_confidence,
            "diagnosed_at": sig.diagnosed_at.isoformat() if sig.diagnosed_at else None,
        }

        # Attach source details
        if sig.source_type == "payment":
            payment = db.query(Payment).filter(Payment.id == sig.source_id).first()
            if payment:
                sig_dict["source_details"] = {
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "failure_code": payment.failure_code,
                    "payment_method": payment.payment_method,
                    "customer_id": payment.customer_id,
                    "merchant_id": payment.merchant_id,
                }
        elif sig.source_type == "checkout":
            session = db.query(CheckoutSession).filter(CheckoutSession.id == sig.source_id).first()
            if session:
                sig_dict["source_details"] = {
                    "cart_value": session.cart_value,
                    "stage_reached": session.stage_reached,
                    "customer_id": session.customer_id,
                    "merchant_id": session.merchant_id,
                }

        results.append(sig_dict)

    return results
