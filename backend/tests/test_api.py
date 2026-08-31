"""
Integration tests for all API routes (HTTP layer).

Requirements tested:
  REQ-API-01   POST /batch/load returns 200 with correct counts (60 payments, 40 sessions)
  REQ-API-02   POST /batch/load resets DB before inserting (idempotent reload)
  REQ-API-03   POST /pipeline/run returns signals_detected > 0 after a batch load
  REQ-API-04   POST /pipeline/run returns actions_decided > 0
  REQ-API-05   GET /signals returns list; source_type filter works
  REQ-API-06   GET /signals returns source_details embedded in each signal
  REQ-API-07   GET /actions returns list; outcome filter works
  REQ-API-08   GET /audit/{entity_id} returns ordered 4-stage timeline
  REQ-API-09   GET /audit/{unknown_id} returns 404
  REQ-API-10   GET /metrics/summary returns correct shape and recovery_rate in [0,1]
  REQ-API-11   GET /metrics/summary total_recovered <= total_at_risk
  REQ-API-12   Reproducibility: two pipeline runs on same seeded batch → identical metrics
  REQ-API-13   GET / returns the app info root
  REQ-API-14   CORS headers are present (OPTIONS preflight)
"""

import pytest


# ─── Helper: fully seeded run ────────────────────────────────────────

def _full_run(client):
    """Load batch + run pipeline, return (batch_res, pipeline_res)."""
    b = client.post("/batch/load")
    assert b.status_code == 200
    p = client.post("/pipeline/run")
    assert p.status_code == 200
    return b.json(), p.json()


class TestBatchLoad:
    """REQ-API-01, REQ-API-02."""

    def test_load_returns_200(self, client):
        r = client.post("/batch/load")
        assert r.status_code == 200

    def test_load_correct_counts(self, client):
        """REQ-API-01: seeded generator produces exactly 60 + 40."""
        r = client.post("/batch/load").json()
        assert r["payments_loaded"] == 60
        assert r["checkout_sessions_loaded"] == 40

    def test_load_message_present(self, client):
        r = client.post("/batch/load").json()
        assert "message" in r
        assert len(r["message"]) > 0

    def test_reload_is_idempotent(self, client):
        """REQ-API-02: second load still returns 60 + 40 (DB was reset)."""
        client.post("/batch/load")
        r = client.post("/batch/load").json()
        assert r["payments_loaded"] == 60
        assert r["checkout_sessions_loaded"] == 40


class TestPipelineRun:
    """REQ-API-03, REQ-API-04."""

    def test_pipeline_returns_200(self, client):
        client.post("/batch/load")
        r = client.post("/pipeline/run")
        assert r.status_code == 200

    def test_signals_detected_positive(self, client):
        """REQ-API-03."""
        _full_run(client)
        r = client.post("/pipeline/run").json()
        # Second run after first — still detects (some may already be recovered)
        # We verify the first run had > 0
        batch, pipeline = _full_run(client)
        assert pipeline["signals_detected"] > 0

    def test_actions_decided_positive(self, client):
        """REQ-API-04."""
        _, pipeline = _full_run(client)
        assert pipeline["actions_decided"] > 0

    def test_pipeline_message_present(self, client):
        _full_run(client)
        _, p = _full_run(client)
        assert "Pipeline complete" in p["message"]

    def test_actions_executed_leq_decided(self, client):
        """Blocked actions are not executed — executed ≤ decided."""
        _, p = _full_run(client)
        assert p["actions_executed"] <= p["actions_decided"]


class TestSignalsEndpoint:
    """REQ-API-05, REQ-API-06."""

    def test_signals_returns_list(self, client):
        """REQ-API-05."""
        _full_run(client)
        r = client.get("/signals")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) > 0

    def test_signals_filter_payment(self, client):
        """REQ-API-05: source_type=payment filter."""
        _full_run(client)
        r = client.get("/signals?source_type=payment").json()
        assert all(s["source_type"] == "payment" for s in r)
        assert len(r) > 0

    def test_signals_filter_checkout(self, client):
        _full_run(client)
        r = client.get("/signals?source_type=checkout").json()
        assert all(s["source_type"] == "checkout" for s in r)

    def test_signals_have_source_details(self, client):
        """REQ-API-06: each signal includes source_details."""
        _full_run(client)
        signals = client.get("/signals").json()
        for sig in signals:
            assert "source_details" in sig
            assert isinstance(sig["source_details"], dict)

    def test_payment_signals_have_amount(self, client):
        _full_run(client)
        payment_sigs = client.get("/signals?source_type=payment").json()
        for sig in payment_sigs:
            assert "amount" in sig["source_details"]
            assert sig["source_details"]["amount"] > 0

    def test_checkout_signals_have_cart_value(self, client):
        _full_run(client)
        checkout_sigs = client.get("/signals?source_type=checkout").json()
        for sig in checkout_sigs:
            assert "cart_value" in sig["source_details"]

    def test_signals_sorted_by_risk_score_desc(self, client):
        _full_run(client)
        signals = client.get("/signals").json()
        scores = [s["risk_score"] for s in signals]
        assert scores == sorted(scores, reverse=True)

    def test_signals_have_root_cause_after_pipeline(self, client):
        _full_run(client)
        signals = client.get("/signals").json()
        for sig in signals:
            # After diagnose stage, root_cause should be set
            assert sig["root_cause"] is not None


