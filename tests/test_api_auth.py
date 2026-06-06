import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from mocco.api_auth import verify_init_data
from api.errors import ApiError


def _sign(params: dict, bot_token: str) -> str:
    data_check = "\n".join(f"{k}={params[k]}" for k in sorted(params))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    return hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()


def test_valid_init_data_returns_user(bot_token, valid_init_data):
    user = verify_init_data(valid_init_data, bot_token, max_age_s=3600)
    assert user["id"] == 7232714487
    assert user["first_name"] == "Test"


def test_wrong_hash_raises(bot_token):
    params = {
        "user": '{"id":1}',
        "auth_date": "1700000000",
        "hash": "deadbeef" * 8,
    }
    raw = urlencode(params)
    with pytest.raises(ApiError) as e:
        verify_init_data(raw, bot_token, max_age_s=3600)
    assert e.value.status == 401
    assert e.value.code == "unauthorized"


def test_expired_raises(bot_token):
    user_json = '{"id":1}'
    params = {"user": user_json, "auth_date": "1700000000"}
    params["hash"] = _sign(params, bot_token)
    raw = urlencode(params)
    with pytest.raises(ApiError) as e:
        verify_init_data(raw, bot_token, max_age_s=10)
    assert e.value.status == 401


def test_missing_hash_raises(bot_token):
    raw = urlencode({"user": '{"id":1}', "auth_date": "1700000000"})
    with pytest.raises(ApiError):
        verify_init_data(raw, bot_token, max_age_s=3600)


def test_tampered_user_field_raises(bot_token, valid_init_data):
    # valid_init_data was signed for user id 7232714487; replace the user field with a different id
    raw = valid_init_data.replace("7232714487", "9999999999")
    with pytest.raises(ApiError):
        verify_init_data(raw, bot_token, max_age_s=3600)
