"""/v1/me — current user info for the TMA."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from mocco.db import get_chat_model, user_connected_providers, get_daily_token_usage

from api.deps import current_user

router = APIRouter()


def _serialize_quota(quota: dict) -> dict:
    out = dict(quota)
    if out.get("resets_at") is not None and hasattr(out["resets_at"], "isoformat"):
        out["resets_at"] = out["resets_at"].isoformat()
    return out


@router.get("/me")
def me(user_id: int = Depends(current_user)):
    return {
        "id": user_id,
        "model": get_chat_model(user_id) or "",
        "language": "",  # filled by /v1/profile in a later task
        "persona": "",
        "connected_providers": user_connected_providers(user_id),
        "quota": _serialize_quota(get_daily_token_usage(user_id)),
    }
