-- Tracks how many tokens a user has consumed from the bot's OPENROUTER_API_KEY
-- (the Mocco fallback key). Combined with DAILY_FALLBACK_QUOTA on the api service
-- this enforces a soft daily cap on the fallback path so new users can chat
-- before connecting their own OpenRouter key.
-- Idempotent: safe to run on an already-migrated DB.
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS daily_tokens_used     INTEGER     NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS daily_tokens_reset_at TIMESTAMPTZ NOT NULL DEFAULT now();
