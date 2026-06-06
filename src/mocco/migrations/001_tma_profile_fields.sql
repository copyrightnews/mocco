-- Adds TMA profile fields to the users table.
-- Idempotent: safe to run on an already-migrated DB.
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS gender         text,
  ADD COLUMN IF NOT EXISTS age            int,
  ADD COLUMN IF NOT EXISTS location       text,
  ADD COLUMN IF NOT EXISTS occupation     text,
  ADD COLUMN IF NOT EXISTS interests      text[],
  ADD COLUMN IF NOT EXISTS timezone       text,
  ADD COLUMN IF NOT EXISTS language       text NOT NULL DEFAULT 'en';
