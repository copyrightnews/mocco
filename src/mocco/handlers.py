import os
import logging
import asyncio
import tempfile
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)
from telegram.error import TelegramError, BadRequest

from .config import load_config
from .db import (
    ensure_user,
    is_blacklisted as db_is_blacklisted,
    save_message,
    clear_history,
    get_stats,
    set_blacklist,
    get_all_active_users,
)
from .ai import (
    get_ai_reply,
    web_search,
    generate_image,
    get_groq_client,
)
from .utils import is_rate_limited, split_message

logger = logging.getLogger("mocco")

BROADCAST_CHUNK = 25

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
    "_Example: `/search latest AI news 2026`_\n\n"
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
    "🗂 `/menu` — Show main menu\n"
    "❓ `/help` — Show this guide."
)


def build_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Reset Chat",        switch_inline_query_current_chat="/reset"),
            InlineKeyboardButton("🔍 Search Web",         switch_inline_query_current_chat="/search "),
        ],
        [
            InlineKeyboardButton("🎨 Generate Image",     switch_inline_query_current_chat="/imagine "),
            InlineKeyboardButton("📝 Summarize",          switch_inline_query_current_chat="/summarize "),
        ],
        [
            InlineKeyboardButton("🌐 Translate",          switch_inline_query_current_chat="/translate "),
            InlineKeyboardButton("🧠 Set Personality",    switch_inline_query_current_chat="/setprompt "),
        ],
        [
            InlineKeyboardButton("🗑️ Clear Personality",  switch_inline_query_current_chat="/clearprompt"),
            InlineKeyboardButton("📖 Full Guide",         switch_inline_query_current_chat="/help"),
        ],
    ])


def is_owner(update: Update) -> bool:
    cfg = load_config()
    return bool(update.effective_user and update.effective_user.id == cfg.OWNER_ID)


async def safe_reply(msg, text, parse_mode=None, business_connection_id=None,
                     bot=None, reply_markup=None):
    chunks = split_message(text)
    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks) - 1 else None
        try:
            if business_connection_id and bot:
                await bot.send_message(
                    chat_id=msg.chat_id,
                    text=chunk,
                    parse_mode=parse_mode,
                    business_connection_id=business_connection_id,
                    reply_markup=markup,
                )
            else:
                await msg.reply_text(chunk, parse_mode=parse_mode, reply_markup=markup)
        except BadRequest as e:
            logger.warning(f"Markdown failed on chunk {i}, retrying plain: {e}")
            try:
                if business_connection_id and bot:
                    await bot.send_message(
                        chat_id=msg.chat_id,
                        text=chunk,
                        business_connection_id=business_connection_id,
                        reply_markup=markup,
                )
                else:
                    await msg.reply_text(chunk, reply_markup=markup)
            except Exception as e2:
                logger.error(f"safe_reply fallback failed on chunk {i}: {e2}")
        except TelegramError as e:
            logger.error(f"Telegram error in safe_reply chunk {i}: {e}")


