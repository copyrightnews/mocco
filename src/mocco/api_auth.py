"""Telegram WebApp `initData` verification.

Implements the algorithm documented at
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qsl


class _Unauthorized(Exception):
    pass


def verify_init_data(raw: str, bot_token: str, max_age_s: int = 300) -> dict[str, Any]:
    """Verify `raw` (the initData query string) and return the parsed `user` object.

    Raises `api.errors.ApiError(401, "unauthorized", ...)` on any failure.
    """
    # Local import to avoid a circular dependency at module import time.
    from api.errors import ApiError

    try:
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=False)
    except Exception:
        raise ApiError(401, "unauthorized", "Malformed initData.")
    parsed = dict(pairs)
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise ApiError(401, "unauthorized", "Missing hash.")
    if "auth_date" not in parsed or "user" not in parsed:
        raise ApiError(401, "unauthorized", "Missing required fields.")

    try:
        auth_date = int(parsed["auth_date"])
    except ValueError:
        raise ApiError(401, "unauthorized", "Invalid auth_date.")
    if time.time() - auth_date > max_age_s:
        raise ApiError(401, "unauthorized", "initData expired.")

    data_check_string = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, received_hash):
        raise ApiError(401, "unauthorized", "Invalid signature.")

    try:
        user = json.loads(parsed["user"])
    except json.JSONDecodeError:
        raise ApiError(401, "unauthorized", "Invalid user field.")
    return user
