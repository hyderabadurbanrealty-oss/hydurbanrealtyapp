-- Migration 003: project_media table
-- Stores media files (images, documents, floor plans, YouTube URLs) per property

CREATE TABLE IF NOT EXISTS project_media (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    media_type  TEXT NOT NULL,        -- 'image' | 'document' | 'floorplan' | 'video'
    title       TEXT,                 -- display name / document name
    file_name   TEXT,                 -- stored filename (null for videos)
    file_url    TEXT NOT NULL,        -- relative path or YouTube URL
    file_size   BIGINT,               -- bytes (null for videos)
    mime_type   TEXT,                 -- e.g. image/jpeg, application/pdf
    sort_order  INTEGER DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_project_media_project  ON project_media(project_id);
CREATE INDEX idx_project_media_type     ON project_media(project_id, media_type);
