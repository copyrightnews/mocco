# Mocco Telegram Mini App — Design Spec

**Date:** 2026-06-06
**Status:** Approved (brainstorming complete, pending implementation plan)
**Owner:** @copyrightnews
**Repo:** https://github.com/copyrightnews/mocco

## 1. Context

Mocco is currently a Telegram bot (`python-telegram-bot` v21.9) with text commands for chat, web search, summarization, translation, image generation, persona customization, and admin tools. The bot is deployed on Railway and uses a shared PostgreSQL database.

The goal of this project is to add a **Telegram Mini App (TMA)** to Mocco, giving users a richer interface for the chat and profile flows while reusing the existing Python backend. A reference design from a competitor (Mira) was used to align on look-and-feel, but the scope is intentionally trimmed.

## 2. Goals and Non-Goals

### Goals (in scope for v1)
- Telegram Mini App that opens inside the Telegram client on all 4 platforms (Android, iOS, Desktop, Web).
- Two tabs: **Agent** (chat) and **Profile** (settings).
- Server-Sent Events (SSE) streaming chat replies, reusing the existing LLM routing stack.
- Profile editing for model, language, persona, and personal fields.
- API key management (OpenRouter, Serper) per user, encrypted at rest.
- Shared history between the TMA and the bot's text interface (one source of truth in Postgres).
- All per-user state remains per-user; no global fallback API keys on the API service.

### Non-goals (explicitly out of scope for v1)
- Image generation (Imagine tab, templates, gallery, Together API, `/imagine` bot command).
- Video generation.
- Token / credit system, payments, "Pro" subscription.
- TON Wallet or any crypto integration.
- Explore apps directory (Private Mode / Cocoon, Canva, Notion, Google Tools).
- Experts / persona marketplace.
- Daily notification scheduling.
- TMA-local image / file uploads.

## 3. Architecture Overview

### 3.1 Repo layout (monorepo, additive only)
```
mocco/
├── bot.py                       existing entrypoint
├── src/mocco/                   existing Python package (handlers, ai, db, config, crypto, providers)
├── api/                         NEW — FastAPI service for the TMA
│   ├── main.py                  app factory, lifespan, middleware
│   ├── deps.py                  initData verification, current_user
│   ├── routes/
│   │   ├── me.py                GET  /v1/me
│   │   ├── profile.py           GET/PATCH /v1/profile
│   │   ├── models.py            GET  /v1/models, POST /v1/model
│   │   ├── keys.py              GET/POST/DELETE /v1/keys[/{provider}]
│   │   ├── chat.py              POST /v1/chat/stream (SSE)
│   │   ├── history.py           GET  /v1/history, POST /v1/reset
│   │   └── health.py            GET  /v1/health
│   ├── models.py                pydantic request/response shapes
│   └── errors.py                ApiError + centralized handlers
├── webapp/                      NEW — React + Vite TMA
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── router.tsx
│   │   ├── pages/
│   │   │   ├── AgentPage.tsx
│   │   │   └── ProfilePage.tsx
│   │   ├── components/
│   │   │   ├── AppShell.tsx
│   │   │   ├── TopBar.tsx
│   │   │   ├── BottomNav.tsx
│   │   │   ├── ChatPanel.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── QuickActionChips.tsx
│   │   │   ├── ProfileForm.tsx
│   │   │   ├── ConnectKeyModal.tsx
│   │   │   ├── Toast.tsx
│   │   │   └── ErrorBoundary.tsx
│   │   ├── stores/
│   │   │   ├── useUserStore.ts
│   │   │   ├── useChatStore.ts
│   │   │   └── useProfileStore.ts
│   │   ├── lib/
│   │   │   ├── telegram.ts      WebApp SDK wrapper, hooks
│   │   │   ├── api.ts           fetch wrapper with initData
│   │   │   └── stream.ts        SSE parser
│   │   └── styles/
│   │       └── globals.css
├── docs/
│   └── superpowers/specs/       NEW
├── tests/
│   ├── test_api_auth.py
│   ├── test_api_chat_stream.py
│   └── test_api_profile.py
├── Dockerfile                   existing, unchanged
├── Dockerfile.api               NEW — FastAPI image
├── railway.toml                 UPDATED — two services
└── requirements.api.txt         NEW — fastapi, uvicorn, pydantic (everything else shared with bot)
```

