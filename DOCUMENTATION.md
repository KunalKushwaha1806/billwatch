# 📚 BillWatch — Technical Documentation & API Reference

> **Comprehensive Developer Guide, API Endpoint Specifications, and Operator Manual for BillWatch.**

---

## 1. Quick Start & Developer Setup

### 1.1 Prerequisites
- **Python**: Version 3.10 or higher
- **Node.js**: Version 18.0.0 or higher
- **Package Managers**: `pip` and `npm`

### 1.2 Installation & Startup

#### Backend Setup
```powershell
# Navigate to backend directory
cd backend

# Install dependencies
pip install -r requirements.txt
pip install pytest httpx pytest-asyncio

# Launch FastAPI development server with auto-reload
python -m uvicorn app.main:app --reload --port 8000
```
- API Base URL: `http://localhost:8000`
- Interactive Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON Spec: `http://localhost:8000/openapi.json`

#### Frontend Setup
```powershell
# Navigate to frontend directory
cd frontend

# Install npm dependencies
npm install

# Start Vite dev server
npm run dev
```
- Web Application UI: `http://localhost:5173`

---

## 2. API Endpoints Specification

### 2.1 `POST /batch/load`
Wipes the existing SQLite database and seeds 60 payments and 40 checkout sessions using `SEED=42`.

#### Request
```http
POST /batch/load HTTP/1.1
Host: localhost:8000
Content-Type: application/json
```

#### Response (`200 OK`)
```json
{
  "payments_loaded": 60,
  "checkout_sessions_loaded": 40,
  "message": "Loaded 60 payments and 40 checkout sessions."
}
```

---

### 2.2 `POST /pipeline/run`
Orchestrates the 4-stage autonomous recovery pipeline (`DETECT` ➔ `DIAGNOSE` ➔ `DECIDE` ➔ `EXECUTE`) across all records in the database.

#### Request
```http
POST /pipeline/run HTTP/1.1
Host: localhost:8000
Content-Type: application/json
```

#### Response (`200 OK`)
```json
{
  "signals_detected": 39,
  "actions_decided": 39,
  "actions_executed": 35,
  "message": "Pipeline complete: detected 39 signals, decided 39 actions, executed 35."
}
```

---

### 2.3 `GET /signals`
Returns all risk signals flagged by the Detect stage, sorted by `risk_score` descending.

#### Query Parameters
- `source_type` *(optional, string)*: Filter by `"payment"` or `"checkout"`.

#### Response (`200 OK`)
```json
[
  {
    "id": "sig_pay_29d4beef3eab",
    "source_type": "payment",
    "source_id": "pay_29d4beef3eab",
    "risk_score": 0.5875,
    "root_cause": "bank_timeout",
    "diagnosis_confidence": 1.0,
    "diagnosed_at": "2026-08-28T17:40:00.000Z",
    "source_details": {
      "amount": 16236.08,
      "currency": "INR",
      "status": "failed",
      "failure_code": "bank_timeout",
      "customer_id": "cust_013",
      "payment_method": "card",
      "attempt_number": 3,
      "created_at": "2026-08-18T10:15:00.000Z"
    }
  }
]
```

---

### 2.4 `GET /actions`
Returns all decided recovery actions joined with signal and source metadata.

#### Query Parameters
- `outcome` *(optional, string)*: Filter by `"recovered"`, `"failed"`, or `"still_pending"`.

#### Response (`200 OK`)
```json
[
  {
    "id": "act_sess_0a8381bec85a_1",
    "signal_id": "sig_sess_0a8381bec85a",
    "action_type": "send_nudge",
    "attempt_number": 1,
    "scheduled_at": "2026-08-28T17:40:00.000Z",
    "executed_at": "2026-08-28T17:40:01.000Z",
    "outcome": "recovered",
    "amount_recovered": 12784.34,
    "stopped_reason": null,
    "source_id": "sess_0a8381bec85a",
    "root_cause": "payment_friction",
    "source_type": "checkout"
  }
]
```

---

### 2.5 `GET /audit/{entity_id}`
Returns the complete chronological 4-stage audit trail for a specific transaction or session.

#### Path Parameters
- `entity_id` *(required, string)*: ID of the payment (`pay_xxx`) or checkout session (`sess_xxx`).

#### Response (`200 OK`)
```json
[
  {
    "id": "audit_001",
    "entity_id": "sess_0a8381bec85a",
    "stage": "detect",
    "explanation": "Flagged abandoned checkout: cart=₹12784.34, stage=otp, risk_score=0.6556",
    "timestamp": "2026-08-28T17:40:00.000Z",
    "metadata": {
      "cart_value": 12784.34,
      "stage_reached": "otp",
      "risk_score": 0.6556
    }
  },
  {
    "id": "audit_002",
    "entity_id": "sess_0a8381bec85a",
    "stage": "diagnose",
    "explanation": "Rule-based checkout diagnosis: stage=otp, cause=payment_friction, confidence=0.90.",
    "timestamp": "2026-08-28T17:40:01.000Z",
    "metadata": {
      "root_cause": "payment_friction",
      "confidence": 0.9,
      "method": "rule_heuristic"
    }
  },
  {
    "id": "audit_003",
    "entity_id": "sess_0a8381bec85a",
    "stage": "decide",
    "explanation": "ACTION APPROVED: send_nudge for root_cause='payment_friction', risk_score=0.6556.",
    "timestamp": "2026-08-28T17:40:02.000Z",
    "metadata": {
      "action_type": "send_nudge",
      "attempt_number": 1
    }
  },
  {
    "id": "audit_004",
    "entity_id": "sess_0a8381bec85a",
    "stage": "execute",
    "explanation": "[SIMULATED] ✅ send_nudge: outcome=RECOVERED, amount=₹12784.34, success_rate=55%.",
    "timestamp": "2026-08-28T17:40:03.000Z",
    "metadata": {
      "outcome": "recovered",
      "amount_recovered": 12784.34,
      "simulated": true
    }
  }
]
```

