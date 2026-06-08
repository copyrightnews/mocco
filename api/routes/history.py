"""/v1/history and /v1/reset — chat memory controls for the TMA."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from mocco.db import clear_history, get_history

from api.deps import current_user

router = APIRouter()

HISTORY_LIMIT = 14


@router.get("/history")
def history(user_id: int = Depends(current_user)):
    rows = get_history(user_id)
    rows = rows[-HISTORY_LIMIT:]
    return [
        {"role": r["role"], "content": r["content"], "ts": r.get("ts").isoformat() if r.get("ts") else None}
        for r in rows
    ]


@router.post("/reset")
def reset(user_id: int = Depends(current_user)):
    clear_history(user_id)
    return {"ok": True}
