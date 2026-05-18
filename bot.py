import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from groq import Groq

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

client = Groq(api_key=GROQ_API_KEY)

# Store conversation history per user
conversation_history = {}

SYSTEM_PROMPT = """You are a helpful assistant replying on behalf of the user.
Be concise, friendly, and natural. Keep replies short unless asked for detail."""


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    user_msg = update.message.text

    logger.info(f"Message from {user_id}: {user_msg}")

    # Init history for new users
    if user_id not in conversation_history:
        conversation_history[user_id] = []

    # Append user message
    conversation_history[user_id].append({
        "role": "user",
        "content": user_msg
    })

    # Keep last 10 messages only
    if len(conversation_history[user_id]) > 10:
        conversation_history[user_id] = conversation_history[user_id][-10:]

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history[user_id],
            max_tokens=500,
            temperature=0.7
        )

        reply = response.choices[0].message.content

        # Append assistant reply to history
        conversation_history[user_id].append({
            "role": "assistant",
            "content": reply
        })

        logger.info(f"Reply to {user_id}: {reply}")
        await update.message.reply_text(reply)

    except Exception as e:
        logger.error(f"Groq error: {e}")
        await update.message.reply_text(f"⚠️ Error: {str(e)}")


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversation_history.pop(update.message.chat_id, None)
    await update.message.reply_text("Hi! I'm an AI assistant. How can I help you?")


async def handle_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversation_history.pop(update.message.chat_id, None)
    await update.message.reply_text("🔄 Conversation reset. Start fresh!")


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("reset", handle_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()