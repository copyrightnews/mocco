import os
import logging
from datetime import datetime
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
    logger.info("Groq client initialized")
except Exception as e:
    logger.error(f"Groq init failed: {e}")
    raise

conversation_history = {}

BOT_ID = 8877277512  # moccoaibot — skip own messages


def get_system_prompt():
    today = datetime.utcnow().strftime("%B %d, %Y")
    return f"""You are Mocco, a smart and helpful AI assistant replying on behalf of the user.
Today's date is {today}. You are fully aware of the current date and time.
Be concise, friendly, and natural. Keep replies short unless asked for detail.
Never claim your knowledge is limited to 2023. You know the current date is {today}.
If asked about real-time data like live scores, prices, or breaking news, say you don't have live internet access but offer what you know."""


async def handle_business_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.business_message
    if not msg or not msg.text:
        return

    if msg.from_user and msg.from_user.id == BOT_ID:
        logger.info("Skipping own message")
        return

    user_id = msg.chat_id
    user_msg = msg.text
    business_connection_id = msg.business_connection_id

    logger.info(f"Business message from {user_id}: {user_msg}")

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
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": get_system_prompt()}] + conversation_history[user_id],
            max_tokens=500,
            temperature=0.7
        )

        reply = response.choices[0].message.content

        conversation_history[user_id].append({
            "role": "assistant",
            "content": reply
        })

        logger.info(f"Reply to {user_id}: {reply}")

        await context.bot.send_message(
            chat_id=user_id,
            text=reply,
            business_connection_id=business_connection_id
        )

    except Exception as e:
        logger.error(f"Error: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    user_id = msg.chat_id
    user_msg = msg.text

    logger.info(f"Regular message from {user_id}: {user_msg}")

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
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": get_system_prompt()}] + conversation_history[user_id],
            max_tokens=500,
            temperature=0.7
        )

        reply = response.choices[0].message.content

        conversation_history[user_id].append({
            "role": "assistant",
            "content": reply
        })

        await msg.reply_text(reply)

    except Exception as e:
        logger.error(f"Error: {e}")


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg:
        conversation_history.pop(msg.chat_id, None)
        await msg.reply_text("Hi! I'm Mocco, your AI assistant. How can I help you?")


async def handle_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg:
        conversation_history.pop(msg.chat_id, None)
        await msg.reply_text("🔄 Conversation reset!")


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("reset", handle_reset))
    app.add_handler(MessageHandler(filters.UpdateType.BUSINESS_MESSAGE, handle_business_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()