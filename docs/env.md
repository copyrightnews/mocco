# Environment variables

**Hard requirements** (bot won't start without these):
- `TELEGRAM_TOKEN`: bot token from @BotFather
- `DATABASE_URL`: PostgreSQL DSN (Railway: New → Database → PostgreSQL → Variables tab)

**Optional** (bot starts; the related feature is gracefully disabled with a clear user-facing message if missing):
- `OPENROUTER_API_KEY`: OpenRouter API key (https://openrouter.ai/keys) — used as the bot's fallback for users who haven't connected their own key. If missing, users without a key cannot chat.
- `ENCRYPTION_KEY`: 32-byte url-safe base64 Fernet key used to encrypt user-supplied API keys at rest. Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Keep this secret — if you lose it, all stored user keys become unrecoverable. If missing, `/connect` is disabled.
- `SERPER_API_KEY`: Serper (google.serper.dev) API key for web search. If missing, `/search` and auto-search return a "not configured" message.
- `TOGETHER_API_KEY`: Together AI key for image generation. If missing, `/imagine` returns a "not configured" message.

**Behavioural (optional):**
- `CHAT_MODEL`: default model slug used when a user hasn't picked one via `/model`. Default: `minimax/minimax-m2.5:free`. Any OpenRouter model slug works.
- `OWNER_ID`: numeric Telegram user id for admin commands
- `BOT_ID`: numeric bot id to ignore self-messages
- `LOG_LEVEL`: default INFO

**Minimum viable deployment:** set only `TELEGRAM_TOKEN` + `DATABASE_URL`. Users will then be able to `/connect` their own API keys to unlock the corresponding features.

## Startup behaviour

On startup, the bot:
1. Loads config; fails **once with a clear error** if `TELEGRAM_TOKEN` or `DATABASE_URL` is missing (no crash-loop).
2. Logs a warning block listing any optional features that are disabled.
3. Connects to Postgres and runs `init_db()`; fails cleanly with a clear error if the DB is unreachable.
4. Starts polling Telegram.

## Multi-provider, per-user API keys

Each user runs `/connect` to open a provider picker. Supported providers:
- OpenRouter — one key unlocks the full OpenRouter catalog (~300+ models)
- OpenAI — direct billing; auto-routed for any `openai/...` model the user picks
- Anthropic — verified & stored (direct routing falls back to OpenRouter for now)
- Google AI (Gemini) — verified & stored
- Groq — verified & stored
- Together AI — verified & stored

- Pasted keys are *verified live* against each provider's API (`GET /models` or `/auth/key`) before saving. Revoked, mistyped, or fake keys are rejected at `/connect` time, not later during chat.
- 5xx / 429 / network errors from the provider are treated as transient ("please try again in a minute") rather than as a rejected key.
- Keys are encrypted with Fernet (`ENCRYPTION_KEY`) and stored in `user_api_keys(user_id, provider, key_cipher)`.
- `/connect <provider>`, `/disconnect <provider>` work as shortcuts. `/keys` shows all connected providers. `/cancel` aborts an in-progress connect.

**Routing priority per chat request:**
1. Direct provider key for the model's prefix (e.g. picked `openai/gpt-4o` + has OpenAI direct key → calls `api.openai.com` with the user's key)
2. User's OpenRouter key (any model)
3. Bot's `OPENROUTER_API_KEY` (if configured)
4. Otherwise: clear "no API key" error pointing the user to `/connect`

## Model picker

- `/model` opens the full OpenRouter catalog, cached for 1 hour, refreshable with the Refresh button.
- Free models work with the bot's key (or with any user-connected OpenRouter key).
- Paid models (labeled `paid` in the picker) require an appropriate user key (any OpenRouter key OR the matching direct-provider key). Without one, `/model` refuses the pick with an inline alert.
- Selection is stored in `users.chat_model`. The bot resolves the model per request with priority: `user choice → CHAT_MODEL env → built-in default`.
- Models whose IDs would make the `callback_data` exceed Telegram's 64-byte limit are silently skipped (logged as a warning).

## DB migration note

`init_db()` is idempotent for `CREATE TABLE IF NOT EXISTS`. The `ALTER TABLE users ADD COLUMN IF NOT EXISTS chat_model` is a one-time fix-up for pre-existing DBs. If you ran the bot before the modular refactor, run it once or just drop the table — user data in `messages` is preserved either way.

## Notes

- The free model tier on OpenRouter is rate-limited and may be slow. For production traffic, switch `CHAT_MODEL` to a paid model.
- OpenRouter routes to upstream providers. Latency is typically 100-300ms higher than calling the provider directly.
- For Bengali/Bangla responses, the system prompt instructs the model to use Unicode script — quality depends on the chosen model's Bengali support.

