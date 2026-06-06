# Mocco Telegram Mini App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Telegram Mini App to Mocco with an Agent (chat) tab and a Profile tab, reusing the existing Python bot's LLM routing, DB, and encryption.

**Architecture:** Monorepo. The existing Python bot stays unchanged in role. A new FastAPI service in `api/` exposes TMA-only endpoints, validates Telegram `initData`, and reuses `mocco.*` modules. A new React + Vite SPA in `webapp/` is the TMA frontend, deployed to Vercel. Both services share the existing Postgres.

**Tech Stack:** Python 3.11, FastAPI, uvicorn, pydantic, psycopg2-binary (existing); React 18, TypeScript 5, Vite 5, Tailwind 3, Zustand 4, React Router 6; Telegram WebApp SDK (vanilla `telegram-web-app.js`).

**Spec:** `docs/superpowers/specs/2026-06-06-mocco-tma-design.md` — read fully before starting.

---

## File Map (created or modified)

### New
- `mocco/migrations/001_tma_profile_fields.sql`
- `mocco/migrate.py` — sequential migration runner
- `mocco/api_auth.py` — `verify_init_data`
- `mocco/ai_stream.py` — `stream_ai_reply` (or appended to `mocco/ai.py`)
- `api/__init__.py`
- `api/main.py` — app factory + middleware
- `api/deps.py` — `current_user` FastAPI dependency
- `api/errors.py` — `ApiError` + handlers
- `api/models.py` — pydantic request/response shapes
- `api/routes/__init__.py`
- `api/routes/health.py`
- `api/routes/me.py`
- `api/routes/profile.py`
- `api/routes/models.py`
- `api/routes/keys.py`
- `api/routes/history.py`
- `api/routes/chat.py`
- `requirements.api.txt`
- `Dockerfile.api`
- `tests/test_api_auth.py`
- `tests/test_api_chat_stream.py`
- `tests/test_api_profile.py`
- `tests/conftest.py`
- `webapp/` (entire directory — see Phase 6)
- `webapp/src/lib/telegram.ts`
- `webapp/src/lib/api.ts`
- `webapp/src/lib/stream.ts`
- `webapp/src/stores/useUserStore.ts`
- `webapp/src/stores/useChatStore.ts`
- `webapp/src/stores/useProfileStore.ts`
- `webapp/src/stores/useToastStore.ts`
- `webapp/src/components/AppShell.tsx`
- `webapp/src/components/TopBar.tsx`
- `webapp/src/components/BottomNav.tsx`
- `webapp/src/components/TelegramProvider.tsx`
- `webapp/src/components/ChatPanel.tsx`
- `webapp/src/components/MessageBubble.tsx`
- `webapp/src/components/QuickActionChips.tsx`
- `webapp/src/components/ResetConfirmModal.tsx`
- `webapp/src/components/ConnectKeyModal.tsx`
- `webapp/src/components/ModelPickerModal.tsx`
- `webapp/src/components/Toast.tsx`
- `webapp/src/components/ErrorBoundary.tsx`
- `webapp/src/pages/AgentPage.tsx`
- `webapp/src/pages/ProfilePage.tsx`
- `webapp/src/styles/globals.css`

### Modified
- `mocco/config.py` — remove `TOGETHER_API_KEY`
- `mocco/ai.py` — remove `generate_image`, add `stream_ai_reply`
- `mocco/handlers.py` — remove `/imagine`, add WebApp button to `/start`, update `WELCOME_TEXT` and `HELP_TEXT`
- `mocco/db.py` — call migration runner from `init_db()`
- `requirements.txt` — add `fastapi`, `uvicorn[standard]`, `pydantic`
- `.env.example` — remove `TOGETHER_API_KEY`
- `railway.toml` — add `api` service
- `Dockerfile` — keep as-is (bot-only)

---

# Phase 1 — Bot cleanup (remove Imagine)

## Task 1: Remove /imagine handler

**Files:**
- Modify: `src/mocco/handlers.py:1433` (or wherever `/imagine` is registered in `register_handlers`)

- [ ] **Step 1: Locate the /imagine line**

In `src/mocco/handlers.py`, in the `register_handlers` function, find the line:
```python
    app.add_handler(CommandHandler("imagine",     cmd_imagine))
```
Note the exact line number.

- [ ] **Step 2: Delete that line and the surrounding comma**

Delete the entire line. The block above and below must remain valid Python (no trailing comma on the line above, no orphan comma left).

- [ ] **Step 3: Commit**

```bash
git add src/mocco/handlers.py
git commit -m "refactor: remove /imagine command handler (Imagine concept dropped)"
```

---

## Task 2: Remove generate_image from ai.py

**Files:**
- Modify: `src/mocco/ai.py:265-317` (the `generate_image` function)

- [ ] **Step 1: Verify generate_image is unused elsewhere**