async def process_message(update, context, msg, business_connection_id=None):
    if not msg:
        return

    if not msg.text and not msg.document:
        return

    user = msg.from_user
    if not user or user.is_bot:
        return

    cfg = load_config()

    # ── Telegram Business Connection Loop Protection ──────────────────────────────
    if business_connection_id:
        chat_type = msg.chat.type
        if chat_type == "private":
            # msg.chat.id is customer's user ID. We only reply if customer sent the message.
            # If user.id != msg.chat.id, it is outgoing from the business owner (or the bot).
            if user.id != msg.chat.id:
                logger.debug(f"Ignoring outgoing business message from user {user.id}")
                return
        elif chat_type in ["group", "supergroup"]:
            # In group chats under business connections, only reply if mentioned or replied to
            bot_user = await context.bot.get_me()
            bot_username = bot_user.username
            is_mentioned = False
            msg_text = msg.text or msg.caption or ""
            if msg_text and f"@{bot_username}" in msg_text:
                is_mentioned = True
            is_reply_to_bot = False
            if msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.id == context.bot.id:
                is_reply_to_bot = True
            if not is_mentioned and not is_reply_to_bot:
                return

    # ── Standard Group/Supergroup Spam Guard ──────────────────────────────────────
    else:
        chat_type = msg.chat.type
        if chat_type in ["group", "supergroup"]:
            bot_user = await context.bot.get_me()
            bot_username = bot_user.username
            is_mentioned = False
            msg_text = msg.text or msg.caption or ""
            if msg_text and f"@{bot_username}" in msg_text:
                is_mentioned = True
            is_reply_to_bot = False
            if msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.id == context.bot.id:
                is_reply_to_bot = True
            if not is_mentioned and not is_reply_to_bot:
                return

    user_id = user.id
    chat_id = msg.chat_id

    ensure_user(user_id, user.username, user.first_name)

    if db_is_blacklisted(user_id):
        logger.info(f"Blocked blacklisted user {user_id}")
        return

    if is_rate_limited(user_id):
        logger.debug(f"Rate limited user {user_id}")
        return

    user_msg = ""
    if msg.document:
        if msg.document.file_size and msg.document.file_size > 500 * 1024:
            await safe_reply(
                msg,
                "❌ *File is too large.*\nPlease upload a text file smaller than 500 KB.",
                parse_mode="Markdown",
                business_connection_id=business_connection_id,
                bot=context.bot,
            )
            return

        file_name = msg.document.file_name or ""
        lower_name = file_name.lower()
        binary_extensions = {".zip", ".tar", ".gz", ".rar", ".7z", ".pdf", ".exe", ".bin", ".dmg", ".iso", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp3", ".mp4", ".wav", ".avi", ".mov", ".ogg", ".class", ".dll", ".so"}
        _, ext = os.path.splitext(lower_name)

        tmp_path = None
        file_bytes = None
        try:
            file = await context.bot.get_file(msg.document.file_id)
            with tempfile.NamedTemporaryFile(delete=False) as f:
                tmp_path = f.name
            await file.download_to_drive(tmp_path)
            with open(tmp_path, "rb") as f:
                file_bytes = f.read()
        except Exception as e:
            logger.exception(f"Error downloading file: {e}")
            await safe_reply(
                msg,
                "❌ *Failed to download the file.*\nPlease try uploading again.",
                parse_mode="Markdown",
                business_connection_id=business_connection_id,
                bot=context.bot,
            )
            return
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        if not file_bytes:
            await safe_reply(
                msg,
                "❌ *Empty file.*\nThe uploaded file contains no data.",
                parse_mode="Markdown",
                business_connection_id=business_connection_id,
                bot=context.bot,
            )
            return

        if ext in binary_extensions or b"\x00" in file_bytes:
            await safe_reply(
                msg,
                "❌ *Unsupported file type.*\nMocco only supports text-based files (e.g., code files, logs, text documents).",
                parse_mode="Markdown",
                business_connection_id=business_connection_id,
                bot=context.bot,
            )
            return

        file_content = None
        for encoding in ["utf-8", "utf-16", "latin-1"]:
            try:
                file_content = file_bytes.decode(encoding)
                break
            except Exception:
                continue

        if file_content is None:
            await safe_reply(
                msg,
                "❌ *Decoding failed.*\nCould not decode the file content. Please ensure it's a valid text file.",
                parse_mode="Markdown",
                business_connection_id=business_connection_id,
                bot=context.bot,
            )
            return

        caption_part = msg.caption.strip() if msg.caption else ""
        file_info = f"File: {file_name}\n" if file_name else ""
        prompt_lines = []
        if caption_part:
            prompt_lines.append(caption_part)
            prompt_lines.append("")
        prompt_lines.append(f"```{ext[1:] if ext else ''}\n// {file_info}{file_content}\n```")
        user_msg = "\n".join(prompt_lines)
    else:
        user_msg = msg.text or ""

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
        if reply is None:
            # Groq API failed; reply with error but do NOT save to history database
            await safe_reply(
                msg,
                "I couldn't generate a response right now.\n"
                "This is likely a temporary issue — please try again in a few seconds.",
                business_connection_id=business_connection_id,
                bot=context.bot,
            )
            return

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


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    ensure_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name)
    clear_history(msg.from_user.id)
    await msg.reply_text(WELCOME_TEXT, parse_mode="Markdown", reply_markup=build_menu_keyboard())


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    await msg.reply_text(HELP_TEXT, parse_mode="Markdown", reply_markup=build_menu_keyboard())


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    await msg.reply_text(
        "🗂 *Main Menu* — What would you like to do?",
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
        "🔄 *Conversation cleared.*\nStarting fresh — what would you like to talk about?",
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
            "_Example:_ `/search latest AI news 2026`",
            parse_mode="Markdown",
        )
        return
    try:
        await context.bot.send_chat_action(chat_id=msg.chat_id, action=ChatAction.TYPING)
    except TelegramError:
        pass
    search_text, _ = await asyncio.to_thread(web_search, query)
    await safe_reply(msg, f"🔍 *Results for:* `{query}`\n\n{search_text}", parse_mode="Markdown")


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
        f"🎨 Generating:\n_{prompt}_\n\nThis takes up to 30 seconds...",
        parse_mode="Markdown",
    )
    try:
        await context.bot.send_chat_action(chat_id=msg.chat_id, action=ChatAction.UPLOAD_PHOTO)
    except TelegramError:
        pass
    res = await asyncio.to_thread(generate_image, prompt)
    if res:
        img_data, is_url = res
        try:
            await context.bot.send_photo(
                chat_id=msg.chat_id,
                photo=img_data,
                caption=f"🎨 {prompt[:900]}",
            )
        except TelegramError as e:
            logger.error(f"send_photo failed: {e}")
            await safe_reply(
                msg,
                "❌ *Image was generated but could not be sent.*\nPlease try again.",
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
            "_Usage:_ `/summarize <text>`",
            parse_mode="Markdown",
        )
        return
    try:
        await context.bot.send_chat_action(chat_id=msg.chat_id, action=ChatAction.TYPING)
    except TelegramError:
        pass
    try:
        groq_client = get_groq_client()
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
        await safe_reply(msg, "❌ *Summarization failed.*\nPlease try again.", parse_mode="Markdown")


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
            "• `/translate Bengali Where is the nearest hospital?`",
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
        groq_client = get_groq_client()
        resp = await asyncio.to_thread(
            lambda: groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"You are an expert translator. Translate the given text accurately "
                            f"to {lang}. Ensure that you use standard script, native grammar, "
                            f"and formal/natural phrasing for the target language. If the target "
                            f"language is Bengali/Bangla, translate to correct and standard Bengali "
                            f"Unicode script (বাংলা) with proper spelling. Reply with only the "
                            f"translated text — no explanations, no labels, no preamble."
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
        await safe_reply(msg, f"❌ *Translation to {lang} failed.*\nPlease try again.", parse_mode="Markdown")


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
            "• `/setprompt Always reply in French.`\n"
            "• `/setprompt Be very concise. Max 2 sentences per reply.`",
            parse_mode="Markdown",
        )
        return
    ensure_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name)
    from .db import set_custom_prompt
    set_custom_prompt(msg.from_user.id, prompt)
    await safe_reply(
        msg,
        f"✅ *Custom personality set.*\n\nI'll follow these instructions:\n_{prompt}_\n\n"
        f"Use `/clearprompt` to reset to default.",
        parse_mode="Markdown",
    )


