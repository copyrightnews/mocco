import logging
import os
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime, timezone, timedelta
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from .config import load_config
from .migrate import apply_migrations

logger = logging.getLogger("mocco")

_config = None
_pool: Optional[pool.ThreadedConnectionPool] = None

def get_config():
    global _config
    if _config is None:
        _config = load_config()
    return _config

def get_pool() -> pool.ThreadedConnectionPool:
    """Create or return a ThreadedConnectionPool with RealDictCursor as default."""
    global _pool
    if _pool is None:
        cfg = get_config()
        _pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=cfg.DATABASE_URL,
            cursor_factory=RealDictCursor,
        )
        logger.info("DB connection pool created (1–10 connections)")
    return _pool

class db_conn:
    """Context manager that yields a raw connection from the pool."""

    def __enter__(self):
        self.conn = get_pool().getconn()
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
        finally:
            get_pool().putconn(self.conn)
        return False


def init_db():
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id        BIGINT PRIMARY KEY,
                    username       TEXT,
                    first_name     TEXT,
                    custom_prompt  TEXT,
                    chat_model     TEXT,
                    is_blacklisted BOOLEAN DEFAULT FALSE,
                    message_count  INTEGER DEFAULT 0,
                    created_at     TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_api_keys (
                    user_id     BIGINT NOT NULL,
                    provider    TEXT NOT NULL,
                    key_cipher  TEXT NOT NULL,
                    created_at  TIMESTAMP DEFAULT NOW(),
                    updated_at  TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (user_id, provider)
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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bot_config (
                    key        TEXT PRIMARY KEY,
                    value      TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_chats (
                    owner_id    BIGINT NOT NULL,
                    chat_id     BIGINT NOT NULL,
                    chat_title  TEXT,
                    chat_type   TEXT,
                    chat_username TEXT,
                    is_admin    BOOLEAN DEFAULT FALSE,
                    added_at    TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (owner_id, chat_id)
                );
            """)
            try:
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS chat_model TEXT")
            except Exception:
                pass
        migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")
        try:
            apply_migrations(conn, migrations_dir)
        except Exception as e:
            logger.exception(f"Migration runner failed (continuing without migrations): {e}")
        conn.commit()
    logger.info("Database initialized")


def ensure_user(user_id: int, username: Optional[str] = None, first_name: Optional[str] = None):
    try:
        with db_conn() as conn:
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


def is_blacklisted(user_id: int) -> bool:
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT is_blacklisted FROM users WHERE user_id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
                return bool(row and row["is_blacklisted"])
    except Exception as e:
        logger.error(f"is_blacklisted failed: {e}")
        return False


def get_history(user_id: int, limit: int = 14) -> List[dict]:
    try:
        with db_conn() as conn:
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


def save_message(user_id: int, role: str, content: str):
    try:
        with db_conn() as conn:
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


def clear_history(user_id: int):
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM messages WHERE user_id = %s", (user_id,))
                conn.commit()
    except Exception as e:
        logger.error(f"clear_history failed: {e}")


def get_custom_prompt(user_id: int) -> Optional[str]:
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT custom_prompt FROM users WHERE user_id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
                return row["custom_prompt"] if row and row["custom_prompt"] else None
    except Exception as e:
        logger.error(f"get_custom_prompt failed: {e}")
        return None


def set_custom_prompt(user_id: int, prompt: Optional[str]):
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET custom_prompt = %s WHERE user_id = %s",
                    (prompt, user_id),
                )
                conn.commit()
    except Exception as e:
        logger.error(f"set_custom_prompt failed: {e}")


def get_chat_model(user_id: int) -> Optional[str]:
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT chat_model FROM users WHERE user_id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
                return row["chat_model"] if row and row["chat_model"] else None
    except Exception as e:
        logger.error(f"get_chat_model failed: {e}")
        return None


def set_chat_model(user_id: int, model: Optional[str]):
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (user_id, chat_model)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO UPDATE
                    SET chat_model = EXCLUDED.chat_model
                    """,
                    (user_id, model),
                )
                conn.commit()
    except Exception as e:
        logger.error(f"set_chat_model failed: {e}")


def get_user_api_key(user_id: int, provider: str) -> Optional[str]:
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT key_cipher FROM user_api_keys WHERE user_id = %s AND provider = %s",
                    (user_id, provider),
                )
                row = cur.fetchone()
                return row["key_cipher"] if row else None
    except Exception as e:
        logger.error(f"get_user_api_key failed: {e}")
        return None


def set_user_api_key(user_id: int, provider: str, key_cipher: str) -> bool:
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_api_keys (user_id, provider, key_cipher)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, provider) DO UPDATE
                    SET key_cipher = EXCLUDED.key_cipher,
                        updated_at = NOW()
                    """,
                    (user_id, provider, key_cipher),
                )
                conn.commit()
        return True
    except Exception as e:
        logger.error(f"set_user_api_key failed: {e}")
        return False


def delete_user_api_key(user_id: int, provider: str) -> bool:
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM user_api_keys WHERE user_id = %s AND provider = %s",
                    (user_id, provider),
                )
                conn.commit()
                return cur.rowcount > 0
    except Exception as e:
        logger.error(f"delete_user_api_key failed: {e}")
        return False


def get_all_user_keys(user_id: int) -> List[Tuple[str, str]]:
    """Return [(provider, key_cipher), ...] for every key this user has stored."""
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT provider, key_cipher FROM user_api_keys WHERE user_id = %s",
                    (user_id,),
                )
                return [(r["provider"], r["key_cipher"]) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"get_all_user_keys failed: {e}")
        return []


def get_stats() -> Tuple[int, int, int]:
    try:
        with db_conn() as conn:
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


def set_blacklist(user_id: int, value: bool) -> bool:
    try:
        with db_conn() as conn:
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


def get_all_active_users() -> List[int]:
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM users WHERE is_blacklisted = FALSE")
                return [row["user_id"] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"get_all_active_users failed: {e}")
        return []


def get_bot_config(key: str) -> Optional[str]:
    """Read a single key from the bot_config table. Returns None if missing."""
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM bot_config WHERE key = %s", (key,))
                row = cur.fetchone()
                return row["value"] if row else None
    except Exception as e:
        logger.error(f"get_bot_config failed: {e}")
        return None


def set_bot_config(key: str, value: str) -> bool:
    """Upsert a key/value into bot_config. Returns True on success."""
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bot_config (key, value, updated_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (key) DO UPDATE
                    SET value = EXCLUDED.value, updated_at = NOW()
                    """,
                    (key, value),
                )
                conn.commit()
        return True
    except Exception as e:
        logger.error(f"set_bot_config failed: {e}")
        return False


