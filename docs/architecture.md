# Architecture

- bot.py: legacy entrypoint using python-telegram-bot for long polling.
- src/mocco/: package for configuration, DB connection pooling, AI wrappers, and handlers.
- PostgreSQL is used (DATABASE_URL).
- Groq client is used for LLM completions; Serper for web search; Together for image gen.

The repo is organized so the functional pieces can be refactored into src/mocco gradually.