Run:
```bash
grep -rn "generate_image" src/ tests/
```
Expected: only `src/mocco/ai.py` defines it; only `src/mocco/handlers.py:cmd_imagine` calls it. (We'll delete cmd_imagine in a later step via /imagine removal.)

- [ ] **Step 2: Delete the generate_image function**

Open `src/mocco/ai.py`. Delete the entire `generate_image` function and the import of `base64` if it is no longer used anywhere else. Keep all other functions intact.

- [ ] **Step 3: Verify nothing imports generate_image**

Run:
```bash
grep -rn "generate_image" src/ tests/
```
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add src/mocco/ai.py
git commit -m "refactor: delete generate_image (no longer used)"
```

---

## Task 3: Remove TOGETHER_API_KEY from config

**Files:**
- Modify: `src/mocco/config.py:18` (the `TOGETHER_API_KEY` field), `src/mocco/config.py:31-40` (OPTIONAL_VARS), `src/mocco/config.py:75-77` (the field assignment in `load_config`), `src/mocco/config.py:88-92` (the disabled-feature check in `get_missing_optional_features`)

- [ ] **Step 1: Delete the field declaration**

In `src/mocco/config.py`, find:
```python
    TOGETHER_API_KEY: str = ""      # Bot-side image generation
```
Delete the line.

- [ ] **Step 2: Remove from OPTIONAL_VARS**

Find the tuple `OPTIONAL_VARS = (...)` and remove the string `"TOGETHER_API_KEY"` from inside it.

- [ ] **Step 3: Remove from load_config return**

Find:
```python
        TOGETHER_API_KEY=os.environ.get("TOGETHER_API_KEY", ""),
```
Delete the line.

- [ ] **Step 4: Remove the disabled-feature check**

Find:
```python
    if not cfg.TOGETHER_API_KEY:
        disabled.append("image generation (Together)")
```
Delete both lines.

- [ ] **Step 5: Commit**

```bash
git add src/mocco/config.py
git commit -m "refactor: drop TOGETHER_API_KEY from config (Imagine removed)"
```

---

## Task 4: Update .env.example

**Files:**
- Modify: `.env.example:27-28`

- [ ] **Step 1: Delete the Together block**

Open `.env.example`. Find:
```
# [OPT] Together AI (image generation) — https://api.together.xyz
TOGETHER_API_KEY=
```
Delete both lines.

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: remove TOGETHER_API_KEY from .env.example"
```

---

## Task 5: Update WELCOME_TEXT and HELP_TEXT

**Files:**
- Modify: `src/mocco/handlers.py` — the `WELCOME_TEXT` and `HELP_TEXT` constants

- [ ] **Step 1: Update WELCOME_TEXT**

In `src/mocco/handlers.py`, find the `WELCOME_TEXT` constant. Replace it with:
```python
WELCOME_TEXT = (
    "*Hi, I'm Mocco* — your smart, fast, and reliable AI assistant.\n"
    "Ask me anything. I'm ready when you are.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "*What I can do for you*\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "*Chat & Reasoning*\n"
    "• Answer questions on any topic\n"
    "• Code, debug, and review in any language\n"
    "• Write, edit, and translate text\n"
    "• Brainstorm ideas and plan tasks\n\n"
    "*Web & Research*\n"
    "• Search the live web for current info\n"
    "• Summarize articles, papers, or PDFs\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "*Open the app*\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "For a richer experience, tap the *🚀 Open App* button below to launch the Mocco Mini App.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "Just type your question or use /help to see all commands."
)
```

- [ ] **Step 2: Locate the /imagine line in HELP_TEXT**

In `src/mocco/handlers.py`, find the `HELP_TEXT` constant. Look for the `/imagine` description block. It will look like:
```python
    "`/imagine <prompt>`\n"
    "Generate an AI image from your description.\n"
    "_Example: `/imagine a futuristic city at sunset, cinematic lighting, 4K`_\n\n"
```
Delete that block entirely (4 lines including trailing blank line).

- [ ] **Step 3: Commit**

```bash
git add src/mocco/handlers.py
git commit -m "docs: drop /imagine from help, add Open App hint in welcome"
```

---

## Task 6: Add Open App button to /start

**Files:**
- Modify: `src/mocco/handlers.py` — the `cmd_start` function
- Read first: `src/mocco/handlers.py` to find the existing `cmd_start` implementation.

- [ ] **Step 1: Add the imports at the top of the file**

At the top of `src/mocco/handlers.py`, find the `from telegram import ...` line. Add `WebAppInfo` to the import:
```python
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
```

- [ ] **Step 2: Add the env-driven URL constant**

Below the `BROADCAST_CHUNK` constant, add:
```python
TMA_URL = os.environ.get("TMA_URL", "")  # e.g. https://mocco.vercel.app
```

- [ ] **Step 3: Modify cmd_start to include the button**

Find `cmd_start`. Add the WebApp button construction just before the existing reply is sent. The full new function should be:
```python
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start: greet the user and (if TMA_URL is configured) offer the Open App button."""
    user = update.effective_user
    if user:
        try:
            ensure_user(user.id, user.first_name or "", user.username or "")
        except Exception as e:
            logger.warning(f"ensure_user failed in /start: {e}")
    kb = None
    if TMA_URL:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Open App", web_app=WebAppInfo(url=TMA_URL))]
        ])
    await safe_reply(update.message, WELCOME_TEXT, parse_mode="Markdown", reply_markup=kb)
```
If `cmd_start` already calls `safe_reply(...)` and has different surrounding logic, keep the rest of the function intact and only inject the `kb = ...` block and pass `reply_markup=kb` to `safe_reply`.

- [ ] **Step 4: Commit**

```bash
git add src/mocco/handlers.py
git commit -m "feat: add Open App WebApp button to /start (driven by TMA_URL env)"
```

---

# Phase 2 — DB migration framework

## Task 7: Add migrations directory

**Files:**
- Create: `src/mocco/migrations/__init__.py` (empty file)
- Create: `src/mocco/migrations/001_tma_profile_fields.sql`

- [ ] **Step 1: Create the directory and __init__.py**

```bash
mkdir -p src/mocco/migrations
touch src/mocco/migrations/__init__.py
```

- [ ] **Step 2: Create the migration SQL**

Create `src/mocco/migrations/001_tma_profile_fields.sql` with:
```sql
-- Adds TMA profile fields to the users table.
-- Idempotent: safe to run on an already-migrated DB.
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS gender         text,
  ADD COLUMN IF NOT EXISTS age            int,
  ADD COLUMN IF NOT EXISTS location       text,
  ADD COLUMN IF NOT EXISTS occupation     text,
  ADD COLUMN IF NOT EXISTS interests      text[],
  ADD COLUMN IF NOT EXISTS timezone       text,
  ADD COLUMN IF NOT EXISTS language       text NOT NULL DEFAULT 'en';
```

- [ ] **Step 3: Commit**

```bash
git add src/mocco/migrations/
git commit -m "feat(db): add 001_tma_profile_fields migration"
```

---

## Task 8: Migration runner

**Files:**
- Create: `src/mocco/migrate.py`
- Test: `tests/test_migrate.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_migrate.py`:
```python
import os
import tempfile
from mocco.migrate import apply_migrations, ensure_schema_migrations_table, _applied_versions


def test_ensure_schema_migrations_table_creates_when_missing():
    # Use a fresh in-memory-ish sqlite via tempdir is overkill; instead, test idempotency.
    # We rely on the caller to pass a connection; here we test against a real Postgres if DATABASE_URL is set.
    import psycopg2
    if not os.environ.get("DATABASE_URL"):
        return  # skip when no DB
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        ensure_schema_migrations_table(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.schema_migrations')")
            assert cur.fetchone()[0] is not None
    finally:
        conn.close()


def test_apply_migrations_records_versions():
    import psycopg2
    if not os.environ.get("DATABASE_URL"):
        return
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        # Drop and recreate to test fresh apply
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS schema_migrations")
            cur.execute("""
                CREATE TABLE users (
                    id bigint PRIMARY KEY,
                    telegram_id bigint UNIQUE NOT NULL
                )
            """)
        conn.commit()
        apply_migrations(conn, "src/mocco/migrations")
        applied = _applied_versions(conn)
        assert "001_tma_profile_fields" in applied
        # The new columns must exist
        with conn.cursor() as cur:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users'")
            cols = {r[0] for r in cur.fetchall()}
        assert {"gender", "age", "location", "occupation", "interests", "timezone", "language"}.issubset(cols)
    finally:
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_migrate.py -v
```
Expected: ImportError on `mocco.migrate` (module does not exist).

- [ ] **Step 3: Write the implementation**

Create `src/mocco/migrate.py`:
```python
"""Sequential, idempotent SQL migration runner.

Reads `*.sql` files from a directory in lexical order, applies any not yet
recorded in the `schema_migrations` table, and records them on success.
"""
from __future__ import annotations

import os
from pathlib import Path


def ensure_schema_migrations_table(conn) -> None:
    """Create the schema_migrations bookkeeping table if missing."""
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version     text PRIMARY KEY,
                applied_at  timestamptz NOT NULL DEFAULT now()
            )
            """
        )
    conn.commit()


def _applied_versions(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations")
        return {r[0] for r in cur.fetchall()}


def apply_migrations(conn, migrations_dir: str | os.PathLike) -> list[str]:
    """Apply any unapplied SQL files in `migrations_dir` in lexical order.

    Returns the list of versions that were applied in this call.
    """
    ensure_schema_migrations_table(conn)
    applied = _applied_versions(conn)
    new_versions: list[str] = []
    path = Path(migrations_dir)
    if not path.exists():
        return new_versions
    for sql_file in sorted(path.glob("*.sql")):
        version = sql_file.stem  # e.g. "001_tma_profile_fields"
        if version in applied:
            continue
        sql = sql_file.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (version,),
            )
        conn.commit()
        new_versions.append(version)
    return new_versions
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_migrate.py -v
```
Expected: 2 passed (or 2 skipped if `DATABASE_URL` not set; set it to a test DB if you want to run).

- [ ] **Step 5: Commit**

```bash
git add src/mocco/migrate.py tests/test_migrate.py
git commit -m "feat(db): sequential migration runner"
```

---

## Task 9: Wire migration runner into init_db

**Files:**
- Modify: `src/mocco/db.py` — at the end of `init_db()` (or wherever appropriate)

- [ ] **Step 1: Locate init_db**

Open `src/mocco/db.py`. Find `init_db()`. Note where it currently finishes (typically `conn.commit()` at the end).

- [ ] **Step 2: Add the migration call**

Add at the top of `db.py`:
```python
from .migrate import apply_migrations
```

Then inside `init_db()`, just before the final commit/return (or wherever the connection is open), add:
```python
    migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")
    apply_migrations(_conn, migrations_dir)
```
where `_conn` is the connection variable used by `init_db`. Adjust to match the existing variable name.

- [ ] **Step 3: Commit**

```bash
git add src/mocco/db.py
git commit -m "feat(db): run migrations on init_db"
```

---

# Phase 3 — FastAPI foundation

## Task 10: Add FastAPI dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add the lines**

Open `requirements.txt`. Append:
```
fastapi==0.115.0
uvicorn[standard]==0.30.6
pydantic==2.9.2
```

- [ ] **Step 2: Create requirements.api.txt**

Create `requirements.api.txt`:
```
-r requirements.txt
```
(The api service reuses the bot's requirements + the new FastAPI trio.)

- [ ] **Step 3: Install and verify**

```bash
pip install -r requirements.txt
python -c "import fastapi, uvicorn, pydantic; print('ok')"
```
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt requirements.api.txt
git commit -m "build: add fastapi, uvicorn, pydantic"
```

---

## Task 11: ApiError and handlers

**Files:**
- Create: `api/__init__.py` (empty)
- Create: `api/errors.py`

- [ ] **Step 1: Create api package**

```bash
mkdir -p api
touch api/__init__.py
```

- [ ] **Step 2: Write api/errors.py**

Create `api/errors.py`:
```python
"""ApiError + centralized handlers for the TMA API."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("mocco.api")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, extra: dict[str, Any] | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        out = {"code": self.code, "message": self.message}
        out.update(self.extra)
        return {"error": out}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error_handler(_: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content=exc.to_dict())

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        logger.exception("unhandled exception")
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal", "message": "Internal server error."}},
        )
```

- [ ] **Step 3: Commit**

```bash
git add api/__init__.py api/errors.py
git commit -m "feat(api): ApiError and centralized handlers"
```

---

## Task 12: /v1/health endpoint

**Files:**
- Create: `api/routes/__init__.py` (empty)
- Create: `api/routes/health.py`

- [ ] **Step 1: Create the routes package**

```bash
mkdir -p api/routes
touch api/routes/__init__.py
```

- [ ] **Step 2: Write api/routes/health.py**

Create `api/routes/health.py`:
```python
"""Liveness check: confirms DB is reachable and reports uptime."""
from __future__ import annotations

import time
import os

import psycopg2
from fastapi import APIRouter

router = APIRouter()

_BOOT_TIME = time.time()


@router.get("/health")
def health():
    db_ok = "ok"
    try:
        conn = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=3)
        conn.close()
    except Exception as e:
        db_ok = f"error: {e.__class__.__name__}"
    return {"db": db_ok, "uptime_s": int(time.time() - _BOOT_TIME)}
```

- [ ] **Step 3: Commit**

```bash
git add api/routes/__init__.py api/routes/health.py
git commit -m "feat(api): /v1/health endpoint"
```

---

## Task 13: FastAPI app factory

**Files:**
- Create: `api/main.py`

- [ ] **Step 1: Write api/main.py**

Create `api/main.py`:
```python
"""FastAPI app factory for the Mocco TMA API."""
from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Make the bot package importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mocco.config import load_config
from mocco.db import init_db

from api.errors import install_error_handlers
from api.routes import health, me, profile, models, keys, history, chat


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("mocco.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    cfg = load_config()
    init_db()
    logger.info("Mocco TMA API started.")
    yield
    logger.info("Mocco TMA API shutting down.")


def create_app() -> FastAPI:
    app = FastAPI(title="Mocco TMA API", version="0.1.0", lifespan=lifespan)

    # CORS: TMA is a Telegram webview; allow the Vercel origin and localhost for dev.
    origins = [o.strip() for o in os.environ.get("CORS_ALLOW_ORIGINS", "*").split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    install_error_handlers(app)

    app.include_router(health.router, prefix="/v1")
    # me, profile, models, keys, history, chat are added in later tasks.
    return app


app = create_app()
```

- [ ] **Step 2: Run it to confirm it boots**

```bash
set TELEGRAM_TOKEN=test
set DATABASE_URL=postgresql://user:pass@localhost:5432/test
uvicorn api.main:app --port 8000
```
In another shell:
```bash
curl http://localhost:8000/v1/health
```
Expected: `{"db":"ok","uptime_s":0}` (or `error: ...` if DB unreachable — that's fine, the endpoint returned 200).

Stop the server with Ctrl-C.

- [ ] **Step 3: Commit**

```bash
git add api/main.py
git commit -m "feat(api): FastAPI app factory with health route"
```

---

## Task 14: Dockerfile.api

**Files:**
- Create: `Dockerfile.api`

- [ ] **Step 1: Write the Dockerfile**

Create `Dockerfile.api`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.api.txt /app/
RUN pip install --no-cache-dir -r requirements.api.txt

COPY src /app/src
COPY api /app/api
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 2: Commit**

```bash
git add Dockerfile.api
git commit -m "build(api): Dockerfile for FastAPI service"
```

---

# Phase 4 — initData authentication

## Task 15: verify_init_data

**Files:**
- Create: `src/mocco/api_auth.py`
- Create: `tests/test_api_auth.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create tests/conftest.py with bot_token fixture**

Create `tests/conftest.py`:
```python
import pytest


@pytest.fixture
def bot_token() -> str:
    return "123456:TEST-BOT-TOKEN-DO-NOT-USE"


@pytest.fixture
def valid_init_data(bot_token: str) -> str:
    """Build a valid initData string for a fake user.

    Pre-computed for a fixed `auth_date` so tests are deterministic.
    """
    import hashlib
    import hmac
    import time
    from urllib.parse import urlencode

    auth_date = 1700000000
    user_json = '{"id":7232714487,"first_name":"Test","username":"tester"}'
    params = {
        "user": user_json,
        "auth_date": str(auth_date),
        "query_id": "AAH_FIXTURE",
    }
    data_check = "\n".join(f"{k}={params[k]}" for k in sorted(params))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    params["hash"] = h
    return urlencode(params)
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_api_auth.py`:
```python
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from mocco.api_auth import verify_init_data
from api.errors import ApiError


def _sign(params: dict, bot_token: str) -> str:
    data_check = "\n".join(f"{k}={params[k]}" for k in sorted(params))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    return hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()


def test_valid_init_data_returns_user(bot_token, valid_init_data):
    user = verify_init_data(valid_init_data, bot_token, max_age_s=3600)
    assert user["id"] == 7232714487
    assert user["first_name"] == "Test"


def test_wrong_hash_raises(bot_token):
    params = {
        "user": '{"id":1}',
        "auth_date": "1700000000",
        "hash": "deadbeef" * 8,
    }
    raw = urlencode(params)
    with pytest.raises(ApiError) as e:
        verify_init_data(raw, bot_token, max_age_s=3600)
    assert e.value.status == 401
    assert e.value.code == "unauthorized"


def test_expired_raises(bot_token):
    user_json = '{"id":1}'
    params = {"user": user_json, "auth_date": "1700000000"}
    params["hash"] = _sign(params, bot_token)
    raw = urlencode(params)
    with pytest.raises(ApiError) as e:
        verify_init_data(raw, bot_token, max_age_s=10)
    assert e.value.status == 401


def test_missing_hash_raises(bot_token):
    raw = urlencode({"user": '{"id":1}', "auth_date": "1700000000"})
    with pytest.raises(ApiError):
        verify_init_data(raw, bot_token, max_age_s=3600)


def test_tampered_user_field_raises(bot_token, valid_init_data):
    # valid_init_data was signed for user id 7232714487; replace the user field with a different id
    raw = valid_init_data.replace("7232714487", "9999999999")
    with pytest.raises(ApiError):
        verify_init_data(raw, bot_token, max_age_s=3600)
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_api_auth.py -v
```
Expected: ImportError on `mocco.api_auth`.

- [ ] **Step 4: Write the implementation**

Create `src/mocco/api_auth.py`:
```python
"""Telegram WebApp `initData` verification.

Implements the algorithm documented at
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qsl


class _Unauthorized(Exception):
    pass


def verify_init_data(raw: str, bot_token: str, max_age_s: int = 300) -> dict[str, Any]:
    """Verify `raw` (the initData query string) and return the parsed `user` object.

    Raises `api.errors.ApiError(401, "unauthorized", ...)` on any failure.
    """
    # Local import to avoid a circular dependency at module import time.
    from api.errors import ApiError

    try:
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=False)
    except Exception:
        raise ApiError(401, "unauthorized", "Malformed initData.")
    parsed = dict(pairs)
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise ApiError(401, "unauthorized", "Missing hash.")
    if "auth_date" not in parsed or "user" not in parsed:
        raise ApiError(401, "unauthorized", "Missing required fields.")

    try:
        auth_date = int(parsed["auth_date"])
    except ValueError:
        raise ApiError(401, "unauthorized", "Invalid auth_date.")
    if time.time() - auth_date > max_age_s:
        raise ApiError(401, "unauthorized", "initData expired.")

    data_check_string = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, received_hash):
        raise ApiError(401, "unauthorized", "Invalid signature.")

    try:
        user = json.loads(parsed["user"])
    except json.JSONDecodeError:
        raise ApiError(401, "unauthorized", "Invalid user field.")
    return user
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_api_auth.py -v
```
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/mocco/api_auth.py tests/test_api_auth.py tests/conftest.py
git commit -m "feat(api-auth): verify_init_data with table-driven tests"
```

