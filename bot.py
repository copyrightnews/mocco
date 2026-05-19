import sys
import os
import logging
from telegram.ext import ApplicationBuilder
from telegram import Update

# Add 'src' directory to the import path so 'mocco' can be loaded
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from mocco.config import load_config
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
    # Load configuration and ensure all required environment variables are set
    cfg = load_config()
    
    # Initialize the PostgreSQL Database tables and indexes
    init_db()
    
    # Initialize the Telegram Application Builder
    app = ApplicationBuilder().token(cfg.TELEGRAM_TOKEN).build()
    
    # Register all Telegram Command and Message handlers
    register_handlers(app)
    
    logger.info("Mocco is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()