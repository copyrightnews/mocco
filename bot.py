import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, TypeHandler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]


async def debug_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"RAW UPDATE: {update.to_dict()}")


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(TypeHandler(Update, debug_all))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()