"""
End-to-End Verification Test for BillWatch AI Revenue Recovery Agent
"""

import json
import sys
import urllib.request
from fastapi.testclient import TestClient
from app.main import app

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

API_BASE = "http://localhost:8000"

_client = TestClient(app)

def _is_server_up():
    try:
        urllib.request.urlopen(f"{API_BASE}/", timeout=0.5)
        return True
    except Exception:
        return False

_use_live = _is_server_up()

def get(path: str):
    if _use_live:
        req = urllib.request.urlopen(f"{API_BASE}{path}")
        return json.loads(req.read().decode())
    res = _client.get(path)
    return res.json()

def post(path: str):
    if _use_live:
        req = urllib.request.Request(
            f"{API_BASE}{path}",
            method="POST",
            headers={"Content-Type": "application/json"}
        )
        res = urllib.request.urlopen(req)
        return json.loads(res.read().decode())
    res = _client.post(path)
    return res.json()


def run_test():
    print("==================================================")
    print(" BILLWATCH AI REVENUE RECOVERY AGENT — E2E TEST")
    print("==================================================")
    
    # 1. Reset and Load Batch
    load_res = post("/batch/load")
    print(f"[*] /batch/load: {load_res['message']}")
    assert load_res["payments_loaded"] == 60
    assert load_res["checkout_sessions_loaded"] == 40

    # 2. Run Pipeline
    pipeline_res = post("/pipeline/run")
    print(f"[*] /pipeline/run: {pipeline_res['message']}")
    assert pipeline_res["signals_detected"] > 0
    assert pipeline_res["actions_decided"] > 0

    # 3. Verify Signals
    signals = get("/signals")
    print(f"[*] /signals: {len(signals)} signals retrieved")
    payment_signals = [s for s in signals if s["source_type"] == "payment"]
    checkout_signals = [s for s in signals if s["source_type"] == "checkout"]
    print(f"    - Payment signals: {len(payment_signals)}")
    print(f"    - Checkout signals: {len(checkout_signals)}")

    # 4. Verify Actions
    actions = get("/actions")
    print(f"[*] /actions: {len(actions)} recovery actions retrieved")
    action_types = {a["action_type"] for a in actions}
    print(f"    - Action types found: {action_types}")

    # 5. Verify Metrics Summary
    metrics = get("/metrics/summary")
    print(f"[*] /metrics/summary:")
    print(f"    - Total At Risk: ₹{metrics['total_at_risk']:,.2f}")
    print(f"    - Total Recovered: ₹{metrics['total_recovered']:,.2f}")
    print(f"    - Recovery Rate: {metrics['recovery_rate'] * 100:.1f}%")
    print(f"    - Actions Taken: {metrics['actions_taken']}")
    print(f"    - Blocked by Policy: {metrics['actions_blocked_by_policy']}")
    print(f"    - Escalated to Human: {metrics['escalated_to_human']}")
    print(f"    - Stopped Reasons: {metrics['stopped_reasons']}")

    # 6. Audit Trail Inspections
    print("\n==================================================")
    print(" SAMPLE AUDIT TRAILS ACROSS 3 KEY SCENARIOS")
    print("==================================================")

    # A. Recovered Payment / Session
    rec_sig = next(
        s for s in signals
        if any(a["signal_id"] == s["id"] and a["outcome"] == "recovered" for a in actions)
    )
    print(f"\n[SCENARIO A: RECOVERED] Source: {rec_sig['source_id']} ({rec_sig['source_type']})")
    for entry in get(f"/audit/{rec_sig['source_id']}"):
        print(f"  [{entry['stage'].upper():8s}] {entry['explanation']}")

    # B. Blocked by Fraud Policy
    blocked_sig = next(
        (s for s in signals
         if any(a["signal_id"] == s["id"] and a["stopped_reason"] == "fraud_policy_block" for a in actions)),
        None
    )
    if blocked_sig:
        print(f"\n[SCENARIO B: FRAUD POLICY BLOCK] Source: {blocked_sig['source_id']} ({blocked_sig['source_type']})")
        for entry in get(f"/audit/{blocked_sig['source_id']}"):
            print(f"  [{entry['stage'].upper():8s}] {entry['explanation']}")

    # C. Escalated to Human (Low Confidence Diagnosis)
    esc_sig = next(
        (s for s in signals
         if any(a["signal_id"] == s["id"] and a["stopped_reason"] == "low_confidence_diagnosis" for a in actions)),
        None
    )
    if esc_sig:
        print(f"\n[SCENARIO C: HUMAN ESCALATION] Source: {esc_sig['source_id']} ({esc_sig['source_type']})")
        for entry in get(f"/audit/{esc_sig['source_id']}"):
            print(f"  [{entry['stage'].upper():8s}] {entry['explanation']}")

    # 7. Reproducibility test
    print("\n==================================================")
    print(" REPRODUCIBILITY TEST")
    print("==================================================")
    post("/batch/load")
    post("/pipeline/run")
    metrics2 = get("/metrics/summary")
    assert metrics["total_recovered"] == metrics2["total_recovered"], "Non-deterministic recovery total!"
    assert metrics["recovery_rate"] == metrics2["recovery_rate"], "Non-deterministic recovery rate!"
    print("[✓] Re-run test passed: Identical numbers reproduced perfectly on seeded dataset.")
    print("==================================================")
    print(" ALL TESTS PASSED SUCCESSFULLY! ")
    print("==================================================")

if __name__ == "__main__":
    run_test()
