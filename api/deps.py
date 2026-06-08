"""FastAPI dependencies: auth (initData verification) and current_user."""
from __future__ import annotations

import os
from typing import Annotated

from fastapi import Header, Request

from mocco.api_auth import verify_init_data
from mocco.config import load_config
from mocco.db import ensure_user, is_blacklisted

from api.errors import ApiError


_READ_MAX_AGE_S = 24 * 3600
_WRITE_MAX_AGE_S = 300


def _cfg():
    return load_config()


def _max_age_for(method: str) -> int:
    return _READ_MAX_AGE_S if method.upper() in {"GET", "HEAD", "OPTIONS"} else _WRITE_MAX_AGE_S


def current_user(
    request: Request,
    x_telegram_init_data: Annotated[str | None, Header(alias="X-Telegram-Init-Data")] = None,
) -> int:
    """Validate initData, upsert the user, return the Mocco internal user.id.

    Use as a FastAPI dependency: `user_id: int = Depends(current_user)`.
    """
    if not x_telegram_init_data:
        raise ApiError(401, "unauthorized", "Missing X-Telegram-Init-Data header.")
    cfg = _cfg()
    user = verify_init_data(
        x_telegram_init_data,
        cfg.TELEGRAM_TOKEN,
        max_age_s=_max_age_for(request.method),
    )
    tg_id = int(user["id"])
    if cfg.OWNER_ID != 0 and tg_id != cfg.OWNER_ID:
        raise ApiError(403, "forbidden", "Access denied. This bot is private.")
    if is_blacklisted(tg_id):
        raise ApiError(403, "forbidden", "This account is blocked.")
    name = user.get("first_name") or user.get("username") or ""
    username = user.get("username") or ""
    ensure_user(tg_id, username=username, first_name=name)
    return tg_id
