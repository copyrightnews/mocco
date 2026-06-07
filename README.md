# Mocco

Telegram AI assistant with a Telegram Mini App (TMA) frontend. Multi-provider LLM routing, per-user API keys, daily quota, owner-only access gate, web search, and inline model picker.

## Features

- **Multi-provider** — OpenRouter, OpenAI, Anthropic, Google Gemini, Groq, Together AI. Direct routing bypasses middleman.
- **Telegram Mini App** — React + Tailwind web app embedded in Telegram. Chat panel, profile, model picker.
- **Per-user keys** — `/connect <provider>` stores an encrypted API key. No shared billing.
- **Daily fallback quota** — 5K tokens/day free tier using the bot's OpenRouter key.
- **Owner-only gate** — Bot and TMA restricted to `OWNER_ID`. Non-owners see a themed access denied screen.
- **Web search** — Serper API injects live results into the LLM prompt for queries about news, prices, weather, etc.
- **Model picker** — `/model` shows direct-provider models when a key is connected, OpenRouter catalog otherwise.

## Quickstart

1. `pip install -r requirements.txt`
2. Set required env vars (see below)
3. `python bot.py`

### Required

| Var | Description |
|-----|-------------|
| `TELEGRAM_TOKEN` | Bot token from BotFather |
| `DATABASE_URL` | PostgreSQL connection string |

### Optional

| Var | Description |
|-----|-------------|
| `OPENROUTER_API_KEY` | Fallback LLM key (bot-side) |
| `SERPER_API_KEY` | Web search via google.serper.dev |
| `ENCRYPTION_KEY` | Fernet key for user API keys. Auto-gen'd on first `/connect` |
| `OWNER_ID` | Telegram user ID. 0 = unrestricted |
| `BOT_ID` | Bot Telegram ID (for TMA init data validation) |
| `CHAT_MODEL` | Default model. Default: `llama-3.3-70b-versatile` |
| `DAILY_FALLBACK_QUOTA` | Daily free tokens. Default: 5000 |
| `TMA_URL` | Web app URL for the `/mocco` WebApp button |
| `LOG_LEVEL` | Default: `INFO` |

## Deployment (Railway)

Two services, same repo:

| Service | Dockerfile | Entrypoint |
|---------|-----------|------------|
| **MOCCO** (bot) | `Dockerfile` | `python bot.py` |
| **mocco** (api) | `Dockerfile.api` | `uvicorn api.main:app` |

## Project layout

```
├── bot.py                  # Bot entrypoint
├── api/                    # FastAPI (TMA backend)
│   ├── main.py
│   ├── deps.py             # InitData auth + owner gate
│   ├── routes/             # chat, models, keys, me, profile, history, health
│   └── models.py
├── src/mocco/
│   ├── config.py           # Env loading + Config dataclass
│   ├── db.py               # PostgreSQL (psycopg2 pool, migrations)
│   ├── handlers.py         # All Telegram command/callback handlers
│   ├── ai.py               # LLM client routing, web search, model catalog
│   ├── ai_stream.py        # Streaming SSM for TMA
│   ├── providers.py        # PROViders dict (label, base_url, known_models)
│   ├── crypto.py           # Fernet encrypt/decrypt
│   └── migrations/          # SQL migrations
├── webapp/                 # React + Vite + Tailwind 3 TMA
│   ├── src/
│   │   ├── pages/           # AgentPage, ProfilePage
│   │   ├── components/      # ChatPanel, ModelPickerModal, etc.
│   │   ├── stores/          # Zustand (userStore, chatStore, etc.)
│   │   └── lib/             # api, stream, telegram helpers
│   └── dist/                # Built static files
├── tests/
└── docs/