### 3.2 Data flow (chat example)
1. User opens TMA → Telegram injects `window.Telegram.WebApp` with `initData`.
2. Frontend reads `initData`, attaches it to every request as `X-Telegram-Init-Data`.
3. FastAPI middleware validates the HMAC, extracts `telegram_user_id`, upserts the user row.
4. TMA `POST /v1/chat/stream` → FastAPI calls `mocco.ai.stream_ai_reply(user_id, messages)`.
5. New `stream_ai_reply` in `mocco/ai.py` wraps the existing OpenRouter client with `stream=True`, yielding text chunks.
6. FastAPI `StreamingResponse` emits SSE `data: {"delta":"..."}` per chunk, then `data: {"done":true}`.
7. Frontend appends each delta to the last assistant bubble; abort closes the fetch, which closes the upstream LLM call.

### 3.3 Deploy targets
| Target | Project | Serves |
|---|---|---|
| Vercel | new project | `webapp/` (static SPA) |
| Railway | new api service | `api/` (FastAPI on `uvicorn`) |
| Railway | existing bot service | `bot.py` (unchanged) |

All three share the same PostgreSQL instance (Railway's `DATABASE_URL` referenced by both services).

## 4. Backend (FastAPI)

### 4.1 Endpoints

| Method | Path | Auth | Body | Returns |
|---|---|---|---|---|
| `GET` | `/v1/health` | no | – | `{ "db": "ok", "uptime_s": int }` |
| `GET` | `/v1/me` | yes | – | `{ id, name, model, language, persona, connected_providers }` |
| `GET` | `/v1/profile` | yes | – | full profile object (see 4.5) |
| `PATCH` | `/v1/profile` | yes | partial profile | updated profile object |
| `GET` | `/v1/models` | yes | – | `[{ id, name, is_free, context_length }]` |
| `POST` | `/v1/model` | yes | `{ model_id }` | `{ model: model_id }` |
| `GET` | `/v1/keys` | yes | – | `[{ provider, created_at }]` (never the key itself) |
| `POST` | `/v1/keys/{provider}` | yes | `{ api_key }` | `{ provider, created_at }` |
| `DELETE` | `/v1/keys/{provider}` | yes | – | `204` |
| `POST` | `/v1/chat/stream` | yes | `{ messages: [...] }` | SSE: `data: {"delta": "..."}\n\n` chunks, then `data: {"done": true}\n\n` |
| `GET` | `/v1/history` | yes | – | last 14 messages `[{ role, content, ts }]` |
| `POST` | `/v1/reset` | yes | – | `{ ok: true }` |

### 4.2 Auth: initData verification
- Header: `X-Telegram-Init-Data: <raw query string>`.
- Algorithm (per Telegram spec):
  1. Parse query string, remove `hash` field.
  2. Build `data_check_string` by sorting remaining keys alphabetically and joining `k=v` with newlines.
  3. Compute `secret_key = HMAC-SHA256(key=b"WebAppData", msg=bot_token)`.
  4. Compute `hash = HMAC-SHA256(key=secret_key, msg=data_check_string).hexdigest()`.
  5. Constant-time compare with the `hash` field.
  6. Reject if `time.time() - int(auth_date) > 300` (5 min).
- Implementation: `api/deps.py::verify_init_data(raw: str) -> dict` (returns the parsed `user` object).
- Mounted as FastAPI dependency on every `/v1/*` route.

### 4.3 Read vs write expiry policy
- Read endpoints (`/v1/me`, `/v1/profile`, `/v1/models`, `/v1/keys`, `/v1/history`): accept `initData` up to **24 hours** old. TMA sessions can be long-lived.
- Write endpoints (everything else): strict **5 minute** window. Stops stale-data replay on writes.

### 4.4 SSE chat streaming
- Implemented with `fastapi.responses.StreamingResponse(media_type="text/event-stream")`.
- New function in `mocco/ai.py`:
  ```python
  async def stream_ai_reply(user_id: int, messages: list[dict], system_prompt: str | None = None) -> AsyncIterator[str]:
      model_id = resolve_model(user_id)
      client, real_model = get_client_for_chat(user_id, model_id)
      payload = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + messages
      stream = await client.chat.completions.create(model=real_model, messages=payload, stream=True, max_tokens=800, temperature=0.65)
      async for chunk in stream:
          delta = chunk.choices[0].delta.content
          if delta:
              yield f"data: {json.dumps({'delta': delta})}\n\n"
      yield f"data: {json.dumps({'done': True})}\n\n"
  ```
- Existing `get_ai_reply` remains unchanged for the bot's text path.
- Client disconnect: `StreamingResponse` cancels the inner generator; the OpenAI SDK's async context manager closes the upstream `httpx` request.

### 4.5 Profile schema
Returned by `GET /v1/profile`; PATCH body is any subset of these fields:
```json
{
  "language": "en",
  "persona": "Be concise. Max 2 sentences per reply.",
  "gender": "female",
  "age": 26,
  "location": "Dhaka, BD",
  "occupation": "Developer",
  "interests": ["coding", "music"],
  "timezone": "Asia/Dhaka"
}
```

### 4.6 Errors
- `ApiError(status: int, code: str, message: str, extra: dict | None = None)`.
- Centralized handler returns `{ "error": { "code": code, "message": message, ...extra } }`.
- Codes the frontend cares about:
  - `unauthorized` → 401, TMA re-inits
  - `forbidden` (blacklisted) → 403, "This account is blocked."
  - `rate_limited` → 429, with `retry_after` (seconds) in `extra`
  - `no_api_key` → 400, TMA opens Connect modal
  - `provider_error` → 502, "Upstream LLM error, try again."
  - `upstream_error` → 502, generic catch-all

### 4.7 Rate limiting
- In-process token bucket per `user_id`.
- Limits: 30 chat requests / 60 s, 60 PATCH requests / 60 s.
- On overflow: 429 with `{"code": "rate_limited", "extra": {"retry_after": int}}`.

## 5. Database changes

### 5.1 New columns on `users` table
```sql
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS gender         text,
  ADD COLUMN IF NOT EXISTS age            int,
  ADD COLUMN IF NOT EXISTS location       text,
  ADD COLUMN IF NOT EXISTS occupation     text,
  ADD COLUMN IF NOT EXISTS interests      text[],
  ADD COLUMN IF NOT EXISTS timezone       text,
  ADD COLUMN IF NOT EXISTS language       text NOT NULL DEFAULT 'en';
```

### 5.2 Migration runner
- File pattern: `mocco/migrations/NNN_description.sql` (sequential, 3-digit prefix).
- New file: `mocco/migrations/001_tma_profile_fields.sql` (the ALTER above).
- Boot-time application in `init_db()`:
  1. Ensure `schema_migrations` table exists.
  2. Read all `mocco/migrations/*.sql` files in order.
  3. For each one not in `schema_migrations`, run it inside a transaction, then insert `(version, applied_at)`.
- Idempotent (uses `IF NOT EXISTS`).

## 6. Frontend (React + Vite + TS)

### 6.1 Stack and versions
- React 18, TypeScript 5, Vite 5.
- Tailwind CSS 3 (with CSS-variable-driven theme).
- React Router 6 (`createBrowserRouter`).
- Zustand 4 (state).
- `@telegram-apps/telegram-ui` is **not** used; vanilla `telegram-web-app.js` is loaded via a `<script>` tag in `index.html`.

### 6.2 Routes
- `/` → `<AgentPage>`
- `/profile` → `<ProfilePage>`

### 6.3 Component layout
```
<App>
  <TelegramProvider>
    <ErrorBoundary>
      <AppShell>
        <TopBar />
        <BottomNav />
        <Outlet />
      </AppShell>
      <Toast />
    </ErrorBoundary>
  </TelegramProvider>
</App>
```

### 6.4 State (Zustand stores)
- `useUserStore` — `telegramUser`, `model`, `language`, `persona`, `connectedProviders`, `isOwner`; persist `model`, `language`, `persona` to `localStorage`.
- `useChatStore` — `messages[]`, `streaming: boolean`, `abort: AbortController | null`; ephemeral.
- `useProfileStore` — `profile` object; persist full object to `localStorage` for instant paint.

### 6.5 Telegram WebApp integration
- `lib/telegram.ts`:
  - `getInitData(): string` → `window.Telegram.WebApp.initData`
  - `useTelegramUser(): TelegramUser | null`
  - `useTelegramTheme(): ThemeParams` (reactive; subscribes to `themeChanged`)
  - `useMainButton(label, onClick, deps)`, `useBackButton(onClick, show)`
  - `haptic.impact("light"|"medium"|"heavy")`, `haptic.notify("success"|"warning"|"error")`
- `<TelegramProvider>` mounts with: `WebApp.ready()`, `WebApp.expand()`, then `themeChanged` subscription. On unmount: hide buttons, unsubscribe.

### 6.6 Theme
- Read `Telegram.WebApp.themeParams` once + on `themeChanged`.
- Mirror to CSS custom properties on `:root`:
  - `--tg-bg`, `--tg-secondary-bg`, `--tg-text`, `--tg-hint`, `--tg-link`, `--tg-button`, `--tg-button-text`.
- `tailwind.config.ts` reads these via `theme.extend.colors` so components use `bg-tg-bg`, `text-tg-text`, etc.

### 6.7 API client
- `lib/api.ts`:
  ```ts
  async function api<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        "X-Telegram-Init-Data": tg.getInitData(),
        ...init?.headers,
      },
    });
    if (!res.ok) throw await ApiError.fromResponse(res);
    return res.json();
  }
  ```
- `lib/stream.ts`:
  ```ts
  async function* streamChat(body: object, signal: AbortSignal): AsyncGenerator<string> {
    const res = await fetch(`${BASE}/v1/chat/stream`, { method: "POST", headers: { "X-Telegram-Init-Data": tg.getInitData(), "Content-Type": "application/json" }, body: JSON.stringify(body), signal });
    if (!res.ok || !res.body) throw await ApiError.fromResponse(res);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) !== -1) {
        const frame = buf.slice(0, idx); buf = buf.slice(idx + 2);
        const line = frame.split("\n").find(l => l.startsWith("data: "));
        if (!line) continue;
        const json = JSON.parse(line.slice(6));
        if (json.delta) yield json.delta as string;
        if (json.done) return;
      }
    }
  }
  ```

### 6.8 Per-page behavior

**AgentPage (`/`):**
- On mount: `useChatStore.hydrate()` → `GET /v1/history` → render messages.
- Input field bound to `useChatStore.input`. Typing makes `<MainButton>` visible (label "Send").
- Send:
  1. Append user message + empty assistant bubble.
  2. `MainButton.showProgress()`, `haptic.impact("light")`.
  3. Iterate `streamChat(...)`, append each delta to the assistant bubble.
  4. On first delta: `MainButton.hideProgress()`, `haptic.notify("success")`.
  5. On done: mark bubble complete (✓).
- Quick-action chips below input: **Search**, **Summarize**, **Translate**, **Reset chat**.
  - Search/Summarize/Translate → pre-fill input with the corresponding command prefix (`/search `, `/summarize `, `/translate `) and focus it.
  - Reset chat → confirm modal → `POST /v1/reset` → clear local messages.
- Empty state: heading "How can I help you today?" + chips, no history.

**ProfilePage (`/profile`):**
- On mount: `GET /v1/me`, `GET /v1/profile` → populate stores.
- Sections, each with its own PATCH on blur:
  - **LLM model** → modal picker (uses `/v1/models`); save via `POST /v1/model`.
  - **Language** → dropdown; save via `PATCH /v1/profile { language }`.
  - **Persona** → textarea; save via `PATCH /v1/profile { persona }`.
  - **About You** → name (read-only, from Telegram), gender select, age number, location string, occupation multi-select chips, interests text, timezone dropdown (auto-detect from `Intl.DateTimeFormat().resolvedOptions().timeZone` + override).
- **API Keys** section: list connected providers; "Connect" button → modal with provider dropdown + key input → `POST /v1/keys/{provider}`.

### 6.9 Error UX
- Global `<Toast>` driven by a `useToastStore` (queue, types: success/info/warning/error, auto-dismiss 4 s, sticky on error).
- Per-page `<ErrorBoundary>` shows "Something went wrong, reload" + reload button.
- Specific behaviors:
  - `unauthorized` (401) → full-screen "Session expired, reopening…" → `WebApp.close()` (Telegram re-opens TMA on next user action).
  - `forbidden` (403) → toast "This account is blocked. Contact the owner."
  - `rate_limited` (429) → toast with countdown, disables submit for `retry_after` seconds.
  - `no_api_key` (400) → modal "Connect a key to start chatting" with Connect button.
  - Network error → top banner "Connection lost, retrying…" + 1 auto-retry with backoff (1 s, 2 s, 4 s).
  - LLM stream error mid-flight → inline on the assistant bubble: "Reply failed, tap to retry" (re-runs the stream).

## 7. Bot changes (small)

- **Remove `/imagine` command entirely** from `register_handlers` and from the BotFather command list. The image-generation concept is fully dropped per scope.
- **Remove `TOGETHER_API_KEY`** from `config.py` and `.env.example` (no code path uses it after the previous point).
- **Delete `mocco/ai.py::generate_image`** and the `TOGETHER_API_KEY` field from `Config`. The fallback-image-models hardcoded list inside `fetch_all_models` is kept (it is a fallback for model listing, not for image gen).
- Update `WELCOME_TEXT` and `HELP_TEXT` to:
  - Drop the "Image generation" bullet.
  - Add a line about the TMA: "Open the app: tap the 🚀 Open App button below."
- Add an InlineKeyboardButton in `/start` reply: `web_app=WebAppInfo(url=VERCEL_URL)`, label "🚀 Open App".
- No new BotFather command is added; the entry point is a reply-markup button, not a slash command.

## 8. Environment variables

### Bot service (Railway, existing)
| Var | Required? | Purpose |
|---|---|---|
| `DATABASE_URL` | yes | Postgres |
| `TELEGRAM_TOKEN` | yes | Bot auth |
| `ENCRYPTION_KEY` | yes (for /connect) | Fernet for user keys |
| `OWNER_ID` | yes (for admin commands) | Admin identification |
| `BOT_ID` | yes (for safe /blacklist) | Self-protection |
| `OPENROUTER_API_KEY` | optional | Fallback when user has no key |
| `SERPER_API_KEY` | optional | Fallback web search |

### API service (Railway, new)
| Var | Required? | Purpose |
|---|---|---|
| `DATABASE_URL` | yes | Postgres (shared with bot) |
| `TELEGRAM_TOKEN` | yes | initData HMAC |
| `ENCRYPTION_KEY` | yes | Must match bot's, else stored keys undecryptable |

### Webapp (Vercel, new)
| Var | Required? | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | yes | e.g. `https://<api-service>.up.railway.app/v1` |

No secrets in Vercel. All auth is per-request via `initData`.

## 9. Testing

### 9.1 Unit (pytest)
- `tests/test_api_auth.py` — `verify_init_data` table-driven:
  - valid → returns user
  - wrong hash → raises ApiError(401, "unauthorized")
  - expired auth_date → raises ApiError(401, "unauthorized")
  - missing hash field → raises
  - replayed payload with new `user.id` → raises (hash mismatch)
- `tests/test_api_chat_stream.py` — `stream_ai_reply`:
  - yields `{"delta": "..."}` per token
  - emits `{"done": true}` at the end
  - raises on upstream error
  - aborts the underlying httpx request on generator close
- `tests/test_api_profile.py` — PATCH validates types, rejects unknown fields, persists, returns merged object.

### 9.2 Integration (httpx.AsyncClient + ASGITransport)
- Spin up `api.main:app` in-process.
- Sign a valid `initData` with the test bot token fixture, assert `/v1/me` 200.
- Sign stale `initData`, assert 401 on write endpoint, 200 on read endpoint.
- `/v1/chat/stream` round-trip: assert SSE frame shape and that the message is persisted in DB.

### 9.3 Manual E2E
- Real Telegram account on each of: Android, iOS, Desktop, Web.
- Per platform: open TMA, send a message, change model, change language, save persona, connect an OpenRouter key, reset chat, sign out (close TMA and reopen).

## 10. Rollout

1. **Day 0 — deploy infrastructure:** api service and Vercel project go live, both idle. The bot is unchanged. The TMA button does not exist in `/start` yet, so no user can reach it.
2. **Day 1 — internal test:** add the `🚀 Open App` button to `/start` reply, only you see it (or set a test user id gate). Watch logs, exercise every endpoint manually.
3. **Day 2-3 — dogfood:** send the button to 3-5 trusted users, collect feedback, fix issues.
4. **Day 4+ — public:** mention the TMA in `/help`, WELCOME_TEXT, and any release notes.

## 11. Launch checklist (all must be green)

- [ ] `ENCRYPTION_KEY` on api service == bot's `ENCRYPTION_KEY` (verified by `/v1/me` round-trip).
- [ ] initData validation rejects a tampered payload (manual `curl` test).
- [ ] Chat streaming works end-to-end with a real Telegram user on each of the 4 clients.
- [ ] Profile save/load round-trips through Postgres.
- [ ] `/reset` works from TMA and clears the bot's view of the same user.
- [ ] Bot's text commands still work (no regression: `/start`, `/help`, `/menu`, `/reset`, `/model`, `/connect`, `/disconnect`, `/keys`, `/setprompt`, `/clearprompt`, `/search`, `/summarize`, `/translate`, `/stats`, `/blacklist`, `/unblacklist`, `/broadcast`).
- [ ] Vercel build succeeds, deploys, serves at the production URL.
- [ ] CORS: api service allows the Vercel origin.
- [ ] Telegram bot has the "🚀 Open App" button pointing to the Vercel URL.
- [ ] All 4 Telegram clients tested (Android/iOS/Desktop/Web).

## 12. Post-launch monitoring

- **Logs:** structured log lines on every API request: `user_id`, `endpoint`, `method`, `status`, `latency_ms`.
- **Errors:** catch-all in FastAPI exception handler, log with stack trace, return generic message to client.
- **Health check:** `GET /v1/health` returns `{ db: "ok", uptime_s: int }`. Wire to UptimeRobot (free, 5 min interval).
- **Abuse:** per-user rate limit is in-process. If the api service scales to >1 instance later, switch to a Redis-backed limiter (out of scope for v1).

## 13. Out-of-scope (future work)

- Imagine tab + image generation (templates, gallery, Together).
- Token / credit system and payments.
- TON Wallet and other crypto flows.
- Video generation.
- Explore apps directory.
- Experts marketplace.
- Daily notification scheduler.
- Image / file uploads from TMA.
- Multi-language UI (the TMA UI itself, not just the assistant replies).
- Dark/light theme override independent of Telegram's.

## 14. Open questions (none blocking)

None. The design is ready for the implementation plan.
