"""
Tests for the Detect stage (detect.py).

Requirements tested:
  REQ-DETECT-01  Only failed payments with attempt_number <= 3 are flagged
  REQ-DETECT-02  Payments with a prior successful recovery are skipped
  REQ-DETECT-03  Risk score is bounded [0, 1] and deterministic for same inputs
  REQ-DETECT-04  Risk score formula: 0.4*amount_norm + 0.3*attempt_prox + 0.3*time_decay
  REQ-DETECT-05  Successful payments produce no signals
  REQ-DETECT-06  Abandoned checkouts at payment_selection/otp OR cart_value >= 2000 are flagged
  REQ-DETECT-07  Completed checkouts are never flagged
  REQ-DETECT-08  An AuditEntry with stage='detect' is written for every flagged entity
  REQ-DETECT-09  detect_checkout_signals uses 12h half-life (faster decay than payments)
"""

import math
import pytest
from datetime import datetime, timedelta

from tests.conftest import make_payment, make_checkout, make_signal, make_action
from app.pipeline.detect import (
    detect_payment_signals,
    detect_checkout_signals,
    _time_decay,
    _normalize,
    CART_VALUE_THRESHOLD,
)
from app.models import AuditEntry


class TestTimeDecay:
    """REQ-DETECT-03: risk helpers are deterministic and bounded."""

    def test_very_recent_record_scores_near_one(self):
        """Record created <1 min ago should have decay ≈ 1.0."""
        score = _time_decay(datetime.utcnow() - timedelta(seconds=10))
        assert score > 0.99

    def test_24h_old_record_scores_half(self):
        """At exactly one half-life (24h), decay = 0.5."""
        score = _time_decay(datetime.utcnow() - timedelta(hours=24))
        assert abs(score - 0.5) < 0.02  # allow floating point slippage

    def test_48h_old_record_scores_quarter(self):
        score = _time_decay(datetime.utcnow() - timedelta(hours=48))
        assert abs(score - 0.25) < 0.02

    def test_very_old_record_scores_near_zero(self):
        score = _time_decay(datetime.utcnow() - timedelta(days=30))
        assert score < 0.01

    def test_custom_half_life_12h(self):
        """Checkout uses 12h half-life — verify formula."""
        score = _time_decay(datetime.utcnow() - timedelta(hours=12), half_life_hours=12.0)
        assert abs(score - 0.5) < 0.02


class TestNormalize:
    def test_value_equals_max(self):
        assert _normalize(100.0, 100.0) == 1.0

    def test_value_exceeds_max_is_capped(self):
        assert _normalize(200.0, 100.0) == 1.0

    def test_zero_value(self):
        assert _normalize(0.0, 100.0) == 0.0

    def test_zero_max_returns_zero(self):
        assert _normalize(50.0, 0.0) == 0.0

    def test_proportional(self):
        assert abs(_normalize(50.0, 100.0) - 0.5) < 1e-9