def user_connected_providers(user_id: int) -> List[str]:
    return [provider for provider, _ in get_all_user_keys(user_id)]


def get_user_api_keys(user_id: int) -> List[Dict[str, Any]]:
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT provider, created_at FROM user_api_keys WHERE user_id = %s ORDER BY created_at",
                (user_id,),
            )
            return [{"provider": r["provider"], "created_at": r["created_at"]} for r in cur.fetchall()]


def get_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT gender, age, location, occupation, interests, timezone, language "
                "FROM users WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return {
                "gender": row["gender"],
                "age": row["age"],
                "location": row["location"],
                "occupation": row["occupation"],
                "interests": row["interests"],
                "timezone": row["timezone"],
                "language": row["language"],
            }


def update_user_profile(user_id: int, **fields) -> None:
    cols = {k: v for k, v in fields.items() if v is not None}
    if not cols:
        return
    set_clause = ", ".join(f"{col} = %s" for col in cols)
    params = list(cols.values()) + [user_id]
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE users SET {set_clause} WHERE user_id = %s",
                params,
            )
            conn.commit()


def _next_reset_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def get_daily_token_usage(user_id: int) -> Dict[str, Any]:
    """Return {'used', 'limit', 'resets_at'} for the user's Mocco-fallback quota.

    Lazily resets the counter when the stored reset timestamp is in the past.
    Returns a fresh usage snapshot on each call.
    """
    limit = int(getattr(get_config(), "DAILY_FALLBACK_QUOTA", 0) or 0)
    fallback_resets_at = _next_reset_utc()
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT daily_tokens_used, daily_tokens_reset_at FROM users WHERE user_id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return {"used": 0, "limit": limit, "resets_at": fallback_resets_at}
                used = int(row["daily_tokens_used"] or 0)
                resets_at = row["daily_tokens_reset_at"]
                if not isinstance(resets_at, datetime):
                    resets_at = datetime.now(timezone.utc)
                if resets_at.tzinfo is None:
                    resets_at = resets_at.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                if now >= resets_at:
                    used = 0
                    next_reset = _next_reset_utc()
                    cur.execute(
                        "UPDATE users SET daily_tokens_used = 0, daily_tokens_reset_at = %s WHERE user_id = %s",
                        (next_reset, user_id),
                    )
                    conn.commit()
                    return {"used": used, "limit": limit, "resets_at": next_reset}
                return {"used": used, "limit": limit, "resets_at": resets_at}
    except Exception as e:
        logger.error(f"get_daily_token_usage failed: {e}")
        return {"used": 0, "limit": limit, "resets_at": fallback_resets_at}


def increment_daily_token_usage(user_id: int, tokens: int) -> None:
    if tokens <= 0:
        return
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET daily_tokens_used = daily_tokens_used + %s WHERE user_id = %s",
                    (int(tokens), user_id),
                )
                conn.commit()
    except Exception as e:
        logger.error(f"increment_daily_token_usage failed: {e}")


# ── User Chats (Channels/Groups owned by the user) ─────────────────────────


def add_user_chat(owner_id: int, chat_id: int, chat_title: str,
                  chat_type: str, chat_username: str = "", is_admin: bool = False) -> bool:
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO user_chats (owner_id, chat_id, chat_title, chat_type, chat_username, is_admin)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (owner_id, chat_id) DO UPDATE
                    SET chat_title = EXCLUDED.chat_title,
                        chat_username = EXCLUDED.chat_username,
                        is_admin = EXCLUDED.is_admin
                """, (owner_id, chat_id, chat_title, chat_type, chat_username, is_admin))
                conn.commit()
        return True
    except Exception as e:
        logger.error(f"add_user_chat failed: {e}")
        return False


def remove_user_chat(owner_id: int, chat_id: int) -> bool:
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM user_chats WHERE owner_id = %s AND chat_id = %s",
                    (owner_id, chat_id),
                )
                conn.commit()
                return cur.rowcount > 0
    except Exception as e:
        logger.error(f"remove_user_chat failed: {e}")
        return False


def get_user_chats(owner_id: int) -> list:
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT chat_id, chat_title, chat_type, chat_username, is_admin, added_at "
                    "FROM user_chats WHERE owner_id = %s ORDER BY added_at DESC",
                    (owner_id,),
                )
                return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"get_user_chats failed: {e}")
        return []


def get_user_chats_context(owner_id: int) -> str:
    """Return a formatted summary of the user's registered chats for the assistant prompt."""
    chats = get_user_chats(owner_id)
    if not chats:
        return ""
    lines = ["## Account owner's chats:"]
    for c in chats:
        role = "admin" if c["is_admin"] else "member"
        uname = f" (@{c['chat_username']})" if c.get("chat_username") else ""
        lines.append(f"- {c['chat_title']}{uname} — {c['chat_type']} ({role})")
    return "\n".join(lines)
