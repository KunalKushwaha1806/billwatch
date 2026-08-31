"""Pydantic schemas for API request/response validation."""

from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


# ── Payment ──────────────────────────────────────────────────────────

class PaymentSchema(BaseModel):
    id: str
    merchant_id: str
    amount: float
    currency: str = "INR"
    status: str
    failure_code: str | None = None
    customer_id: str
    payment_method: str
    attempt_number: int = 1
    created_at: datetime
    mandate_id: str | None = None

    model_config = {"from_attributes": True}


# ── Checkout Session ─────────────────────────────────────────────────

class CheckoutSessionSchema(BaseModel):
    id: str
    merchant_id: str
    customer_id: str
    cart_value: float
    status: str
    stage_reached: str
    created_at: datetime
    last_activity_at: datetime

    model_config = {"from_attributes": True}


# ── Risk Signal ──────────────────────────────────────────────────────

class RiskSignalSchema(BaseModel):
    id: str
    source_type: str
    source_id: str
    risk_score: float
    root_cause: str | None = None
    diagnosis_confidence: float | None = None
    diagnosed_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Recovery Action ──────────────────────────────────────────────────

class RecoveryActionSchema(BaseModel):
    id: str
    signal_id: str
    action_type: str
    attempt_number: int
    scheduled_at: datetime
    executed_at: datetime | None = None
    outcome: str | None = None
    amount_recovered: float | None = None
    stopped_reason: str | None = None

    model_config = {"from_attributes": True}


# ── Audit Entry ──────────────────────────────────────────────────────

class AuditEntrySchema(BaseModel):
    id: str
    entity_id: str
    stage: str
    explanation: str
    timestamp: datetime
    metadata: dict = {}

    model_config = {"from_attributes": True}


# ── Metrics Summary ─────────────────────────────────────────────────

class RootCauseBreakdown(BaseModel):
    attempted: int
    recovered: int

class MetricsSummary(BaseModel):
    total_at_risk: float
    total_recovered: float
    recovery_rate: float
    actions_taken: int
    actions_blocked_by_policy: int
    escalated_to_human: int
    by_root_cause: dict[str, RootCauseBreakdown]


# ── Batch Load Response ─────────────────────────────────────────────

class BatchLoadResponse(BaseModel):
    payments_loaded: int
    checkout_sessions_loaded: int
    message: str


# ── Pipeline Run Response ────────────────────────────────────────────

class PipelineRunResponse(BaseModel):
    signals_detected: int
    actions_decided: int
    actions_executed: int
    message: str
