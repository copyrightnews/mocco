import sys
import os
import logging
from telegram.ext import ApplicationBuilder
from telegram import Update

# Add 'src' directory to the import path so 'mocco' can be loaded
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from mocco.config import load_config, get_missing_optional_features
from mocco.db import init_db
from mocco.handlers import register_handlers

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logger = logging.getLogger("mocco")


def main():
    try:
        cfg = load_config()
    except RuntimeError as e:
        # Exit cleanly so Railway shows ONE clear error instead of crash-looping.
        logger.error(str(e))
        logger.error(
            "Set the missing variable(s) in Railway → Service → Variables, then redeploy."
        )
        sys.exit(1)

    disabled = get_missing_optional_features(cfg)
    if disabled:
        logger.warning("=" * 60)
        logger.warning("OPTIONAL FEATURES DISABLED (missing env vars):")
        for feat in disabled:
            logger.warning(f"  • {feat}")
        logger.warning(
            "The bot will still run — users can /connect their own API keys to enable the corresponding features."
        )
        logger.warning("=" * 60)
    if not cfg.ENCRYPTION_KEY:
        logger.warning("=" * 60)
        logger.warning(
            "ENCRYPTION_KEY is not in env. The bot will auto-generate one and"
        )
        logger.warning(
            "store it in the database on first /connect. To make it stable across"
        )
        logger.warning(
            "DB resets, copy the printed key into Railway as ENCRYPTION_KEY after"
        )
        logger.warning("the first /connect succeeds.")
        logger.warning("=" * 60)

    try:
        init_db()
    except Exception as e:
        logger.exception(f"Database initialization failed: {e!r}")
        logger.error("Check DATABASE_URL and that the Postgres service is reachable.")
        sys.exit(1)

    app = ApplicationBuilder().token(cfg.TELEGRAM_TOKEN).build()
    register_handlers(app)

    logger.info("Mocco is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
