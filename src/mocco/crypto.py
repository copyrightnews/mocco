import os
import threading
import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("mocco")

_KEY: bytes | None = None
_KEY_LOCK = threading.Lock()


class EncryptionKeyMissing(RuntimeError):
    """ENCRYPTION_KEY is unavailable and could not be auto-generated."""
    pass


def _get_key() -> bytes:
    """Resolve the Fernet key with a 3-tier fallback.

    Priority:
      1. ``ENCRYPTION_KEY`` env var (lets the bot owner pin the key across
         DB resets / multi-replica deployments).
      2. ``bot_config.encryption_key`` in the database (auto-generated on
         first /connect, persisted, reused on every restart).
      3. Auto-generate a fresh Fernet key, persist it to the DB, and use it.
         Logged loudly so the owner can copy it into the env var later.

    Raises:
        EncryptionKeyMissing: if no env var, no DB row, AND the DB write
            for a freshly-generated key fails.
    """
    global _KEY
    if _KEY is not None:
        return _KEY
    with _KEY_LOCK:
        if _KEY is not None:
            return _KEY

        raw = os.environ.get("ENCRYPTION_KEY", "").strip()
        if raw:
            try:
                Fernet(raw.encode("utf-8"))
            except Exception as exc:
                raise ValueError(
                    "ENCRYPTION_KEY env var is not a valid Fernet key. "
                    "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
                ) from exc
            _KEY = raw.encode("utf-8")
            return _KEY

        from .db import get_bot_config, set_bot_config

        stored = get_bot_config("encryption_key")
        if stored:
            _KEY = stored.encode("utf-8")
            logger.info("Loaded ENCRYPTION_KEY from database (bot_config table)")
            return _KEY

        new_key = Fernet.generate_key().decode("ascii")
        if set_bot_config("encryption_key", new_key):
            _KEY = new_key.encode("utf-8")
            logger.warning("=" * 70)
            logger.warning(
                "ENCRYPTION_KEY was not in env and not in DB — auto-generated one and"
            )
            logger.warning(
                "stored it in bot_config. To make it stable across DB resets, set:"
            )
            logger.warning(f"  ENCRYPTION_KEY={new_key}")
            logger.warning("=" * 70)
            return _KEY

        raise EncryptionKeyMissing(
            "ENCRYPTION_KEY is not in env, the DB has no stored key, AND the auto-"
            "generation write failed (DB unreachable?). Set ENCRYPTION_KEY env var"
            " manually. Generate with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )


def encrypt_api_key(plaintext: str) -> str:
    f = Fernet(_get_key())
    return f.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_api_key(token: str) -> str:
    f = Fernet(_get_key())
    try:
        return f.decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as e:
        raise RuntimeError(
            "Stored key could not be decrypted — the bot's ENCRYPTION_KEY may have "
            "changed since this key was saved. The user will need to /connect again."
        ) from e


def reset_key_cache() -> None:
    """Test helper: clear the cached key so the next call re-resolves."""
    global _KEY
    _KEY = None
