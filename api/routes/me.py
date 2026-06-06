"""/v1/me — current user info for the TMA."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from mocco.db import get_chat_model, user_connected_providers

from api.deps import current_user

router = APIRouter()


@router.get("/me")
def me(user_id: int = Depends(current_user)):
    return {
        "id": user_id,
        "model": get_chat_model(user_id) or "",
        "language": "",  # filled by /v1/profile in a later task
        "persona": "",
        "connected_providers": user_connected_providers(user_id),
    }
