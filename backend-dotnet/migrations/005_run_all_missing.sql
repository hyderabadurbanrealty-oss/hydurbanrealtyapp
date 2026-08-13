-- =============================================================================
-- 005_run_all_missing.sql
-- Run in Supabase SQL Editor to create all tables missing from the initial setup.
-- Safe to re-run — all statements use IF NOT EXISTS.
-- =============================================================================

-- ── project_media ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS project_media (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    media_type  TEXT NOT NULL,
    title       TEXT,
    file_name   TEXT,
    file_url    TEXT NOT NULL,
    file_size   BIGINT,
    mime_type   TEXT,
    sort_order  INTEGER DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_project_media_project ON project_media(project_id);
CREATE INDEX IF NOT EXISTS idx_project_media_type    ON project_media(project_id, media_type);

-- ── social_tweets ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS social_tweets (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    url         TEXT        NOT NULL UNIQUE,
    label       TEXT,
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    sort_order  INTEGER     NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_social_tweets_active ON social_tweets(is_active, sort_order);

-- ── reviews ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reviews (
    id          SERIAL PRIMARY KEY,
    project_id  TEXT NOT NULL,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL,
    contact     TEXT NOT NULL,
    rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review      TEXT NOT NULL,
    is_approved BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reviews_project  ON reviews(project_id);
CREATE INDEX IF NOT EXISTS idx_reviews_approved ON reviews(project_id, is_approved);

-- ── schedule_visits ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schedule_visits (
    id               SERIAL PRIMARY KEY,
    project_id       TEXT,
    project_name     TEXT,
    name             TEXT NOT NULL,
    email            TEXT NOT NULL,
    mobile           TEXT NOT NULL,
    visit_date       DATE NOT NULL,
    visit_time       TEXT NOT NULL,
    message          TEXT,
    location_address TEXT,
    location_lat     DOUBLE PRECISION,
    location_lng     DOUBLE PRECISION,
    location_map_url TEXT,
    status           TEXT NOT NULL DEFAULT 'pending',
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_visits_project ON schedule_visits(project_id);
CREATE INDEX IF NOT EXISTS idx_visits_status  ON schedule_visits(status);