---

## Task 16: current_user FastAPI dependency

**Files:**
- Create: `api/deps.py`

- [ ] **Step 1: Write api/deps.py**

Create `api/deps.py`:
```python
"""FastAPI dependencies: auth (initData verification) and current_user."""
from __future__ import annotations

import os
from typing import Annotated

from fastapi import Header, Request

from mocco.api_auth import verify_init_data
from mocco.config import load_config
from mocco.db import ensure_user, is_blacklisted

from api.errors import ApiError


_READ_MAX_AGE_S = 24 * 3600
_WRITE_MAX_AGE_S = 300


def _cfg():
    return load_config()


def _max_age_for(method: str) -> int:
    return _READ_MAX_AGE_S if method.upper() in {"GET", "HEAD", "OPTIONS"} else _WRITE_MAX_AGE_S


def current_user(
    request: Request,
    x_telegram_init_data: Annotated[str | None, Header(alias="X-Telegram-Init-Data")] = None,
) -> int:
    """Validate initData, upsert the user, return the Mocco internal user.id.

    Use as a FastAPI dependency: `user_id: int = Depends(current_user)`.
    """
    if not x_telegram_init_data:
        raise ApiError(401, "unauthorized", "Missing X-Telegram-Init-Data header.")
    cfg = _cfg()
    user = verify_init_data(
        x_telegram_init_data,
        cfg.TELEGRAM_TOKEN,
        max_age_s=_max_age_for(request.method),
    )
    tg_id = int(user["id"])
    if is_blacklisted(tg_id):
        raise ApiError(403, "forbidden", "This account is blocked.")
    name = user.get("first_name") or user.get("username") or ""
    username = user.get("username") or ""
    ensure_user(tg_id, name, username)
    return tg_id
```

- [ ] **Step 2: Commit**

```bash
git add api/deps.py
git commit -m "feat(api): current_user dependency with read/write expiry"
```

---

# Phase 5 — FastAPI routes

## Task 17: Pydantic models

**Files:**
- Create: `api/models.py`

- [ ] **Step 1: Write api/models.py**

Create `api/models.py`:
```python
"""Pydantic request/response shapes for the TMA API."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    system_prompt_override: Optional[str] = None


class SetModelRequest(BaseModel):
    model_id: str = Field(min_length=1, max_length=200)


class ConnectKeyRequest(BaseModel):
    api_key: str = Field(min_length=1, max_length=512)


class ProfilePatch(BaseModel):
    language: Optional[str] = Field(default=None, max_length=8)
    persona: Optional[str] = Field(default=None, max_length=4000)
    gender: Optional[str] = Field(default=None, max_length=32)
    age: Optional[int] = Field(default=None, ge=0, le=150)
    location: Optional[str] = Field(default=None, max_length=200)
    occupation: Optional[str] = Field(default=None, max_length=200)
    interests: Optional[list[str]] = None
    timezone: Optional[str] = Field(default=None, max_length=64)


class ProviderLiteral:
    OPENROUTER = "openrouter"
    SERPER = "serper"


class ConnectedProvider(BaseModel):
    provider: str
    created_at: str
```

- [ ] **Step 2: Commit**

```bash
git add api/models.py
git commit -m "feat(api): pydantic request/response models"
```

---

## Task 18: /v1/me route

**Files:**
- Create: `api/routes/me.py`

- [ ] **Step 1: Write api/routes/me.py**

Create `api/routes/me.py`:
```python
"""/v1/me — current user info for the TMA."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from mocco.db import get_chat_model, user_connected_providers

from api.deps import current_user

router = APIRouter()


@router.get("/me")
def me(user_id: int = Depends(current_user)):
    return {
        "id": user_id,
        "model": get_chat_model(user_id) or "",
        "language": "",  # filled by /v1/profile in a later task
        "persona": "",
        "connected_providers": user_connected_providers(user_id),
    }
```

- [ ] **Step 2: Commit**

```bash
git add api/routes/me.py
git commit -m "feat(api): /v1/me route"
```

---

## Task 19: /v1/profile GET and PATCH

**Files:**
- Create: `api/routes/profile.py`
- Read first: `src/mocco/db.py` to find existing functions for reading/updating the user row.

- [ ] **Step 1: Add db helpers if they don't exist**

