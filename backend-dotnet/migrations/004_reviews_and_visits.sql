-- Migration 004: reviews and schedule_visits tables

-- ── Property Reviews ──────────────────────────────────────────────────────
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

CREATE INDEX idx_reviews_project ON reviews(project_id);
CREATE INDEX idx_reviews_approved ON reviews(project_id, is_approved);

-- ── Schedule Visit Requests ───────────────────────────────────────────────
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
    status           TEXT NOT NULL DEFAULT 'pending',   -- pending | confirmed | cancelled
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_visits_project ON schedule_visits(project_id);
CREATE INDEX idx_visits_status  ON schedule_visits(status);
