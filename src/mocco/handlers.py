import os
import logging
import asyncio
import functools
import tempfile
from typing import List, Optional
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
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
    get_chat_model,
    set_chat_model,
    set_user_api_key,
    delete_user_api_key,
    add_user_chat,
    remove_user_chat,
    get_user_chats,
    get_user_chats_context,
)
from .ai import (
    get_ai_reply,
    web_search,
    get_client_for_chat,
    resolve_model,
    user_has_key,
    user_connected_providers,
    can_use_paid_model,
    fetch_all_models,
    NoAPIKeyError,
)
from .crypto import encrypt_api_key
from .providers import (
    PROVIDERS,
    VERIFY_OK,
    VERIFY_TRANSIENT,
    is_known_provider,
    looks_like_provider_key,
    verify_key,
)
from .utils import is_rate_limited, split_message

logger = logging.getLogger("mocco")

BROADCAST_CHUNK = 25

ACCESS_DENIED_TEXT = (
    "🔒 *Access denied.*\n"
    "This bot is private. If you think this is a mistake, contact the bot owner."
)

WELCOME_TEXT = (
    "*Welcome to Mocco.*\n"
    "Your personal AI — intelligent, fast, and built for Telegram.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "*Capabilities*\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "*Chat & Reasoning*\n"
    "Answer questions, debug code, write content, translate languages, "
    "brainstorm ideas — across any topic.\n\n"
    "*Deep Knowledge*\n"
    "Thorough, well-researched responses with full context. "
    "Mocco explains the *why* and *how*, not just the *what*.\n\n"
    "*Web Search*\n"
    "Live search powered by Serper. Get current information, "
    "news, prices, and real-time data.\n\n"
    "*File Analysis*\n"
    "Upload text files (code, logs, documents) — Mocco reads and "
    "analyzes them.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "*How to use*\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "Just type your message and I'll respond.\n"
    "Commands: `/help` for full guide, `/model` to pick an AI model, "
    "`/connect` to use your own API key.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "*Personal Assistant*\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "Go to *Settings > Chat Automation* in Telegram and connect Mocco "
    "to your profile. Now Mocco replies on your behalf when people "
    "message your account — handles questions, shares info about your "
    "channels, and respects your privacy.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "Type anything to begin."
)

HELP_TEXT = (
    "*Mocco — Command Guide*\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "*Essentials*\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "Just type anything — I'll reply with deep, thorough answers.\n"
    "I keep context of the last 14 messages.\n\n"
    "`/reset` — Clear conversation and start fresh.\n\n"
    "`/search <query>` — Search the web.\n"
    "_Example: `/search latest AI news 2026`_\n\n"
    "`/summarize <text>` — Condense any text into key points.\n\n"
    "`/translate <language> <text>` — Translate instantly.\n"
    "_Example: `/translate Arabic Good morning`_\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "*Personalization*\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "`/setprompt <instructions>` — Custom personality or role.\n"
    "_Example: `/setprompt Act as a senior Python developer`_\n\n"
    "`/clearprompt` — Remove your custom instructions.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "*Models & Keys*\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "`/model` — Browse and pick from 100+ AI models.\n"
    "`/model reset` — Back to the default model.\n\n"
    "`/connect <provider>` — Add your own API key.\n"
    "_Supported:_ OpenRouter · OpenAI · Anthropic · Google · Groq · Together\n"
    "Keys are verified live and encrypted at rest.\n\n"
    "`/keys` — View your connected providers.\n"
    "`/disconnect <provider>` — Remove a stored key.\n"
    "`/cancel` — Abort an in-progress `/connect`.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "*Chat Automation*\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "`/addchat @channel` — Register a channel you manage.\n"
    "`/removechat @channel` — Remove a registered channel.\n"
    "`/mychats` — List all your registered chats.\n\n"
    "Connect Mocco in *Settings > Chat Automation* to let it reply "
    "on your behalf when people message you.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "`/menu` — Main menu\n"
    "`/help` — This guide"
)


def build_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Reset Chat",        callback_data="menu:reset"),
            InlineKeyboardButton("Search Web",         callback_data="menu:search"),
        ],
        [
            InlineKeyboardButton("Summarize",          callback_data="menu:summarize"),
        ],
        [
            InlineKeyboardButton("Choose Model",       callback_data="model:open"),
            InlineKeyboardButton("Connect Key",        callback_data="model:connect"),
        ],
        [
            InlineKeyboardButton("Set Personality",    callback_data="menu:setprompt"),
            InlineKeyboardButton("Full Guide",         callback_data="menu:help"),
        ],
    ])


def is_owner(update: Update) -> bool:
    cfg = load_config()
    return bool(update.effective_user and update.effective_user.id == cfg.OWNER_ID)


def _is_owner_set() -> bool:
    return load_config().OWNER_ID != 0


def owner_only(handler):
    """Decorator: when OWNER_ID is set, allow only that user; reply with access denied otherwise.

    When OWNER_ID is unset (0) the handler runs unrestricted.
    """

    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        cfg = load_config()
        if cfg.OWNER_ID == 0:
            return await handler(update, context, *args, **kwargs)
        user = update.effective_user
        if not user or user.id != cfg.OWNER_ID:
            uid = user.id if user else "unknown"
            logger.info(f"Blocked non-owner {uid} from {handler.__name__}")
            msg = update.effective_message
            if msg:
                try:
                    await safe_reply(msg, ACCESS_DENIED_TEXT, parse_mode="Markdown")
                except Exception:
                    pass
            query = getattr(update, "callback_query", None)
            if query is not None:
                try:
                    await query.answer("Access denied.", show_alert=False)
                except TelegramError:
                    pass
            return None
        return await handler(update, context, *args, **kwargs)

    return wrapper


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


async def safe_edit(query, *, text=None, reply_markup=None, **kwargs):
    """Wrapper around query.edit_message_text / edit_message_reply_markup.

    Telegram rejects an edit whose new content equals the current one with
    'BadRequest: Message is not modified'. We swallow that specific error so
    callback handlers (refresh, re-open picker, same-page nav) no-op cleanly.
    """
    try:
        if text is not None:
            return await query.edit_message_text(text, reply_markup=reply_markup, **kwargs)
        if reply_markup is not None:
            return await query.edit_message_reply_markup(reply_markup=reply_markup, **kwargs)
        return None
    except BadRequest as e:
        if "Message is not modified" in str(e):
            try:
                await query.answer()
            except TelegramError:
                pass
            return None
        raise


