# Mocco

Mocco is a Telegram AI assistant that uses Groq LLM, web search, and image generation services.

Quickstart
1. Copy .env.example to .env and set required vars:
   - TELEGRAM_TOKEN, GROQ_API_KEY, SERPER_API_KEY, TOGETHER_API_KEY, DATABASE_URL, OWNER_ID, BOT_ID
2. Install: pip install -r requirements.txt
3. Run: python bot.py

Docker
  docker build -t mocco .
  docker-compose up -d

Project layout
  - bot.py — current entrypoint (legacy)
  - src/mocco/ — package for refactor (config, db, ai, handlers, utils)
  - tests/ — unit tests
  - docs/ — documentation

Contributing
See CONTRIBUTING.md
