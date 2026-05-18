import os
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from groq import Groq

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

    # Init history for new users
    if user_id not in conversation_history:
        conversation_history[user_id] = []

    # Append user message
    conversation_history[user_id].append({
        "role": "user",
        "content": user_msg
    })

    # Keep last 10 messages only (avoid token overflow)
    if len(conversation_history[user_id]) > 10:
        conversation_history[user_id] = conversation_history[user_id][-10:]

    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
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

        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text("Sorry, I couldn't process that right now.")
        print(f"Error: {e}")

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! I'm an AI assistant. How can I help you?")

from telegram.ext import CommandHandler
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", handle_start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()