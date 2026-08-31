"""GET /audit/{entity_id} — full explanation chain for a payment or checkout session."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditEntry

router = APIRouter()

# Stage ordering for timeline display
STAGE_ORDER = {"detect": 0, "diagnose": 1, "decide": 2, "execute": 3}


@router.get("/audit/{entity_id}")
def get_audit_trail(entity_id: str, db: Session = Depends(get_db)):
    """
    Return the full audit trail for a given entity (payment or checkout session).
    Entries are ordered by stage (detect → diagnose → decide → execute), then by timestamp.
    """
    entries = (
        db.query(AuditEntry)
        .filter(AuditEntry.entity_id == entity_id)
        .all()
    )

    if not entries:
        raise HTTPException(status_code=404, detail=f"No audit entries found for entity '{entity_id}'.")

    # Sort by stage order, then timestamp
    entries.sort(key=lambda e: (STAGE_ORDER.get(e.stage, 99), e.timestamp))

    return [
        {
            "id": entry.id,
            "entity_id": entry.entity_id,
            "stage": entry.stage,
            "explanation": entry.explanation,
            "timestamp": entry.timestamp.isoformat(),
            "metadata": entry.meta,
        }
        for entry in entries
    ]
