"""/v1/profile — read and update TMA profile fields."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from mocco.db import get_user_profile, update_user_profile

from api.deps import current_user
from api.models import ProfilePatch

router = APIRouter()


def _normalize(profile):
    if not profile:
        return profile
    if profile.get("interests") is None:
        profile["interests"] = []
    return profile


@router.get("/profile")
def get_profile(user_id: int = Depends(current_user)):
    return _normalize(get_user_profile(user_id))


@router.patch("/profile")
def patch_profile(patch: ProfilePatch, user_id: int = Depends(current_user)):
    fields = {k: v for k, v in patch.model_dump(exclude_none=True).items() if v is not None}
    update_user_profile(user_id, **fields)
    return _normalize(get_user_profile(user_id))
