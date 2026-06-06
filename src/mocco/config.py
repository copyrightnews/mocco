from dataclasses import dataclass
import os

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_CHAT_MODEL = "minimax/minimax-m2.5:free"

@dataclass
class Config:
    TELEGRAM_TOKEN: str
    OPENROUTER_API_KEY: str
    SERPER_API_KEY: str
    TOGETHER_API_KEY: str
    DATABASE_URL: str
    OWNER_ID: int
    BOT_ID: int
    CHAT_MODEL: str = DEFAULT_CHAT_MODEL
    LOG_LEVEL: str = "INFO"

def load_config() -> Config:
    """Load and validate environment variables required by the application.

    Raises:
        RuntimeError: if any required variable is missing.
    """
    required = [
        "TELEGRAM_TOKEN",
        "OPENROUTER_API_KEY",
        "SERPER_API_KEY",
        "TOGETHER_API_KEY",
        "DATABASE_URL",
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    owner = int(os.environ.get("OWNER_ID", "0"))
    bot = int(os.environ.get("BOT_ID", "0"))

    return Config(
        TELEGRAM_TOKEN=os.environ["TELEGRAM_TOKEN"],
        OPENROUTER_API_KEY=os.environ["OPENROUTER_API_KEY"],
        SERPER_API_KEY=os.environ["SERPER_API_KEY"],
        TOGETHER_API_KEY=os.environ["TOGETHER_API_KEY"],
        DATABASE_URL=os.environ["DATABASE_URL"],
        OWNER_ID=owner,
        BOT_ID=bot,
        CHAT_MODEL=os.environ.get("CHAT_MODEL", DEFAULT_CHAT_MODEL),
        LOG_LEVEL=os.environ.get("LOG_LEVEL", "INFO"),
    )
