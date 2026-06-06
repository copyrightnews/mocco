# Architecture

- bot.py: legacy entrypoint using python-telegram-bot for long polling.
- src/mocco/: package for configuration, DB connection pooling, AI wrappers, providers, and handlers.
- PostgreSQL is used (DATABASE_URL).
- OpenAI-compatible client (`openai` SDK) is reused across providers by swapping `base_url`. Serper for web search; Together for image gen.
- Model selection is per-user (DB) and falls back to `CHAT_MODEL` env. The full OpenRouter catalog (~300+ models) is listed live from `https://openrouter.ai/api/v1/models` and cached 1h.
- `src/mocco/providers.py` is a single registry of supported providers (OpenRouter, OpenAI, Anthropic, Google AI, Groq, Together). Each entry declares base_url, key prefix, live-verify endpoint, and optional `direct_route_prefix` for smart routing.
- Users connect a key via `/connect` → provider keyboard → paste → **live verification** against the provider's `/models` (or `/auth/key` for OpenRouter) → Fernet-encrypted (`ENCRYPTION_KEY`) → stored in `user_api_keys`. Bad keys are rejected at connect time, not at chat time.
- Per-request routing (`ai.get_client_for_chat`): direct provider key for matching model prefix → user's OpenRouter key → bot's OpenRouter key. Paid models without an appropriate user key are blocked in the model picker via `ai.can_use_paid_model`.

The repo is organized so the functional pieces can be refactored into src/mocco gradually.
