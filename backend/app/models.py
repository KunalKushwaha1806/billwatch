"""SQLAlchemy ORM models for BillWatch."""

import json
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Text
from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True)
    merchant_id = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    status = Column(String, nullable=False)  # success | failed | pending
    failure_code = Column(String, nullable=True)
    customer_id = Column(String, nullable=False)
    payment_method = Column(String, nullable=False)  # card | upi | netbanking | wallet
    attempt_number = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    mandate_id = Column(String, nullable=True)


class CheckoutSession(Base):
    __tablename__ = "checkout_sessions"

    id = Column(String, primary_key=True)
    merchant_id = Column(String, nullable=False)
    customer_id = Column(String, nullable=False)
    cart_value = Column(Float, nullable=False)
    status = Column(String, nullable=False)  # abandoned | completed | in_progress
    stage_reached = Column(String, nullable=False)  # cart | address | payment_selection | otp
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity_at = Column(DateTime, default=datetime.utcnow)


class RiskSignal(Base):
    __tablename__ = "risk_signals"

    id = Column(String, primary_key=True)
    source_type = Column(String, nullable=False)  # payment | checkout
    source_id = Column(String, nullable=False)
    risk_score = Column(Float, nullable=False)  # 0-1
    root_cause = Column(String, nullable=True)
    diagnosis_confidence = Column(Float, nullable=True)
    diagnosed_at = Column(DateTime, nullable=True)


class RecoveryAction(Base):
    __tablename__ = "recovery_actions"

    id = Column(String, primary_key=True)
    signal_id = Column(String, nullable=False)
    action_type = Column(String, nullable=False)
    attempt_number = Column(Integer, default=1)
    scheduled_at = Column(DateTime, nullable=False)
    executed_at = Column(DateTime, nullable=True)
    outcome = Column(String, nullable=True)  # recovered | failed | still_pending
    amount_recovered = Column(Float, nullable=True)
    stopped_reason = Column(String, nullable=True)


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id = Column(String, primary_key=True)
    entity_id = Column(String, nullable=False)
    stage = Column(String, nullable=False)  # detect | diagnose | decide | execute
    explanation = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    _metadata = Column("metadata", Text, nullable=True)  # stored as JSON string

    @property
    def meta(self) -> dict:
        """Deserialize metadata JSON."""
        if self._metadata:
            return json.loads(self._metadata)
        return {}

    @meta.setter
    def meta(self, value: dict):
        """Serialize metadata to JSON."""
        self._metadata = json.dumps(value) if value else None