async def process_business_assistant(update, context, msg, business_connection_id):
    """Handle messages from Chat Automation (personal AI assistant mode).

    When the bot is connected via Settings > Chat Automation, people who 
    message the user's Telegram account get an AI response here.
    """
    if not msg or not msg.text:
        return
    user = msg.from_user
    if not user or user.is_bot:
        return
    chat_type = msg.chat.type
    if chat_type == "private":
        if user.id != msg.chat.id:
            return
    elif chat_type in ["group", "supergroup"]:
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

    cfg = load_config()
    owner_id = cfg.OWNER_ID
    logger.info(f"Assistant msg from {user.id} ({user.first_name}): {msg.text[:120]}")

    # ── t.me link resolution ────────────────────────────────────────────────
    import re as _re
    tme_links = _re.findall(r"https?://t\.me/([a-zA-Z0-9_]+)", msg.text)
    resolved_links = []
    if tme_links:
        for link_uname in tme_links:
            try:
                chat_info = await context.bot.get_chat(f"@{link_uname}")
                title = chat_info.title or chat_info.effective_name or link_uname
                ctype = chat_info.type
                desc = chat_info.description or ""
                member_count = ""
                try:
                    mc = await context.bot.get_chat_member_count(chat_info.id)
                    member_count = f" ({mc} members)"
                except Exception:
                    pass
                resolved_links.append(f"- t.me/{link_uname} → **{title}** ({ctype}{member_count}): {desc[:200]}")
            except Exception:
                resolved_links.append(f"- t.me/{link_uname} → (private or inaccessible)")

    # ── Build context for the AI ────────────────────────────────────────────
    extra_context = ""
    chats_summary = get_user_chats_context(owner_id)
    if chats_summary:
        extra_context += f"\n{chats_summary}\n"
    if resolved_links:
        extra_context += "\nLinks shared in this message:\n" + "\n".join(resolved_links) + "\n"

    thinking_msg = None
    try:
        thinking_msg = await context.bot.send_message(
            chat_id=msg.chat_id,
            text="\u2728 *Thinking*",
            parse_mode="Markdown",
            business_connection_id=business_connection_id,
        )
    except TelegramError:
        pass

    enriched = msg.text
    if extra_context:
        enriched = f"{msg.text}\n\n[Context for you]:{extra_context}"
    try:
        reply, error_kind, error_msg = await asyncio.to_thread(
            get_ai_reply, owner_id, enriched, assistant_mode=True
        )
        if reply is None:
            text = "Sorry, I couldn't process that. Please try again in a moment."
            if thinking_msg:
                try:
                    await thinking_msg.edit_text(text)
                except TelegramError:
                    await context.bot.send_message(
                        chat_id=msg.chat_id, text=text,
                        business_connection_id=business_connection_id,
                    )
            else:
                await context.bot.send_message(
                    chat_id=msg.chat_id, text=text,
                    business_connection_id=business_connection_id,
                )
            return

        if thinking_msg:
            try:
                if len(reply) > 4096:
                    raise ValueError("too long")
                await thinking_msg.edit_text(reply, parse_mode="Markdown")
            except (BadRequest, ValueError):
                try:
                    await thinking_msg.delete()
                except TelegramError:
                    pass
                await context.bot.send_message(
                    chat_id=msg.chat_id, text=reply, parse_mode="Markdown",
                    business_connection_id=business_connection_id,
                )
        else:
            await context.bot.send_message(
                chat_id=msg.chat_id, text=reply, parse_mode="Markdown",
                business_connection_id=business_connection_id,
            )
    except Exception as e:
        logger.exception(f"Business assistant error: {e}")
        text = "Something went wrong. Please try again."
        if thinking_msg:
            try:
                await thinking_msg.edit_text(text)
            except TelegramError:
                pass


