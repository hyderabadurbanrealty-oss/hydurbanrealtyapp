-- Migration 006: resale_listings table
-- Stores user-submitted property resale listings

CREATE TABLE IF NOT EXISTS resale_listings (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES users(id) ON DELETE SET NULL,
    owner_name          TEXT NOT NULL,
    residence_type      TEXT NOT NULL DEFAULT 'india',
    contact_phone       TEXT NOT NULL,
    contact_email       TEXT,
    builder_name        TEXT,
    project_name        TEXT,
    location            TEXT,
    configuration       TEXT,
    super_built_up_area NUMERIC,
    age_of_property     TEXT,
    expected_price      BIGINT,
    preferred_callback  TEXT,
    features            JSONB DEFAULT '[]',
    images              JSONB DEFAULT '[]',
    status              TEXT NOT NULL DEFAULT 'pending',
    admin_notes         TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resale_user   ON resale_listings(user_id);
CREATE INDEX IF NOT EXISTS idx_resale_status ON resale_listings(status);
CREATE INDEX IF NOT EXISTS idx_resale_config ON resale_listings(configuration);
