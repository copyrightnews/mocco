# Environment variables

Required:
- TELEGRAM_TOKEN: bot token from BotFather
- OPENROUTER_API_KEY: OpenRouter API key (https://openrouter.ai/keys) — used as the bot's fallback for all users. Required even if you expect every user to bring their own key.
- ENCRYPTION_KEY: 32-byte url-safe base64 Fernet key used to encrypt user-supplied API keys at rest. Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Keep this secret — if you lose it, all stored user keys become unrecoverable.
- SERPER_API_KEY: Serper (google.serper.dev) API key for web search
- TOGETHER_API_KEY: Image generation API key
- DATABASE_URL: PostgreSQL DSN

Optional:
- CHAT_MODEL: default model slug used when a user hasn't picked one via `/model`. Default: `minimax/minimax-m2.5:free`. Any OpenRouter model slug works.
- OWNER_ID: numeric Telegram user id for admin commands
- BOT_ID: numeric bot id to ignore self-messages
- LOG_LEVEL: default INFO

Multi-provider, per-user API keys:
- Each user runs `/connect` to open a provider picker. Supported providers:
  - 🌐 OpenRouter — one key unlocks the full OpenRouter catalog (~300+ models)
  - 🟢 OpenAI — direct billing; auto-routed for any `openai/...` model the user picks
  - 🟠 Anthropic — verified & stored (direct routing falls back to OpenRouter for now)
  - 🔵 Google AI (Gemini) — verified & stored
  - ⚡ Groq — verified & stored
  - 🤝 Together AI — verified & stored
- Pasted keys are *verified live* against each provider's API (`GET /models` or `/auth/key`) before saving. Revoked, mistyped, or fake keys are rejected at `/connect` time, not later during chat.
- Keys are encrypted with Fernet (`ENCRYPTION_KEY`) and stored in `user_api_keys(user_id, provider, key_cipher)`. Adding more providers is a one-line entry in `src/mocco/providers.py`.
- `/connect <provider>`, `/disconnect <provider>` work as shortcuts. `/keys` shows all connected providers. `/cancel` aborts an in-progress connect.
- Routing priority per chat request:
  1. Direct provider key for the model's prefix (e.g. picked `openai/gpt-4o` + has OpenAI direct key → calls `api.openai.com` with the user's key)
  2. User's OpenRouter key (any model)
  3. Bot's `OPENROUTER_API_KEY` (free models only; paid models are blocked at pick time via `can_use_paid_model`)
- Direct routing is currently implemented only for OpenAI. Anthropic / Google / Groq / Together keys are stored & verified but billed through OpenRouter for now — direct routing for those needs a model-name translation table and is on the roadmap.

Model picker:
- `/model` opens the full OpenRouter catalog, cached for 1 hour, refreshable with the 🔄 button.
- Free models work with the bot's key. Paid models marked 🔒 require an appropriate user key (any OpenRouter key OR the matching direct-provider key). Without one, `/model` refuses the pick with an inline alert.
- Selection is stored in `users.chat_model`. The bot resolves the model per request with priority: `user choice → CHAT_MODEL env → built-in default`.

DB migration note: `init_db()` is idempotent for `CREATE TABLE IF NOT EXISTS`, but the `ALTER TABLE users ADD COLUMN IF NOT EXISTS chat_model` is a one-time fix-up for pre-existing DBs. If you ran the bot before this refactor, run it manually or just drop the table — user data is preserved in `messages` regardless.

Notes:
- The free model tier on OpenRouter is rate-limited and may be slow. For production traffic, switch `CHAT_MODEL` to a paid model.
- OpenRouter routes to upstream providers. Latency is typically 100-300ms higher than calling the provider directly.
- For Bengali/Bangla responses, the system prompt instructs the model to use Unicode script — quality depends on the chosen model's Bengali support.
