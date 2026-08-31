"""
Synthetic data generator for BillWatch demo.

Produces:
  - 60 payments (mostly successful, minority failed with realistic failure-code distribution)
  - 40 checkout sessions (mix of completed/abandoned, varied cart values & stages)
  - Timestamps spread over a 7-day window
  - Seeded (random.seed(42)) for full reproducibility
"""

import random
import uuid
from datetime import datetime, timedelta


SEED = 42

MERCHANTS = ["merch_razorpay_001", "merch_shopify_002", "merch_woocom_003"]
CUSTOMERS = [f"cust_{i:03d}" for i in range(1, 31)]  # 30 customers
PAYMENT_METHODS = ["card", "upi", "netbanking", "wallet"]
PAYMENT_METHOD_WEIGHTS = [0.35, 0.40, 0.15, 0.10]

# Failure code distribution — weighted toward recoverable causes
FAILURE_CODES = ["bank_timeout", "otp_failed", "network_error", "insufficient_funds", "card_expired"]
FAILURE_WEIGHTS = [0.35, 0.25, 0.20, 0.15, 0.05]

CHECKOUT_STAGES = ["cart", "address", "payment_selection", "otp"]


def _random_datetime(rng: random.Random, base: datetime, window_days: int = 7) -> datetime:
    """Return a random datetime within `window_days` before `base`."""
    offset = timedelta(seconds=rng.randint(0, window_days * 86400))
    return base - offset


def generate_payments(rng: random.Random, base_time: datetime) -> list[dict]:
    """Generate 60 payments: ~70% success, ~30% failed."""
    payments = []
    for i in range(60): 
        is_failed = rng.random() < 0.30
        failure_code = None
        status = "success"
        attempt_number = 1

        if is_failed:
            status = "failed"
            failure_code = rng.choices(FAILURE_CODES, weights=FAILURE_WEIGHTS, k=1)[0]
            attempt_number = rng.randint(1, 3)

        amount = round(rng.uniform(100, 25000), 2)
        created_at = _random_datetime(rng, base_time)

        payments.append({
            "id": f"pay_{uuid.UUID(int=rng.getrandbits(128)).hex[:12]}",
            "merchant_id": rng.choice(MERCHANTS),
            "amount": amount,
            "currency": "INR",
            "status": status,
            "failure_code": failure_code,
            "customer_id": rng.choice(CUSTOMERS),
            "payment_method": rng.choices(PAYMENT_METHODS, weights=PAYMENT_METHOD_WEIGHTS, k=1)[0],
            "attempt_number": attempt_number,
            "created_at": created_at.isoformat(),
            "mandate_id": None,
        })
    return payments


def generate_checkout_sessions(rng: random.Random, base_time: datetime) -> list[dict]:
    """Generate 40 checkout sessions: ~60% completed, ~40% abandoned."""
    sessions = []
    for i in range(40):
        is_abandoned = rng.random() < 0.40
        status = "abandoned" if is_abandoned else "completed"

        # Abandoned sessions more likely to stop at later stages (more interesting for recovery)
        if is_abandoned:
            stage_weights = [0.10, 0.20, 0.40, 0.30]  # skew toward payment_selection & otp
        else:
            stage_weights = [0.05, 0.10, 0.20, 0.65]  # completed sessions mostly reach otp

        stage = rng.choices(CHECKOUT_STAGES, weights=stage_weights, k=1)[0]
        cart_value = round(rng.uniform(200, 15000), 2)
        created_at = _random_datetime(rng, base_time)

        # last_activity is 1-60 min after created_at for abandoned, same as created for completed
        if is_abandoned:
            activity_gap = timedelta(minutes=rng.randint(1, 60))
        else:
            activity_gap = timedelta(minutes=rng.randint(1, 10))

        sessions.append({
            "id": f"sess_{uuid.UUID(int=rng.getrandbits(128)).hex[:12]}",
            "merchant_id": rng.choice(MERCHANTS),
            "customer_id": rng.choice(CUSTOMERS),
            "cart_value": cart_value,
            "status": status,
            "stage_reached": stage,
            "created_at": created_at.isoformat(),
            "last_activity_at": (created_at + activity_gap).isoformat(),
        })
    return sessions


def generate_all() -> dict:
    """Generate the full synthetic dataset. Returns {"payments": [...], "checkout_sessions": [...]}."""
    rng = random.Random(SEED)
    base_time = datetime(2026, 8, 20, 12, 0, 0)  # fixed base for reproducibility

    payments = generate_payments(rng, base_time)
    sessions = generate_checkout_sessions(rng, base_time)

    return {
        "payments": payments,
        "checkout_sessions": sessions,
    }


if __name__ == "__main__":
    import json
    data = generate_all()
    print(f"Generated {len(data['payments'])} payments, {len(data['checkout_sessions'])} checkout sessions")
    # Print summary
    failed = [p for p in data["payments"] if p["status"] == "failed"]
    abandoned = [s for s in data["checkout_sessions"] if s["status"] == "abandoned"]
    print(f"  Failed payments: {len(failed)}")
    print(f"  Abandoned checkouts: {len(abandoned)}")

    # Failure code distribution
    from collections import Counter
    codes = Counter(p["failure_code"] for p in failed)
    print(f"  Failure codes: {dict(codes)}")

    # Write to file for inspection
    with open("synthetic_data.json", "w") as f:
        json.dump(data, f, indent=2, default=str)
    print("  Written to synthetic_data.json")
