"""
Tests for the Diagnose stage (diagnose.py).

Requirements tested:
  REQ-DIAG-01  Payment failure codes map deterministically to root causes
  REQ-DIAG-02  All known failure codes have confidence = 1.0 (rule-based)
  REQ-DIAG-03  Unknown failure codes fall back to the raw code as root cause
  REQ-DIAG-04  Payment with no failure_code → root_cause='unknown', confidence=0.3
  REQ-DIAG-05  Checkout at 'otp' stage → 'payment_friction', confidence=0.90
  REQ-DIAG-06  Checkout at 'payment_selection' → 'price_hesitation', confidence=0.70
  REQ-DIAG-07  Checkout at 'address' → 'shipping_cost_surprise', confidence=0.55
  REQ-DIAG-08  Checkout at 'cart' → 'distraction_timeout', confidence=0.40
  REQ-DIAG-09  Unknown checkout stage → root_cause='unknown', confidence=0.3
  REQ-DIAG-10  LLM path: when ANTHROPIC_API_KEY is absent, falls back to heuristic silently
  REQ-DIAG-11  diagnosed_at is populated after diagnosis
  REQ-DIAG-12  An AuditEntry with stage='diagnose' is written for every diagnosed signal
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from tests.conftest import make_payment, make_checkout, make_signal
from app.pipeline.diagnose import (
    diagnose_payment,
    diagnose_checkout,
    FAILURE_CAUSE_MAP,
    CHECKOUT_STAGE_HEURISTICS,
)
from app.models import AuditEntry


class TestDiagnosePayment:
    """REQ-DIAG-01 through REQ-DIAG-04, REQ-DIAG-11, REQ-DIAG-12."""

    @pytest.mark.parametrize("failure_code,expected_cause", [
        ("bank_timeout",       "bank_timeout"),
        ("otp_failed",         "otp_failed"),
        ("network_error",      "network_error"),
        ("insufficient_funds", "insufficient_funds"),
        ("card_expired",       "card_expired"),
    ])
    def test_known_failure_codes_map_correctly(self, db_session, failure_code, expected_cause):
        """REQ-DIAG-01: every known failure code maps to the correct root cause."""
        p = make_payment(db_session, id=f"pay_{failure_code}", failure_code=failure_code)
        sig = make_signal(db_session, id=f"sig_{failure_code}", source_id=p.id)
        diagnose_payment(db_session, sig)
        assert sig.root_cause == expected_cause

    @pytest.mark.parametrize("failure_code", list(FAILURE_CAUSE_MAP.keys()))
    def test_known_codes_have_full_confidence(self, db_session, failure_code):
        """REQ-DIAG-02: deterministic rule → confidence must be 1.0."""
        p = make_payment(db_session, id=f"pay_conf_{failure_code}", failure_code=failure_code)
        sig = make_signal(db_session, id=f"sig_conf_{failure_code}", source_id=p.id)
        diagnose_payment(db_session, sig)
        assert sig.diagnosis_confidence == 1.0

    def test_no_failure_code_yields_unknown(self, db_session):
        """REQ-DIAG-04."""
        p = make_payment(db_session, id="pay_nocode", failure_code=None)
        sig = make_signal(db_session, id="sig_nocode", source_id=p.id)
        diagnose_payment(db_session, sig)
        assert sig.root_cause == "unknown"
        assert sig.diagnosis_confidence == 0.3

    def test_unknown_failure_code_uses_raw_code(self, db_session):
        """REQ-DIAG-03: unrecognized failure_code becomes the root_cause itself."""
        p = make_payment(db_session, id="pay_unk", failure_code="some_new_error")
        sig = make_signal(db_session, id="sig_unk", source_id=p.id)
        diagnose_payment(db_session, sig)
        assert sig.root_cause == "some_new_error"

    def test_diagnosed_at_is_set(self, db_session):
        """REQ-DIAG-11."""
        p = make_payment(db_session, id="pay_ts", failure_code="bank_timeout")
        sig = make_signal(db_session, id="sig_ts", source_id=p.id)
        diagnose_payment(db_session, sig)
        assert sig.diagnosed_at is not None
        assert isinstance(sig.diagnosed_at, datetime)

    def test_audit_entry_written(self, db_session):
        """REQ-DIAG-12."""
        p = make_payment(db_session, id="pay_aud", failure_code="otp_failed")
        sig = make_signal(db_session, id="sig_aud", source_id=p.id)
        diagnose_payment(db_session, sig)
        entry = db_session.query(AuditEntry).filter(
            AuditEntry.entity_id == p.id,
            AuditEntry.stage == "diagnose",
        ).first()
        assert entry is not None
        assert "otp_failed" in entry.explanation

    def test_audit_metadata_contains_confidence(self, db_session):
        p = make_payment(db_session, id="pay_meta", failure_code="card_expired")
        sig = make_signal(db_session, id="sig_meta", source_id=p.id)
        diagnose_payment(db_session, sig)
        entry = db_session.query(AuditEntry).filter(
            AuditEntry.entity_id == p.id,
            AuditEntry.stage == "diagnose",
        ).first()
        assert entry.meta.get("confidence") == 1.0
        assert entry.meta.get("root_cause") == "card_expired"


class TestDiagnoseCheckout:
    """REQ-DIAG-05 through REQ-DIAG-10, REQ-DIAG-11, REQ-DIAG-12."""

    @pytest.mark.parametrize("stage,expected_cause,expected_conf", [
        ("otp",               "payment_friction",       0.90),
        ("payment_selection", "price_hesitation",       0.70),
        ("address",           "shipping_cost_surprise", 0.55),
        ("cart",              "distraction_timeout",    0.40),
    ])
    def test_stage_heuristic_mapping(self, db_session, stage, expected_cause, expected_conf):
        """REQ-DIAG-05 through REQ-DIAG-08: each stage maps to correct root cause & confidence."""
        c = make_checkout(db_session, id=f"sess_{stage}", stage_reached=stage)
        sig = make_signal(db_session, id=f"sig_{stage}", source_type="checkout", source_id=c.id)
        # Ensure no LLM call by unsetting any env key
        with patch.dict("os.environ", {}, clear=False):
            import os; os.environ.pop("ANTHROPIC_API_KEY", None)
            diagnose_checkout(db_session, sig)
        assert sig.root_cause == expected_cause
        assert abs(sig.diagnosis_confidence - expected_conf) < 1e-9

    def test_unknown_stage_yields_unknown(self, db_session):
        """REQ-DIAG-09."""
        c = make_checkout(db_session, id="sess_weird", stage_reached="checkout_stage_xyz")
        sig = make_signal(db_session, id="sig_weird", source_type="checkout", source_id=c.id)
        diagnose_checkout(db_session, sig)
        assert sig.root_cause == "unknown"
        assert sig.diagnosis_confidence == 0.3

    def test_no_api_key_falls_back_to_heuristic(self, db_session):
        """REQ-DIAG-10: absent ANTHROPIC_API_KEY → graceful heuristic fallback."""
        import os
        os.environ.pop("ANTHROPIC_API_KEY", None)
        c = make_checkout(db_session, id="sess_llmfb", stage_reached="payment_selection")
        sig = make_signal(db_session, id="sig_llmfb", source_type="checkout", source_id=c.id)
        diagnose_checkout(db_session, sig)
        # Should fall back to heuristic, not raise
        assert sig.root_cause == "price_hesitation"
        assert sig.diagnosis_confidence == 0.70

    def test_llm_result_overrides_heuristic(self, db_session):
        """When LLM returns a valid result it should be used over heuristic."""
        c = make_checkout(db_session, id="sess_llmok", stage_reached="payment_selection")
        sig = make_signal(db_session, id="sig_llmok", source_type="checkout", source_id=c.id)

        mock_result = {"root_cause": "shipping_cost_surprise", "confidence": 0.85, "reasoning": "test"}
        with patch("app.pipeline.diagnose._try_llm_diagnosis", return_value=mock_result):
            diagnose_checkout(db_session, sig)

        assert sig.root_cause == "shipping_cost_surprise"
        assert sig.diagnosis_confidence == 0.85

    def test_llm_exception_falls_back(self, db_session):
        """If LLM raises, _try_llm_diagnosis returns None → heuristic used."""
        c = make_checkout(db_session, id="sess_llmerr", stage_reached="address")
        sig = make_signal(db_session, id="sig_llmerr", source_type="checkout", source_id=c.id)
        with patch("app.pipeline.diagnose._try_llm_diagnosis", return_value=None):
            diagnose_checkout(db_session, sig)
        assert sig.root_cause == "shipping_cost_surprise"

    def test_checkout_audit_entry_written(self, db_session):
        """REQ-DIAG-12."""
        c = make_checkout(db_session, id="sess_aud2", stage_reached="otp")
        sig = make_signal(db_session, id="sig_aud2", source_type="checkout", source_id=c.id)
        with patch.dict("os.environ", {}, clear=False):
            import os; os.environ.pop("ANTHROPIC_API_KEY", None)
            diagnose_checkout(db_session, sig)
        entry = db_session.query(AuditEntry).filter(
            AuditEntry.entity_id == c.id,
            AuditEntry.stage == "diagnose",
        ).first()
        assert entry is not None

    def test_diagnosed_at_populated_checkout(self, db_session):
        """REQ-DIAG-11."""
        c = make_checkout(db_session, id="sess_ts2", stage_reached="otp")
        sig = make_signal(db_session, id="sig_ts2", source_type="checkout", source_id=c.id)
        diagnose_checkout(db_session, sig)
        assert sig.diagnosed_at is not None
