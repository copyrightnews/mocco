# Mocco

Mocco is a Telegram AI assistant that uses OpenRouter (LLM), web search, and image generation services.

Quickstart
1. Copy .env.example to .env and set required vars:
   - TELEGRAM_TOKEN, OPENROUTER_API_KEY, ENCRYPTION_KEY, SERPER_API_KEY, TOGETHER_API_KEY, DATABASE_URL, OWNER_ID, BOT_ID
2. Generate ENCRYPTION_KEY: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
3. (Optional) Override CHAT_MODEL — default is `minimax/minimax-m2.5:free`. Users can pick any model at runtime with `/model` and use paid models by connecting their own key via `/connect`.
4. Install: pip install -r requirements.txt
5. Run: python bot.py

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
