import sys
import pathlib
import pytest

# Ensure src is importable during tests
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import mocco.config as config
import mocco.db as db
import mocco.ai as ai
import mocco.utils as utils
import mocco.handlers as handlers
import mocco.providers as providers

def test_imports():
    """Verify that all modular package files can be imported successfully."""
    assert config is not None
    assert db is not None
    assert ai is not None
    assert utils is not None
    assert handlers is not None
    assert providers is not None


def test_providers_registry_complete():
    """All 6 expected providers must be registered with required fields."""
    expected = {"openrouter", "openai", "anthropic", "google", "groq", "together"}
    assert set(providers.PROVIDERS.keys()) == expected
    required_fields = {
        "label", "base_url", "key_hint",
        "verify_path", "verify_method", "verify_headers",
        "direct_route_prefix", "model_strip_prefix", "signup_url", "blurb",
    }
    for name, p in providers.PROVIDERS.items():
        missing = required_fields - set(p.keys())
        assert not missing, f"Provider {name!r} missing fields: {missing}"


def test_looks_like_provider_key():
    assert providers.looks_like_provider_key("openai", "sk-" + "x" * 30) is True
    assert providers.looks_like_provider_key("openai", "nope") is False
    assert providers.looks_like_provider_key("anthropic", "sk-ant-" + "x" * 30) is True
    assert providers.looks_like_provider_key("anthropic", "sk-" + "x" * 30) is False
    assert providers.looks_like_provider_key("google", "AIza" + "x" * 30) is True
    assert providers.looks_like_provider_key("groq", "gsk_" + "x" * 30) is True
    # Together has no prefix — only length check
    assert providers.looks_like_provider_key("together", "x" * 30) is True
    assert providers.looks_like_provider_key("together", "short") is False
    # Unknown provider
    assert providers.looks_like_provider_key("bogus", "sk-" + "x" * 30) is False


def test_direct_route_for_model():
    assert providers.direct_route_for_model("openai/gpt-4o") == "openai"
    assert providers.direct_route_for_model("anthropic/claude-3.5-sonnet") is None  # no direct routing yet
    assert providers.direct_route_for_model("meta-llama/llama-3.3-70b-instruct") is None
    assert providers.direct_route_for_model("minimax/minimax-m2.5:free") is None


def test_verify_key_unknown_provider_returns_false():
    assert providers.verify_key("bogus", "sk-anything") == providers.VERIFY_AUTH


def test_verify_key_handles_network_error(monkeypatch):
    """A network failure must return VERIFY_TRANSIENT, not raise."""
    import requests
    def boom(*a, **kw):
        raise requests.exceptions.ConnectionError("no network")
    monkeypatch.setattr(requests, "request", boom)
    assert providers.verify_key("openai", "sk-" + "x" * 30) == providers.VERIFY_TRANSIENT


def test_verify_key_distinguishes_401_from_500(monkeypatch):
    """401 → AUTH; 500 → TRANSIENT; 200 → OK."""
    import requests

    class FakeResp:
        def __init__(self, code):
            self.status_code = code
            self.text = ""
    def fake_req(method, url, **kw):
        if "auth/key" in url:
            return FakeResp(401)
        return FakeResp(500)
    monkeypatch.setattr(requests, "request", fake_req)

    # OpenRouter uses /auth/key for verify; 401 → bad key
    assert providers.verify_key("openrouter", "sk-or-" + "x" * 30) == providers.VERIFY_AUTH
    # OpenAI uses /models; 500 → transient
    assert providers.verify_key("openai", "sk-" + "x" * 30) == providers.VERIFY_TRANSIENT


def test_verify_key_429_is_transient(monkeypatch):
    import requests
    class FakeResp:
        status_code = 429
        text = ""
    monkeypatch.setattr(requests, "request", lambda *a, **kw: FakeResp())
    assert providers.verify_key("openai", "sk-" + "x" * 30) == providers.VERIFY_TRANSIENT


def test_verify_key_200_is_ok(monkeypatch):
    import requests
    class FakeResp:
        status_code = 200
        text = ""
    monkeypatch.setattr(requests, "request", lambda *a, **kw: FakeResp())
    assert providers.verify_key("openai", "sk-" + "x" * 30) == providers.VERIFY_OK