async def process_message(update, context, msg, business_connection_id=None):
    if not msg:
        return

    if not msg.text and not msg.document:
        return

    user = msg.from_user
    if not user or user.is_bot:
        return

    # ── Business assistant mode ────────────────────────────────────────────────
    # If this is a business connection message, route to the assistant handler
    # which bypasses the owner check and uses assistant personality.
    if business_connection_id:
        await process_business_assistant(update, context, msg, business_connection_id)
        return

    cfg = load_config()
    if cfg.OWNER_ID != 0 and user.id != cfg.OWNER_ID:
        logger.info(f"Blocked non-owner message from user {user.id}")
        try:
            await safe_reply(
                msg,
                ACCESS_DENIED_TEXT,
                parse_mode="Markdown",
                business_connection_id=business_connection_id,
                bot=context.bot,
            )
        except Exception:
            pass
        return

    # ── Standard Group/Supergroup Spam Guard ──────────────────────────────────────
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
                "*File is too large.*\nPlease upload a text file smaller than 500 KB.",
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
                "*Failed to download the file.*\nPlease try uploading again.",
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
                "*Empty file.*\nThe uploaded file contains no data.",
                parse_mode="Markdown",
                business_connection_id=business_connection_id,
                bot=context.bot,
            )
            return

        if ext in binary_extensions or b"\x00" in file_bytes:
            await safe_reply(
                msg,
                "*Unsupported file type.*\nMocco only supports text-based files (e.g., code files, logs, text documents).",
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
                "*Decoding failed.*\nCould not decode the file content. Please ensure it's a valid text file.",
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

    thinking_msg = None
    thinking_alive = True
    try:
        if business_connection_id:
            thinking_msg = await context.bot.send_message(
                chat_id=chat_id,
                text="\u2728 *Thinking*",
                parse_mode="Markdown",
                business_connection_id=business_connection_id,
            )
        else:
            thinking_msg = await msg.reply_text("\u2728 *Thinking*", parse_mode="Markdown")
    except TelegramError:
        pass

    async def _keep_typing():
        """Keep the native Telegram typing indicator alive while AI processes."""
        while thinking_alive:
            try:
                kw = {"chat_id": chat_id, "action": ChatAction.TYPING}
                if business_connection_id:
                    kw["business_connection_id"] = business_connection_id
                await context.bot.send_chat_action(**kw)
            except TelegramError:
                pass
            await asyncio.sleep(4)

    typing_task = asyncio.create_task(_keep_typing())

    try:
        reply, error_kind, error_msg = await asyncio.to_thread(get_ai_reply, user_id, user_msg)
        if reply is None:
            if error_kind == "rate_limited":
                text = (
                    "This model is rate-limited right now.\n\n"
                    "Quick fixes:\n"
                    "• /connect <provider> to use your own key (recommended)\n"
                    "• /model to pick a different model\n"
                    "• Wait a minute and retry (free-tier limits reset fast)"
                )
            elif error_kind == "auth":
                text = (
                    "Your API key was rejected by the provider.\n\n"
                    "Re-run /connect <provider> with a fresh key."
                )
            elif error_kind == "timeout":
                text = (
                    "The provider didn't respond in time.\n\n"
                    "Try /model to pick a faster model, or retry in a moment."
                )
            elif error_kind == "server":
                text = "The provider is having an outage. Please try again in a minute."
            elif error_kind == "bad_request":
                text = (
                    "That model rejected the request. It may not support this conversation.\n\n"
                    "Try /model to pick a different one."
                )
            else:
                text = (
                    "I couldn't generate a response right now.\n"
                    "This is likely a temporary issue — please try again in a few seconds."
                )
            logger.info(f"AI failure for user {user_id} (model={resolve_model(user_id)}): {error_kind} — {error_msg}")
            thinking_alive = False
            typing_task.cancel()
            if thinking_msg:
                try:
                    await thinking_msg.edit_text(text, parse_mode="Markdown")
                except TelegramError:
                    await safe_reply(
                        msg, text,
                        business_connection_id=business_connection_id,
                        bot=context.bot,
                    )
            else:
                await safe_reply(
                    msg, text,
                    business_connection_id=business_connection_id,
                    bot=context.bot,
                )
            return

        save_message(user_id, "user", user_msg)
        save_message(user_id, "assistant", reply)
        thinking_alive = False
        typing_task.cancel()
        if thinking_msg:
            try:
                if len(reply) > 4096:
                    raise ValueError("too long for edit")
                await thinking_msg.edit_text(reply, parse_mode="Markdown")
            except (BadRequest, ValueError):
                try:
                    await thinking_msg.delete()
                except TelegramError:
                    pass
                await safe_reply(
                    msg, reply,
                    business_connection_id=business_connection_id,
                    bot=context.bot,
                )
        else:
            await safe_reply(
                msg, reply,
                business_connection_id=business_connection_id,
                bot=context.bot,
            )
    except NoAPIKeyError as e:
        thinking_alive = False
        typing_task.cancel()
        logger.warning(f"No API key available for user {user_id}: {e}")
        text = (
            "*No API key is configured for chatting.*\n\n"
            "The bot owner hasn't set a fallback OpenRouter key, and you don't "
            "have one connected either. Run `/connect openrouter` (or `/connect openai`) "
            "to add your own — it stays encrypted and only you can use it."
        )
        if thinking_msg:
            try:
                await thinking_msg.edit_text(text, parse_mode="Markdown")
            except TelegramError:
                await safe_reply(msg, text, parse_mode="Markdown",
                                 business_connection_id=business_connection_id, bot=context.bot)
        else:
            await safe_reply(msg, text, parse_mode="Markdown",
                             business_connection_id=business_connection_id, bot=context.bot)
    except Exception as e:
        thinking_alive = False
        typing_task.cancel()
        logger.exception(f"process_message error: {e}")
        text = "Something went wrong on my end.\nPlease try sending your message again."
        if thinking_msg:
            try:
                await thinking_msg.edit_text(text)
            except TelegramError:
                await safe_reply(msg, text,
                                 business_connection_id=business_connection_id, bot=context.bot)
        else:
            await safe_reply(msg, text,
                             business_connection_id=business_connection_id, bot=context.bot)


async def handle_business_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.business_message
    if msg:
        await process_business_assistant(update, context, msg, msg.business_connection_id)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    user = msg.from_user
    if user and msg.text and not msg.text.startswith("/"):
        text_stripped = msg.text.strip()

        pending_provider = _pending_get(user.id)
        if pending_provider and is_known_provider(pending_provider):
            p = PROVIDERS[pending_provider]
            key = text_stripped
            # Delete the user's plaintext key message (best-effort; fails silently in private chats)
            try:
                await msg.delete()
            except TelegramError:
                pass

            # Cheap format check first to avoid hitting the network for obvious junk.
            if not looks_like_provider_key(pending_provider, key):
                PENDING_KEY.pop(user.id, None)
                hint = "/".join(p["key_hint"]) if p["key_hint"] else "(no fixed prefix)"
                await safe_reply(
                    msg,
                    f"*That doesn't look like a valid {p['label']} key.*\n"
                    f"Keys for {p['label']} typically start with: `{hint}`.\n"
                    f"Run `/connect {pending_provider}` to try again.",
                    parse_mode="Markdown",
                )
                return

            # Tell user we're verifying (verify_key is a network call, ~200-1000ms)
            await safe_reply(
                msg,
                f"Verifying your {p['label']} key live against {p['label']}...",
                parse_mode="Markdown",
            )
            result = await asyncio.to_thread(verify_key, pending_provider, key)
            if result != VERIFY_OK:
                PENDING_KEY.pop(user.id, None)
                if result == VERIFY_TRANSIENT:
                    await safe_reply(
                        msg,
                        f"*{p['label']} is temporarily unreachable.*\n"
                        f"Their servers didn't respond (rate limit or outage).\n"
                        f"Please try `/connect {pending_provider}` again in a minute.",
                        parse_mode="Markdown",
                    )
                else:
                    await safe_reply(
                        msg,
                        f"*{p['label']} rejected that key.*\n"
                        f"It may be revoked, mistyped, or missing required scopes.\n"
                        f"Run `/connect {pending_provider}` to try again.",
                        parse_mode="Markdown",
                    )
                return

            ok = await _save_user_key(user.id, pending_provider, key)
            PENDING_KEY.pop(user.id, None)
            if ok:
                routing_note = (
                    f"\n\n_Models prefixed with `{p['direct_route_prefix']}` will now be routed "
                    f"directly to {p['label']} (cheaper than via OpenRouter)._"
                    if p.get("direct_route_prefix") else ""
                )
                await safe_reply(
                    msg,
                    f"*{p['label']} key verified and saved!*\n\n"
                    f"Your key is encrypted; only you can use it. "
                    f"Run `/keys` to see all your providers, `/model` to pick a model."
                    f"{routing_note}\n\n"
                    f"*Please delete your message above containing the key* so it isn't "
                    f"visible in your chat history.",
                    parse_mode="Markdown",
                )
            else:
                await safe_reply(
                    msg,
                    "*Failed to save your key.*\nPlease try again with `/connect`.",
                    parse_mode="Markdown",
                )
            return

        # Defensive: user pasted what looks like an API key without running /connect first.
        suspicious_prefixes = ("sk-or-", "sk-ant-", "sk-proj-", "sk-", "gsk_", "AIza")
        if (
            any(text_stripped.startswith(pref) for pref in suspicious_prefixes)
            and len(text_stripped) >= 40
            and not any(c.isspace() for c in text_stripped)
        ):
            try:
                await msg.delete()
            except TelegramError:
                pass
            await safe_reply(
                msg,
                "*That looks like an API key.*\n"
                "I won't save or process it because you didn't run `/connect` first.\n\n"
                "Run `/connect` and pick the right provider to save your key properly.\n"
                "_Please delete your message above containing the key._",
                parse_mode="Markdown",
            )
            return
    await process_message(update, context, msg)


@owner_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    ensure_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name)
    clear_history(msg.from_user.id)
    await msg.reply_text(WELCOME_TEXT, parse_mode="Markdown")


