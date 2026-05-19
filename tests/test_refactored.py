import sys
import pathlib
import pytest
import base64

# Ensure src is importable during tests
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import mocco.config as config
import mocco.db as db
import mocco.ai as ai
import mocco.utils as utils
import mocco.handlers as handlers

def test_imports():
    """Verify that all modular package files can be imported successfully."""
    assert config is not None
    assert db is not None
    assert ai is not None
    assert utils is not None
    assert handlers is not None

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
    monkeypatch.setenv("GROQ_API_KEY", "fake_token")
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
    monkeypatch.setenv("GROQ_API_KEY", "fake_token")
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

