import os
import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("mocco")

_KEY: bytes | None = None


class EncryptionKeyMissing(RuntimeError):
    """ENCRYPTION_KEY env var is not set; /connect cannot work."""
    pass


def _get_key() -> bytes:
    global _KEY
    if _KEY is None:
        raw = os.environ.get("ENCRYPTION_KEY")
        if not raw:
            raise EncryptionKeyMissing(
                "ENCRYPTION_KEY env var is not set. The bot owner must generate one with: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        _KEY = raw.encode("utf-8")
    return _KEY


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

