"""
Tests for the Decide stage (decide.py).

Requirements tested:
  REQ-DECIDE-01  Rule 1 — max_attempts_reached: >= 3 prior actions → policy block
  REQ-DECIDE-02  Rule 2 — cooldown_active: last action < 15 min ago → policy block
  REQ-DECIDE-03  Rule 3 — low_confidence_diagnosis: confidence < 0.5 → escalate_human
  REQ-DECIDE-04  Rule 4 — fraud_policy_block: customer in FRAUD_FLAGGED_CUSTOMERS → hard stop
  REQ-DECIDE-05  Rule 5 — action approved: no stopping rules fired → action created
  REQ-DECIDE-06  Payment root cause → action type mapping (PAYMENT_ACTION_MAP)
  REQ-DECIDE-07  Checkout root cause → action type mapping (CHECKOUT_ACTION_MAP)
  REQ-DECIDE-08  card_expired maps to send_nudge (not retry_payment)
  REQ-DECIDE-09  Stopping rules fire in correct priority order
  REQ-DECIDE-10  AuditEntry with stage='decide' is written for every decision
  REQ-DECIDE-11  Blocked actions get stopped_reason populated
  REQ-DECIDE-12  Attempt number increments correctly relative to prior actions
"""

import pytest
from datetime import datetime, timedelta

from tests.conftest import make_payment, make_checkout, make_signal, make_action
from app.pipeline.decide import decide_action, FRAUD_FLAGGED_CUSTOMERS, MAX_ATTEMPTS, COOLDOWN_MINUTES
from app.models import AuditEntry, RecoveryAction