@owner_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    await msg.reply_text(HELP_TEXT, parse_mode="Markdown", reply_markup=build_menu_keyboard())


@owner_only
async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    await msg.reply_text(
        "*Main Menu* — What would you like to do?",
        parse_mode="Markdown",
        reply_markup=build_menu_keyboard(),
    )


@owner_only
async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    clear_history(msg.from_user.id)
    await safe_reply(
        msg,
        "*Conversation cleared.*\nStarting fresh — what would you like to talk about?",
        parse_mode="Markdown",
    )


@owner_only
async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    query = " ".join(context.args).strip()
    if not query:
        await safe_reply(
            msg,
            "*Web Search*\n\n"
            "Please provide a search query.\n"
            "_Usage:_ `/search <your query>`\n"
            "_Example:_ `/search latest AI news 2026`",
            parse_mode="Markdown",
        )
        return
    search_msg = None
    try:
        search_msg = await msg.reply_text("\u2728 *Searching...*", parse_mode="Markdown")
    except TelegramError:
        pass
    search_text, _ = await asyncio.to_thread(web_search, query)
    reply = f"*Results for:* `{query}`\n\n{search_text}"
    if search_msg:
        try:
            if len(reply) > 4096:
                raise ValueError("too long")
            await search_msg.edit_text(reply, parse_mode="Markdown")
        except (BadRequest, ValueError):
            try:
                await search_msg.delete()
            except TelegramError:
                pass
            await safe_reply(msg, reply, parse_mode="Markdown")
    else:
        await safe_reply(msg, reply, parse_mode="Markdown")


