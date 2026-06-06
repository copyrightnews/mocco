import pytest


@pytest.fixture
def bot_token() -> str:
    return "123456:TEST-BOT-TOKEN-DO-NOT-USE"


@pytest.fixture
def valid_init_data(bot_token: str) -> str:
    """Build a valid initData string for a fake user.

    Pre-computed for a fixed `auth_date` so tests are deterministic.
    """
    import hashlib
    import hmac
    import time
    from urllib.parse import urlencode

    auth_date = 1700000000
    user_json = '{"id":7232714487,"first_name":"Test","username":"tester"}'
    params = {
        "user": user_json,
        "auth_date": str(auth_date),
        "query_id": "AAH_FIXTURE",
    }
    data_check = "\n".join(f"{k}={params[k]}" for k in sorted(params))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    params["hash"] = h
    return urlencode(params)
