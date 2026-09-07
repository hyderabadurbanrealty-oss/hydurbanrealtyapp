-- Create project_media table for new Supabase database

CREATE TABLE IF NOT EXISTS project_media (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL,
    media_type VARCHAR(50) NOT NULL,  -- 'image', 'floorplan', 'document', 'video'
    title VARCHAR(500),
    file_url TEXT NOT NULL,
    file_name VARCHAR(500),
    file_size BIGINT,
    mime_type VARCHAR(100),
    thumbnail_url TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_project_media_project_id ON project_media(project_id);
CREATE INDEX IF NOT EXISTS idx_project_media_type ON project_media(media_type);
CREATE INDEX IF NOT EXISTS idx_project_media_created ON project_media(created_at DESC);

-- Add comment
COMMENT ON TABLE project_media IS 'Stores media files (images, floor plans, documents, videos) for projects';