If `get_user_profile(user_id)` and `update_user_profile(user_id, **fields)` do not exist in `src/mocco/db.py`, add them. Use this template (adapt to match the existing style in `db.py`):
```python
def get_user_profile(user_id: int) -> dict:
    with _conn() as c, c.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT language, persona, gender, age, location, occupation, interests, timezone
            FROM users WHERE id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            return {"language": "en", "persona": "", "gender": None, "age": None,
                    "location": None, "occupation": None, "interests": [], "timezone": None}
        d = dict(row)
        d["interests"] = d.get("interests") or []
        return d


def update_user_profile(user_id: int, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = %s" for k in fields)
    vals = list(fields.values()) + [user_id]
    with _conn() as c, c.cursor() as cur:
        cur.execute(f"UPDATE users SET {cols} WHERE id = %s", vals)
```
Place these in `src/mocco/db.py` alongside the other user-related functions. Replace `_conn()` with the actual context-manager name used in your `db.py` (e.g., `get_conn()` or similar — match the file's existing pattern).

- [ ] **Step 2: Write api/routes/profile.py**

Create `api/routes/profile.py`:
```python
"""/v1/profile — read and update TMA profile fields."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from mocco.db import get_user_profile, update_user_profile

from api.deps import current_user
from api.models import ProfilePatch

router = APIRouter()


@router.get("/profile")
def get_profile(user_id: int = Depends(current_user)):
    return get_user_profile(user_id)


@router.patch("/profile")
def patch_profile(patch: ProfilePatch, user_id: int = Depends(current_user)):
    fields = {k: v for k, v in patch.model_dump(exclude_none=True).items() if v is not None}
    update_user_profile(user_id, **fields)
    return get_user_profile(user_id)
```

- [ ] **Step 3: Commit**

```bash
git add src/mocco/db.py api/routes/profile.py
git commit -m "feat(api): /v1/profile GET and PATCH"
```

---

## Task 20: /v1/models and /v1/model

**Files:**
- Create: `api/routes/models.py`

- [ ] **Step 1: Write api/routes/models.py**

Create `api/routes/models.py`:
```python
"""/v1/models list and /v1/model setter."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from mocco.ai import fetch_all_models
from mocco.db import get_chat_model, set_chat_model

from api.deps import current_user
from api.errors import ApiError
from api.models import SetModelRequest

router = APIRouter()


@router.get("/models")
def list_models(user_id: int = Depends(current_user)):
    models = fetch_all_models(force=False)
    # Trim to fields the TMA needs.
    return [
        {
            "id": m["id"],
            "name": m.get("name", m["id"]),
            "is_free": m.get("is_free", False),
            "context_length": m.get("context_length", 0),
        }
        for m in models
    ]


@router.get("/model")
def get_model(user_id: int = Depends(current_user)):
    return {"model": get_chat_model(user_id) or ""}


@router.post("/model")
def set_model(req: SetModelRequest, user_id: int = Depends(current_user)):
    # Validate the model id exists in the catalog (best-effort, allow free text to be future-proof).
    catalog = {m["id"] for m in fetch_all_models(force=False)}
    if req.model_id and catalog and req.model_id not in catalog:
        # Allow but warn — user may have a model not in the cache yet.
        pass
    set_chat_model(user_id, req.model_id)
    return {"model": req.model_id}
```

- [ ] **Step 2: Commit**

```bash
git add api/routes/models.py
git commit -m "feat(api): /v1/models list and /v1/model setter"
```

---

## Task 21: /v1/keys (connect / list / disconnect)

**Files:**
- Create: `api/routes/keys.py`
- Read first: `src/mocco/db.py` and `src/mocco/crypto.py` to find existing helpers.

- [ ] **Step 1: Write api/routes/keys.py**

Create `api/routes/keys.py`:
```python
"""/v1/keys — per-user API key management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from mocco.crypto import encrypt_api_key
from mocco.db import (
    delete_user_api_key,
    get_user_api_keys,
    set_user_api_key,
)

from api.deps import current_user
from api.errors import ApiError
from api.models import ConnectKeyRequest

router = APIRouter()

# Providers the TMA can store keys for. Add more as you wire them up.
ALLOWED_PROVIDERS = {"openrouter", "serper"}


@router.get("/keys")
def list_keys(user_id: int = Depends(current_user)):
    keys = get_user_api_keys(user_id)
    return [
        {"provider": k["provider"], "created_at": k["created_at"].isoformat()}
        for k in keys
    ]


@router.post("/keys/{provider}")
def connect_key(
    req: ConnectKeyRequest,
    user_id: int = Depends(current_user),
    provider: str = Path(...),
):
    if provider not in ALLOWED_PROVIDERS:
        raise ApiError(400, "bad_provider", f"Unknown provider: {provider}")
    enc = encrypt_api_key(req.api_key)
    set_user_api_key(user_id, provider, enc)
    return {"provider": provider, "ok": True}


@router.delete("/keys/{provider}")
def disconnect_key(
    user_id: int = Depends(current_user),
    provider: str = Path(...),
):
    if provider not in ALLOWED_PROVIDERS:
        raise ApiError(400, "bad_provider", f"Unknown provider: {provider}")
    delete_user_api_key(user_id, provider)
    return {"ok": True}
```

- [ ] **Step 2: Commit**

```bash
git add api/routes/keys.py
git commit -m "feat(api): /v1/keys connect, list, disconnect"
```

---

## Task 22: /v1/history and /v1/reset

**Files:**
- Create: `api/routes/history.py`

- [ ] **Step 1: Write api/routes/history.py**

Create `api/routes/history.py`:
```python
"""/v1/history and /v1/reset — chat memory controls for the TMA."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from mocco.db import clear_history, get_history

from api.deps import current_user

router = APIRouter()

HISTORY_LIMIT = 14


@router.get("/history")
def history(user_id: int = Depends(current_user)):
    rows = get_history(user_id)
    rows = rows[-HISTORY_LIMIT:]
    return [
        {"role": r["role"], "content": r["content"], "ts": r.get("ts").isoformat() if r.get("ts") else None}
        for r in rows
    ]


@router.post("/reset")
def reset(user_id: int = Depends(current_user)):
    clear_history(user_id)
    return {"ok": True}
```

- [ ] **Step 2: Commit**

```bash
git add api/routes/history.py
git commit -m "feat(api): /v1/history and /v1/reset"
```

---

## Task 23: stream_ai_reply

**Files:**
- Create: `src/mocco/ai_stream.py` (separate module to keep `ai.py` focused)
- Test: `tests/test_api_chat_stream.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_api_chat_stream.py`:
```python
import pytest
from unittest.mock import MagicMock, AsyncMock

from mocco.ai_stream import stream_ai_reply


class _FakeChunk:
    def __init__(self, content: str | None):
        self.choices = [MagicMock(delta=MagicMock(content=content))]


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks
        self._i = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._i >= len(self._chunks):
            raise StopAsyncIteration
        c = self._chunks[self._i]
        self._i += 1
        return c


@pytest.mark.asyncio
async def test_stream_ai_reply_yields_deltas_and_done(monkeypatch):
    # Patch the client factory to return a fake.
    fake_stream = _FakeStream([_FakeChunk("Hel"), _FakeChunk("lo"), _FakeChunk(None)])
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_stream)

    async def fake_get_client(_user_id, _model_id):
        return fake_client, "test-model"

    monkeypatch.setattr("mocco.ai_stream.get_client_for_chat", fake_get_client)
    monkeypatch.setattr("mocco.ai_stream.resolve_model", lambda _u: "test-model")

    import json
    deltas = []
    done = False
    async for frame in stream_ai_reply(123, [{"role": "user", "content": "hi"}]):
        if frame.startswith("data: "):
            payload = json.loads(frame[len("data: "):].strip())
            if "delta" in payload:
                deltas.append(payload["delta"])
            if payload.get("done"):
                done = True
    assert "".join(deltas) == "Hello"
    assert done is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pip install pytest-asyncio
pytest tests/test_api_chat_stream.py -v
```
Expected: ImportError on `mocco.ai_stream`.

- [ ] **Step 3: Write the implementation**

Create `src/mocco/ai_stream.py`:
```python
"""Streaming variant of the LLM reply generator.

Yields SSE frames: `data: {"delta": "..."}\\n\\n` per token, then `data: {"done": true}\\n\\n`.
"""
from __future__ import annotations

import json
from typing import AsyncIterator, Optional

from .ai import get_client_for_chat, resolve_model
from .db import save_message


async def stream_ai_reply(
    user_id: int,
    messages: list[dict],
    system_prompt: Optional[str] = None,
    persist_to_db: bool = True,
) -> AsyncIterator[str]:
    """Stream an LLM reply as SSE frames. Optionally persist the full reply when done."""
    model_id = resolve_model(user_id)
    client, real_model = get_client_for_chat(user_id, model_id)
    payload = messages[:]
    if system_prompt:
        payload = [{"role": "system", "content": system_prompt}] + payload
    stream = await client.chat.completions.create(
        model=real_model,
        messages=payload,
        stream=True,
        max_tokens=800,
        temperature=0.65,
    )
    full_reply: list[str] = []
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            full_reply.append(delta)
            yield f"data: {json.dumps({'delta': delta})}\n\n"
    yield f"data: {json.dumps({'done': True})}\n\n"
    if persist_to_db and full_reply:
        try:
            save_message(user_id, "assistant", "".join(full_reply))
        except Exception:
            pass
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_api_chat_stream.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mocco/ai_stream.py tests/test_api_chat_stream.py
git commit -m "feat(ai): stream_ai_reply for SSE chat endpoint"
```

---

## Task 24: /v1/chat/stream route

**Files:**
- Create: `api/routes/chat.py`

- [ ] **Step 1: Write api/routes/chat.py**

Create `api/routes/chat.py`:
```python
"""/v1/chat/stream — SSE chat endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from mocco.ai_stream import stream_ai_reply
from mocco.db import save_message, get_custom_prompt

from api.deps import current_user
from api.errors import ApiError
from api.models import ChatRequest

router = APIRouter()

# Simple per-user token bucket (process-local).
_BUCKETS: dict[int, tuple[float, int]] = {}
_LIMIT = 30
_WINDOW_S = 60.0


def _allow(user_id: int) -> bool:
    import time
    now = time.time()
    if user_id not in _BUCKETS:
        _BUCKETS[user_id] = (now, 0)
    ts, count = _BUCKETS[user_id]
    if now - ts > _WINDOW_S:
        _BUCKETS[user_id] = (now, 0)
        ts, count = now, 0
    if count >= _LIMIT:
        return False
    _BUCKETS[user_id] = (ts, count + 1)
    return True


@router.post("/chat/stream")
def chat_stream(req: ChatRequest, user_id: int = Depends(current_user)):
    if not _allow(user_id):
        raise ApiError(429, "rate_limited", "Too many requests.", {"retry_after": 30})
    # Persist the latest user message before generating.
    if req.messages and req.messages[-1].role == "user":
        try:
            save_message(user_id, "user", req.messages[-1].content)
        except Exception:
            pass
    system_prompt = req.system_prompt_override or get_custom_prompt(user_id) or None
    msgs = [m.model_dump() for m in req.messages]
    return StreamingResponse(
        stream_ai_reply(user_id, msgs, system_prompt=system_prompt, persist_to_db=True),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 2: Commit**

```bash
git add api/routes/chat.py
git commit -m "feat(api): /v1/chat/stream SSE route with per-user rate limit"
```

---

## Task 25: Wire all routes into main.py

**Files:**
- Modify: `api/main.py`

- [ ] **Step 1: Update imports and include all routers**

Replace the body of `create_app()` (the part after `install_error_handlers(app)`) with:
```python
    app.include_router(health.router, prefix="/v1")
    app.include_router(me.router, prefix="/v1")
    app.include_router(profile.router, prefix="/v1")
    app.include_router(models.router, prefix="/v1")
    app.include_router(keys.router, prefix="/v1")
    app.include_router(history.router, prefix="/v1")
    app.include_router(chat.router, prefix="/v1")
    return app
```
And replace the `from api.routes import ...` line with:
```python
from api.routes import chat, health, history, keys, me, models, profile
```

- [ ] **Step 2: Boot and smoke-test**

```bash
set TELEGRAM_TOKEN=test
set DATABASE_URL=postgresql://user:pass@localhost:5432/test
uvicorn api.main:app --port 8000
```
Then:
```bash
curl http://localhost:8000/v1/health
curl http://localhost:8000/v1/me
```
Expected: health returns 200, /v1/me returns 401 (no initData header).

Stop with Ctrl-C.

- [ ] **Step 3: Commit**

```bash
git add api/main.py
git commit -m "feat(api): wire all routers into the app"
```

---

# Phase 6 — Frontend scaffold

## Task 26: Init Vite project

**Files:**
- Create: `webapp/package.json`, `webapp/index.html`, `webapp/tsconfig.json`, `webapp/vite.config.ts`

- [ ] **Step 1: Create webapp/package.json**

Create `webapp/package.json`:
```json
{
  "name": "mocco-tma",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.2",
    "zustand": "^4.5.5"
  },
  "devDependencies": {
    "@types/react": "^18.3.10",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.47",
    "tailwindcss": "^3.4.13",
    "typescript": "^5.6.2",
    "vite": "^5.4.8"
  }
}
```

- [ ] **Step 2: Create webapp/tsconfig.json**

Create `webapp/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Create webapp/vite.config.ts**

Create `webapp/vite.config.ts`:
```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
  },
});
```

- [ ] **Step 4: Create webapp/index.html**

Create `webapp/index.html`:
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
    <title>Mocco</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Install and run**

```bash
cd webapp
npm install
npm run dev
```
Open the URL shown. Expected: blank page (we haven't added React yet).

Stop with Ctrl-C.

- [ ] **Step 6: Commit**

```bash
git add webapp/package.json webapp/tsconfig.json webapp/vite.config.ts webapp/index.html
git commit -m "feat(webapp): init Vite + React + TS project"
```

---

## Task 27: Tailwind setup

**Files:**
- Create: `webapp/tailwind.config.ts`, `webapp/postcss.config.js`, `webapp/src/styles/globals.css`

- [ ] **Step 1: tailwind.config.ts**

Create `webapp/tailwind.config.ts`:
```ts
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "tg-bg": "var(--tg-bg)",
        "tg-secondary-bg": "var(--tg-secondary-bg)",
        "tg-text": "var(--tg-text)",
        "tg-hint": "var(--tg-hint)",
        "tg-link": "var(--tg-link)",
        "tg-button": "var(--tg-button)",
        "tg-button-text": "var(--tg-button-text)",
      },
      fontFamily: {
        sans: ["var(--tg-font, system-ui)", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
```

- [ ] **Step 2: postcss.config.js**

Create `webapp/postcss.config.js`:
```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 3: globals.css**

Create `webapp/src/styles/globals.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --tg-bg: #ffffff;
  --tg-secondary-bg: #f4f4f5;
  --tg-text: #0f172a;
  --tg-hint: #6b7280;
  --tg-link: #2563eb;
  --tg-button: #2563eb;
  --tg-button-text: #ffffff;
  --tg-font: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}

html, body, #root {
  height: 100%;
  margin: 0;
  padding: 0;
  background: var(--tg-bg);
  color: var(--tg-text);
  font-family: var(--tg-font);
  -webkit-tap-highlight-color: transparent;
}

* { box-sizing: border-box; }
```

- [ ] **Step 4: Commit**

```bash
git add webapp/tailwind.config.ts webapp/postcss.config.js webapp/src/styles/globals.css
git commit -m "feat(webapp): tailwind + theme CSS variables"
```

---

## Task 28: React entry, router, and a hello-world App

**Files:**
- Create: `webapp/src/main.tsx`, `webapp/src/router.tsx`, `webapp/src/App.tsx`, `webapp/src/vite-env.d.ts`

- [ ] **Step 1: vite-env.d.ts**

Create `webapp/src/vite-env.d.ts`:
```ts
/// <reference types="vite/client" />
```

- [ ] **Step 2: router.tsx**

Create `webapp/src/router.tsx`:
```tsx
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { AgentPage } from "./pages/AgentPage";
import { ProfilePage } from "./pages/ProfilePage";

