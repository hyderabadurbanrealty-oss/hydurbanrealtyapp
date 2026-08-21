-- Migration 007: Google OAuth support
-- Adds google_id column and makes password_hash nullable
-- for users who sign up exclusively via Google.

-- Allow Google-only users (no password set)
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;

-- Store Google subject ID for lookup on subsequent logins
ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id TEXT UNIQUE;

-- Index for fast Google-login lookups
CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);