def test_set_user_api_key_returns_bool(monkeypatch):
    """db.set_user_api_key must return False on error, True on success."""
    from cryptography.fernet import Fernet
    key = b"wPK0bI5wQz0Op9-cE_pP6yV3aQ5cT7uY9zE1aR4eB6w="
    f = Fernet(key)
    enc = f.encrypt(b"sk-fake").decode("ascii")
    monkeypatch.setattr(db, "db_conn", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    assert db.set_user_api_key(1, "openai", enc) is False


def test_build_models_keyboard_skips_oversize_ids():
    """Telegram caps callback_data at 64 bytes — must not include >64B buttons."""
    # A model with a 70-byte id would produce a >64B callback_data and must be skipped.
    long_id = "a" * 70
    fake_models = [
        {"id": "openai/gpt-4o",      "name": "GPT-4o",  "context_length": 8192,  "is_free": False, "pricing": {}},
        {"id": long_id,             "name": "LongID",  "context_length": 4096,  "is_free": True,  "pricing": {}},
    ]
    kb = handlers._build_models_keyboard(fake_models, page=0, current="openai/gpt-4o", has_user_key=False)
    button_datas = [b.callback_data for row in kb.inline_keyboard for b in row]
    # The short one is present
    assert any("openai/gpt-4o" in d for d in button_datas)
    # The overlong one was skipped
    assert not any(long_id in d for d in button_datas)


def test_blacklist_blocks_self(monkeypatch):
    """Owner /blacklist <self_id> must be refused."""
    monkeypatch.setenv("TELEGRAM_TOKEN", "x")
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.setenv("SERPER_API_KEY", "x")
    monkeypatch.setenv("TOGETHER_API_KEY", "x")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@x:5432/x")
    monkeypatch.setenv("OWNER_ID", "777")
    monkeypatch.setenv("BOT_ID", "0")

    set_called = []
    monkeypatch.setattr(db, "set_blacklist", lambda uid, v: set_called.append((uid, v)) or True)

    sent = []
    async def fake_safe_reply(msg, text, **kw):
        sent.append(text)
    monkeypatch.setattr(handlers, "safe_reply", fake_safe_reply)

    # Stub Update with args=["777"] and from_user.id=777
    class U:
        class _M:
            from_user = type("X", (), {"id": 777})()
            chat_id = 1
        effective_user = type("X", (), {"id": 777})()
        message = _M()
    class Ctx:
        args = ["777"]

    import asyncio
    asyncio.run(handlers.cmd_blacklist(U(), Ctx()))

    assert set_called == [], f"set_blacklist should NOT have been called; got {set_called}"
    assert any("can't blacklist yourself" in t for t in sent), f"Got: {sent}"


def test_looks_like_provider_key_includes_sk_prefix():
    """OpenAI old-format keys (sk- + 48 chars) must pass the cheap format check."""
    # OpenAI new format: sk-proj-...
    assert providers.looks_like_provider_key("openai", "sk-proj-" + "x" * 40) is True
    # OpenAI old format: sk- + 48 chars
    assert providers.looks_like_provider_key("openai", "sk-" + "x" * 48) is True
    # OpenAI sk- + too short → fail
    assert providers.looks_like_provider_key("openai", "sk-short") is False


def test_format_model_label_free():
    """Free models should be labeled 'Name: free'."""
    m = {"id": "openai/gpt-4o", "name": "GPT-4o", "is_free": True}
    assert handlers._format_model_label(m) == "GPT-4o: free"


def test_format_model_label_paid():
    """Paid models should be labeled 'Name: paid'."""
    m = {"id": "openai/gpt-4o", "name": "GPT-4o", "is_free": False}
    assert handlers._format_model_label(m) == "GPT-4o: paid"


def test_format_model_label_strips_free_suffix():
    """OpenRouter's 'Name (free)' suffix should be stripped before suffixing."""
    m = {"id": "minimax/minimax-m2.5:free", "name": "Minimax M2.5 (free)", "is_free": True}
    assert handlers._format_model_label(m) == "Minimax M2.5: free"


def test_no_emojis_in_user_facing_strings():
    """Sanity: no emojis in handlers module's top-level user-facing strings."""
    import re
    emoji_re = re.compile(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]")
    for name in ("WELCOME_TEXT", "HELP_TEXT"):
        text = getattr(handlers, name)
        assert not emoji_re.search(text), f"{name} still contains an emoji: {emoji_re.findall(text)}"


def test_utils_split_message():
    """Verify utility functions like split_message function correctly."""
    short = "Hello world"
    assert utils.split_message(short) == [short]

    long_text = "a" * 4005
    chunks = utils.split_message(long_text)
    assert len(chunks) == 2
    assert len(chunks[0]) <= 4000
    assert len(chunks[1]) <= 4000

def test_ai_search_keywords():
    """Verify search keyword detection functions properly."""
    assert ai.needs_search("What is the latest AI news today?") is True
    assert ai.needs_search("Hello, how are you?") is False

def test_ai_system_prompt_language():
    """Verify system prompt contains language adaptability guidelines."""
    prompt = ai.get_system_prompt()
    assert "Language Adaptability" in prompt
    assert "Bengali (Bangla)" in prompt
    assert "বাংলা" in prompt


def test_get_client_for_chat_routes_openai_direct(monkeypatch):
    """When user has an OpenAI direct key and picks openai/... model, route direct."""
    monkeypatch.setenv("TELEGRAM_TOKEN", "x")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-bot-key")
    monkeypatch.setenv("SERPER_API_KEY", "x")
    monkeypatch.setenv("TOGETHER_API_KEY", "x")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@x:5432/x")
    monkeypatch.setenv("ENCRYPTION_KEY", "wPK0bI5wQz0Op9-cE_pP6yV3aQ5cT7uY9zE1aR4eB6w=")

    # Simulate user 42 has an openai key stored
    def fake_get_user_api_key(uid, provider):
        if uid == 42 and provider == "openai":
            # Fernet-encrypted value of "sk-fake-openai-key"
            from cryptography.fernet import Fernet
            f = Fernet(b"wPK0bI5wQz0Op9-cE_pP6yV3aQ5cT7uY9zE1aR4eB6w=")
            return f.encrypt(b"sk-fake-openai-key").decode("ascii")
        return None
    monkeypatch.setattr(ai, "get_user_api_key", fake_get_user_api_key)

    client, resolved = ai.get_client_for_chat(42, "openai/gpt-4o")
    assert resolved == "gpt-4o"
    assert "api.openai.com" in str(client.base_url)


def test_get_client_for_chat_falls_back_to_openrouter(monkeypatch):
    """When user has no matching direct key, fall back to OpenRouter (bot key if no user OR key)."""
    monkeypatch.setenv("TELEGRAM_TOKEN", "x")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-bot-key")
    monkeypatch.setenv("SERPER_API_KEY", "x")
    monkeypatch.setenv("TOGETHER_API_KEY", "x")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@x:5432/x")
    monkeypatch.setenv("ENCRYPTION_KEY", "wPK0bI5wQz0Op9-cE_pP6yV3aQ5cT7uY9zE1aR4eB6w=")
    monkeypatch.setattr(ai, "get_user_api_key", lambda uid, p: None)

    client, resolved = ai.get_client_for_chat(99, "anthropic/claude-3.5-sonnet")
    assert resolved == "anthropic/claude-3.5-sonnet"  # un-stripped, sent through OpenRouter
    assert "openrouter.ai" in str(client.base_url)


def test_can_use_paid_model_smart_gating(monkeypatch):
    """Paid-model gate accepts user with OpenRouter key OR matching direct key."""
    monkeypatch.setenv("TELEGRAM_TOKEN", "x")
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.setenv("SERPER_API_KEY", "x")
    monkeypatch.setenv("TOGETHER_API_KEY", "x")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@x:5432/x")
    monkeypatch.setenv("ENCRYPTION_KEY", "wPK0bI5wQz0Op9-cE_pP6yV3aQ5cT7uY9zE1aR4eB6w=")

    from cryptography.fernet import Fernet
    f = Fernet(b"wPK0bI5wQz0Op9-cE_pP6yV3aQ5cT7uY9zE1aR4eB6w=")
    enc = f.encrypt(b"sk-fake").decode("ascii")

    # Case 1: user has only Groq key, picks openai paid model → blocked
    monkeypatch.setattr(ai, "get_user_api_key",
                        lambda uid, p: enc if (uid == 1 and p == "groq") else None)
    assert ai.can_use_paid_model(1, "openai/gpt-4o") is False

    # Case 2: user has OpenAI direct key, picks openai paid model → allowed
    monkeypatch.setattr(ai, "get_user_api_key",
                        lambda uid, p: enc if (uid == 2 and p == "openai") else None)
    assert ai.can_use_paid_model(2, "openai/gpt-4o") is True

    # Case 3: user has OpenRouter key, picks anything paid → allowed
    monkeypatch.setattr(ai, "get_user_api_key",
                        lambda uid, p: enc if (uid == 3 and p == "openrouter") else None)
    assert ai.can_use_paid_model(3, "anthropic/claude-3.5-sonnet") is True
    assert ai.can_use_paid_model(3, "openai/gpt-4o") is True

    # Case 4: no keys at all → blocked
    monkeypatch.setattr(ai, "get_user_api_key", lambda uid, p: None)
    assert ai.can_use_paid_model(4, "openai/gpt-4o") is False
    assert ai.can_use_paid_model(None, "openai/gpt-4o") is False


def test_image_base64_decoding_logic(monkeypatch):
    """Verify image generation logic handles base64 payload correctly."""
    # Mock requests.post to return a fake base64 image
    class FakeResponse:
        status_code = 200
        text = "Fake payload text"
        def raise_for_status(self):
            pass
        def json(self):
            # A valid 1x1 transparent PNG in base64
            fake_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
            return {
                "data": [
                    {
                        "b64_json": fake_b64
                    }
                ]
            }

    monkeypatch.setattr("requests.post", lambda *args, **kwargs: FakeResponse())
    
    # Mock config
    monkeypatch.setenv("TELEGRAM_TOKEN", "fake_token")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_token")
    monkeypatch.setenv("SERPER_API_KEY", "fake_token")
    monkeypatch.setenv("TOGETHER_API_KEY", "fake_token")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")

    res = ai.generate_image("a beautiful test scene")
    assert res is not None
    img_bytes, is_url = res
    assert is_url is False
    assert isinstance(img_bytes, bytes)
    assert img_bytes.startswith(b"\x89PNG\r\n\x1a\n") # Correct PNG header!


@pytest.mark.anyio
async def test_process_message_document(monkeypatch):
    """Verify that process_message successfully processes text document uploads."""
    # Mock config
    monkeypatch.setenv("TELEGRAM_TOKEN", "fake_token")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_token")
    monkeypatch.setenv("SERPER_API_KEY", "fake_token")
    monkeypatch.setenv("TOGETHER_API_KEY", "fake_token")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")

    # Mock database helper functions to avoid database connection
    saved_msgs = []
    def mock_ensure_user(user_id, username, first_name):
        pass
    def mock_is_blacklisted(user_id):
        return False
    def mock_save_message(user_id, role, content):
        saved_msgs.append((user_id, role, content))
    
    monkeypatch.setattr(handlers, "ensure_user", mock_ensure_user)
    monkeypatch.setattr(handlers, "db_is_blacklisted", mock_is_blacklisted)
    monkeypatch.setattr(handlers, "save_message", mock_save_message)

    # Mock get_ai_reply
    def mock_get_ai_reply(user_id, prompt):
        assert "detect errors and bugs in this codes" in prompt
        assert "def buggy_function():" in prompt
        return "Here is the bug analysis."
    
    monkeypatch.setattr(handlers, "get_ai_reply", mock_get_ai_reply)

    # Mock safe_reply to capture the reply
    replies = []
    async def mock_safe_reply(msg, text, **kwargs):
        replies.append(text)
    
    monkeypatch.setattr(handlers, "safe_reply", mock_safe_reply)

    # Set up mock Update, Context, Bot, Message, and Document objects
    class MockFile:
        async def download_to_drive(self, path):
            with open(path, "wb") as f:
                f.write(b"def buggy_function():\n    return x + 1\n")

    class MockBot:
        id = 9999
        async def get_me(self):
            class BotUser:
                username = "mocco_bot"
            return BotUser()
        async def get_file(self, file_id):
            assert file_id == "mock_file_id"
            return MockFile()
        async def send_chat_action(self, *args, **kwargs):
            pass

    class MockChat:
        type = "private"

    class MockUser:
        id = 12345
        username = "test_user"
        first_name = "Test"
        is_bot = False

    class MockDocument:
        file_id = "mock_file_id"
        file_name = "test_code.py"
        file_size = 120

    class MockMessage:
        chat = MockChat()
        chat_id = 12345
        from_user = MockUser()
        text = None
        caption = "detect errors and bugs in this codes"
        document = MockDocument()
        reply_to_message = None

    class MockContext:
        bot = MockBot()

    # Create instances
    msg = MockMessage()
    context = MockContext()

    # Call process_message
    await handlers.process_message(None, context, msg)

    # Asserts
    assert len(replies) == 1
    assert replies[0] == "Here is the bug analysis."
    assert len(saved_msgs) == 2
    assert saved_msgs[0][1] == "user"
    assert "test_code.py" in saved_msgs[0][2]
    assert saved_msgs[1][1] == "assistant"
    assert saved_msgs[1][2] == "Here is the bug analysis."

