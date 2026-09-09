-- Floor Plan Analysis Table
-- Stores AI-generated insights for floor plans

CREATE TABLE IF NOT EXISTS floor_plan_analysis (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    plan_url TEXT NOT NULL,
    
    -- Overall scores (0-100)
    overall_score INTEGER CHECK (overall_score >= 0 AND overall_score <= 100),
    flow_score INTEGER CHECK (flow_score >= 0 AND flow_score <= 100),
    privacy_score INTEGER CHECK (privacy_score >= 0 AND privacy_score <= 100),
    light_score INTEGER CHECK (light_score >= 0 AND light_score <= 100),
    space_efficiency_score INTEGER CHECK (space_efficiency_score >= 0 AND space_efficiency_score <= 100),
    storage_score INTEGER CHECK (storage_score >= 0 AND storage_score <= 100),
    vastu_score INTEGER CHECK (vastu_score >= 0 AND vastu_score <= 100),
    
    -- Metrics
    bedroom_count INTEGER DEFAULT 0,
    bathroom_count INTEGER DEFAULT 0,
    balcony_count INTEGER DEFAULT 0,
    total_area_sqft NUMERIC(10, 2),
    carpet_area_sqft NUMERIC(10, 2),
    efficiency_ratio NUMERIC(5, 2),
    
    -- Analysis results (JSON)
    findings JSONB DEFAULT '[]'::jsonb,
    highlights JSONB DEFAULT '[]'::jsonb,
    concerns JSONB DEFAULT '[]'::jsonb,
    vastu_analysis JSONB DEFAULT '{}'::jsonb,
    recommendations JSONB DEFAULT '[]'::jsonb,
    
    -- Metadata
    analyzed_at TIMESTAMP DEFAULT NOW(),
    analysis_version TEXT DEFAULT '1.0',
    
    CONSTRAINT unique_project_plan UNIQUE(project_id, plan_url)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_plan_analysis_project ON floor_plan_analysis(project_id);
CREATE INDEX IF NOT EXISTS idx_plan_analysis_score ON floor_plan_analysis(overall_score DESC);
CREATE INDEX IF NOT EXISTS idx_plan_analysis_vastu ON floor_plan_analysis(vastu_score DESC);
CREATE INDEX IF NOT EXISTS idx_plan_analysis_date ON floor_plan_analysis(analyzed_at DESC);

-- Comments
COMMENT ON TABLE floor_plan_analysis IS 'AI-generated floor plan analysis and scoring';
COMMENT ON COLUMN floor_plan_analysis.overall_score IS 'Overall livability score 0-100';
COMMENT ON COLUMN floor_plan_analysis.findings IS 'Array of specific findings with category, severity, title, description';
COMMENT ON COLUMN floor_plan_analysis.vastu_analysis IS 'Vastu compliance analysis for Indian market';
