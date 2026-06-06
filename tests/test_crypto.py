import sys
import pathlib
import pytest

# Ensure src is importable during tests
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from mocco.crypto import encrypt_api_key, decrypt_api_key, reset_key_cache, EncryptionKeyMissing


@pytest.fixture(autouse=True)
def _clear_key_cache():
    """Reset the cached key before/after every test in this module."""
    reset_key_cache()
    yield
    reset_key_cache()


def test_encryption_roundtrip_with_explicit_env(monkeypatch):
    """Env var is the highest priority; encrypt+decrypt round-trips."""
    from cryptography.fernet import Fernet
    k = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("ENCRYPTION_KEY", k)
    cipher = encrypt_api_key("sk-fake-key")
    assert cipher != "sk-fake-key"
    assert decrypt_api_key(cipher) == "sk-fake-key"


def test_auto_generates_when_env_and_db_missing(monkeypatch):
    """No env, no DB → auto-generate, persist, and reuse."""
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)

    persisted = {}
    def fake_get(key):
        return persisted.get(key)
    def fake_set(key, value):
        persisted[key] = value
        return True
    monkeypatch.setattr("mocco.db.get_bot_config", fake_get)
    monkeypatch.setattr("mocco.db.set_bot_config", fake_set)

    # First call: auto-generate
    cipher = encrypt_api_key("sk-test-1")
    assert persisted["encryption_key"], "key should have been persisted"

    # Second call: should reuse the persisted key (decrypt works)
    reset_key_cache()
    assert decrypt_api_key(cipher) == "sk-test-1"


def test_uses_db_stored_key_when_env_missing(monkeypatch):
    """No env, DB has key → use it (not a new auto-generated one)."""
    from cryptography.fernet import Fernet
    stored_key = Fernet.generate_key().decode("ascii")

    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    monkeypatch.setattr("mocco.db.get_bot_config", lambda k: stored_key if k == "encryption_key" else None)
    monkeypatch.setattr("mocco.db.set_bot_config", lambda *a, **kw: False)  # must NOT be called

    cipher = encrypt_api_key("sk-db-stored")
    # Decrypt with the DB key
    f = Fernet(stored_key.encode("utf-8"))
    assert f.decrypt(cipher.encode("ascii")).decode("utf-8") == "sk-db-stored"


def test_env_overrides_db(monkeypatch):
    """If env is set, DB value is ignored."""
    from cryptography.fernet import Fernet
    env_key = Fernet.generate_key().decode("ascii")
    db_key = Fernet.generate_key().decode("ascii")

    monkeypatch.setenv("ENCRYPTION_KEY", env_key)
    set_called = []
    monkeypatch.setattr("mocco.db.get_bot_config", lambda k: set_called.append(k) or db_key)

    cipher = encrypt_api_key("sk-env-wins")
    f_env = Fernet(env_key.encode("utf-8"))
    assert f_env.decrypt(cipher.encode("ascii")).decode("utf-8") == "sk-env-wins"
    # f_db should NOT be able to decrypt
    f_db = Fernet(db_key.encode("utf-8"))
    with pytest.raises(Exception):
        f_db.decrypt(cipher.encode("ascii"))


def test_raises_when_db_write_fails(monkeypatch):
    """No env, no DB row, and DB write also fails → clear error."""
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    monkeypatch.setattr("mocco.db.get_bot_config", lambda k: None)
    monkeypatch.setattr("mocco.db.set_bot_config", lambda k, v: False)

    with pytest.raises(EncryptionKeyMissing) as exc:
        encrypt_api_key("anything")
    assert "ENCRYPTION_KEY" in str(exc.value)
    assert "auto-generation" in str(exc.value) or "DB unreachable" in str(exc.value)
