import os
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger("mocco")

_KEY: bytes | None = None


def _get_key() -> bytes:
    global _KEY
    if _KEY is None:
        raw = os.environ.get("ENCRYPTION_KEY")
        if not raw:
            raise RuntimeError(
                "ENCRYPTION_KEY env var is required. Generate one with: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        _KEY = raw.encode("utf-8")
    return _KEY


def encrypt_api_key(plaintext: str) -> str:
    f = Fernet(_get_key())
    return f.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_api_key(token: str) -> str:
    f = Fernet(_get_key())
    return f.decrypt(token.encode("ascii")).decode("utf-8")
