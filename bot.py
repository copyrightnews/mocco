import os
import logging
import asyncio
import requests
import tempfile
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)
from telegram.error import TelegramError, BadRequest
from groq import Groq
import psycopg2
from psycopg2.extras import RealDictCursor

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logger = logging.getLogger("mocco")

# ── Config ────────────────────────────────────────────────────────────────────

TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY     = os.environ["GROQ_API_KEY"]
SERPER_API_KEY   = os.environ["SERPER_API_KEY"]
TOGETHER_API_KEY = os.environ["TOGETHER_API_KEY"]
DATABASE_URL     = os.environ["DATABASE_URL"]
OWNER_ID         = int(os.environ.get("OWNER_ID", "7232714487"))
BOT_ID           = int(os.environ.get("BOT_ID",   "8877277512"))

groq_client = Groq(api_key=GROQ_API_KEY)

# ── Database ──────────────────────────────────────────────────────────────────

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id       BIGINT PRIMARY KEY,
                    username      TEXT,
                    first_name    TEXT,
                    custom_prompt TEXT,
                    is_blacklisted BOOLEAN DEFAULT FALSE,
                    message_count  INTEGER DEFAULT 0,
                    created_at    TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id         SERIAL PRIMARY KEY,
                    user_id    BIGINT,
                    role       TEXT,
                    content    TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_user_id
                ON messages(user_id, id);
            """)
            conn.commit()
    logger.info("Database initialized")

def ensure_user(user_id, username=None, first_name=None):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (user_id, username, first_name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE
                    SET username   = EXCLUDED.username,
                        first_name = EXCLUDED.first_name
                """, (user_id, username, first_name))
                conn.commit()
    except Exception as e:
        logger.error(f"ensure_user failed: {e}")

def is_blacklisted(user_id):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT is_blacklisted FROM users WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
                return bool(row and row["is_blacklisted"])
    except Exception as e:
        logger.error(f"is_blacklisted failed: {e}")
        return False

def get_history(user_id, limit=14):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT role, content FROM messages
                    WHERE user_id = %s
                    ORDER BY id DESC
                    LIMIT %s
                """, (user_id, limit))
                rows = cur.fetchall()
                return list(reversed(rows))
    except Exception as e:
        logger.error(f"get_history failed: {e}")
        return []

def save_message(user_id, role, content):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO messages (user_id, role, content)
                    VALUES (%s, %s, %s)
                """, (user_id, role, content))
                cur.execute("""
                    UPDATE users SET message_count = message_count + 1
                    WHERE user_id = %s
                """, (user_id,))
                conn.commit()
    except Exception as e:
        logger.error(f"save_message failed: {e}")

def clear_history(user_id):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM messages WHERE user_id = %s", (user_id,))
                conn.commit()
    except Exception as e:
        logger.error(f"clear_history failed: {e}")

def get_custom_prompt(user_id):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT custom_prompt FROM users WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
                return row["custom_prompt"] if row and row["custom_prompt"] else None
    except Exception as e:
        logger.error(f"get_custom_prompt failed: {e}")
        return None

def set_custom_prompt(user_id, prompt):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET custom_prompt = %s WHERE user_id = %s",
                    (prompt, user_id),
                )
                conn.commit()
    except Exception as e:
        logger.error(f"set_custom_prompt failed: {e}")

def get_stats():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM users")
                users = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(*) AS c FROM messages")
                msgs = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(*) AS c FROM users WHERE is_blacklisted = TRUE")
                blk = cur.fetchone()["c"]
                return users, msgs, blk
    except Exception as e:
        logger.error(f"get_stats failed: {e}")
        return 0, 0, 0

