"""POST /pipeline/run — orchestrate the 4-stage recovery pipeline."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RiskSignal
from app.schemas import PipelineRunResponse
from app.pipeline.detect import detect_payment_signals, detect_checkout_signals
from app.pipeline.diagnose import diagnose_payment, diagnose_checkout
from app.pipeline.decide import decide_action
from app.pipeline.execute import execute_action

router = APIRouter()


@router.post("/pipeline/run", response_model=PipelineRunResponse)
def run_pipeline(db: Session = Depends(get_db)):
    """
    Run the full DETECT → DIAGNOSE → DECIDE → EXECUTE pipeline
    over all payments and checkout sessions in the database.
    """
    # ── Stage 1: DETECT ─────────────────────────────────────────────
    payment_signals = detect_payment_signals(db)
    checkout_signals = detect_checkout_signals(db)
    all_signals = payment_signals + checkout_signals

    # ── Stage 2: DIAGNOSE ───────────────────────────────────────────
    for signal in all_signals:
        if signal.source_type == "payment":
            diagnose_payment(db, signal)
        else:
            diagnose_checkout(db, signal)

    # ── Stage 3: DECIDE ─────────────────────────────────────────────
    actions = []
    for signal in all_signals:
        action = decide_action(db, signal)
        if action:
            actions.append(action)

    # ── Stage 4: EXECUTE ────────────────────────────────────────────
    executed_count = 0
    for action in actions:
        signal = db.query(RiskSignal).filter(RiskSignal.id == action.signal_id).first()
        if signal and action.action_type not in ("no_action_policy_block",):
            execute_action(db, action, signal)
            executed_count += 1

    db.commit()

    return PipelineRunResponse(
        signals_detected=len(all_signals),
        actions_decided=len(actions),
        actions_executed=executed_count,
        message=(
            f"Pipeline complete: detected {len(all_signals)} signals, "
            f"decided {len(actions)} actions, executed {executed_count}."
        ),
    )
