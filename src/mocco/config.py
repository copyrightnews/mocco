from dataclasses import dataclass
import os

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_CHAT_MODEL = "minimax/minimax-m2.5:free"


@dataclass
class Config:
    # Hard requirements — bot cannot start without these.
    TELEGRAM_TOKEN: str
    DATABASE_URL: str

    # Soft requirements — bot starts without these but features that need them
    # gracefully degrade with a clear user-facing error.
    OPENROUTER_API_KEY: str = ""   # Fallback key when no user has connected one
    SERPER_API_KEY: str = ""        # Bot-side web search
    TOGETHER_API_KEY: str = ""      # Bot-side image generation
    ENCRYPTION_KEY: str = ""        # Required only when a user runs /connect

    OWNER_ID: int = 0
    BOT_ID: int = 0
    CHAT_MODEL: str = DEFAULT_CHAT_MODEL
    LOG_LEVEL: str = "INFO"


# Vars that must be set or the bot cannot start at all.
REQUIRED_VARS = ("TELEGRAM_TOKEN", "DATABASE_URL")

# Vars that are optional at startup but enable specific features.
OPTIONAL_VARS = (
    "OPENROUTER_API_KEY",
    "SERPER_API_KEY",
    "TOGETHER_API_KEY",
    "ENCRYPTION_KEY",
    "OWNER_ID",
    "BOT_ID",
    "CHAT_MODEL",
    "LOG_LEVEL",
)


def load_config() -> Config:
    """Load and validate environment variables.

    Only TELEGRAM_TOKEN and DATABASE_URL are strictly required. Other vars
    enable specific features; if any is missing, the bot still starts but logs
    a warning and the affected feature will be disabled with a friendly
    user-facing message.

    Raises:
        RuntimeError: if TELEGRAM_TOKEN or DATABASE_URL is missing.
    """
    missing_required = [k for k in REQUIRED_VARS if not os.environ.get(k)]
    if missing_required:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing_required)}"
        )

    owner_raw = os.environ.get("OWNER_ID", "0")
    bot_raw = os.environ.get("BOT_ID", "0")
    try:
        owner = int(owner_raw) if owner_raw else 0
    except ValueError:
        owner = 0
    try:
        bot = int(bot_raw) if bot_raw else 0
    except ValueError:
        bot = 0

    return Config(
        TELEGRAM_TOKEN=os.environ["TELEGRAM_TOKEN"],
        DATABASE_URL=os.environ["DATABASE_URL"],
        OPENROUTER_API_KEY=os.environ.get("OPENROUTER_API_KEY", ""),
        SERPER_API_KEY=os.environ.get("SERPER_API_KEY", ""),
        TOGETHER_API_KEY=os.environ.get("TOGETHER_API_KEY", ""),
        ENCRYPTION_KEY=os.environ.get("ENCRYPTION_KEY", ""),
        OWNER_ID=owner,
        BOT_ID=bot,
        CHAT_MODEL=os.environ.get("CHAT_MODEL", DEFAULT_CHAT_MODEL),
        LOG_LEVEL=os.environ.get("LOG_LEVEL", "INFO"),
    )


def get_missing_optional_features(cfg: Config) -> list[str]:
    """Return a list of human-readable feature names disabled by missing config."""
    disabled = []
    if not cfg.OPENROUTER_API_KEY:
        disabled.append("fallback LLM key (users without their own OpenRouter key can't chat)")
    if not cfg.SERPER_API_KEY:
        disabled.append("web search (Serper)")
    if not cfg.TOGETHER_API_KEY:
        disabled.append("image generation (Together)")
    if not cfg.ENCRYPTION_KEY:
        disabled.append("user key storage (/connect will be disabled)")
    return disabled
