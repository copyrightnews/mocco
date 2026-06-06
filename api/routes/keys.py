"""/v1/keys — per-user API key management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from mocco.crypto import encrypt_api_key
from mocco.db import (
    delete_user_api_key,
    get_user_api_keys,
    set_user_api_key,
)

from api.deps import current_user
from api.errors import ApiError
from api.models import ConnectKeyRequest

router = APIRouter()

# Providers the TMA can store keys for. Add more as you wire them up.
ALLOWED_PROVIDERS = {"openrouter", "serper"}


@router.get("/keys")
def list_keys(user_id: int = Depends(current_user)):
    keys = get_user_api_keys(user_id)
    return [
        {"provider": k["provider"], "created_at": k["created_at"].isoformat()}
        for k in keys
    ]


@router.post("/keys/{provider}")
def connect_key(
    req: ConnectKeyRequest,
    user_id: int = Depends(current_user),
    provider: str = Path(...),
):
    if provider not in ALLOWED_PROVIDERS:
        raise ApiError(400, "bad_provider", f"Unknown provider: {provider}")
    enc = encrypt_api_key(req.api_key)
    set_user_api_key(user_id, provider, enc)
    return {"provider": provider, "ok": True}


@router.delete("/keys/{provider}")
def disconnect_key(
    user_id: int = Depends(current_user),
    provider: str = Path(...),
):
    if provider not in ALLOWED_PROVIDERS:
        raise ApiError(400, "bad_provider", f"Unknown provider: {provider}")
    delete_user_api_key(user_id, provider)
    return {"ok": True}
