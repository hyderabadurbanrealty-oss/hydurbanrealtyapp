-- =============================================================================
-- Migration: 001_initial_schema.sql
-- Description: Initial PostgreSQL schema for HydUrban
--              Creates projects, sro_transactions, unit_rates, leads, and
--              scrape_runs tables with all columns, constraints, and indexes.
-- Requirements: 1.1 – 1.11
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Table: projects
-- Stores RERA project data. raw_data holds the full scraped JSONB blob.
-- Primary key is the sanitized project name (folder name used as the ID).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS projects (
    id                      TEXT PRIMARY KEY,
    project_name            TEXT NOT NULL,
    project_status          TEXT,
    project_type            TEXT,
    district                TEXT,
    mandal                  TEXT,
    locality                TEXT,
    pin_code                TEXT,
    village                 TEXT,
    approved_date           DATE,
    completion_date         DATE,
    revised_completion_date DATE,
    total_area_sqmt         NUMERIC,
    net_area_sqmt           NUMERIC,
    built_up_area_sqmt      NUMERIC,
    mortgage_area_sqmt      NUMERIC,
    promoter_name           TEXT,
    org_type                TEXT,
    bank_name               TEXT,
    branch_name             TEXT,
    plan_approval_number    TEXT,
    survey_number           TEXT,
    is_msb                  BOOLEAN DEFAULT FALSE,
    has_litigation          BOOLEAN DEFAULT FALSE,
    total_flats             INTEGER,
    total_booked            INTEGER,
    saleable_area_sqmt      NUMERIC,
    raw_data                JSONB NOT NULL,          -- full scraped blob (view_page_data.json contents)
    pricing                 JSONB,                   -- admin-entered pricing.json
    available_documents     TEXT[],
    scraped_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common query patterns on projects (Requirement 1.7)
CREATE INDEX IF NOT EXISTS idx_projects_pin_code  ON projects(pin_code);
CREATE INDEX IF NOT EXISTS idx_projects_district  ON projects(district);
CREATE INDEX IF NOT EXISTS idx_projects_status    ON projects(project_status);
CREATE INDEX IF NOT EXISTS idx_projects_locality  ON projects(locality);
CREATE INDEX IF NOT EXISTS idx_projects_raw_data  ON projects USING GIN(raw_data);  -- JSONB full search

-- ---------------------------------------------------------------------------
-- Table: sro_transactions
-- Stores Sub-Registrar Office transaction records scraped by the SRO scraper.
-- Uses a SERIAL primary key; idempotency on re-inserts is handled at the
-- application level via ON CONFLICT DO NOTHING in the scraper.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sro_transactions (
    id              SERIAL PRIMARY KEY,
    sro_name        TEXT,
    district        TEXT,
    village         TEXT,
    apartment       TEXT,
    flat_no         TEXT,
    reg_date        DATE,
    quarter         TEXT,          -- e.g. "2024-Q2"
    mkt_value       BIGINT,
    cons_value      BIGINT,
    price_per_sqft  NUMERIC,
    scraped_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for SRO analytics queries (Requirement 1.8)
CREATE INDEX IF NOT EXISTS idx_sro_village   ON sro_transactions(village);
CREATE INDEX IF NOT EXISTS idx_sro_quarter   ON sro_transactions(quarter);
CREATE INDEX IF NOT EXISTS idx_sro_apartment ON sro_transactions(apartment);

-- ---------------------------------------------------------------------------
-- Table: unit_rates
-- Stores government guideline unit rates scraped by the RR scraper.
-- This table is truncated and re-inserted on every scraper run.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS unit_rates (
    id              SERIAL PRIMARY KEY,
    district        TEXT,
    mandal          TEXT,
    locality        TEXT,
    search_type     TEXT DEFAULT 'apartment',   -- 'apartment' | 'land'
    unit_rate_sqft  NUMERIC,
    scraped_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for unit rates lookups (Requirement 1.9)
CREATE INDEX IF NOT EXISTS idx_unit_rates_mandal   ON unit_rates(mandal);
CREATE INDEX IF NOT EXISTS idx_unit_rates_district ON unit_rates(district);

-- ---------------------------------------------------------------------------
-- Table: leads
-- Stores visitor lead capture submissions from the property detail page.
-- project_id is a nullable foreign key to projects(id); a lead may be
-- submitted before the project row exists or without a linked project.
-- (Requirement 1.11)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS leads (
    id                  SERIAL PRIMARY KEY,
    name                TEXT NOT NULL,
    email               TEXT NOT NULL,
    mobile              TEXT NOT NULL,
    area_of_interest    TEXT,
    project_name        TEXT,
    project_id          TEXT REFERENCES projects(id),   -- FK to projects (Requirement 1.11)
    device_fingerprint  TEXT,
    source              TEXT DEFAULT 'property_detail_page',
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Table: scrape_runs
-- Tracks each scraper execution: start time, finish time, counts, and errors.
-- errors stores an array of error detail objects as JSONB.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scrape_runs (
    id          SERIAL PRIMARY KEY,
    scraper     TEXT NOT NULL,              -- 'rera' | 'sro' | 'rr'
    status      TEXT NOT NULL,              -- 'running' | 'completed' | 'failed'
    started_at  TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    total       INTEGER DEFAULT 0,
    completed   INTEGER DEFAULT 0,
    errors      JSONB DEFAULT '[]'
);
