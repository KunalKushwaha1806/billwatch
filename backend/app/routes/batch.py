"""POST /batch/load — load synthetic dataset into the database."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db, drop_tables, create_tables
from app.models import Payment, CheckoutSession
from app.schemas import BatchLoadResponse

# Import the generator — it lives one level up but we import the function
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from generate_data import generate_all

router = APIRouter()


@router.post("/batch/load", response_model=BatchLoadResponse)
def load_batch(db: Session = Depends(get_db)):
    """
    Clear existing data and load a fresh synthetic dataset.
    This resets the entire DB — signals, actions, and audit entries are wiped too.
    """
    # Reset all tables
    drop_tables()
    create_tables()

    # Generate synthetic data (seeded — always the same)
    data = generate_all()

    # Insert payments
    for p in data["payments"]:
        payment = Payment(
            id=p["id"],
            merchant_id=p["merchant_id"],
            amount=p["amount"],
            currency=p["currency"],
            status=p["status"],
            failure_code=p["failure_code"],
            customer_id=p["customer_id"],
            payment_method=p["payment_method"],
            attempt_number=p["attempt_number"],
            created_at=datetime.fromisoformat(p["created_at"]),
            mandate_id=p.get("mandate_id"),
        )
        db.add(payment)

    # Insert checkout sessions
    for s in data["checkout_sessions"]:
        session = CheckoutSession(
            id=s["id"],
            merchant_id=s["merchant_id"],
            customer_id=s["customer_id"],
            cart_value=s["cart_value"],
            status=s["status"],
            stage_reached=s["stage_reached"],
            created_at=datetime.fromisoformat(s["created_at"]),
            last_activity_at=datetime.fromisoformat(s["last_activity_at"]),
        )
        db.add(session)

    db.commit()

    return BatchLoadResponse(
        payments_loaded=len(data["payments"]),
        checkout_sessions_loaded=len(data["checkout_sessions"]),
        message=f"Loaded {len(data['payments'])} payments and {len(data['checkout_sessions'])} checkout sessions.",
    )