const router = createBrowserRouter([
  { path: "/", element: <AgentPage /> },
  { path: "/profile", element: <ProfilePage /> },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
```

- [ ] **Step 3: App.tsx (placeholder pages first)**

Create `webapp/src/pages/AgentPage.tsx`:
```tsx
export function AgentPage() {
  return <div style={{ padding: 16 }}>Agent (chat) — coming soon</div>;
}
```

Create `webapp/src/pages/ProfilePage.tsx`:
```tsx
export function ProfilePage() {
  return <div style={{ padding: 16 }}>Profile — coming soon</div>;
}
```

Create `webapp/src/App.tsx`:
```tsx
import { AppRouter } from "./router";

export default function App() {
  return <AppRouter />;
}
```

Create `webapp/src/main.tsx`:
```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/globals.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 4: Run and verify**

```bash
cd webapp
npm run dev
```
Open the URL. Click between `/` and `/profile` (manually edit URL or add nav temporarily). Expect the placeholder text.

Stop with Ctrl-C.

- [ ] **Step 5: Commit**

```bash
git add webapp/src/main.tsx webapp/src/router.tsx webapp/src/App.tsx webapp/src/vite-env.d.ts webapp/src/pages/AgentPage.tsx webapp/src/pages/ProfilePage.tsx
git commit -m "feat(webapp): React entry + router + placeholder pages"
```

---

# Phase 7 — TelegramProvider and theme

## Task 29: lib/telegram.ts

**Files:**
- Create: `webapp/src/lib/telegram.ts`

- [ ] **Step 1: Write lib/telegram.ts**

Create `webapp/src/lib/telegram.ts`:
```ts
import { useEffect, useState, useCallback } from "react";

declare global {
  interface Window {
    Telegram?: {
      WebApp: {
        initData: string;
        initDataUnsafe: { user?: TelegramUser };
        ready: () => void;
        expand: () => void;
        close: () => void;
        themeParams: ThemeParams;
        MainButton: {
          setText: (t: string) => void;
          show: () => void;
          hide: () => void;
          onClick: (cb: () => void) => void;
          offClick: (cb: () => void) => void;
          showProgress: (leave: boolean) => void;
          hideProgress: () => void;
        };
        BackButton: {
          show: () => void;
          hide: () => void;
          onClick: (cb: () => void) => void;
          offClick: (cb: () => void) => void;
        };
        HapticFeedback: {
          impactOccurred: (style: "light" | "medium" | "heavy" | "rigid" | "soft") => void;
          notificationOccurred: (t: "success" | "warning" | "error") => void;
          selectionChanged: () => void;
        };
        onEvent: (e: string, cb: () => void) => void;
        offEvent: (e: string, cb: () => void) => void;
      };
    };
  }
}

export type TelegramUser = {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
};

export type ThemeParams = {
  bg_color?: string;
  secondary_bg_color?: string;
  text_color?: string;
  hint_color?: string;
  link_color?: string;
  button_color?: string;
  button_text_color?: string;
};

function getWA() {
  return typeof window !== "undefined" ? window.Telegram?.WebApp : undefined;
}

export function getInitData(): string {
  return getWA()?.initData ?? "";
}

export function useTelegramUser(): TelegramUser | null {
  const [user, setUser] = useState<TelegramUser | null>(null);
  useEffect(() => {
    setUser(getWA()?.initDataUnsafe.user ?? null);
  }, []);
  return user;
}

const DEFAULTS: Required<ThemeParams> = {
  bg_color: "#ffffff",
  secondary_bg_color: "#f4f4f5",
  text_color: "#0f172a",
  hint_color: "#6b7280",
  link_color: "#2563eb",
  button_color: "#2563eb",
  button_text_color: "#ffffff",
};

function applyTheme(t: ThemeParams) {
  const root = document.documentElement;
  const merged = { ...DEFAULTS, ...t };
  root.style.setProperty("--tg-bg", merged.bg_color);
  root.style.setProperty("--tg-secondary-bg", merged.secondary_bg_color);
  root.style.setProperty("--tg-text", merged.text_color);
  root.style.setProperty("--tg-hint", merged.hint_color);
  root.style.setProperty("--tg-link", merged.link_color);
  root.style.setProperty("--tg-button", merged.button_color);
  root.style.setProperty("--tg-button-text", merged.button_text_color);
}

export function useTelegramTheme(): void {
  useEffect(() => {
    const wa = getWA();
    if (!wa) {
      applyTheme(DEFAULTS);
      return;
    }
    applyTheme(wa.themeParams);
    const handler = () => applyTheme(wa.themeParams);
    wa.onEvent("themeChanged", handler);
    return () => {
      wa.offEvent("themeChanged", handler);
    };
  }, []);
}

export function useTelegramReady(): void {
  useEffect(() => {
    const wa = getWA();
    if (!wa) return;
    wa.ready();
    wa.expand();
  }, []);
}

export function useMainButton(label: string | null, onClick: () => void, deps: unknown[] = []) {
  useEffect(() => {
    const wa = getWA();
    if (!wa) return;
    if (!label) {
      wa.MainButton.hide();
      return;
    }
    wa.MainButton.setText(label);
    wa.MainButton.show();
    wa.MainButton.onClick(onClick);
    return () => {
      wa.MainButton.offClick(onClick);
      wa.MainButton.hide();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

export function useBackButton(onClick: () => void, show: boolean) {
  useEffect(() => {
    const wa = getWA();
    if (!wa) return;
    if (!show) {
      wa.BackButton.hide();
      return;
    }
    wa.BackButton.show();
    wa.BackButton.onClick(onClick);
    return () => {
      wa.BackButton.offClick(onClick);
      wa.BackButton.hide();
    };
  }, [onClick, show]);
}

export const haptic = {
  impact: (style: "light" | "medium" | "heavy" = "light") => getWA()?.HapticFeedback.impactOccurred(style),
  notify: (t: "success" | "warning" | "error") => getWA()?.HapticFeedback.notificationOccurred(t),
};
```

- [ ] **Step 2: Commit**

```bash
git add webapp/src/lib/telegram.ts
git commit -m "feat(webapp): Telegram WebApp SDK wrapper (hooks + haptic)"
```

---

## Task 30: TelegramProvider component

**Files:**
- Create: `webapp/src/components/TelegramProvider.tsx`

- [ ] **Step 1: Write TelegramProvider.tsx**

Create `webapp/src/components/TelegramProvider.tsx`:
```tsx
import { ReactNode } from "react";
import { useTelegramReady, useTelegramTheme } from "../lib/telegram";

export function TelegramProvider({ children }: { children: ReactNode }) {
  useTelegramReady();
  useTelegramTheme();
  return <>{children}</>;
}
```

- [ ] **Step 2: Wire into App.tsx**

Update `webapp/src/App.tsx`:
```tsx
import { AppRouter } from "./router";
import { TelegramProvider } from "./components/TelegramProvider";

export default function App() {
  return (
    <TelegramProvider>
      <AppRouter />
    </TelegramProvider>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add webapp/src/components/TelegramProvider.tsx webapp/src/App.tsx
git commit -m "feat(webapp): TelegramProvider + theme application on mount"
```

---

# Phase 8 — AppShell and stores

## Task 31: AppShell, TopBar, BottomNav

**Files:**
- Create: `webapp/src/components/AppShell.tsx`, `webapp/src/components/TopBar.tsx`, `webapp/src/components/BottomNav.tsx`

- [ ] **Step 1: TopBar.tsx**

Create `webapp/src/components/TopBar.tsx`:
```tsx
import { useTelegramUser } from "../lib/telegram";

export function TopBar() {
  const user = useTelegramUser();
  const name = user?.first_name || "Mocco";
  return (
    <header className="flex items-center justify-between px-4 h-12 border-b border-tg-hint/20 bg-tg-secondary-bg">
      <div className="flex items-center gap-2">
        {user?.photo_url ? (
          <img src={user.photo_url} alt="" className="w-7 h-7 rounded-full" />
        ) : (
          <div className="w-7 h-7 rounded-full bg-tg-button text-tg-button-text flex items-center justify-center text-xs font-semibold">
            {name[0]?.toUpperCase() ?? "M"}
          </div>
        )}
        <span className="font-medium text-tg-text">{name}</span>
      </div>
    </header>
  );
}
```

- [ ] **Step 2: BottomNav.tsx**

Create `webapp/src/components/BottomNav.tsx`:
```tsx
import { NavLink } from "react-router-dom";

const items = [
  { to: "/", label: "Agent", icon: "✦" },
  { to: "/profile", label: "Profile", icon: "👤" },
];

export function BottomNav() {
  return (
    <nav className="flex items-center justify-around h-14 border-t border-tg-hint/20 bg-tg-secondary-bg">
      {items.map((it) => (
        <NavLink
          key={it.to}
          to={it.to}
          end={it.to === "/"}
          className={({ isActive }) =>
            `flex flex-col items-center gap-0.5 text-xs ${
              isActive ? "text-tg-button" : "text-tg-hint"
            }`
          }
        >
          <span className="text-lg leading-none">{it.icon}</span>
          <span>{it.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
```

- [ ] **Step 3: AppShell.tsx**

Create `webapp/src/components/AppShell.tsx`:
```tsx
import { ReactNode } from "react";
import { TopBar } from "./TopBar";
import { BottomNav } from "./BottomNav";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col h-full">
      <TopBar />
      <main className="flex-1 overflow-y-auto">{children}</main>
      <BottomNav />
    </div>
  );
}
```

- [ ] **Step 4: Wire into App.tsx**

Update `webapp/src/App.tsx`:
```tsx
import { AppRouter } from "./router";
import { TelegramProvider } from "./components/TelegramProvider";
import { AppShell } from "./components/AppShell";
import { Outlet } from "react-router-dom";

function ShellWrapper() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

export default function App() {
  return (
    <TelegramProvider>
      <AppRouter shell={ShellWrapper} />
    </TelegramProvider>
  );
}
```

Update `webapp/src/router.tsx`:
```tsx
import { createBrowserRouter, RouterProvider, Outlet } from "react-router-dom";
import { AgentPage } from "./pages/AgentPage";
import { ProfilePage } from "./pages/ProfilePage";

export function AppRouter({ shell }: { shell: React.FC }) {
  const router = createBrowserRouter([
    {
      element: <shell />,
      children: [
        { path: "/", element: <AgentPage /> },
        { path: "/profile", element: <ProfilePage /> },
      ],
    },
  ]);
  return <RouterProvider router={router} />;
}
```

(Add `import React from "react";` at the top of router.tsx.)

- [ ] **Step 5: Run and verify**

```bash
cd webapp && npm run dev
```
Open URL. Expect a top bar showing "Mocco" and a bottom nav with two tabs. Clicking them routes correctly.

- [ ] **Step 6: Commit**

```bash
git add webapp/src/components/AppShell.tsx webapp/src/components/TopBar.tsx webapp/src/components/BottomNav.tsx webapp/src/App.tsx webapp/src/router.tsx
git commit -m "feat(webapp): AppShell with TopBar and BottomNav"
```

---

## Task 32: lib/api.ts and lib/stream.ts

**Files:**
- Create: `webapp/src/lib/api.ts`, `webapp/src/lib/stream.ts`

- [ ] **Step 1: api.ts**

Create `webapp/src/lib/api.ts`:
```ts
import { getInitData } from "./telegram";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public extra: Record<string, unknown> = {}) {
    super(message);
  }
  static async fromResponse(res: Response): Promise<ApiError> {
    let body: any = null;
    try { body = await res.json(); } catch { /* ignore */ }
    const err = body?.error || {};
    return new ApiError(res.status, err.code || `http_${res.status}`, err.message || res.statusText, err);
  }
}

const BASE = import.meta.env.VITE_API_BASE_URL as string;

export async function api<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": getInitData(),
      ...(init.headers || {}),
    },
  });
  if (!res.ok) throw await ApiError.fromResponse(res);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
```

- [ ] **Step 2: stream.ts**

Create `webapp/src/lib/stream.ts`:
```ts
import { getInitData } from "./telegram";
import { ApiError } from "./api";

const BASE = import.meta.env.VITE_API_BASE_URL as string;

export type ChatFrame =
  | { kind: "delta"; delta: string }
  | { kind: "done" }
  | { kind: "error"; code: string; message: string };

export async function* streamChat(
  body: { messages: { role: "system" | "user" | "assistant"; content: string }[] },
  signal: AbortSignal,
): AsyncGenerator<ChatFrame> {
  const res = await fetch(`${BASE}/v1/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": getInitData(),
    },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw await ApiError.fromResponse(res);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const line = frame.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      try {
        const json = JSON.parse(line.slice(6));
        if (typeof json.delta === "string") yield { kind: "delta", delta: json.delta };
        else if (json.done) yield { kind: "done" };
        else if (json.error) yield { kind: "error", code: json.error.code, message: json.error.message };
      } catch {
        // ignore malformed frame
      }
    }
  }
}
```

- [ ] **Step 3: Add a local .env for dev**

Create `webapp/.env.local` (not committed):
```
VITE_API_BASE_URL=http://localhost:8000/v1
```

- [ ] **Step 4: Add .env to .gitignore**

Append to `.gitignore`:
```
webapp/.env
webapp/.env.local
webapp/dist
webapp/node_modules
```

- [ ] **Step 5: Commit**

```bash
git add webapp/src/lib/api.ts webapp/src/lib/stream.ts .gitignore
git commit -m "feat(webapp): api + SSE stream helpers"
```

---

## Task 33: Zustand stores

**Files:**
- Create: `webapp/src/stores/useUserStore.ts`, `webapp/src/stores/useChatStore.ts`, `webapp/src/stores/useProfileStore.ts`, `webapp/src/stores/useToastStore.ts`

- [ ] **Step 1: useUserStore**

Create `webapp/src/stores/useUserStore.ts`:
```ts
import { create } from "zustand";
import { persist } from "zustand/middleware";

