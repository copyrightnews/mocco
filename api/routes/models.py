"""/v1/models list and /v1/model setter."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from mocco.ai import fetch_all_models
from mocco.db import get_chat_model, set_chat_model

from api.deps import current_user
from api.errors import ApiError
from api.models import SetModelRequest

router = APIRouter()


@router.get("/models")
def list_models(user_id: int = Depends(current_user)):
    models = fetch_all_models(force=False, user_id=user_id)
    # Trim to fields the TMA needs.
    return [
        {
            "id": m["id"],
            "name": m.get("name", m["id"]),
            "is_free": m.get("is_free", False),
            "context_length": m.get("context_length", 0),
            "via": m.get("via"),
        }
        for m in models
    ]


@router.get("/model")
def get_model(user_id: int = Depends(current_user)):
    return {"model": get_chat_model(user_id) or ""}


@router.post("/model")
def set_model(req: SetModelRequest, user_id: int = Depends(current_user)):
    # Validate the model id exists in the catalog (best-effort, allow free text to be future-proof).
    catalog = {m["id"] for m in fetch_all_models(force=False, user_id=user_id)}
    if req.model_id and catalog and req.model_id not in catalog:
        # Allow but warn — user may have a model not in the cache yet.
        pass
    set_chat_model(user_id, req.model_id)
    return {"model": req.model_id}