@owner_only
async def cmd_summarize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    text = " ".join(context.args).strip()
    if not text:
        await safe_reply(
            msg,
            "*Summarize Text*\n\n"
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
        model_id = resolve_model(msg.from_user.id)
        client, resolved_model = get_client_for_chat(msg.from_user.id, model_id)
        resp = await asyncio.to_thread(
            lambda: client.chat.completions.create(
                model=resolved_model,
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
            f"*Summary* _({word_count} words, condensed)_\n\n{out}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"summarize failed: {e}")
        if isinstance(e, NoAPIKeyError):
            await safe_reply(
                msg,
                "*No API key is configured for summarizing.*\n"
                "Run `/connect` to add your own.",
                parse_mode="Markdown",
            )
        else:
            await safe_reply(msg, "*Summarization failed.*\nPlease try again.", parse_mode="Markdown")


@owner_only
async def cmd_translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    if len(context.args) < 2:
        await safe_reply(
            msg,
            "*Translate Text*\n\n"
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
        model_id = resolve_model(msg.from_user.id)
        client, resolved_model = get_client_for_chat(msg.from_user.id, model_id)
        resp = await asyncio.to_thread(
            lambda: client.chat.completions.create(
                model=resolved_model,
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
            f"*Translation to {lang}*\n\n"
            f"*Original:* _{text[:200]}_\n\n"
            f"*Result:* {out}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"translate failed: {e}")
        if isinstance(e, NoAPIKeyError):
            await safe_reply(
                msg,
                "*No API key is configured for translating.*\n"
                "Run `/connect` to add your own.",
                parse_mode="Markdown",
            )
        else:
            await safe_reply(msg, f"*Translation to {lang} failed.*\nPlease try again.", parse_mode="Markdown")


@owner_only
async def cmd_setprompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    prompt = " ".join(context.args).strip()
    if not prompt:
        await safe_reply(
            msg,
            "*Set Custom Personality*\n\n"
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
        f"*Custom personality set.*\n\nI'll follow these instructions:\n_{prompt}_\n\n"
        f"Use `/clearprompt` to reset to default.",
        parse_mode="Markdown",
    )


@owner_only
async def cmd_clearprompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    from .db import set_custom_prompt
    set_custom_prompt(msg.from_user.id, None)
    await safe_reply(
        msg,
        "*Custom personality removed.*\nI'm back to my default behavior.",
        parse_mode="Markdown",
    )


MODELS_PAGE_SIZE = 6
# Maps user_id -> (provider_name, expiry_unix_ts). Entries past expiry are treated as absent.
PENDING_KEY_TTL_SECONDS = 600  # 10 minutes
PENDING_KEY: dict[int, tuple[str, float]] = {}


def _pending_get(user_id: int) -> Optional[str]:
    """Return the pending provider for this user, or None if expired/missing."""
    import time as _time
    entry = PENDING_KEY.get(user_id)
    if entry is None:
        return None
    provider, expiry = entry
    if _time.time() > expiry:
        PENDING_KEY.pop(user_id, None)
        return None
    return provider


def _pending_set(user_id: int, provider: str) -> None:
    import time as _time
    PENDING_KEY[user_id] = (provider, _time.time() + PENDING_KEY_TTL_SECONDS)


def _build_provider_keyboard(action: str, only_connected_for: Optional[int] = None) -> InlineKeyboardMarkup:
    """Build a 2-column keyboard of providers.

    action: "connect" or "disconnect" — used in callback_data prefix.
    only_connected_for: if set, restrict to providers this user has actually connected.
    """
    connected = set(user_connected_providers(only_connected_for)) if only_connected_for else None
    rows: List[List[InlineKeyboardButton]] = []
    pair: List[InlineKeyboardButton] = []
    for name, p in PROVIDERS.items():
        if connected is not None and name not in connected:
            continue
        label = p['label']
        pair.append(InlineKeyboardButton(label, callback_data=f"key:{action}:{name}"))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([InlineKeyboardButton("Cancel", callback_data="key:cancel")])
    return InlineKeyboardMarkup(rows)


def _short_model_label(m: dict) -> str:
    name = m.get("name", m["id"])
    if name.endswith(" (free)"):
        name = name[: -len(" (free)")]
    short = name.split(":")[-1].strip()
    return short[:32] if len(short) > 32 else short


def _format_model_label(m: dict) -> str:
    """Format a model for the picker:
    - OpenRouter free: 'Model Name: free'
    - OpenRouter paid: 'Model Name: paid'
    - Direct provider: 'Model Name via <Provider>'
    """
    base = _short_model_label(m)
    if m.get("via"):
        return f"{base} via {m['via']}"
    suffix = ": free" if m.get("is_free") else ": paid"
    return base + suffix


def _format_ctx(n: int) -> str:
    if n >= 1_000_000:
        return f"{n // 1_000_000}M"
    if n >= 1_000:
        return f"{n // 1_000}K"
    return str(n)


def _build_models_keyboard(
    models: List[dict], page: int, current: str, has_user_key: bool
) -> InlineKeyboardMarkup:
    total = len(models)
    start = page * MODELS_PAGE_SIZE
    end = min(start + MODELS_PAGE_SIZE, total)
    rows = []
    skipped = 0
    for m in models[start:end]:
        cb = f"model:pick:{page}:{m['id']}"
        # Telegram caps callback_data at 64 bytes; skip overlong IDs to avoid API errors.
        if len(cb.encode("utf-8")) > 64:
            skipped += 1
            continue
        marker = "* " if m["id"] == current else "  "
        ctx_tag = f" ({_format_ctx(m.get('context_length', 0))})" if m.get("context_length") else ""
        label = f"{marker}{_format_model_label(m)}{ctx_tag}"
        if len(label) > 60:
            label = label[:60]
        rows.append([InlineKeyboardButton(
            label,
            callback_data=cb,
        )])
    if skipped:
        logger.warning(f"Models page {page}: skipped {skipped} model(s) with overlong IDs")
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("< Prev", callback_data=f"model:page:{page - 1}"))
    nav.append(InlineKeyboardButton(
        f"Page {page + 1}/{(total + MODELS_PAGE_SIZE - 1) // MODELS_PAGE_SIZE}",
        callback_data="model:none",
    ))
    if end < total:
        nav.append(InlineKeyboardButton("Next >", callback_data=f"model:page:{page + 1}"))
    rows.append(nav)
    action_row = [
        InlineKeyboardButton("Connect key", callback_data="model:connect"),
        InlineKeyboardButton("Refresh", callback_data="model:refresh"),
    ]
    if has_user_key:
        action_row.append(InlineKeyboardButton("Disconnect", callback_data="model:disconnect"))
    action_row.append(InlineKeyboardButton("Reset model", callback_data="model:reset"))
    rows.append(action_row)
    return InlineKeyboardMarkup(rows)


@owner_only
async def cmd_connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """`/connect` opens the provider picker. `/connect <provider>` skips straight to that one."""
    msg = update.message
    if not msg:
        return
    user_id = msg.from_user.id
    ensure_user(user_id, msg.from_user.username, msg.from_user.first_name)
    if db_is_blacklisted(user_id):
        return

    from .crypto import _get_key, EncryptionKeyMissing
    try:
        _get_key()  # triggers DB lookup / auto-generation
    except EncryptionKeyMissing as e:
        await safe_reply(
            msg,
            f"*Key storage is not available right now.*\n{str(e)}",
            parse_mode="Markdown",
        )
        return

    args = context.args or []
    if args and is_known_provider(args[0].lower()):
        await _prompt_for_provider_key(msg, user_id, args[0].lower())
        return

    await msg.reply_text(
        "*Connect a provider*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Pick which API key you want to add.\n"
        "Your key is *verified live*, then *encrypted* and stored — only you can use it.\n\n"
        "_Tip: shortcut `/connect openai`, `/connect anthropic`, etc._",
        parse_mode="Markdown",
        reply_markup=_build_provider_keyboard("connect"),
    )


async def _prompt_for_provider_key(msg, user_id: int, provider: str, via_callback=None):
    """Send the 'paste your key' instructions for the chosen provider."""
    p = PROVIDERS[provider]
    _pending_set(user_id, provider)
    text = (
        f"*Connect {p['label']}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{p['blurb']}\n\n"
        f"*How to get one:*\n"
        f"1. Go to [{p['label']} keys page]({p['signup_url']})\n"
        f"2. Create / copy an API key\n"
        f"3. Paste it as your next message here\n\n"
        f"Your key will be *verified live* against {p['label']} before saving.\n"
        f"You have *{PENDING_KEY_TTL_SECONDS // 60} minutes* — send `/cancel` to abort."
    )
    if via_callback is not None:
        await via_callback.edit_message_text(
            text,
            parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Cancel", callback_data="key:cancel")]
            ]),
        )
    else:
        await safe_reply(msg, text, parse_mode="Markdown")


@owner_only
async def cmd_disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    user_id = msg.from_user.id
    ensure_user(user_id, msg.from_user.username, msg.from_user.first_name)
    PENDING_KEY.pop(user_id, None)

    args = context.args or []
    if args and is_known_provider(args[0].lower()):
        provider = args[0].lower()
        if delete_user_api_key(user_id, provider):
            p = PROVIDERS[provider]
            await safe_reply(
                msg,
                f"*Disconnected {p['label']}.*\nYour stored key has been removed.",
                parse_mode="Markdown",
            )
        else:
            await safe_reply(msg, "You don't have that provider connected.", parse_mode="Markdown")
        return

    connected = user_connected_providers(user_id)
    if not connected:
        await safe_reply(msg, "You don't have any provider keys connected.", parse_mode="Markdown")
        return

    await msg.reply_text(
        "*Disconnect a provider*\n━━━━━━━━━━━━━━━━━━━━\nPick which key to remove:",
        parse_mode="Markdown",
        reply_markup=_build_provider_keyboard("disconnect", only_connected_for=user_id),
    )


@owner_only
async def cmd_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    user_id = msg.from_user.id
    ensure_user(user_id, msg.from_user.username, msg.from_user.first_name)
    connected = set(user_connected_providers(user_id))
    lines = ["*Your connected providers*", "━━━━━━━━━━━━━━━━━━━━"]
    for name, p in PROVIDERS.items():
        mark = "[x]" if name in connected else "[ ]"
        suffix = "*connected*" if name in connected else "_not connected_"
        lines.append(f"{mark} {p['label']} — {suffix}")
    lines.append("")
    lines.append("Use `/connect` to add more, `/disconnect` to remove.")
    await safe_reply(msg, "\n".join(lines), parse_mode="Markdown")


@owner_only
async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    user_id = msg.from_user.id
    if PENDING_KEY.pop(user_id, None):
        await safe_reply(msg, "Cancelled. No key was saved.", parse_mode="Markdown")
    else:
        await safe_reply(msg, "Nothing to cancel.", parse_mode="Markdown")


@owner_only
async def callback_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user_id = query.from_user.id
    parts = (query.data or "").split(":", 2)
    if len(parts) < 2 or parts[0] != "key":
        return
    action = parts[1]

    if action == "cancel":
        PENDING_KEY.pop(user_id, None)
        await safe_edit(query, text="Cancelled. No changes made.")
        return

    if len(parts) < 3 or not is_known_provider(parts[2]):
        return
    provider = parts[2]

    if action == "connect":
        await _prompt_for_provider_key(query.message, user_id, provider, via_callback=query)
        return

    if action == "disconnect":
        if delete_user_api_key(user_id, provider):
            p = PROVIDERS[provider]
            await safe_edit(
                query,
                text=f"*Disconnected {p['label']}.*\nYour stored key has been removed.",
                parse_mode="Markdown",
            )
        else:
            await safe_edit(query, text="That provider wasn't connected.", parse_mode="Markdown")
        return


async def _save_user_key(user_id: int, provider: str, plaintext: str) -> bool:
    def _do_save() -> bool:
        cipher = encrypt_api_key(plaintext.strip())
        return set_user_api_key(user_id, provider, cipher)
    try:
        return await asyncio.to_thread(_do_save)
    except Exception as e:
        logger.error(f"Failed to save user key ({provider}): {e}")
        return False


@owner_only
async def cmd_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    user_id = msg.from_user.id
    ensure_user(user_id, msg.from_user.username, msg.from_user.first_name)
    if db_is_blacklisted(user_id):
        return

    current = get_chat_model(user_id) or resolve_model()
    default = load_config().CHAT_MODEL
    has_key = user_has_key(user_id)
    connected = user_connected_providers(user_id)

    args = context.args or []
    if args and args[0].lower() in ("reset", "default", "clear"):
        set_chat_model(user_id, None)
        await safe_reply(
            msg,
            f"↩️ *Model reset to default.*\n\nYou're now using: `{default}`",
            parse_mode="Markdown",
        )
        return

    models = await asyncio.to_thread(fetch_all_models, False, user_id)
    if not models:
        await safe_reply(
            msg,
            "*Could not load the model list right now.*\nPlease try again in a moment.",
            parse_mode="Markdown",
        )
        return

    if connected:
        provider_chips = ", ".join(PROVIDERS[p]['label'] for p in connected)
        direct_providers = [p for p in connected if PROVIDERS[p].get("direct_route_prefix")]
        if direct_providers:
            key_status = (
                f"*Your keys:* {provider_chips} ({len(connected)} connected)\n"
                f"_Showing only models from your connected providers. "
                f"Disconnect one from /keys to see the full catalog._"
            )
        else:
            key_status = f"*Your keys:* {provider_chips} ({len(connected)} connected)"
    else:
        key_status = "*Your keys:* none connected — showing the public catalog. `/connect` to add your own."
    body = (
        f"*Choose your AI model*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"*Current:* `{current}`\n"
        f"*Default:* `{default}`\n"
        f"{key_status}\n\n"
        f"Models labeled `free` work with the bot's key. Models labeled `paid` need *your own* key "
        f"for the matching provider (or any OpenRouter key).\n"
        f"Use `/model reset` to go back to the default. Use `/keys` to manage providers."
    )
    await msg.reply_text(
        body,
        parse_mode="Markdown",
        reply_markup=_build_models_keyboard(models, 0, current, has_key),
    )


@owner_only
async def callback_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    data = (query.data or "").split(":", 1)
    if len(data) < 2 or data[0] != "menu":
        return
    action = data[1]
    user_id = query.from_user.id

    if action == "reset":
        clear_history(user_id)
        await query.message.reply_text(
            "*Conversation cleared.*\nStarting fresh — what would you like to talk about?",
            parse_mode="Markdown",
        )
        return

    if action == "help":
        await query.message.reply_text(
            HELP_TEXT, parse_mode="Markdown", reply_markup=build_menu_keyboard()
        )
        return

    hints = {
        "search": (
            "*Web Search*\n\n"
            "Type:\n`/search <your query>`\n\n"
            "_Example:_ `/search latest AI news 2026`"
        ),
        "summarize": (
            "*Summarize*\n\n"
            "Type:\n`/summarize <text to summarize>`"
        ),
        "setprompt": (
            "*Set Custom Personality*\n\n"
            "Type:\n`/setprompt <instructions>`\n\n"
            "_Example:_ `/setprompt Act as a senior Python developer.`"
        ),
    }
    if action in hints:
        await query.message.reply_text(hints[action], parse_mode="Markdown")


@owner_only
async def callback_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user_id = query.from_user.id
    data = (query.data or "").split(":")

    if len(data) < 2 or data[0] != "model":
        return

    action = data[1]

    if action == "none":
        return

    if action == "connect":
        await safe_edit(
            query,
            text=(
                "*Connect a provider*\n\n"
                "Pick which API key you want to add.\n"
                "Your key is verified live, then encrypted and stored."
            ),
            parse_mode="Markdown",
            reply_markup=_build_provider_keyboard("connect"),
        )
        return

    if action == "disconnect":
        connected = user_connected_providers(user_id)
        if not connected:
            await query.answer("No keys connected", show_alert=False)
            await safe_edit(
                query,
                text="You don't have any provider keys connected.",
                parse_mode="Markdown",
            )
            return
        await safe_edit(
            query,
            text="*Disconnect a provider*\n\nPick which key to remove:",
            parse_mode="Markdown",
            reply_markup=_build_provider_keyboard("disconnect", only_connected_for=user_id),
        )
        return

    if action == "open":
        models = await asyncio.to_thread(fetch_all_models, False, user_id)
        current = get_chat_model(user_id) or resolve_model()
        has_key = user_has_key(user_id)
        connected = user_connected_providers(user_id)
        if not models:
            await safe_edit(
                query,
                text="*Could not load the model list right now.*\nPlease try again in a moment.",
                parse_mode="Markdown",
            )
            return
        if connected:
            provider_chips = ", ".join(PROVIDERS[p]['label'] for p in connected)
            direct_providers = [p for p in connected if PROVIDERS[p].get("direct_route_prefix")]
            if direct_providers:
                key_status = (
                    f"*Your keys:* {provider_chips} ({len(connected)} connected)\n"
                    f"_Showing only models from your connected providers. "
                    f"Disconnect one from /keys to see the full catalog._"
                )
            else:
                key_status = f"*Your keys:* {provider_chips} ({len(connected)} connected)"
        else:
            key_status = "*Your keys:* none connected — showing the public catalog. `/connect` to add your own."
        body = (
            f"*Choose your AI model*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"*Current:* `{current}`\n"
            f"*Default:* `{load_config().CHAT_MODEL}`\n"
            f"{key_status}\n\n"
            f"Models labeled `free` work with the bot's key. Models labeled `paid` need *your own* key."
        )
        await safe_edit(
            query,
            text=body,
            parse_mode="Markdown",
            reply_markup=_build_models_keyboard(models, 0, current, has_key),
        )
        return

    if action == "refresh":
        models = await asyncio.to_thread(fetch_all_models, True, user_id)
        current = get_chat_model(user_id) or resolve_model()
        has_key = user_has_key(user_id)
        await safe_edit(query, reply_markup=_build_models_keyboard(models, 0, current, has_key))
        return

    if action == "reset":
        set_chat_model(user_id, None)
        default = load_config().CHAT_MODEL
        await safe_edit(
            query,
            text=f"*Model reset to default.*\n\nYou're now using: `{default}`",
            parse_mode="Markdown",
        )
        return

    if action == "page":
        page = int(data[2]) if len(data) > 2 else 0
        models = await asyncio.to_thread(fetch_all_models, False, user_id)
        current = get_chat_model(user_id) or resolve_model()
        has_key = user_has_key(user_id)
        if not models:
            return
        max_page = max(0, (len(models) - 1) // MODELS_PAGE_SIZE)
        page = max(0, min(page, max_page))
        await safe_edit(query, reply_markup=_build_models_keyboard(models, page, current, has_key))
        return

    if action == "pick":
        model_id = ":".join(data[3:])
        if not model_id:
            return
        # Guard: paid models require the user's own key for the matching provider,
        # otherwise the bot's account would be billed for this user's chats.
        models = await asyncio.to_thread(fetch_all_models, False, user_id)
        model_info = next((m for m in models if m["id"] == model_id), None)
        if model_info and not model_info["is_free"] and not can_use_paid_model(user_id, model_id):
            await query.answer("Paid model — connect a matching key first", show_alert=True)
            await query.message.reply_text(
                "*That model requires your own API key.*\n\n"
                "Connect either an *OpenRouter* key (works for any model) or the "
                "direct provider key for this model (cheaper). Tap `/connect`.\n"
                "Or pick a model not marked `paid`.",
                parse_mode="Markdown",
            )
            return
        set_chat_model(user_id, model_id)
        await safe_edit(
            query,
            text=f"*Model set!*\n\nYou're now using: `{model_id}`\n\n"
            f"_Tip: `/model reset` to go back to default, `/keys` to manage your providers._",
            parse_mode="Markdown",
        )
        return


@owner_only
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not is_owner(update):
        return
    users, msgs, blk = get_stats()
    active = users - blk
    await safe_reply(
        msg,
        f"*Mocco — Live Stats*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Total users:     *{users}*\n"
        f"Active users:    *{active}*\n"
        f"Blacklisted:    *{blk}*\n"
        f"Total messages: *{msgs}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{datetime.now(timezone.utc).strftime('%B %d, %Y  %H:%M UTC')}",
        parse_mode="Markdown",
    )


@owner_only
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
        await safe_reply(msg, "Invalid user ID.")
        return
    cfg = load_config()
    if target_id == msg.from_user.id or target_id == cfg.OWNER_ID or target_id == cfg.BOT_ID:
        await safe_reply(
            msg,
            "You can't blacklist yourself, the bot owner, or the bot itself.",
            parse_mode="Markdown",
        )
        return
    if set_blacklist(target_id, True):
        await safe_reply(msg, f"User `{target_id}` blacklisted.", parse_mode="Markdown")
    else:
        await safe_reply(msg, "Failed to blacklist user.")


@owner_only
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
        await safe_reply(msg, "Invalid user ID.")
        return
    if set_blacklist(target_id, False):
        await safe_reply(msg, f"User `{target_id}` unblacklisted.", parse_mode="Markdown")
    else:
        await safe_reply(msg, "Failed to update user.")


@owner_only
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
    await safe_reply(msg, f"Broadcasting to {len(user_ids)} users...")
    sent = 0
    failed = 0
    sem = asyncio.Semaphore(BROADCAST_CHUNK)

    async def send_one(uid: int):
        nonlocal sent, failed
        async with sem:
            try:
                await context.bot.send_message(chat_id=uid, text=f"{text}")
                sent += 1
            except Exception:
                failed += 1

    await asyncio.gather(*[send_one(uid) for uid in user_ids])
    await safe_reply(
        msg,
        f"*Broadcast complete.*\nSent: *{sent}* | Failed: *{failed}*",
        parse_mode="Markdown",
    )


@owner_only
async def cmd_addchat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register a channel/group the user owns or admins for the assistant."""
    msg = update.message
    if not msg:
        return
    args = context.args or []
    if not args:
        await safe_reply(msg, "Usage: /addchat @channelusername or /addchat https://t.me/...",
                         parse_mode="Markdown")
        return
    raw = " ".join(args).strip()
    username = raw.replace("https://t.me/", "").replace("@", "").split("/")[0].split("?")[0]
    if not username:
        await safe_reply(msg, "Could not parse the chat link. Use @username or t.me/username.")
        return
    try:
        chat = await context.bot.get_chat(f"@{username}")
        cid = chat.id
        title = chat.title or chat.effective_name or username
        ctype = chat.type  # "channel", "group", "supergroup"
        uname = chat.username or ""
        administrator = False
        try:
            me = await context.bot.get_me()
            member = await chat.get_member(me.id)
            administrator = member.status in ("administrator", "creator")
        except Exception:
            pass
        add_user_chat(msg.from_user.id, cid, title, ctype, uname, administrator)
        role = "admin" if administrator else "member"
        await safe_reply(
            msg,
            f"*Added:* {title} (@{uname}) — {ctype} ({role})",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning(f"addchat failed for {username}: {e}")
        await safe_reply(
            msg,
            f"*Could not find* `{username}`.\n"
            "Make sure the chat is public and the bot is a member.",
            parse_mode="Markdown",
        )


@owner_only
async def cmd_removechat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    args = context.args or []
    if not args:
        await safe_reply(msg, "Usage: /removechat @channelusername")
        return
    raw = " ".join(args).strip()
    username = raw.replace("https://t.me/", "").replace("@", "").split("/")[0].split("?")[0]
    chats = get_user_chats(msg.from_user.id)
    for c in chats:
        if c.get("chat_username", "").lower() == username.lower():
            remove_user_chat(msg.from_user.id, c["chat_id"])
            await safe_reply(msg, f"*Removed:* {c['chat_title']}", parse_mode="Markdown")
            return
    await safe_reply(msg, f"No registered chat found for `{username}`.", parse_mode="Markdown")


@owner_only
async def cmd_mychats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    chats = get_user_chats(msg.from_user.id)
    if not chats:
        await safe_reply(
            msg,
            "*Your registered chats:*\nNone yet.\n\n"
            "Use `/addchat @channelusername` to add channels or groups you own/admin.\n"
            "The assistant will know about them when people ask.",
            parse_mode="Markdown",
        )
        return
    lines = [f"*Your chats ({len(chats)}):*"]
    for c in chats:
        role = "admin" if c["is_admin"] else "member"
        uname = f" (@{c['chat_username']})" if c.get("chat_username") else ""
        lines.append(f"- {c['chat_title']}{uname} — {c['chat_type']} ({role})")
    lines.append("\nUse `/addchat` to add more, `/removechat` to remove.")
    await safe_reply(msg, "\n".join(lines), parse_mode="Markdown")


async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-track when the OWNER adds the bot to a group/channel they manage."""
    member_update = update.my_chat_member
    if not member_update:
        return
    user = member_update.from_user
    owner_id = load_config().OWNER_ID
    if not owner_id or not user or user.id != owner_id:
        return
    chat = member_update.chat
    new_status = member_update.new_chat_member.status
    old_status = member_update.old_chat_member.status
    cid = chat.id
    title = chat.title or chat.effective_name or str(cid)
    ctype = chat.type
    uname = chat.username or ""
    is_admin = new_status in ("administrator", "creator")
    if new_status in ("administrator", "creator", "member"):
        add_user_chat(owner_id, cid, title, ctype, uname, is_admin)
        logger.info(f"Owner added bot to {title} ({ctype}) — admin={is_admin}")
    elif new_status in ("left", "kicked", "restricted") and old_status not in (new_status,):
        remove_user_chat(owner_id, cid)
        logger.info(f"Bot removed from {title} ({ctype}) by owner")


async def on_telegram_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch-all for unhandled exceptions in any handler.

    Logs the full traceback (replaces the 'No error handlers are registered'
    stderr spam) and, when the access gate allows it, sends the user a brief
    'something went wrong' reply so they aren't left staring at a silent bot.
    """
    logger.exception(f"Unhandled exception in update: {context.error}")

    cfg = load_config()
    upd = update if isinstance(update, Update) else None
    user = upd.effective_user if upd else None
    if cfg.OWNER_ID != 0 and (not user or user.id != cfg.OWNER_ID):
        return

    if upd and getattr(upd, "effective_message", None):
        try:
            await upd.effective_message.reply_text(
                "*Something went wrong on my end.*\nPlease try again in a moment.",
                parse_mode="Markdown",
            )
        except Exception:
            pass
    elif upd and getattr(upd, "callback_query", None):
        try:
            await upd.callback_query.answer("Something went wrong.", show_alert=False)
        except Exception:
            pass


def register_handlers(app):
    """Register all Mocco handlers to the telegram application instance."""
    app.add_error_handler(on_telegram_error)
    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("help",        cmd_help))
    app.add_handler(CommandHandler("menu",        cmd_menu))
    app.add_handler(CommandHandler("reset",       cmd_reset))
    app.add_handler(CommandHandler("search",      cmd_search))
    app.add_handler(CommandHandler("summarize",   cmd_summarize))
    app.add_handler(CommandHandler("translate",   cmd_translate))
    app.add_handler(CommandHandler("setprompt",   cmd_setprompt))
    app.add_handler(CommandHandler("clearprompt", cmd_clearprompt))
    app.add_handler(CommandHandler("model",       cmd_model))
    app.add_handler(CommandHandler("connect",     cmd_connect))
    app.add_handler(CommandHandler("disconnect",  cmd_disconnect))
    app.add_handler(CommandHandler("keys",        cmd_keys))
    app.add_handler(CommandHandler("cancel",      cmd_cancel))
    app.add_handler(CallbackQueryHandler(callback_model, pattern=r"^model:"))
    app.add_handler(CallbackQueryHandler(callback_menu,  pattern=r"^menu:"))
    app.add_handler(CallbackQueryHandler(callback_key,   pattern=r"^key:"))
    app.add_handler(CommandHandler("stats",       cmd_stats))
    app.add_handler(CommandHandler("blacklist",   cmd_blacklist))
    app.add_handler(CommandHandler("unblacklist", cmd_unblacklist))
    app.add_handler(CommandHandler("broadcast",   cmd_broadcast))
    app.add_handler(CommandHandler("addchat",     cmd_addchat))
    app.add_handler(CommandHandler("removechat",  cmd_removechat))
    app.add_handler(CommandHandler("mychats",     cmd_mychats))

    app.add_handler(ChatMemberHandler(handle_my_chat_member))

    app.add_handler(MessageHandler(filters.UpdateType.BUSINESS_MESSAGE, handle_business_message))
    app.add_handler(MessageHandler((filters.TEXT | filters.Document.ALL) & ~filters.COMMAND, handle_message))
