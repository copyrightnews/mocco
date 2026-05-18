import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

try:
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    logger.info("Groq client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Groq: {e}")
    raise

conversation_history = {}

SYSTEM_PROMPT = """You are a helpful assistant replying on behalf of the user.
Be concise, friendly, and natural. Keep replies short unless asked for detail."""


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle both regular and business messages
    message = update.message or update.business_message
    if not message or not message.text:
        return

    # Ignore messages sent by the account owner themselves
    if update.business_message and message.from_user and message.from_user.is_bot is False:
        # Check if sender is the business owner — skip replying to self
        me = await context.bot.get_me()
        if message.from_user.id == me.id:
            return

    user_id = message.chat_id
    user_msg = message.text

    logger.info(f"Message from {user_id}: {user_msg}")

    if user_id not in conversation_history:
        conversation_history[user_id] = []

    conversation_history[user_id].append({
        "role": "user",
        "content": user_msg
    })

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

        conversation_history[user_id].append({
            "role": "assistant",
            "content": reply
        })

        logger.info(f"Reply to {user_id}: {reply}")

        # Business messages need business_connection_id to reply
        if update.business_message:
            await context.bot.send_message(
                chat_id=user_id,
                text=reply,
                business_connection_id=update.business_message.business_connection_id
            )
        else:
            await message.reply_text(reply)

    except Exception as e:
        logger.error(f"Groq error: {e}")


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.business_message
    if message:
        conversation_history.pop(message.chat_id, None)
        await message.reply_text("Hi! I'm Mocco, your AI assistant. How can I help you?")


async def handle_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.business_message
    if message:
        conversation_history.pop(message.chat_id, None)
        await message.reply_text("🔄 Conversation reset. Start fresh!")


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("reset", handle_reset))

    # Regular messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Business messages
    app.add_handler(MessageHandler(filters.UpdateType.BUSINESS_MESSAGE, handle_message))

    app.run_polling(
        allowed_updates=[
            Update.MESSAGE,
            Update.BUSINESS_MESSAGE,
            Update.BUSINESS_CONNECTION,
        ]
    )


if __name__ == "__main__":
    main()