async def cmd_clearprompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    from .db import set_custom_prompt
    set_custom_prompt(msg.from_user.id, None)
    await safe_reply(
        msg,
        "✅ *Custom personality removed.*\nI'm back to my default behavior.",
        parse_mode="Markdown",
    )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.voice:
        return
    user = msg.from_user
    if not user or user.is_bot:
        return
    ensure_user(user.id, user.username, user.first_name)
    if db_is_blacklisted(user.id):
        return
    if is_rate_limited(user.id):
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
            groq_client = get_groq_client()
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
                "❌ *Could not transcribe your voice message.*\nPlease ensure your audio is clear and try again.",
                parse_mode="Markdown",
            )
            return
        await safe_reply(msg, f"🎤 *Transcribed:*\n_{user_msg}_", parse_mode="Markdown")
        reply = await asyncio.to_thread(get_ai_reply, user.id, user_msg)
        if reply is None:
            await safe_reply(
                msg,
                "❌ *Voice processing failed.*\n"
                "I couldn't generate a response right now. Please try again in a moment.",
                parse_mode="Markdown",
            )
            return
        
        save_message(user.id, "user", user_msg)
        save_message(user.id, "assistant", reply)
        await safe_reply(msg, reply)
    except Exception as e:
        logger.exception(f"Voice error: {e}")
        await safe_reply(
            msg,
            "❌ *Voice processing failed.*\nPlease try again or type your message instead.",
            parse_mode="Markdown",
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


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
        await safe_reply(msg, "❌ Invalid user ID.")
        return
    if set_blacklist(target_id, True):
        await safe_reply(msg, f"🚫 User `{target_id}` blacklisted.", parse_mode="Markdown")
    else:
        await safe_reply(msg, "❌ Failed to blacklist user.")


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
        await safe_reply(msg, "❌ Invalid user ID.")
        return
    if set_blacklist(target_id, False):
        await safe_reply(msg, f"✅ User `{target_id}` unblacklisted.", parse_mode="Markdown")
    else:
        await safe_reply(msg, "❌ Failed to update user.")


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_owner(update):
        return
    text = " ".join(context.args).strip()
    if not text:
        await safe_reply(msg, "Usage: /broadcast <message>")
        return
    user_ids = await asyncio.to_thread(get_all_active_users)
    if not user_ids:
        await safe_reply(msg, "No active users found.")
        return
    await safe_reply(msg, f"📢 Broadcasting to {len(user_ids)} users...")
    sent = 0
    failed = 0
    sem = asyncio.Semaphore(BROADCAST_CHUNK)

    async def send_one(uid: int):
        nonlocal sent, failed
        async with sem:
            try:
                await context.bot.send_message(chat_id=uid, text=f"📢 {text}")
                sent += 1
            except Exception:
                failed += 1

    await asyncio.gather(*[send_one(uid) for uid in user_ids])
    await safe_reply(
        msg,
        f"✅ *Broadcast complete.*\nSent: *{sent}* | Failed: *{failed}*",
        parse_mode="Markdown",
    )


def register_handlers(app):
    """Register all Mocco handlers to the telegram application instance."""
    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("help",        cmd_help))
    app.add_handler(CommandHandler("menu",        cmd_menu))
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
    app.add_handler(MessageHandler((filters.TEXT | filters.Document.ALL) & ~filters.COMMAND, handle_message))
