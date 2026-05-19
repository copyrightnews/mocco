import logging
from typing import Optional, List, Tuple
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from .config import load_config

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
                    is_blacklisted BOOLEAN DEFAULT FALSE,
                    message_count  INTEGER DEFAULT 0,
                    created_at     TIMESTAMP DEFAULT NOW()
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
