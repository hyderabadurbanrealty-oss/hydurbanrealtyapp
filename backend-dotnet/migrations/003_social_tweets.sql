-- Migration 003: Social tweet URL management
-- Stores curated X/Twitter post URLs for the social feeds page.

CREATE TABLE IF NOT EXISTS social_tweets (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    url         TEXT         NOT NULL UNIQUE,
    label       TEXT,                          -- optional admin note e.g. "RERA news post"
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    sort_order  INTEGER      NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_social_tweets_active ON social_tweets (is_active, sort_order);

COMMENT ON TABLE social_tweets IS 'Curated X/Twitter post URLs shown on the social feeds page.';