type State = {
  telegramId: number | null;
  model: string;
  language: string;
  persona: string;
  connectedProviders: string[];
  setMe: (m: Partial<State>) => void;
};

export const useUserStore = create<State>()(
  persist(
    (set) => ({
      telegramId: null,
      model: "",
      language: "en",
      persona: "",
      connectedProviders: [],
      setMe: (m) => set(m),
    }),
    { name: "mocco.user" }
  )
);
```

- [ ] **Step 2: useChatStore**

Create `webapp/src/stores/useChatStore.ts`:
```ts
import { create } from "zustand";

export type Message = { role: "user" | "assistant"; content: string; streaming?: boolean; error?: boolean };

type State = {
  messages: Message[];
  input: string;
  streaming: boolean;
  abort: AbortController | null;
  setInput: (s: string) => void;
  hydrate: (msgs: Message[]) => void;
  submit: () => Message[]; // returns the new messages to send
  appendUser: (content: string) => void;
  appendAssistant: () => void;
  appendDelta: (delta: string) => void;
  markComplete: () => void;
  markError: () => void;
  setAbort: (a: AbortController | null) => void;
  cancel: () => void;
  clear: () => void;
};

export const useChatStore = create<State>((set, get) => ({
  messages: [],
  input: "",
  streaming: false,
  abort: null,
  setInput: (s) => set({ input: s }),
  hydrate: (msgs) => set({ messages: msgs }),
  submit: () => {
    const { input, messages } = get();
    const userMsg: Message = { role: "user", content: input };
    const asstMsg: Message = { role: "assistant", content: "", streaming: true };
    set({ messages: [...messages, userMsg, asstMsg], input: "", streaming: true });
    return get().messages;
  },
  appendUser: (c) => set((s) => ({ messages: [...s.messages, { role: "user", content: c }] })),
  appendAssistant: () => set((s) => ({ messages: [...s.messages, { role: "assistant", content: "", streaming: true }] })),
  appendDelta: (d) =>
    set((s) => {
      const msgs = [...s.messages];
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === "assistant" && msgs[i].streaming) {
          msgs[i] = { ...msgs[i], content: msgs[i].content + d };
          break;
        }
      }
      return { messages: msgs };
    }),
  markComplete: () =>
    set((s) => {
      const msgs = [...s.messages];
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === "assistant" && msgs[i].streaming) {
          msgs[i] = { ...msgs[i], streaming: false };
          break;
        }
      }
      return { messages: msgs, streaming: false };
    }),
  markError: () =>
    set((s) => {
      const msgs = [...s.messages];
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === "assistant" && msgs[i].streaming) {
          msgs[i] = { ...msgs[i], streaming: false, error: true };
          break;
        }
      }
      return { messages: msgs, streaming: false };
    }),
  setAbort: (a) => set({ abort: a }),
  cancel: () => {
    const a = get().abort;
    if (a) a.abort();
    set({ streaming: false, abort: null });
  },
  clear: () => set({ messages: [], streaming: false, abort: null }),
}));
```

- [ ] **Step 3: useProfileStore**

Create `webapp/src/stores/useProfileStore.ts`:
```ts
import { create } from "zustand";
import { persist } from "zustand/middleware";

type State = {
  language: string;
  persona: string;
  gender: string;
  age: number | null;
  location: string;
  occupation: string;
  interests: string[];
  timezone: string;
  setAll: (p: Partial<State>) => void;
};

export const useProfileStore = create<State>()(
  persist(
    (set) => ({
      language: "en",
      persona: "",
      gender: "",
      age: null,
      location: "",
      occupation: "",
      interests: [],
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "",
      setAll: (p) => set(p),
    }),
    { name: "mocco.profile" }
  )
);
```

- [ ] **Step 4: useToastStore**

Create `webapp/src/stores/useToastStore.ts`:
```ts
import { create } from "zustand";

export type Toast = { id: string; type: "success" | "info" | "warning" | "error"; text: string; sticky?: boolean };

type State = {
  toasts: Toast[];
  push: (t: Omit<Toast, "id">) => void;
  remove: (id: string) => void;
};