#### Error Response (`404 Not Found`)
```json
{
  "detail": "No audit trail found for entity 'pay_invalid_id'."
}
```

---

### 2.6 `GET /metrics/summary`
Calculates and returns financial aggregates, recovery percentages, and category distributions across all recovery actions.

#### Response (`200 OK`)
```json
{
  "total_at_risk": 361848.79,
  "total_recovered": 169370.51,
  "recovery_rate": 0.468,
  "actions_taken": 35,
  "actions_blocked_by_policy": 4,
  "escalated_to_human": 1,
  "by_root_cause": {
    "bank_timeout": { "attempted": 12, "recovered": 8 },
    "payment_friction": { "attempted": 8, "recovered": 5 },
    "network_error": { "attempted": 5, "recovered": 4 },
    "insufficient_funds": { "attempted": 4, "recovered": 2 },
    "price_hesitation": { "attempted": 6, "recovered": 2 }
  },
  "stopped_reasons": {
    "fraud_policy_block": 4,
    "low_confidence_diagnosis": 1
  }
}
```

---

## 3. Testing Reference

The system is validated by an automated test suite across both frontend and backend.

```
Total Tests: 224 Automated Tests (100% Pass Rate)
├── Backend (pytest): 146 tests
│   ├── test_detect.py        (20 tests)
│   ├── test_diagnose.py      (23 tests)
│   ├── test_decide.py        (25 tests)
│   ├── test_execute.py       (21 tests)
│   ├── test_api.py           (28 tests)
│   └── test_generate_data.py (29 tests)
│
├── Frontend (vitest): 77 tests
│   ├── api.test.js           (8 tests)
│   ├── Dashboard.test.jsx    (11 tests)
│   ├── SignalTable.test.jsx  (16 tests)
│   ├── ActionsView.test.jsx  (16 tests)
│   ├── AuditDrilldown.test.jsx (13 tests)
│   └── App.test.jsx          (13 tests)
│
└── E2E Verification: 1 full-system test (test_e2e.py)
```

### Running Backend Tests
```powershell
cd backend
python -m pytest tests/ -v --tb=short
```

### Running Frontend Tests
```powershell
cd frontend
npm test
```

### Running E2E Verification Script
```powershell
cd backend
python test_e2e.py
```

---

## 4. UI Components Guide

| Component | File | Responsibilities |
| :--- | :--- | :--- |
| **`App.jsx`** | [App.jsx](file:///c:/Users/Kunal%20Kushwaha/OneDrive/Desktop/Project/billwatch/frontend/src/App.jsx) | Header, live clock, top trigger action buttons, notification toasts, tab switching. |
| **`Dashboard.jsx`** | [Dashboard.jsx](file:///c:/Users/Kunal%20Kushwaha/OneDrive/Desktop/Project/billwatch/frontend/src/components/Dashboard.jsx) | Hero recovery metrics, count-up animation, recovery bar, stat grid, root cause horizontal bars, stopping rule donut SVG. |
| **`SignalTable.jsx`** | [SignalTable.jsx](file:///c:/Users/Kunal%20Kushwaha/OneDrive/Desktop/Project/billwatch/frontend/src/components/SignalTable.jsx) | Risk signal rows, search bar (ID/cause), filter tabs (All/Payments/Checkouts), sortable columns, risk level visual meters. |
| **`ActionsView.jsx`** | [ActionsView.jsx](file:///c:/Users/Kunal%20Kushwaha/OneDrive/Desktop/Project/billwatch/frontend/src/components/ActionsView.jsx) | Recovery actions table, summary chip bar, outcome filter tabs, search bar, CSV export engine. |
| **`AuditDrilldown.jsx`** | [AuditDrilldown.jsx](file:///c:/Users/Kunal%20Kushwaha/OneDrive/Desktop/Project/billwatch/frontend/src/components/AuditDrilldown.jsx) | 4-stage vertical timeline, decision explanations, stage metadata chips, back button. |

---

## 5. Configuration & Environment Variables

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `ANTHROPIC_API_KEY` | *(Optional)* | Anthropic Claude API Key for enhanced checkout diagnosis. If omitted, heuristic mode operates automatically with zero configuration. |
| `DATABASE_URL` | `sqlite:///./billwatch.db` | SQLAlchemy connection string for SQLite database. |
| `MAX_ATTEMPTS` | `3` | Maximum recovery action attempts allowed per risk signal before triggering policy block. |
| `COOLDOWN_MINUTES` | `15` | Minimum cooldown window between successive recovery actions for the same entity. |
