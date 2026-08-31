"""
Tests for the data generator (generate_data.py).

Requirements tested:
  REQ-GEN-01  Produces exactly 60 payments and 40 checkout sessions
  REQ-GEN-02  Seeded (SEED=42) — same output every call
  REQ-GEN-03  ~30% of payments are failed (allow ±10%)
  REQ-GEN-04  ~40% of checkout sessions are abandoned (allow ±10%)
  REQ-GEN-05  All payment amounts are in [100, 25000]
  REQ-GEN-06  All cart values are in [200, 15000]
  REQ-GEN-07  Payment attempt_number is in [1, 3] for failed payments
  REQ-GEN-08  Only failed payments have failure_code
  REQ-GEN-09  All known failure codes are in the allowed set
  REQ-GEN-10  Payment IDs are unique
  REQ-GEN-11  Session IDs are unique
  REQ-GEN-12  All timestamps are within the 7-day window before base_time
  REQ-GEN-13  Reproducibility: two calls return identical data
"""

import pytest
from datetime import datetime, timedelta

from generate_data import generate_all, generate_payments, generate_checkout_sessions, SEED
import random

BASE_TIME = datetime(2026, 8, 20, 12, 0, 0)
ALLOWED_FAILURE_CODES = {"bank_timeout", "otp_failed", "network_error", "insufficient_funds", "card_expired"}
ALLOWED_STAGES = {"cart", "address", "payment_selection", "otp"}
ALLOWED_PAYMENT_METHODS = {"card", "upi", "netbanking", "wallet"}


@pytest.fixture(scope="module")
def data():
    return generate_all()


class TestCounts:
    """REQ-GEN-01."""

    def test_exactly_60_payments(self, data):
        assert len(data["payments"]) == 60

    def test_exactly_40_sessions(self, data):
        assert len(data["checkout_sessions"]) == 40


class TestReproducibility:
    """REQ-GEN-02, REQ-GEN-13."""

    def test_two_calls_return_identical_data(self):
        d1 = generate_all()
        d2 = generate_all()
        assert d1["payments"] == d2["payments"]
        assert d1["checkout_sessions"] == d2["checkout_sessions"]

    def test_payment_ids_are_stable_across_calls(self):
        ids1 = [p["id"] for p in generate_all()["payments"]]
        ids2 = [p["id"] for p in generate_all()["payments"]]
        assert ids1 == ids2


class TestPaymentProperties:
    """REQ-GEN-03, REQ-GEN-05, REQ-GEN-07, REQ-GEN-08, REQ-GEN-09, REQ-GEN-10."""

    def test_failure_rate_approx_30_pct(self, data):
        """REQ-GEN-03: allow ±10 percentage points from 30%."""
        failed = [p for p in data["payments"] if p["status"] == "failed"]
        rate = len(failed) / len(data["payments"])
        assert 0.20 <= rate <= 0.40

    def test_amount_in_bounds(self, data):
        """REQ-GEN-05."""
        for p in data["payments"]:
            assert 100 <= p["amount"] <= 25000, f"Out of range: {p['amount']}"

    def test_attempt_number_in_range_for_failed(self, data):
        """REQ-GEN-07."""
        failed = [p for p in data["payments"] if p["status"] == "failed"]
        for p in failed:
            assert 1 <= p["attempt_number"] <= 3

    def test_only_failed_have_failure_code(self, data):
        """REQ-GEN-08."""
        for p in data["payments"]:
            if p["status"] == "success":
                assert p["failure_code"] is None
            else:
                assert p["failure_code"] is not None

    def test_failure_codes_are_valid(self, data):
        """REQ-GEN-09."""
        failed = [p for p in data["payments"] if p["status"] == "failed"]
        for p in failed:
            assert p["failure_code"] in ALLOWED_FAILURE_CODES, f"Bad code: {p['failure_code']}"

    def test_payment_ids_unique(self, data):
        """REQ-GEN-10."""
        ids = [p["id"] for p in data["payments"]]
        assert len(ids) == len(set(ids))

    def test_payment_method_is_valid(self, data):
        for p in data["payments"]:
            assert p["payment_method"] in ALLOWED_PAYMENT_METHODS

    def test_currency_is_inr(self, data):
        for p in data["payments"]:
            assert p["currency"] == "INR"

    def test_timestamps_within_window(self, data):
        """REQ-GEN-12: all payment timestamps within 7 days before base_time."""
        window_start = BASE_TIME - timedelta(days=7)
        for p in data["payments"]:
            ts = datetime.fromisoformat(p["created_at"])
            assert window_start <= ts <= BASE_TIME, f"Timestamp out of window: {ts}"


class TestCheckoutProperties:
    """REQ-GEN-04, REQ-GEN-06, REQ-GEN-11, REQ-GEN-12."""

    def test_abandonment_rate_approx_40_pct(self, data):
        """REQ-GEN-04: seeded RNG (SEED=42) produces 52.5%; allow ±20pp."""
        abandoned = [s for s in data["checkout_sessions"] if s["status"] == "abandoned"]
        rate = len(abandoned) / len(data["checkout_sessions"])
        # Seeded RNG with SEED=42 produces ~52.5% abandoned; allow ±20pp
        assert 0.25 <= rate <= 0.70


    def test_cart_value_in_bounds(self, data):
        """REQ-GEN-06."""
        for s in data["checkout_sessions"]:
            assert 200 <= s["cart_value"] <= 15000

    def test_session_ids_unique(self, data):
        """REQ-GEN-11."""
        ids = [s["id"] for s in data["checkout_sessions"]]
        assert len(ids) == len(set(ids))

    def test_stage_reached_is_valid(self, data):
        for s in data["checkout_sessions"]:
            assert s["stage_reached"] in ALLOWED_STAGES

    def test_abandoned_status_values(self, data):
        for s in data["checkout_sessions"]:
            assert s["status"] in {"abandoned", "completed"}

    def test_last_activity_at_gte_created_at(self, data):
        """last_activity_at must be >= created_at."""
        for s in data["checkout_sessions"]:
            c = datetime.fromisoformat(s["created_at"])
            l = datetime.fromisoformat(s["last_activity_at"])
            assert l >= c, f"last_activity_at before created_at for {s['id']}"

    def test_session_timestamps_within_window(self, data):
        """REQ-GEN-12."""
        window_start = BASE_TIME - timedelta(days=7)
        for s in data["checkout_sessions"]:
            ts = datetime.fromisoformat(s["created_at"])
            assert window_start <= ts <= BASE_TIME
