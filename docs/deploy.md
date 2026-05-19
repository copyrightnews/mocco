# Deployment

Common options:
- Docker: build the image and run with docker-compose.
- Heroku: use Procfile and set required environment variables.
- CI: the GitHub Actions workflow runs tests on push and PRs.

Secrets (GROQ_API_KEY, SERPER_API_KEY, TOGETHER_API_KEY, TELEGRAM_TOKEN, DATABASE_URL) should be stored in your hosting provider's secret store.
