"""
Shared pytest fixtures for BillWatch test suite.

Uses an in-memory SQLite database so every test gets a clean slate
without touching the real billwatch.db.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from unittest.mock import patch

import app.database as db_module


@pytest.fixture()
def test_engine():
    """Create a fresh in-memory SQLite engine with StaticPool for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from app.models import Payment, CheckoutSession, RiskSignal, RecoveryAction, AuditEntry  # noqa
    db_module.Base.metadata.create_all(bind=engine)
    yield engine
    db_module.Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_session(test_engine):
    """Fresh session bound to the test engine."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture()
def client(test_engine, db_session):
    """FastAPI TestClient wired to the test DB."""
    from app.main import app
    from app.database import get_db

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    def test_drop_tables():
        db_module.Base.metadata.drop_all(bind=test_engine)

    def test_create_tables():
        db_module.Base.metadata.create_all(bind=test_engine)

    app.dependency_overrides[get_db] = override_get_db
    with patch("app.routes.batch.drop_tables", test_drop_tables), \
         patch("app.routes.batch.create_tables", test_create_tables):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()


# ── Convenience builders ──────────────────────────────────────────────

def make_payment(
    db,
    id="pay_test0001",
    merchant_id="merch_001",
    amount=5000.0,
    currency="INR",
    status="failed",
    failure_code="bank_timeout",
    customer_id="cust_001",
    payment_method="card",
    attempt_number=1,
    created_at=None,
):
    from app.models import Payment
    p = Payment(
        id=id,
        merchant_id=merchant_id,
        amount=amount,
        currency=currency,
        status=status,
        failure_code=failure_code,
        customer_id=customer_id,
        payment_method=payment_method,
        attempt_number=attempt_number,
        created_at=created_at or datetime.utcnow(),
    )
    db.add(p)
    db.flush()
    return p


def make_checkout(
    db,
    id="sess_test0001",
    merchant_id="merch_001",
    customer_id="cust_002",
    cart_value=3000.0,
    status="abandoned",
    stage_reached="otp",
    created_at=None,
    last_activity_at=None,
):
    from app.models import CheckoutSession
    now = created_at or datetime.utcnow()
    c = CheckoutSession(
        id=id,
        merchant_id=merchant_id,
        customer_id=customer_id,
        cart_value=cart_value,
        status=status,
        stage_reached=stage_reached,
        created_at=now,
        last_activity_at=last_activity_at or now,
    )
    db.add(c)
    db.flush()
    return c


def make_signal(
    db,
    id="sig_test0001",
    source_type="payment",
    source_id="pay_test0001",
    risk_score=0.75,
    root_cause=None,
    diagnosis_confidence=None,
    diagnosed_at=None,
):
    from app.models import RiskSignal
    s = RiskSignal(
        id=id,
        source_type=source_type,
        source_id=source_id,
        risk_score=risk_score,
        root_cause=root_cause,
        diagnosis_confidence=diagnosis_confidence,
        diagnosed_at=diagnosed_at,
    )
    db.add(s)
    db.flush()
    return s


def make_action(
    db,
    id="act_test0001",
    signal_id="sig_test0001",
    action_type="retry_payment",
    attempt_number=1,
    scheduled_at=None,
    executed_at=None,
    outcome=None,
    amount_recovered=None,
    stopped_reason=None,
):
    from app.models import RecoveryAction
    a = RecoveryAction(
        id=id,
        signal_id=signal_id,
        action_type=action_type,
        attempt_number=attempt_number,
        scheduled_at=scheduled_at or datetime.utcnow(),
        executed_at=executed_at,
        outcome=outcome,
        amount_recovered=amount_recovered,
        stopped_reason=stopped_reason,
    )
    db.add(a)
    db.flush()
    return a