class TestStoppingRules:
    """REQ-DECIDE-01 through REQ-DECIDE-04."""

    def test_rule1_max_attempts_blocks(self, db_session):
        """REQ-DECIDE-01: 3+ prior actions → no_action_policy_block."""
        p = make_payment(db_session, id="pay_max", customer_id="cust_999")
        sig = make_signal(db_session, id="sig_max", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.9)
        for i in range(MAX_ATTEMPTS):
            make_action(db_session, id=f"act_max_{i}", signal_id=sig.id, attempt_number=i + 1)

        action = decide_action(db_session, sig)
        assert action is not None
        assert action.action_type == "no_action_policy_block"
        assert action.stopped_reason == "max_attempts_reached"

    def test_rule1_exactly_threshold_blocks(self, db_session):
        """At exactly MAX_ATTEMPTS prior actions, the rule fires."""
        p = make_payment(db_session, id="pay_exact", customer_id="cust_998")
        sig = make_signal(db_session, id="sig_exact", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.9)
        for i in range(MAX_ATTEMPTS):
            make_action(db_session, id=f"act_exact_{i}", signal_id=sig.id)

        action = decide_action(db_session, sig)
        assert action.stopped_reason == "max_attempts_reached"

    def test_rule1_below_threshold_does_not_block(self, db_session):
        """2 prior actions (< 3) must NOT trigger the max-attempts rule."""
        p = make_payment(db_session, id="pay_below", customer_id="cust_997")
        sig = make_signal(db_session, id="sig_below", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.9)
        for i in range(MAX_ATTEMPTS - 1):
            old_time = datetime.utcnow() - timedelta(hours=2)  # well outside cooldown
            make_action(db_session, id=f"act_below_{i}", signal_id=sig.id, scheduled_at=old_time)

        action = decide_action(db_session, sig)
        assert action.action_type != "no_action_policy_block"

    def test_rule2_cooldown_blocks(self, db_session):
        """REQ-DECIDE-02: last action within COOLDOWN_MINUTES → cooldown_active."""
        p = make_payment(db_session, id="pay_cd", customer_id="cust_996")
        sig = make_signal(db_session, id="sig_cd", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.9)
        recent = datetime.utcnow() - timedelta(minutes=COOLDOWN_MINUTES - 1)
        make_action(db_session, id="act_cd", signal_id=sig.id, scheduled_at=recent)

        action = decide_action(db_session, sig)
        assert action.stopped_reason == "cooldown_active"

    def test_rule2_after_cooldown_allows(self, db_session):
        """Past the cooldown window — action should be approved."""
        p = make_payment(db_session, id="pay_cd2", customer_id="cust_995")
        sig = make_signal(db_session, id="sig_cd2", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.9)
        old = datetime.utcnow() - timedelta(minutes=COOLDOWN_MINUTES + 5)
        make_action(db_session, id="act_cd2", signal_id=sig.id, scheduled_at=old)

        action = decide_action(db_session, sig)
        assert action.stopped_reason != "cooldown_active"

    def test_rule3_low_confidence_escalates(self, db_session):
        """REQ-DECIDE-03: confidence < 0.5 → escalate_human."""
        p = make_payment(db_session, id="pay_lc", customer_id="cust_994")
        sig = make_signal(db_session, id="sig_lc", source_id=p.id, root_cause="unknown", diagnosis_confidence=0.49)

        action = decide_action(db_session, sig)
        assert action.action_type == "escalate_human"
        assert action.stopped_reason == "low_confidence_diagnosis"

    def test_rule3_exactly_05_does_not_escalate(self, db_session):
        """Confidence of exactly 0.5 must NOT trigger escalation (threshold is strictly < 0.5)."""
        p = make_payment(db_session, id="pay_lc2", customer_id="cust_993")
        sig = make_signal(db_session, id="sig_lc2", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.5)

        action = decide_action(db_session, sig)
        assert action.action_type != "escalate_human"

    def test_rule4_fraud_block(self, db_session):
        """REQ-DECIDE-04: fraud-flagged customer → no_action_policy_block / fraud_policy_block."""
        fraud_cust = next(iter(FRAUD_FLAGGED_CUSTOMERS))  # grab a real fraud-listed customer
        p = make_payment(db_session, id="pay_fraud", customer_id=fraud_cust)
        sig = make_signal(db_session, id="sig_fraud", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.9)

        action = decide_action(db_session, sig)
        assert action.stopped_reason == "fraud_policy_block"
        assert action.action_type == "no_action_policy_block"

    def test_rule4_non_fraud_customer_not_blocked(self, db_session):
        p = make_payment(db_session, id="pay_ok", customer_id="cust_safe_99")
        sig = make_signal(db_session, id="sig_ok", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.9)

        action = decide_action(db_session, sig)
        assert action.stopped_reason != "fraud_policy_block"

    def test_rule_priority_max_attempts_over_cooldown(self, db_session):
        """REQ-DECIDE-09: max_attempts fires before cooldown when both would apply."""
        p = make_payment(db_session, id="pay_prio", customer_id="cust_992")
        sig = make_signal(db_session, id="sig_prio", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.9)
        # Create enough prior actions AND a very recent one
        recent = datetime.utcnow() - timedelta(minutes=1)
        for i in range(MAX_ATTEMPTS):
            make_action(db_session, id=f"act_prio_{i}", signal_id=sig.id, scheduled_at=recent)

        action = decide_action(db_session, sig)
        assert action.stopped_reason == "max_attempts_reached"  # not cooldown_active