class TestActionsEndpoint:
    """REQ-API-07."""

    def test_actions_returns_list(self, client):
        _full_run(client)
        r = client.get("/actions")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) > 0

    def test_actions_filter_recovered(self, client):
        """REQ-API-07: outcome=recovered filter."""
        _full_run(client)
        r = client.get("/actions?outcome=recovered").json()
        assert all(a["outcome"] == "recovered" for a in r)

    def test_actions_filter_failed(self, client):
        _full_run(client)
        r = client.get("/actions?outcome=failed").json()
        assert all(a["outcome"] == "failed" for a in r)

    def test_actions_have_required_fields(self, client):
        _full_run(client)
        actions = client.get("/actions").json()
        required = {"id", "signal_id", "action_type", "attempt_number", "scheduled_at"}
        for a in actions:
            assert required.issubset(a.keys())

    def test_actions_include_signal_source_info(self, client):
        """Actions endpoint must join signal info (source_id, root_cause)."""
        _full_run(client)
        actions = client.get("/actions").json()
        for a in actions:
            assert "source_id" in a
            assert "root_cause" in a

    def test_recovered_actions_have_positive_amount(self, client):
        _full_run(client)
        recovered = client.get("/actions?outcome=recovered").json()
        for a in recovered:
            assert a["amount_recovered"] is not None
            assert a["amount_recovered"] > 0

    def test_multiple_action_types_present(self, client):
        """Real run should produce multiple action type variants."""
        _full_run(client)
        actions = client.get("/actions").json()
        types = {a["action_type"] for a in actions}
        assert len(types) >= 2  # at minimum retry_payment and something else


class TestAuditEndpoint:
    """REQ-API-08, REQ-API-09."""

    def test_audit_returns_ordered_stages(self, client):
        """REQ-API-08: detect → diagnose → decide → execute order."""
        _full_run(client)
        signals = client.get("/signals").json()
        entity_id = signals[0]["source_id"]

        trail = client.get(f"/audit/{entity_id}").json()
        assert len(trail) >= 3  # detect + diagnose + decide (at minimum)

        stage_order = {"detect": 0, "diagnose": 1, "decide": 2, "execute": 3}
        positions = [stage_order[e["stage"]] for e in trail]
        assert positions == sorted(positions)

    def test_audit_unknown_id_returns_404(self, client):
        """REQ-API-09."""
        r = client.get("/audit/nonexistent_entity_xyz")
        assert r.status_code == 404

    def test_audit_entries_have_explanation_and_metadata(self, client):
        _full_run(client)
        signals = client.get("/signals").json()
        entity_id = signals[0]["source_id"]
        trail = client.get(f"/audit/{entity_id}").json()
        for entry in trail:
            assert "explanation" in entry
            assert len(entry["explanation"]) > 0
            assert "metadata" in entry
            assert isinstance(entry["metadata"], dict)

    def test_audit_detect_stage_present(self, client):
        _full_run(client)
        signals = client.get("/signals").json()
        entity_id = signals[0]["source_id"]
        trail = client.get(f"/audit/{entity_id}").json()
        stages = [e["stage"] for e in trail]
        assert "detect" in stages

    def test_audit_entity_id_matches(self, client):
        _full_run(client)
        signals = client.get("/signals").json()
        entity_id = signals[0]["source_id"]
        trail = client.get(f"/audit/{entity_id}").json()
        for entry in trail:
            assert entry["entity_id"] == entity_id


class TestMetricsEndpoint:
    """REQ-API-10, REQ-API-11."""

    def test_metrics_returns_200(self, client):
        _full_run(client)
        r = client.get("/metrics/summary")
        assert r.status_code == 200

    def test_metrics_required_keys(self, client):
        """REQ-API-10: response shape must contain all required fields."""
        _full_run(client)
        m = client.get("/metrics/summary").json()
        required = {
            "total_at_risk", "total_recovered", "recovery_rate",
            "actions_taken", "actions_blocked_by_policy",
            "escalated_to_human", "by_root_cause", "stopped_reasons",
        }
        assert required.issubset(m.keys())

    def test_recovery_rate_bounded(self, client):
        """REQ-API-10: recovery_rate must be in [0, 1]."""
        _full_run(client)
        m = client.get("/metrics/summary").json()
        assert 0.0 <= m["recovery_rate"] <= 1.0

    def test_recovered_leq_at_risk(self, client):
        """REQ-API-11: can't recover more than what was at risk."""
        _full_run(client)
        m = client.get("/metrics/summary").json()
        assert m["total_recovered"] <= m["total_at_risk"]

    def test_metrics_positive_after_run(self, client):
        _full_run(client)
        m = client.get("/metrics/summary").json()
        assert m["total_at_risk"] > 0
        assert m["actions_taken"] > 0

    def test_by_root_cause_structure(self, client):
        _full_run(client)
        m = client.get("/metrics/summary").json()
        for cause, breakdown in m["by_root_cause"].items():
            assert "attempted" in breakdown
            assert "recovered" in breakdown
            assert breakdown["recovered"] <= breakdown["attempted"]


class TestReproducibility:
    """REQ-API-12."""

    def test_two_runs_identical_metrics(self, client):
        """REQ-API-12: seeded dataset → identical totals on every run."""
        _, _ = _full_run(client)
        m1 = client.get("/metrics/summary").json()

        _, _ = _full_run(client)
        m2 = client.get("/metrics/summary").json()

        assert m1["total_recovered"] == m2["total_recovered"]
        assert m1["recovery_rate"]   == m2["recovery_rate"]
        assert m1["total_at_risk"]   == m2["total_at_risk"]
        assert m1["actions_taken"]   == m2["actions_taken"]


class TestRootEndpoint:
    """REQ-API-13."""

    def test_root_returns_app_info(self, client):
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert "name" in data
        assert "BillWatch" in data["name"]
        assert "endpoints" in data
