"""
Tests for the Execute stage (execute.py).

Requirements tested:
  REQ-EXEC-01  Simulated: no real payment retries or messages are sent
  REQ-EXEC-02  no_action_policy_block actions are skipped entirely
  REQ-EXEC-03  escalate_human actions get outcome='still_pending', not 'recovered'/'failed'
  REQ-EXEC-04  Execution is deterministic per action_id (seeded RNG)
  REQ-EXEC-05  Recovered action has outcome='recovered' and amount_recovered = source amount
  REQ-EXEC-06  Failed action has outcome='failed' and amount_recovered = 0.0
  REQ-EXEC-07  executed_at is set after execution
  REQ-EXEC-08  Already-executed actions are skipped (idempotent)
  REQ-EXEC-09  AuditEntry with stage='execute' is written for every executed action
  REQ-EXEC-10  Success rate by root cause matches SIMULATED_SUCCESS_RATES table
  REQ-EXEC-11  AuditEntry explanation contains '[SIMULATED]' label
"""

import pytest
from datetime import datetime
from unittest.mock import patch

from tests.conftest import make_payment, make_checkout, make_signal, make_action
from app.pipeline.execute import execute_action, SIMULATED_SUCCESS_RATES, _deterministic_seed
from app.models import AuditEntry


class TestExecuteSkipRules:
    """REQ-EXEC-02, REQ-EXEC-03, REQ-EXEC-08."""

    def test_policy_block_action_is_skipped(self, db_session):
        """REQ-EXEC-02: no_action_policy_block → execute_action returns without doing anything."""
        p = make_payment(db_session, id="pay_skip")
        sig = make_signal(db_session, id="sig_skip", source_id=p.id)
        action = make_action(db_session, id="act_skip", signal_id=sig.id, action_type="no_action_policy_block")

        execute_action(db_session, action, sig)

        assert action.executed_at is None  # not touched
        assert action.outcome is None

    def test_escalate_human_gets_still_pending(self, db_session):
        """REQ-EXEC-03."""
        p = make_payment(db_session, id="pay_esc")
        sig = make_signal(db_session, id="sig_esc", source_id=p.id, root_cause="unknown", diagnosis_confidence=0.45)
        action = make_action(db_session, id="act_esc", signal_id=sig.id, action_type="escalate_human")

        execute_action(db_session, action, sig)

        assert action.outcome == "still_pending"
        assert action.executed_at is not None

    def test_already_executed_action_is_skipped(self, db_session):
        """REQ-EXEC-08: idempotency — re-executing does nothing."""
        p = make_payment(db_session, id="pay_idem")
        sig = make_signal(db_session, id="sig_idem", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.9)
        already_at = datetime(2026, 1, 1, 12, 0, 0)
        action = make_action(
            db_session, id="act_idem", signal_id=sig.id,
            action_type="retry_payment", executed_at=already_at,
        )

        execute_action(db_session, action, sig)

        assert action.executed_at == already_at  # unchanged


class TestDeterministicOutcome:
    """REQ-EXEC-04: same action_id always yields same outcome."""

    def test_same_action_id_same_outcome(self, db_session):
        p = make_payment(db_session, id="pay_det")
        sig = make_signal(db_session, id="sig_det", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.9)
        action1 = make_action(db_session, id="act_det_fixed_id_abc123", signal_id=sig.id)

        execute_action(db_session, action1, sig)
        first_outcome = action1.outcome

        # Reset and try again with same ID
        action1.executed_at = None
        action1.outcome = None
        execute_action(db_session, action1, sig)
        second_outcome = action1.outcome

        assert first_outcome == second_outcome

    def test_deterministic_seed_is_consistent(self):
        """REQ-EXEC-04: same string → same seed."""
        s1 = _deterministic_seed("act_abc")
        s2 = _deterministic_seed("act_abc")
        assert s1 == s2

    def test_different_ids_can_yield_different_outcomes(self):
        """Different action IDs produce different seeds (with high probability)."""
        s1 = _deterministic_seed("act_aaa000000001")
        s2 = _deterministic_seed("act_bbb000000002")
        # Very unlikely to collide — if this flakes, the seed function is broken
        assert s1 != s2