class TestActionApproval:
    """REQ-DECIDE-05 through REQ-DECIDE-08, REQ-DECIDE-12."""

    @pytest.mark.parametrize("root_cause,expected_action", [
        ("bank_timeout",       "retry_payment"),
        ("otp_failed",         "retry_payment"),
        ("network_error",      "retry_payment"),
        ("insufficient_funds", "retry_payment"),
        ("card_expired",       "send_nudge"),    # REQ-DECIDE-08
    ])
    def test_payment_action_mapping(self, db_session, root_cause, expected_action):
        """REQ-DECIDE-06 + REQ-DECIDE-08."""
        p = make_payment(db_session, id=f"pay_{root_cause}", customer_id="cust_safe_88")
        sig = make_signal(
            db_session, id=f"sig_{root_cause}", source_id=p.id,
            root_cause=root_cause, diagnosis_confidence=0.9,
        )
        action = decide_action(db_session, sig)
        assert action.action_type == expected_action

    @pytest.mark.parametrize("root_cause", [
        "payment_friction", "price_hesitation", "shipping_cost_surprise", "distraction_timeout",
    ])
    def test_checkout_action_mapping(self, db_session, root_cause):
        """REQ-DECIDE-07: all checkout causes map to send_nudge."""
        c = make_checkout(db_session, id=f"sess_{root_cause}", customer_id="cust_safe_77")
        sig = make_signal(
            db_session, id=f"sig_co_{root_cause}", source_type="checkout", source_id=c.id,
            root_cause=root_cause, diagnosis_confidence=0.9,
        )
        action = decide_action(db_session, sig)
        assert action.action_type == "send_nudge"

    def test_approved_action_has_no_stopped_reason(self, db_session):
        """REQ-DECIDE-05."""
        p = make_payment(db_session, id="pay_app", customer_id="cust_safe_66")
        sig = make_signal(db_session, id="sig_app", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.9)
        action = decide_action(db_session, sig)
        assert action.stopped_reason is None

    def test_attempt_number_is_1_for_first_action(self, db_session):
        """REQ-DECIDE-12."""
        p = make_payment(db_session, id="pay_att", customer_id="cust_safe_55")
        sig = make_signal(db_session, id="sig_att", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.9)
        action = decide_action(db_session, sig)
        assert action.attempt_number == 1

    def test_attempt_number_increments_with_prior_actions(self, db_session):
        """REQ-DECIDE-12: attempt # = prior count + 1."""
        p = make_payment(db_session, id="pay_att2", customer_id="cust_safe_44")
        sig = make_signal(db_session, id="sig_att2", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.9)
        old = datetime.utcnow() - timedelta(hours=5)
        make_action(db_session, id="act_att2_0", signal_id=sig.id, scheduled_at=old)
        action = decide_action(db_session, sig)
        assert action.attempt_number == 2


class TestDecideAudit:
    """REQ-DECIDE-10, REQ-DECIDE-11."""

    def test_audit_entry_written_for_approved_action(self, db_session):
        """REQ-DECIDE-10."""
        p = make_payment(db_session, id="pay_aud_ok", customer_id="cust_safe_33")
        sig = make_signal(db_session, id="sig_aud_ok", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.9)
        decide_action(db_session, sig)
        entry = db_session.query(AuditEntry).filter(
            AuditEntry.entity_id == p.id,
            AuditEntry.stage == "decide",
        ).first()
        assert entry is not None
        assert "ACTION APPROVED" in entry.explanation

    def test_audit_entry_written_for_blocked_action(self, db_session):
        """REQ-DECIDE-10: blocked cases also get an audit entry."""
        p = make_payment(db_session, id="pay_aud_blk", customer_id="cust_safe_22")
        sig = make_signal(db_session, id="sig_aud_blk", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.9)
        for i in range(MAX_ATTEMPTS):
            make_action(db_session, id=f"act_aud_blk_{i}", signal_id=sig.id)
        decide_action(db_session, sig)
        entries = db_session.query(AuditEntry).filter(
            AuditEntry.entity_id == p.id,
            AuditEntry.stage == "decide",
        ).all()
        assert len(entries) >= 1

    def test_blocked_action_outcome_is_failed(self, db_session):
        """REQ-DECIDE-11: blocked actions are marked as outcome='failed'."""
        p = make_payment(db_session, id="pay_blk_out", customer_id="cust_safe_11")
        sig = make_signal(db_session, id="sig_blk_out", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.9)
        for i in range(MAX_ATTEMPTS):
            make_action(db_session, id=f"act_blk_out_{i}", signal_id=sig.id)
        action = decide_action(db_session, sig)
        assert action.outcome == "failed"
        assert action.executed_at is not None  # immediately "executed" (blocked)