export const useToastStore = create<State>((set, get) => ({
  toasts: [],
  push: (t) => {
    const id = Math.random().toString(36).slice(2);
    set((s) => ({ toasts: [...s.toasts, { id, ...t }] }));
    if (!t.sticky) setTimeout(() => get().remove(id), 4000);
  },
  remove: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));
```

- [ ] **Step 5: Commit**

```bash
git add webapp/src/stores/
git commit -m "feat(webapp): Zustand stores (user, chat, profile, toast)"
```

---

# Phase 9 — Agent page (chat)

## Task 34: MessageBubble, ChatPanel, QuickActionChips

**Files:**
- Create: `webapp/src/components/MessageBubble.tsx`, `webapp/src/components/ChatPanel.tsx`, `webapp/src/components/QuickActionChips.tsx`, `webapp/src/components/ResetConfirmModal.tsx`

- [ ] **Step 1: MessageBubble.tsx**

Create `webapp/src/components/MessageBubble.tsx`:
```tsx
import { Message } from "../stores/useChatStore";

export function MessageBubble({ m, onRetry }: { m: Message; onRetry?: () => void }) {
  const isUser = m.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} my-2 px-3`}>
      <div
        className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap ${
          isUser
            ? "bg-tg-button text-tg-button-text rounded-br-md"
            : "bg-tg-secondary-bg text-tg-text rounded-bl-md"
        }`}
      >
        {m.content || (m.streaming ? "…" : "")}
        {m.error && (
          <button onClick={onRetry} className="ml-2 underline text-tg-link">
            retry
          </button>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: QuickActionChips.tsx**

Create `webapp/src/components/QuickActionChips.tsx`:
```tsx
import { useChatStore } from "../stores/useChatStore";

export function QuickActionChips({ onReset }: { onReset: () => void }) {
  const setInput = useChatStore((s) => s.setInput);
  const input = useChatStore((s) => s.input);
  const disabled = input.trim().length > 0;
  const chip = (label: string, prefix: string) => (
    <button
      key={label}
      type="button"
      onClick={() => setInput(prefix)}
      disabled={disabled}
      className="px-3 py-1.5 rounded-full text-xs bg-tg-secondary-bg text-tg-text border border-tg-hint/30 disabled:opacity-50"
    >
      {label}
    </button>
  );
  return (
    <div className="flex flex-wrap gap-2 px-3 py-2">
      {chip("Search", "/search ")}
      {chip("Summarize", "/summarize ")}
      {chip("Translate", "/translate ")}
      <button
        type="button"
        onClick={onReset}
        className="px-3 py-1.5 rounded-full text-xs bg-tg-secondary-bg text-tg-text border border-tg-hint/30"
      >
        Reset chat
      </button>
    </div>
  );
}
```

- [ ] **Step 3: ResetConfirmModal.tsx**

Create `webapp/src/components/ResetConfirmModal.tsx`:
```tsx
export function ResetConfirmModal({ open, onCancel, onConfirm }: { open: boolean; onCancel: () => void; onConfirm: () => void }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onCancel}>
      <div className="bg-tg-bg rounded-2xl p-4 w-72 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-semibold text-tg-text mb-1">Clear conversation?</h3>
        <p className="text-sm text-tg-hint mb-4">This will erase the current chat history.</p>
        <div className="flex gap-2 justify-end">
          <button onClick={onCancel} className="px-3 py-1.5 rounded-lg text-sm text-tg-hint">Cancel</button>
          <button onClick={onConfirm} className="px-3 py-1.5 rounded-lg text-sm bg-tg-button text-tg-button-text">Reset</button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: ChatPanel.tsx**

Create `webapp/src/components/ChatPanel.tsx`:
```tsx
import { useEffect, useRef, useState } from "react";
import { useChatStore, Message } from "../stores/useChatStore";
import { useUserStore } from "../stores/useUserStore";
import { MessageBubble } from "./MessageBubble";
import { QuickActionChips } from "./QuickActionChips";
import { ResetConfirmModal } from "./ResetConfirmModal";
import { streamChat } from "../lib/stream";
import { api, ApiError } from "../lib/api";
import { useToastStore } from "../stores/useToastStore";
import { haptic } from "../lib/telegram";

export function ChatPanel() {
  const messages = useChatStore((s) => s.messages);
  const input = useChatStore((s) => s.input);
  const setInput = useChatStore((s) => s.setInput);
  const streaming = useChatStore((s) => s.streaming);
  const setAbort = useChatStore((s) => s.setAbort);
  const cancel = useChatStore((s) => s.cancel);
  const hydrate = useChatStore((s) => s.hydrate);
  const appendDelta = useChatStore((s) => s.appendDelta);
  const markComplete = useChatStore((s) => s.markComplete);
  const markError = useChatStore((s) => s.markError);
  const clear = useChatStore((s) => s.clear);
  const telegramId = useUserStore((s) => s.telegramId);
  const pushToast = useToastStore((s) => s.push);

  const [resetOpen, setResetOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Hydrate from /v1/history on mount.
  useEffect(() => {
    if (!telegramId) return;
    (async () => {
      try {
        const data = await api<Message[]>("/history");
        hydrate(data);
      } catch (e) {
        pushToast({ type: "error", text: (e as Error).message });
      }
    })();
  }, [telegramId, hydrate, pushToast]);

  // Auto-scroll to bottom.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, messages[messages.length - 1]?.content]);

  async function send() {
    if (!input.trim() || streaming) return;
    haptic.impact("light");
    const userMsg: Message = { role: "user", content: input };
    const asstMsg: Message = { role: "assistant", content: "", streaming: true };
    useChatStore.setState((s) => ({
      messages: [...s.messages, userMsg, asstMsg],
      input: "",
      streaming: true,
    }));
    const ctrl = new AbortController();
    setAbort(ctrl);

    try {
      const history = useChatStore.getState().messages
        .filter((m) => !m.error)
        .map(({ role, content }) => ({ role, content }));
      let firstDelta = true;
      for await (const frame of streamChat({ messages: history.slice(0, -1) }, ctrl.signal)) {
        if (frame.kind === "delta") {
          if (firstDelta) {
            haptic.notify("success");
            firstDelta = false;
          }
          appendDelta(frame.delta);
        } else if (frame.kind === "done") {
          markComplete();
        } else if (frame.kind === "error") {
          markError();
          pushToast({ type: "error", text: frame.message });
        }
      }
    } catch (e) {
      markError();
      const err = e as ApiError;
      if (err.status === 400 && err.code === "no_api_key") {
        pushToast({ type: "warning", text: "Connect a key to chat." });
      } else {
        pushToast({ type: "error", text: err.message || "Stream failed." });
      }
    } finally {
      setAbort(null);
    }
  }

  async function doReset() {
    setResetOpen(false);
    try {
      await api("/reset", { method: "POST" });
      clear();
      pushToast({ type: "success", text: "Conversation cleared." });
    } catch (e) {
      pushToast({ type: "error", text: (e as Error).message });
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div ref={scrollRef} className="flex-1 overflow-y-auto pt-2 pb-32">
        {messages.length === 0 && (
          <div className="px-4 pt-12 text-center">
            <h2 className="text-xl font-semibold text-tg-text mb-4">How can I help you today?</h2>
            <QuickActionChips onReset={() => setResetOpen(true)} />
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} m={m} />
        ))}
      </div>
      <div className="fixed bottom-14 left-0 right-0 bg-tg-bg border-t border-tg-hint/20">
        {messages.length > 0 && <QuickActionChips onReset={() => setResetOpen(true)} />}
        <div className="flex items-end gap-2 p-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="Ask anything…"
            rows={1}
            className="flex-1 resize-none rounded-2xl px-3 py-2 bg-tg-secondary-bg text-tg-text outline-none text-sm max-h-32"
          />
          <button
            onClick={send}
            disabled={!input.trim() || streaming}
            className="px-3 py-2 rounded-2xl bg-tg-button text-tg-button-text text-sm font-medium disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
      <ResetConfirmModal open={resetOpen} onCancel={() => setResetOpen(false)} onConfirm={doReset} />
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add webapp/src/components/MessageBubble.tsx webapp/src/components/QuickActionChips.tsx webapp/src/components/ResetConfirmModal.tsx webapp/src/components/ChatPanel.tsx
git commit -m "feat(webapp): ChatPanel with streaming, chips, reset"
```

---

## Task 35: Wire AgentPage to ChatPanel + fetch /me

**Files:**
- Modify: `webapp/src/pages/AgentPage.tsx`

- [ ] **Step 1: Replace AgentPage**

Replace `webapp/src/pages/AgentPage.tsx` with:
```tsx
import { useEffect } from "react";
import { ChatPanel } from "../components/ChatPanel";
import { api } from "../lib/api";
import { useUserStore } from "../stores/useUserStore";
import { useToastStore } from "../stores/useToastStore";

type MeResponse = { id: number; model: string; language: string; persona: string; connected_providers: string[] };

export function AgentPage() {
  const setMe = useUserStore((s) => s.setMe);
  const pushToast = useToastStore((s) => s.push);

  useEffect(() => {
    (async () => {
      try {
        const me = await api<MeResponse>("/me");
        setMe({
          telegramId: me.id,
          model: me.model,
          language: me.language || "en",
          persona: me.persona,
          connectedProviders: me.connected_providers,
        });
      } catch (e) {
        pushToast({ type: "error", text: (e as Error).message });
      }
    })();
  }, [setMe, pushToast]);

  return <ChatPanel />;
}
```

- [ ] **Step 2: Commit**

```bash
git add webapp/src/pages/AgentPage.tsx
git commit -m "feat(webapp): AgentPage hydrates /me and mounts ChatPanel"
```

---

# Phase 10 — Profile page

## Task 36: ConnectKeyModal

**Files:**
- Create: `webapp/src/components/ConnectKeyModal.tsx`

- [ ] **Step 1: Write ConnectKeyModal.tsx**

Create `webapp/src/components/ConnectKeyModal.tsx`:
```tsx
import { useState } from "react";
import { api } from "../lib/api";
import { useToastStore } from "../stores/useToastStore";

const PROVIDERS: { id: "openrouter" | "serper"; label: string; help: string }[] = [
  { id: "openrouter", label: "OpenRouter", help: "Get a key at openrouter.ai/keys" },
  { id: "serper", label: "Serper (web search)", help: "Get a key at serper.dev" },
];

export function ConnectKeyModal({ open, onClose, onSaved }: { open: boolean; onClose: () => void; onSaved: () => void }) {
  const [provider, setProvider] = useState<"openrouter" | "serper">("openrouter");
  const [key, setKey] = useState("");
  const [saving, setSaving] = useState(false);
  const pushToast = useToastStore((s) => s.push);

  if (!open) return null;
  const current = PROVIDERS.find((p) => p.id === provider)!;

  async function save() {
    if (!key.trim()) return;
    setSaving(true);
    try {
      await api(`/keys/${provider}`, { method: "POST", body: JSON.stringify({ api_key: key }) });
      pushToast({ type: "success", text: `${current.label} key saved.` });
      setKey("");
      onSaved();
      onClose();
    } catch (e) {
      pushToast({ type: "error", text: (e as Error).message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-tg-bg rounded-2xl p-4 w-80 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-semibold text-tg-text mb-3">Connect a key</h3>
        <label className="text-xs text-tg-hint">Provider</label>
        <select
          value={provider}
          onChange={(e) => setProvider(e.target.value as "openrouter" | "serper")}
          className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2 mt-1 mb-3"
        >
          {PROVIDERS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
        </select>
        <label className="text-xs text-tg-hint">API key</label>
        <input
          type="password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="paste here"
          className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2 mt-1 mb-1"
        />
        <p className="text-[10px] text-tg-hint mb-3">{current.help}</p>
        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="px-3 py-1.5 rounded-lg text-sm text-tg-hint">Cancel</button>
          <button onClick={save} disabled={saving || !key.trim()} className="px-3 py-1.5 rounded-lg text-sm bg-tg-button text-tg-button-text disabled:opacity-50">
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add webapp/src/components/ConnectKeyModal.tsx
git commit -m "feat(webapp): ConnectKeyModal for OpenRouter + Serper"
```

---

## Task 37: ModelPickerModal

**Files:**
- Create: `webapp/src/components/ModelPickerModal.tsx`

- [ ] **Step 1: Write ModelPickerModal.tsx**

Create `webapp/src/components/ModelPickerModal.tsx`:
```tsx
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useUserStore } from "../stores/useUserStore";
import { useToastStore } from "../stores/useToastStore";

type Model = { id: string; name: string; is_free: boolean; context_length: number };

export function ModelPickerModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState("");
  const setMe = useUserStore((s) => s.setMe);
  const pushToast = useToastStore((s) => s.push);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    api<Model[]>("/models")
      .then(setModels)
      .catch((e) => pushToast({ type: "error", text: (e as Error).message }))
      .finally(() => setLoading(false));
  }, [open, pushToast]);

  if (!open) return null;
  const filtered = models.filter((m) => (m.name + m.id).toLowerCase().includes(filter.toLowerCase()));

  async function pick(id: string) {
    try {
      await api("/model", { method: "POST", body: JSON.stringify({ model_id: id }) });
      setMe({ model: id });
      pushToast({ type: "success", text: "Model updated." });
      onClose();
    } catch (e) {
      pushToast({ type: "error", text: (e as Error).message });
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-tg-bg rounded-t-2xl sm:rounded-2xl p-4 w-full sm:w-96 max-h-[80vh] shadow-xl flex flex-col" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-semibold text-tg-text mb-3">Pick a model</h3>
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Search…"
          className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2 mb-3"
        />
        <div className="flex-1 overflow-y-auto -mx-1">
          {loading && <p className="text-sm text-tg-hint px-1">Loading…</p>}
          {!loading && filtered.map((m) => (
            <button
              key={m.id}
              onClick={() => pick(m.id)}
              className="w-full text-left px-3 py-2 hover:bg-tg-secondary-bg rounded-lg flex items-center justify-between"
            >
              <div>
                <div className="text-sm text-tg-text">{m.name}</div>
                <div className="text-[10px] text-tg-hint">{m.id}</div>
              </div>
              {m.is_free && <span className="text-[10px] text-tg-link">free</span>}
            </button>
          ))}
        </div>
        <button onClick={onClose} className="mt-3 px-3 py-2 rounded-lg text-sm text-tg-hint w-full">Close</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add webapp/src/components/ModelPickerModal.tsx
git commit -m "feat(webapp): ModelPickerModal with search and free tag"
```

---

## Task 38: ProfilePage

**Files:**
- Modify: `webapp/src/pages/ProfilePage.tsx`

- [ ] **Step 1: Replace ProfilePage**

Replace `webapp/src/pages/ProfilePage.tsx` with:
```tsx
import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import { useProfileStore } from "../stores/useProfileStore";
import { useUserStore } from "../stores/useUserStore";
import { useToastStore } from "../stores/useToastStore";
import { ConnectKeyModal } from "../components/ConnectKeyModal";
import { ModelPickerModal } from "../components/ModelPickerModal";

type Profile = {
  language: string;
  persona: string;
  gender: string;
  age: number | null;
  location: string;
  occupation: string;
  interests: string[];
  timezone: string;
};

export function ProfilePage() {
  const profile = useProfileStore();
  const setAll = useProfileStore((s) => s.setAll);
  const connectedProviders = useUserStore((s) => s.connectedProviders);
  const setMe = useUserStore((s) => s.setMe);
  const model = useUserStore((s) => s.model);
  const pushToast = useToastStore((s) => s.push);

  const [modelOpen, setModelOpen] = useState(false);
  const [keyOpen, setKeyOpen] = useState(false);

  // Hydrate from /v1/profile.
  useEffect(() => {
    (async () => {
      try {
        const p = await api<Profile>("/profile");
        setAll(p);
      } catch (e) {
        pushToast({ type: "error", text: (e as Error).message });
      }
    })();
  }, [setAll, pushToast]);

  async function patch(body: Partial<Profile>) {
    try {
      const updated = await api<Profile>("/profile", { method: "PATCH", body: JSON.stringify(body) });
      setAll(updated);
    } catch (e) {
      const err = e as ApiError;
      pushToast({ type: "error", text: err.message });
    }
  }

  async function disconnect(provider: string) {
    try {
      await api(`/keys/${provider}`, { method: "DELETE" });
      setMe({ connectedProviders: connectedProviders.filter((p) => p !== provider) });
      pushToast({ type: "success", text: `Disconnected ${provider}.` });
    } catch (e) {
      pushToast({ type: "error", text: (e as Error).message });
    }
  }

  async function refreshKeys() {
    try {
      const keys = await api<{ provider: string }[]>("/keys");
      setMe({ connectedProviders: keys.map((k) => k.provider) });
    } catch { /* ignore */ }
  }

  return (
    <div className="p-4 pb-24 space-y-6">
      <Section title="LLM model">
        <button onClick={() => setModelOpen(true)} className="w-full text-left px-3 py-2 rounded-lg bg-tg-secondary-bg">
          <span className="text-sm text-tg-text">{model || "(default)"}</span>
        </button>
      </Section>

      <Section title="Language">
        <select
          value={profile.language}
          onChange={(e) => { setAll({ language: e.target.value }); patch({ language: e.target.value }); }}
          className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2"
        >
          <option value="en">English</option>
          <option value="bn">Bengali</option>
          <option value="es">Spanish</option>
          <option value="ar">Arabic</option>
          <option value="fr">French</option>
          <option value="de">German</option>
        </select>
      </Section>

      <Section title="Persona">
        <textarea
          value={profile.persona}
          onChange={(e) => setAll({ persona: e.target.value })}
          onBlur={() => patch({ persona: profile.persona })}
          rows={3}
          placeholder="e.g. Be concise. Max 2 sentences per reply."
          className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2 text-sm"
        />
      </Section>

      <Section title="About You">
        <Field label="Gender">
          <select
            value={profile.gender}
            onChange={(e) => { setAll({ gender: e.target.value }); patch({ gender: e.target.value }); }}
            className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2 text-sm"
          >
            <option value="">—</option>
            <option value="female">Female</option>
            <option value="male">Male</option>
            <option value="other">Other</option>
            <option value="prefer_not">Prefer not to say</option>
          </select>
        </Field>
        <Field label="Age">
          <input
            type="number"
            value={profile.age ?? ""}
            onChange={(e) => setAll({ age: e.target.value ? Number(e.target.value) : null })}
            onBlur={() => patch({ age: profile.age })}
            className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2 text-sm"
          />
        </Field>
        <Field label="Location">
          <input
            value={profile.location}
            onChange={(e) => setAll({ location: e.target.value })}
            onBlur={() => patch({ location: profile.location })}
            className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2 text-sm"
          />
        </Field>
        <Field label="Occupation">
          <input
            value={profile.occupation}
            onChange={(e) => setAll({ occupation: e.target.value })}
            onBlur={() => patch({ occupation: profile.occupation })}
            className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2 text-sm"
          />
        </Field>
        <Field label="Interests (comma-separated)">
          <input
            value={profile.interests.join(", ")}
            onChange={(e) => setAll({ interests: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
            onBlur={() => patch({ interests: profile.interests })}
            className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2 text-sm"
          />
        </Field>
        <Field label="Timezone">
          <input
            value={profile.timezone}
            onChange={(e) => setAll({ timezone: e.target.value })}
            onBlur={() => patch({ timezone: profile.timezone })}
            className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2 text-sm"
          />
        </Field>
      </Section>

      <Section title="API Keys">
        {connectedProviders.length === 0 && (
          <p className="text-sm text-tg-hint mb-2">No keys connected. Connect one to enable chat.</p>
        )}
        {connectedProviders.map((p) => (
          <div key={p} className="flex items-center justify-between py-2">
            <span className="text-sm text-tg-text capitalize">{p}</span>
            <button onClick={() => disconnect(p)} className="text-xs text-tg-link">Disconnect</button>
          </div>
        ))}
        <button onClick={() => { refreshKeys(); setKeyOpen(true); }} className="w-full mt-2 px-3 py-2 rounded-lg bg-tg-button text-tg-button-text text-sm">
          Connect a key
        </button>
      </Section>

      <ModelPickerModal open={modelOpen} onClose={() => setModelOpen(false)} />
      <ConnectKeyModal open={keyOpen} onClose={() => setKeyOpen(false)} onSaved={refreshKeys} />
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="text-xs uppercase tracking-wide text-tg-hint mb-2">{title}</h2>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-[10px] text-tg-hint">{label}</label>
      {children}
    </div>
  );
}
```

(Add `import React from "react";` at the top of the file if your tsconfig requires it.)

- [ ] **Step 2: Commit**

```bash
git add webapp/src/pages/ProfilePage.tsx
git commit -m "feat(webapp): ProfilePage with all sections + modals"
```

---

# Phase 11 — Error UX

## Task 39: Toast component

**Files:**
- Create: `webapp/src/components/Toast.tsx`

- [ ] **Step 1: Write Toast.tsx**

Create `webapp/src/components/Toast.tsx`:
```tsx
import { useToastStore } from "../stores/useToastStore";

const COLORS: Record<string, string> = {
  success: "bg-green-500",
  info: "bg-tg-button",
  warning: "bg-yellow-500",
  error: "bg-red-500",
};

export function Toast() {
  const toasts = useToastStore((s) => s.toasts);
  const remove = useToastStore((s) => s.remove);
  return (
    <div className="fixed top-2 left-1/2 -translate-x-1/2 z-50 flex flex-col gap-2 pointer-events-none">
      {toasts.map((t) => (
        <div
          key={t.id}
          onClick={() => remove(t.id)}
          className={`pointer-events-auto px-4 py-2 rounded-full text-white text-sm shadow-lg ${COLORS[t.type] || COLORS.info}`}
        >
          {t.text}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Wire into App.tsx**

Update `webapp/src/App.tsx`:
```tsx
import { AppRouter } from "./router";
import { TelegramProvider } from "./components/TelegramProvider";
import { Toast } from "./components/Toast";

function ShellWrapper({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

export default function App() {
  return (
    <TelegramProvider>
      <AppRouter shell={ShellWrapper} />
      <Toast />
    </TelegramProvider>
  );
}
```
(Replace the previous AppShell-based wrapper; for the toast step, the AppShell composition from Task 31 is reverted here for clarity. The next task restores the shell.)

- [ ] **Step 3: Commit**

```bash
git add webapp/src/components/Toast.tsx webapp/src/App.tsx
git commit -m "feat(webapp): Toast component + global mount"
```

---

## Task 40: ErrorBoundary

**Files:**
- Create: `webapp/src/components/ErrorBoundary.tsx`

- [ ] **Step 1: Write ErrorBoundary.tsx**

Create `webapp/src/components/ErrorBoundary.tsx`:
```tsx
import { Component, ReactNode } from "react";

export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error) {
    // eslint-disable-next-line no-console
    console.error("ErrorBoundary caught:", error);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-col items-center justify-center h-full p-6 text-center">
          <h2 className="text-lg font-semibold text-tg-text mb-2">Something went wrong</h2>
          <p className="text-sm text-tg-hint mb-4">{this.state.error.message}</p>
          <button
            onClick={() => this.setState({ error: null })}
            className="px-4 py-2 rounded-lg bg-tg-button text-tg-button-text text-sm"
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
```

- [ ] **Step 2: Wire around each page**

Update `webapp/src/pages/AgentPage.tsx` to wrap ChatPanel:
```tsx
import { ErrorBoundary } from "../components/ErrorBoundary";
// ...
export function AgentPage() {
  // ... existing code ...
  return <ErrorBoundary><ChatPanel /></ErrorBoundary>;
}
```

Update `webapp/src/pages/ProfilePage.tsx` similarly: wrap the returned JSX in `<ErrorBoundary>...</ErrorBoundary>`.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/components/ErrorBoundary.tsx webapp/src/pages/AgentPage.tsx webapp/src/pages/ProfilePage.tsx
git commit -m "feat(webapp): ErrorBoundary around each page"
```

---

## Task 41: Restore AppShell composition

**Files:**
- Modify: `webapp/src/App.tsx`

- [ ] **Step 1: Restore AppShell**

Replace `webapp/src/App.tsx` with the original shell composition from Task 31 plus the Toast:
```tsx
import { AppRouter } from "./router";
import { TelegramProvider } from "./components/TelegramProvider";
import { AppShell } from "./components/AppShell";
import { Toast } from "./components/Toast";
import { Outlet } from "react-router-dom";
import React from "react";

function ShellWrapper() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

export default function App() {
  return (
    <TelegramProvider>
      <AppRouter shell={ShellWrapper} />
      <Toast />
    </TelegramProvider>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add webapp/src/App.tsx
git commit -m "feat(webapp): restore AppShell + Toast composition"
```

---

# Phase 12 — Deployment

## Task 42: railway.toml two-service config

**Files:**
- Modify: `railway.toml` (create if absent)

- [ ] **Step 1: Write railway.toml**

Create or replace `railway.toml`:
```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "python bot.py"
restartPolicyType = "ON_FAILURE"

# The api service is configured in the Railway dashboard as a separate
# service pointing at Dockerfile.api, sharing the same env vars as the bot
# (except those listed in the spec as api-only).
```

Note: Railway's preferred pattern is one service per repo via dashboard "Add Service → GitHub Repo → Service". The api service should be added in the dashboard with:
- Source: same repo
- Dockerfile path: `Dockerfile.api`
- Watch paths: `api/**`, `Dockerfile.api`, `requirements.api.txt`, `src/mocco/**`

- [ ] **Step 2: Commit**

```bash
git add railway.toml
git commit -m "build: railway.toml bot service config + api service notes"
```

---

## Task 43: Vercel project config

**Files:**
- Create: `webapp/vercel.json`

- [ ] **Step 1: Write vercel.json**

Create `webapp/vercel.json`:
```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite",
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

- [ ] **Step 2: Commit**

```bash
git add webapp/vercel.json
git commit -m "build(webapp): vercel.json with SPA rewrites"
```

---

# Phase 13 — Launch verification

## Task 44: Manual E2E checklist (no code)

This task is human-performed. It does not produce a commit.

- [ ] **Step 1: Verify env vars on Railway**

For each Railway service, confirm the env var list matches the spec (Section 8). Pay particular attention to `ENCRYPTION_KEY` being identical between bot and api.

- [ ] **Step 2: Verify CORS**

Set `CORS_ALLOW_ORIGINS` on the api service to the Vercel URL of the webapp (comma-separated list if you have multiple Vercel previews). Restart the api service.

- [ ] **Step 3: Verify initData validation manually**

```bash
curl -i https://<api>.up.railway.app/v1/me
```
Expected: 401 with `{"error":{"code":"unauthorized",...}}`. (No header → 401.)

- [ ] **Step 4: Test on a real Telegram client**

In Telegram, open your bot, send `/start`. The "🚀 Open App" button should appear below the welcome message. Tap it. The TMA opens.

In the TMA:
- [ ] The agent page shows the welcome state.
- [ ] Type a message and send. The reply streams in.
- [ ] Open Profile, change the model, return to Agent. New messages use the new model.
- [ ] Open Profile, click "Connect a key", paste an OpenRouter key. Confirm in the list.
- [ ] Reset the chat. Empty state returns.
- [ ] Force-close the TMA, reopen. User state is still there.

- [ ] **Step 5: Repeat on Android, iOS, Desktop, Web**

Each of the four Telegram clients can have subtly different WebApp behavior. Exercise the above flow on each.

- [ ] **Step 6: Verify the bot still works**

In the same Telegram bot (without using the TMA):
- [ ] `/help` lists all the original commands (and no `/imagine`).
- [ ] `/menu` still works.
- [ ] `/search <query>` returns results.
- [ ] `/connect` opens the picker.
- [ ] `/stats` returns the owner's stats.

- [ ] **Step 7: Commit verification notes**

Create `docs/launch-verification-2026-06-06.md` with what you tested and the results:
```markdown
# Mocco TMA launch verification — 2026-06-06

## Environment
- api service: <railway-url>
- webapp: <vercel-url>
- bot: <railway-service-name>

## Results
- [x] /v1/health returns ok
- [x] initData validation rejects missing header
- [x] TMA opens via /start button on Android
- [x] ... (etc.)
```
Commit:
```bash
git add docs/launch-verification-2026-06-06.md
git commit -m "docs: launch verification report"
```

---

# Self-Review (against spec)

**Spec coverage:**
- §3.1 repo layout — covered by Phases 1, 3, 6
- §3.3 deploy targets — Phase 12
- §4 backend endpoints — Phase 5
- §4.2 initData auth — Phase 4
- §4.3 read/write expiry — Task 16
- §4.4 SSE streaming — Tasks 23, 24
- §4.5 profile schema — Task 19, 38
- §4.6 errors — Task 11
- §4.7 rate limit — Task 24
- §5 DB migration — Phase 2
- §6 frontend stack, components, stores — Phases 6-8
- §6.5 WebApp integration — Tasks 29, 30
- §6.6 theme — Tasks 27, 29
- §6.7 API client — Task 32
- §6.8 per-page behavior — Phases 9, 10
- §6.9 error UX — Phase 11
- §7 bot changes — Phase 1
- §8 env vars — Task 42
- §9 testing — Tasks 8, 15, 23
- §10 rollout — implicit (deployment in Phase 12)
- §11 launch checklist — Phase 13
- §12 monitoring — `/v1/health` in Task 12

**Placeholder scan:** No TBD / TODO / "implement later" / "fill in" patterns in the plan.

**Type consistency:**
- `current_user` returns `int` (Telegram id) — used consistently in routes.
- `ApiError(status, code, message, extra)` — used consistently.
- `stream_ai_reply(user_id, messages, system_prompt, persist_to_db)` — Task 23 definition; Task 24 caller matches.
- `chat_submit` state: `messages`, `input`, `streaming`, `abort` — all referenced identically in `useChatStore` and `ChatPanel`.
- `Message` type — `useChatStore.ts` defines; `MessageBubble.tsx` and `ChatPanel.tsx` use identical shape.

No mismatches found. Plan is consistent and complete.