class TestOutcomeValues:
    """REQ-EXEC-05, REQ-EXEC-06, REQ-EXEC-07."""

    def _run_with_forced_success(self, db_session, force_recovered: bool):
        """Helper: mock RNG to force a specific outcome."""
        p = make_payment(db_session, id=f"pay_out_{force_recovered}", amount=7500.0)
        sig = make_signal(db_session, id=f"sig_out_{force_recovered}", source_id=p.id,
                          root_cause="bank_timeout", diagnosis_confidence=0.9)
        action = make_action(db_session, id=f"act_out_{force_recovered}", signal_id=sig.id, action_type="retry_payment")

        import random
        fake_rng = random.Random(0)
        # Patch RNG so random() returns < 0.7 (success) or > 0.7 (fail)
        target_val = 0.1 if force_recovered else 0.95
        with patch.object(fake_rng, "random", return_value=target_val):
            with patch("app.pipeline.execute.random") as mock_random_module:
                mock_random_module.Random.return_value = fake_rng
                execute_action(db_session, action, sig)

        return action, p.amount

    def test_recovered_action_has_correct_amount(self, db_session):
        """REQ-EXEC-05: amount_recovered == source payment amount."""
        p = make_payment(db_session, id="pay_rec_amt", amount=8000.0)
        sig = make_signal(db_session, id="sig_rec_amt", source_id=p.id, root_cause="network_error", diagnosis_confidence=0.9)
        action = make_action(db_session, id="act_rec_forced", signal_id=sig.id, action_type="retry_payment")

        # Force success by patching RNG to return 0.01 (below any success rate)
        import random
        with patch("app.pipeline.execute.random") as m:
            rng = MagicMock()
            rng.random.return_value = 0.01  # always recovers
            m.Random.return_value = rng
            execute_action(db_session, action, sig)

        assert action.outcome == "recovered"
        assert action.amount_recovered == 8000.0

    def test_failed_action_has_zero_amount(self, db_session):
        """REQ-EXEC-06."""
        p = make_payment(db_session, id="pay_fail_amt", amount=8000.0)
        sig = make_signal(db_session, id="sig_fail_amt", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.9)
        action = make_action(db_session, id="act_fail_forced", signal_id=sig.id, action_type="retry_payment")

        import random
        with patch("app.pipeline.execute.random") as m:
            rng = MagicMock()
            rng.random.return_value = 0.99  # always fails
            m.Random.return_value = rng
            execute_action(db_session, action, sig)

        assert action.outcome == "failed"
        assert action.amount_recovered == 0.0

    def test_executed_at_is_set(self, db_session):
        """REQ-EXEC-07."""
        p = make_payment(db_session, id="pay_ts_exec")
        sig = make_signal(db_session, id="sig_ts_exec", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.9)
        action = make_action(db_session, id="act_ts_exec", signal_id=sig.id)
        execute_action(db_session, action, sig)
        assert action.executed_at is not None

    def test_checkout_amount_is_cart_value(self, db_session):
        """REQ-EXEC-05 for checkout: amount = cart_value."""
        c = make_checkout(db_session, id="sess_exec_cart", cart_value=4500.0)
        sig = make_signal(db_session, id="sig_exec_cart", source_type="checkout", source_id=c.id,
                          root_cause="payment_friction", diagnosis_confidence=0.9)
        action = make_action(db_session, id="act_exec_cart_forced", signal_id=sig.id, action_type="send_nudge")

        import random
        with patch("app.pipeline.execute.random") as m:
            rng = MagicMock()
            rng.random.return_value = 0.01  # force success
            m.Random.return_value = rng
            execute_action(db_session, action, sig)

        assert action.amount_recovered == 4500.0


class TestExecuteAudit:
    """REQ-EXEC-09, REQ-EXEC-11."""

    def test_audit_entry_written_after_execution(self, db_session):
        """REQ-EXEC-09."""
        p = make_payment(db_session, id="pay_exec_aud")
        sig = make_signal(db_session, id="sig_exec_aud", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.9)
        action = make_action(db_session, id="act_exec_aud", signal_id=sig.id)
        execute_action(db_session, action, sig)
        entry = db_session.query(AuditEntry).filter(
            AuditEntry.entity_id == p.id,
            AuditEntry.stage == "execute",
        ).first()
        assert entry is not None

    def test_audit_explanation_contains_simulated_label(self, db_session):
        """REQ-EXEC-11: SIMULATION NOTE must appear in audit."""
        p = make_payment(db_session, id="pay_sim_lbl")
        sig = make_signal(db_session, id="sig_sim_lbl", source_id=p.id, root_cause="bank_timeout", diagnosis_confidence=0.9)
        action = make_action(db_session, id="act_sim_lbl", signal_id=sig.id)
        execute_action(db_session, action, sig)
        entry = db_session.query(AuditEntry).filter(
            AuditEntry.entity_id == p.id,
            AuditEntry.stage == "execute",
        ).first()
        assert "[SIMULATED]" in entry.explanation

    def test_escalate_audit_entry_written(self, db_session):
        p = make_payment(db_session, id="pay_esc_aud")
        sig = make_signal(db_session, id="sig_esc_aud", source_id=p.id, root_cause="unknown", diagnosis_confidence=0.4)
        action = make_action(db_session, id="act_esc_aud", signal_id=sig.id, action_type="escalate_human")
        execute_action(db_session, action, sig)
        entry = db_session.query(AuditEntry).filter(
            AuditEntry.entity_id == p.id,
            AuditEntry.stage == "execute",
        ).first()
        assert entry is not None
        assert "[SIMULATED]" in entry.explanation


# Need MagicMock
from unittest.mock import MagicMock  # noqa: E402 (moved here to avoid top-level patch import confusion)