def set_blacklist(user_id, value: bool):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (user_id, is_blacklisted)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO UPDATE
                    SET is_blacklisted = EXCLUDED.is_blacklisted
                """, (user_id, value))
                conn.commit()
                return True
    except Exception as e:
        logger.error(f"set_blacklist failed: {e}")
        return False

# ── System Prompt ─────────────────────────────────────────────────────────────

def get_system_prompt(user_id=None):
    today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")
    base = (
        f"You are Mocco, an advanced AI assistant — smart, precise, and genuinely helpful.\n"
        f"Today's date is {today}.\n\n"
        "## How you behave:\n"
        "- Think carefully before answering. Be accurate and honest.\n"
        "- If unsure about something, say so clearly instead of guessing.\n"
        "- Give well-structured answers: use bullet points, numbered steps, or sections when it helps clarity.\n"
        "- For code, always use proper code blocks with the language specified.\n"
        "- For short factual questions, answer directly and concisely.\n"
        "- For complex topics, give a thorough but scannable answer.\n"
        "- Never pad answers with filler phrases like 'Great question!' or 'Certainly!'.\n"
        "- Never say your knowledge is limited to 2023. You are up to date.\n"
        "- If asked about real-time data (live scores, breaking news, stock prices), use web search "
        "results when provided, otherwise clearly state you don't have live data.\n\n"
        "## Tone:\n"
        "- Calm, clear, and confident — like a knowledgeable friend who respects the user's time.\n"
        "- Warm but not over-the-top. No excessive emojis. No sycophancy.\n"
        "- Adapt depth to the question: brief for simple, detailed for complex.\n\n"
        "## Your capabilities:\n"
        "- Answer questions on any topic: coding, science, math, history, writing, business, and more.\n"
        "- Write, review, debug, and explain code in any programming language.\n"
        "- Summarize, translate, rewrite, and analyze text.\n"
        "- Generate creative content: stories, emails, essays, product descriptions, etc.\n"
        "- Help with planning, brainstorming, and decision-making.\n"
        "- Search the web for current information when triggered.\n"
    )
    if user_id:
        custom = get_custom_prompt(user_id)
        if custom:
            base += f"\n## Custom instructions from this user:\n{custom}\n"
    return base

# ── Web Search ────────────────────────────────────────────────────────────────

SEARCH_KEYWORDS = [
    "latest", "news", "today", "current", "price", "score",
    "weather", "who won", "what happened", "right now", "live",
    "stock", "exchange rate", "update", "recently", "this week",
    "this month", "2024", "2025", "happening", "released", "launched",
]

def needs_search(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in SEARCH_KEYWORDS)

def web_search(query: str):
    """Returns (formatted_text, raw_results_list)"""
    try:
        r = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": 5},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()

        lines = []
        raw = []

        # Answer box (direct answer)
        if "answerBox" in data:
            ab = data["answerBox"]
            answer = ab.get("answer") or ab.get("snippet") or ""
            if answer:
                lines.append(f"📌 *Direct Answer:* {answer}")
                raw.append({"title": "Answer Box", "snippet": answer})

        # Knowledge graph
        if "knowledgeGraph" in data:
            kg = data["knowledgeGraph"]
            desc = kg.get("description", "")
            if desc:
                lines.append(f"📖 *Overview:* {desc}")
                raw.append({"title": kg.get("title", ""), "snippet": desc})

        # Organic results
        organic = data.get("organic", [])[:4]
        if organic:
            if lines:
                lines.append("")
            lines.append("🔗 *Top Results:*")
            for i, item in enumerate(organic, 1):
                title   = item.get("title", "").strip()
                snippet = item.get("snippet", "").strip()
                link    = item.get("link", "")
                if title and snippet:
                    lines.append(f"{i}. {title}\n    {snippet}")
                    raw.append({"title": title, "snippet": snippet, "link": link})

        if not lines:
            return "No results found for your query.", []

        return "\n".join(lines), raw

    except requests.exceptions.Timeout:
        return "Search timed out. Please try again.", []
    except Exception as e:
        logger.error(f"Search error: {e}")
        return "Search failed. Please try again in a moment.", []

# ── Image Generation ──────────────────────────────────────────────────────────

def generate_image(prompt: str):
    try:
        r = requests.post(
            "https://api.together.xyz/v1/images/generations",
            headers={
                "Authorization": f"Bearer {TOGETHER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "black-forest-labs/FLUX.1-schnell-Free",
                "prompt": prompt,
                "n": 1,
                "width": 1024,
                "height": 1024,
                "response_format": "url",
            },
            timeout=90,
        )
        r.raise_for_status()
        data = r.json()
        if "data" in data and data["data"]:
            item = data["data"][0]
            return item.get("url") or item.get("b64_json")
        logger.error(f"Image gen unexpected response: {data}")
        return None
    except requests.exceptions.Timeout:
        logger.error("Image generation timed out")
        return None
    except Exception as e:
        logger.error(f"Image gen error: {e}")
        return None

# ── AI Reply ──────────────────────────────────────────────────────────────────

def get_ai_reply(user_id, user_msg):
    history  = get_history(user_id)
    messages = [{"role": r["role"], "content": r["content"]} for r in history]

    if needs_search(user_msg):
        search_text, _ = web_search(user_msg)
        augmented = (
            f"{user_msg}\n\n"
            f"[Current web search results]:\n{search_text}\n\n"
            "Use the search results above to give an accurate, up-to-date answer."
        )
        messages.append({"role": "user", "content": augmented})
    else:
        messages.append({"role": "user", "content": user_msg})

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": get_system_prompt(user_id)}] + messages,
            max_tokens=800,
            temperature=0.65,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Groq error: {e}")
        return (
            "I couldn't generate a response right now.\n"
            "This is likely a temporary issue — please try again in a few seconds."
        )

# ── Safe Reply Helper ─────────────────────────────────────────────────────────

async def safe_reply(msg, text, parse_mode=None, business_connection_id=None,
                     bot=None, reply_markup=None):
    try:
        if business_connection_id and bot:
            return await bot.send_message(
                chat_id=msg.chat_id,
                text=text,
                parse_mode=parse_mode,
                business_connection_id=business_connection_id,
                reply_markup=reply_markup,
            )
        return await msg.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except BadRequest as e:
        logger.warning(f"Markdown failed, retrying plain: {e}")
        try:
            if business_connection_id and bot:
                return await bot.send_message(
                    chat_id=msg.chat_id,
                    text=text,
                    business_connection_id=business_connection_id,
                    reply_markup=reply_markup,
                )
            return await msg.reply_text(text, reply_markup=reply_markup)
        except Exception as e2:
            logger.error(f"safe_reply fallback failed: {e2}")
    except TelegramError as e:
        logger.error(f"Telegram error in safe_reply: {e}")

# ── Core Message Handler ──────────────────────────────────────────────────────

async def process_message(update, context, msg, business_connection_id=None):
    if not msg or not msg.text:
        return

    user = msg.from_user
    if not user or user.id == BOT_ID or user.is_bot:
        return

    user_id = user.id
    chat_id = msg.chat_id

    ensure_user(user_id, user.username, user.first_name)

    if is_blacklisted(user_id):
        logger.info(f"Blocked blacklisted user {user_id}")
        return

    user_msg = msg.text
    logger.info(f"Msg from {user_id} (chat {chat_id}): {user_msg[:120]}")

    try:
        kwargs = {"chat_id": chat_id, "action": ChatAction.TYPING}
        if business_connection_id:
            kwargs["business_connection_id"] = business_connection_id
        await context.bot.send_chat_action(**kwargs)
    except TelegramError as e:
        logger.debug(f"send_chat_action failed: {e}")

    try:
        reply = await asyncio.to_thread(get_ai_reply, user_id, user_msg)
        save_message(user_id, "user", user_msg)
        save_message(user_id, "assistant", reply)
        await safe_reply(
            msg, reply,
            business_connection_id=business_connection_id,
            bot=context.bot,
        )
    except Exception as e:
        logger.exception(f"process_message error: {e}")
        await safe_reply(
            msg,
            "Something went wrong on my end.\nPlease try sending your message again.",
            business_connection_id=business_connection_id,
            bot=context.bot,
        )

async def handle_business_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.business_message
    if msg:
        await process_message(update, context, msg, msg.business_connection_id)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_message(update, context, update.message)

# ── Welcome & Menu ────────────────────────────────────────────────────────────

WELCOME_TEXT = (
    "👋 Hi, I'm *Mocco* — your smart AI assistant.\n"
    "How can I help you today?\n\n"
    "I can help you with:\n"
    "• 💻 Coding & debugging\n"
    "• ✍️ Writing & editing\n"
    "• 🔍 Web search & research\n"
    "• 🌐 Translation & summarization\n"
    "• 🎨 Image generation\n"
    "• 🧠 Ideas, planning & problem solving\n"
    "• 📚 Learning & everyday questions\n\n"
    "Just type your question, or tap a button below."
)

HELP_TEXT = (
    "📖 *Mocco — Command Guide*\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "💬 *Chat*\n"
    "Just type anything — I'll reply intelligently.\n"
    "I remember your last 14 messages for context.\n\n"
    "🔄 `/reset`\n"
    "Clear your conversation and start fresh.\n\n"
    "🔍 `/search <query>`\n"
    "Search the web for current information.\n"
    "_Example: `/search latest AI news 2025`_\n\n"
    "🎨 `/imagine <prompt>`\n"
    "Generate an AI image from your description.\n"
    "_Example: `/imagine a futuristic city at night, cinematic`_\n\n"
    "📝 `/summarize <text>`\n"
    "Paste any text and get a concise summary.\n\n"
    "🌐 `/translate <language> <text>`\n"
    "Translate text into any language.\n"
    "_Example: `/translate Arabic Good morning`_\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "🧠 *Personalization*\n\n"
    "`/setprompt <instructions>`\n"
    "Give me a custom role or behavior.\n"
    "_Example: `/setprompt Act as a senior Python developer`_\n\n"
    "`/clearprompt`\n"
    "Remove your custom personality.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "🎤 *Voice Messages*\n"
    "Send a voice note — I'll transcribe it and reply.\n\n"
    "❓ `/help` — Show this guide."
)

def build_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Reset Chat",       switch_inline_query_current_chat="/reset"),
            InlineKeyboardButton("🔍 Search Web",        switch_inline_query_current_chat="/search "),
        ],
        [
            InlineKeyboardButton("🎨 Generate Image",    switch_inline_query_current_chat="/imagine "),
            InlineKeyboardButton("📝 Summarize",         switch_inline_query_current_chat="/summarize "),
        ],
        [
            InlineKeyboardButton("🌐 Translate",         switch_inline_query_current_chat="/translate "),
            InlineKeyboardButton("🧠 Set Personality",   switch_inline_query_current_chat="/setprompt "),
        ],
        [
            InlineKeyboardButton("🗑️ Clear Personality", switch_inline_query_current_chat="/clearprompt"),
            InlineKeyboardButton("📖 Full Guide",        switch_inline_query_current_chat="/help"),
        ],
    ])

# ── Commands ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    ensure_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name)
    clear_history(msg.from_user.id)
    await msg.reply_text(
        WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=build_menu_keyboard(),
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    await msg.reply_text(
        HELP_TEXT,
        parse_mode="Markdown",
        reply_markup=build_menu_keyboard(),
    )

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    clear_history(msg.from_user.id)
    await safe_reply(
        msg,
        "🔄 *Conversation cleared.*\n"
        "Starting fresh — what would you like to talk about?",
        parse_mode="Markdown",
    )

async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    query = " ".join(context.args).strip()
    if not query:
        await safe_reply(
            msg,
            "🔍 *Web Search*\n\n"
            "Please provide a search query.\n"
            "_Usage:_ `/search <your query>`\n"
            "_Example:_ `/search latest AI news 2025`",
            parse_mode="Markdown",
        )
        return
    try:
        await context.bot.send_chat_action(chat_id=msg.chat_id, action=ChatAction.TYPING)
    except TelegramError:
        pass

    search_text, _ = await asyncio.to_thread(web_search, query)
    await safe_reply(
        msg,
        f"🔍 *Results for:* `{query}`\n\n{search_text}",
        parse_mode="Markdown",
    )

async def cmd_imagine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    prompt = " ".join(context.args).strip()
    if not prompt:
        await safe_reply(
            msg,
            "🎨 *Image Generation*\n\n"
            "Describe the image you want to generate.\n"
            "_Usage:_ `/imagine <description>`\n\n"
            "*Tips for better results:*\n"
            "• Be specific and descriptive\n"
            "• Add style keywords: _cinematic, realistic, watercolor, 4K_\n"
            "• Add lighting: _golden hour, studio lighting, neon_\n\n"
            "_Example:_ `/imagine a futuristic city at sunset, cinematic lighting, 4K`",
            parse_mode="Markdown",
        )
        return

    await safe_reply(
        msg,
        f"🎨 Generating:\n_\"{prompt}\"_\n\nThis takes up to 30 seconds...",
        parse_mode="Markdown",
    )
    try:
        await context.bot.send_chat_action(chat_id=msg.chat_id, action=ChatAction.UPLOAD_PHOTO)
    except TelegramError:
        pass

    url = await asyncio.to_thread(generate_image, prompt)
    if url:
        try:
            await context.bot.send_photo(
                chat_id=msg.chat_id,
                photo=url,
                caption=f"🎨 {prompt[:900]}",
            )
        except TelegramError as e:
            logger.error(f"send_photo failed: {e}")
            await safe_reply(
                msg,
                "❌ *Image was generated but could not be sent.*\n"
                "Please try again.",
                parse_mode="Markdown",
            )
    else:
        await safe_reply(
            msg,
            "❌ *Image generation failed.*\n"
            "This may be a temporary issue with the image service.\n"
            "Please try again in a moment, or use a different prompt.",
            parse_mode="Markdown",
        )

async def cmd_summarize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    text = " ".join(context.args).strip()
    if not text:
        await safe_reply(
            msg,
            "📝 *Summarize Text*\n\n"
            "Paste the text you want summarized.\n"
            "_Usage:_ `/summarize <text>`\n\n"
            "Works great with articles, paragraphs, or any long content.",
            parse_mode="Markdown",
        )
        return
    try:
        await context.bot.send_chat_action(chat_id=msg.chat_id, action=ChatAction.TYPING)
    except TelegramError:
        pass
    try:
        resp = await asyncio.to_thread(
            lambda: groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a precise summarizer. Given any text, produce a clear and "
                            "concise summary capturing all key points. Use bullet points if there "
                            "are multiple distinct ideas. Be brief but complete. No filler phrases."
                        ),
                    },
                    {"role": "user", "content": f"Summarize this:\n\n{text}"},
                ],
                max_tokens=500,
                temperature=0.4,
            )
        )
        out = resp.choices[0].message.content.strip()
        word_count = len(text.split())
        await safe_reply(
            msg,
            f"📝 *Summary* _({word_count} words → condensed)_\n\n{out}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"summarize failed: {e}")
        await safe_reply(
            msg,
            "❌ *Summarization failed.*\n"
            "Please try again. For very long texts, try splitting into smaller sections.",
            parse_mode="Markdown",
        )

async def cmd_translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    if len(context.args) < 2:
        await safe_reply(
            msg,
            "🌐 *Translate Text*\n\n"
            "_Usage:_ `/translate <language> <text>`\n\n"
            "*Examples:*\n"
            "• `/translate Spanish Hello, how are you?`\n"
            "• `/translate Arabic Good morning`\n"
            "• `/translate Japanese Thank you very much`\n"
            "• `/translate Bengali Where is the nearest hospital?`\n\n"
            "Supports all major world languages.",
            parse_mode="Markdown",
        )
        return
    lang = context.args[0]
    text = " ".join(context.args[1:]).strip()
    try:
        await context.bot.send_chat_action(chat_id=msg.chat_id, action=ChatAction.TYPING)
    except TelegramError:
        pass
    try:
        resp = await asyncio.to_thread(
            lambda: groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"You are an expert translator. Translate the given text accurately "
                            f"to {lang}. Reply with only the translated text — no explanations, "
                            "no labels, no preamble."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                max_tokens=500,
                temperature=0.3,
            )
        )
        out = resp.choices[0].message.content.strip()
        await safe_reply(
            msg,
            f"🌐 *Translation to {lang}*\n\n"
            f"*Original:* _{text[:200]}_\n\n"
            f"*Result:* {out}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"translate failed: {e}")
        await safe_reply(
            msg,
            f"❌ *Translation to {lang} failed.*\n"
            "Please check the language name and try again.\n"
            "_Example: `/translate French Hello`_",
            parse_mode="Markdown",
        )

async def cmd_setprompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    prompt = " ".join(context.args).strip()
    if not prompt:
        await safe_reply(
            msg,
            "🧠 *Set Custom Personality*\n\n"
            "Give me a role or custom instructions to follow.\n"
            "_Usage:_ `/setprompt <instructions>`\n\n"
            "*Examples:*\n"
            "• `/setprompt Act as a senior Python developer. Be technical and precise.`\n"
            "• `/setprompt You are a creative writing coach. Give detailed feedback.`\n"
            "• `/setprompt Always reply in French.`\n"
            "• `/setprompt Be very concise. Max 2 sentences per reply.`\n\n"
            "Use `/clearprompt` to remove it.",
            parse_mode="Markdown",
        )
        return
    ensure_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name)
    set_custom_prompt(msg.from_user.id, prompt)
    await safe_reply(
        msg,
        f"✅ *Custom personality set.*\n\n"
        f"I'll follow these instructions:\n_\"{prompt}\"_\n\n"
        f"Use `/clearprompt` to reset to default.",
        parse_mode="Markdown",
    )

async def cmd_clearprompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    set_custom_prompt(msg.from_user.id, None)
    await safe_reply(
        msg,
        "✅ *Custom personality removed.*\n"
        "I'm back to my default behavior.\n"
        "Use `/setprompt` anytime to set a new one.",
        parse_mode="Markdown",
    )

# ── Voice Messages ────────────────────────────────────────────────────────────

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.voice:
        return

    user = msg.from_user
    if not user or user.is_bot:
        return

    ensure_user(user.id, user.username, user.first_name)
    if is_blacklisted(user.id):
        return

    try:
        await context.bot.send_chat_action(chat_id=msg.chat_id, action=ChatAction.TYPING)
    except TelegramError:
        pass

    tmp_path = None
    try:
        file = await context.bot.get_file(msg.voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            tmp_path = f.name
        await file.download_to_drive(tmp_path)

        def transcribe():
            with open(tmp_path, "rb") as audio:
                return groq_client.audio.transcriptions.create(
                    model="whisper-large-v3",
                    file=audio,
                    response_format="text",
                )

        transcription = await asyncio.to_thread(transcribe)
        user_msg = (transcription or "").strip()

        if not user_msg:
            await safe_reply(
                msg,
                "❌ *Could not transcribe your voice message.*\n"
                "Please ensure your audio is clear and try again, "
                "or type your message instead.",
                parse_mode="Markdown",
            )
            return

        await safe_reply(
            msg,
            f"🎤 *Transcribed:*\n_{user_msg}_",
            parse_mode="Markdown",
        )

        reply = await asyncio.to_thread(get_ai_reply, user.id, user_msg)
        save_message(user.id, "user", user_msg)
        save_message(user.id, "assistant", reply)
        await safe_reply(msg, reply)

    except Exception as e:
        logger.exception(f"Voice error: {e}")
        await safe_reply(
            msg,
            "❌ *Voice processing failed.*\n"
            "Please try again or type your message instead.",
            parse_mode="Markdown",
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

# ── Admin Commands ────────────────────────────────────────────────────────────

def is_owner(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == OWNER_ID

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_owner(update):
        return
    users, msgs, blk = get_stats()
    active = users - blk
    await safe_reply(
        msg,
        f"📊 *Mocco — Live Stats*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Total users:     *{users}*\n"
        f"✅ Active users:    *{active}*\n"
        f"🚫 Blacklisted:    *{blk}*\n"
        f"💬 Total messages: *{msgs}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 {datetime.now(timezone.utc).strftime('%B %d, %Y  %H:%M UTC')}",
        parse_mode="Markdown",
    )

async def cmd_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_owner(update):
        return
    if not context.args:
        await safe_reply(msg, "Usage: /blacklist <user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await safe_reply(msg, "❌ Invalid user ID. Please provide a numeric ID.")
        return
    if set_blacklist(target_id, True):
        await safe_reply(
            msg,
            f"🚫 *User `{target_id}` blacklisted.*\n"
            f"They will no longer receive responses.",
            parse_mode="Markdown",
        )
    else:
        await safe_reply(msg, "❌ Failed to blacklist user. Check logs.")

async def cmd_unblacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_owner(update):
        return
    if not context.args:
        await safe_reply(msg, "Usage: /unblacklist <user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await safe_reply(msg, "❌ Invalid user ID. Please provide a numeric ID.")
        return
    if set_blacklist(target_id, False):
        await safe_reply(
            msg,
            f"✅ *User `{target_id}` unblacklisted.*\n"
            f"They can now interact with Mocco again.",
            parse_mode="Markdown",
        )
    else:
        await safe_reply(msg, "❌ Failed to unblacklist user. Check logs.")

async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_owner(update):
        return
    text = " ".join(context.args).strip()
    if not text:
        await safe_reply(
            msg,
            "Usage: /broadcast <message>\n\n"
            "Sends a message to all non-blacklisted users.",
        )
        return
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM users WHERE is_blacklisted = FALSE")
                users = cur.fetchall()
    except Exception as e:
        logger.error(f"broadcast fetch failed: {e}")
        await safe_reply(msg, "❌ Failed to fetch users. Check logs.")
        return

    await safe_reply(msg, f"📢 Broadcasting to {len(users)} users...")
    sent = 0
    failed = 0
    for u in users:
        try:
            await context.bot.send_message(chat_id=u["user_id"], text=f"📢 {text}")
            sent += 1
        except Exception:
            failed += 1

    await safe_reply(
        msg,
        f"✅ *Broadcast complete.*\n"
        f"Sent: *{sent}* | Failed: *{failed}*",
        parse_mode="Markdown",
    )

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    init_db()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("help",        cmd_help))
    app.add_handler(CommandHandler("reset",       cmd_reset))
    app.add_handler(CommandHandler("search",      cmd_search))
    app.add_handler(CommandHandler("imagine",     cmd_imagine))
    app.add_handler(CommandHandler("summarize",   cmd_summarize))
    app.add_handler(CommandHandler("translate",   cmd_translate))
    app.add_handler(CommandHandler("setprompt",   cmd_setprompt))
    app.add_handler(CommandHandler("clearprompt", cmd_clearprompt))
    app.add_handler(CommandHandler("stats",       cmd_stats))
    app.add_handler(CommandHandler("blacklist",   cmd_blacklist))
    app.add_handler(CommandHandler("unblacklist", cmd_unblacklist))
    app.add_handler(CommandHandler("broadcast",   cmd_broadcast))

    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.UpdateType.BUSINESS_MESSAGE, handle_business_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()