class TestDetectPaymentSignals:
    """REQ-DETECT-01 through REQ-DETECT-04, REQ-DETECT-08."""

    def test_failed_payment_produces_signal(self, db_session):
        make_payment(db_session, id="pay_A", status="failed", failure_code="bank_timeout")
        signals = detect_payment_signals(db_session)
        assert len(signals) == 1
        assert signals[0].source_id == "pay_A"
        assert signals[0].source_type == "payment"

    def test_successful_payment_not_flagged(self, db_session):
        """REQ-DETECT-05."""
        make_payment(db_session, id="pay_B", status="success", failure_code=None)
        signals = detect_payment_signals(db_session)
        assert len(signals) == 0

    def test_attempt_number_4_not_flagged(self, db_session):
        """REQ-DETECT-01: attempt_number must be <= 3."""
        make_payment(db_session, id="pay_C", status="failed", attempt_number=4)
        signals = detect_payment_signals(db_session)
        assert len(signals) == 0

    def test_attempt_number_3_is_flagged(self, db_session):
        make_payment(db_session, id="pay_D", status="failed", attempt_number=3)
        signals = detect_payment_signals(db_session)
        assert len(signals) == 1

    def test_risk_score_bounded_0_to_1(self, db_session):
        """REQ-DETECT-03: risk_score must be in [0, 1]."""
        make_payment(db_session, id="pay_E", status="failed", amount=25000.0, attempt_number=3)
        signals = detect_payment_signals(db_session)
        assert 0.0 <= signals[0].risk_score <= 1.0

    def test_prior_recovered_action_skips_signal(self, db_session):
        """REQ-DETECT-02: don't re-flag already-recovered payments."""
        make_payment(db_session, id="pay_F", status="failed")
        sig = make_signal(db_session, id="sig_F", source_id="pay_F")
        make_action(db_session, id="act_F", signal_id="sig_F", outcome="recovered")

        signals = detect_payment_signals(db_session)
        assert all(s.source_id != "pay_F" for s in signals)

    def test_audit_entry_written_for_each_signal(self, db_session):
        """REQ-DETECT-08: an AuditEntry with stage='detect' must be created."""
        make_payment(db_session, id="pay_G", status="failed")
        detect_payment_signals(db_session)

        entry = db_session.query(AuditEntry).filter(
            AuditEntry.entity_id == "pay_G",
            AuditEntry.stage == "detect",
        ).first()
        assert entry is not None
        assert "pay_G" in entry.explanation or "risk_score" in entry.explanation

    def test_higher_amount_yields_higher_risk_score(self, db_session):
        """REQ-DETECT-04: amount_norm coefficient 0.4 means larger amounts score higher."""
        now = datetime.utcnow()
        make_payment(db_session, id="pay_H1", status="failed", amount=100.0, attempt_number=1, created_at=now)
        make_payment(db_session, id="pay_H2", status="failed", amount=20000.0, attempt_number=1, created_at=now)
        signals = detect_payment_signals(db_session)
        s_low = next(s for s in signals if s.source_id == "pay_H1")
        s_high = next(s for s in signals if s.source_id == "pay_H2")
        assert s_high.risk_score > s_low.risk_score

    def test_multiple_failed_payments_all_flagged(self, db_session):
        for i in range(5):
            make_payment(db_session, id=f"pay_M{i}", status="failed", failure_code="otp_failed")
        signals = detect_payment_signals(db_session)
        assert len(signals) == 5


class TestDetectCheckoutSignals:
    """REQ-DETECT-06, REQ-DETECT-07, REQ-DETECT-09."""

    def test_abandoned_at_otp_flagged(self, db_session):
        make_checkout(db_session, id="sess_A", status="abandoned", stage_reached="otp", cart_value=500.0)
        signals = detect_checkout_signals(db_session)
        assert any(s.source_id == "sess_A" for s in signals)

    def test_abandoned_at_payment_selection_flagged(self, db_session):
        make_checkout(db_session, id="sess_B", status="abandoned", stage_reached="payment_selection", cart_value=500.0)
        signals = detect_checkout_signals(db_session)
        assert any(s.source_id == "sess_B" for s in signals)

    def test_abandoned_early_stage_high_value_flagged(self, db_session):
        """REQ-DETECT-06: cart >= 2000 qualifies even at 'cart' stage."""
        make_checkout(db_session, id="sess_C", status="abandoned", stage_reached="cart", cart_value=CART_VALUE_THRESHOLD)
        signals = detect_checkout_signals(db_session)
        assert any(s.source_id == "sess_C" for s in signals)

    def test_abandoned_early_stage_low_value_not_flagged(self, db_session):
        """Early stage + low value — not worth recovering."""
        make_checkout(db_session, id="sess_D", status="abandoned", stage_reached="cart", cart_value=100.0)
        signals = detect_checkout_signals(db_session)
        assert all(s.source_id != "sess_D" for s in signals)

    def test_completed_checkout_not_flagged(self, db_session):
        """REQ-DETECT-07."""
        make_checkout(db_session, id="sess_E", status="completed", stage_reached="otp")
        signals = detect_checkout_signals(db_session)
        assert all(s.source_id != "sess_E" for s in signals)

    def test_checkout_risk_score_bounded(self, db_session):
        make_checkout(db_session, id="sess_F", status="abandoned", stage_reached="otp", cart_value=15000.0)
        signals = detect_checkout_signals(db_session)
        s = next(s for s in signals if s.source_id == "sess_F")
        assert 0.0 <= s.risk_score <= 1.0

    def test_checkout_audit_entry_written(self, db_session):
        """REQ-DETECT-08."""
        make_checkout(db_session, id="sess_G", status="abandoned", stage_reached="otp")
        detect_checkout_signals(db_session)
        entry = db_session.query(AuditEntry).filter(
            AuditEntry.entity_id == "sess_G",
            AuditEntry.stage == "detect",
        ).first()
        assert entry is not None
