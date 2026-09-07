"""
Create missing tables in the new Supabase database
"""

import psycopg2

TARGET_DB = {
    'host': 'aws-0-ap-south-1.pooler.supabase.com',
    'port': 6543,
    'database': 'postgres',
    'user': 'postgres.rhcepzstokcjuccxhfmm',
    'password': 'HyduUban@!986',
    'sslmode': 'require'
}

# SQL to create project_media table
CREATE_PROJECT_MEDIA = """
CREATE TABLE IF NOT EXISTS project_media (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL,
    media_type VARCHAR(50) NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_project_media_project_id ON project_media(project_id);
CREATE INDEX IF NOT EXISTS idx_project_media_type ON project_media(media_type);
CREATE INDEX IF NOT EXISTS idx_project_media_created ON project_media(created_at DESC);
"""

# SQL to create media table (if different from project_media)
CREATE_MEDIA = """
CREATE TABLE IF NOT EXISTS media (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL,
    media_type VARCHAR(50) NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_media_project_id ON media(project_id);
CREATE INDEX IF NOT EXISTS idx_media_type ON media(media_type);
CREATE INDEX IF NOT EXISTS idx_media_created ON media(created_at DESC);
"""

def create_tables():
    """Create missing tables in target database."""
    print("=" * 70)
    print("🏗️  CREATING MISSING TABLES")
    print("=" * 70)
    
    try:
        conn = psycopg2.connect(**TARGET_DB)
        cur = conn.cursor()
        
        print("\n📦 Creating project_media table...")
        cur.execute(CREATE_PROJECT_MEDIA)
        conn.commit()
        print("✅ project_media table created")
        
        print("\n📦 Creating media table...")
        cur.execute(CREATE_MEDIA)
        conn.commit()
        print("✅ media table created")
        
        # Verify tables exist
        print("\n🔍 Verifying tables...")
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('project_media', 'media')
            ORDER BY table_name
        """)
        
        tables = cur.fetchall()
        print("\n✅ Tables in database:")
        for (table_name,) in tables:
            print(f"   • {table_name}")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 70)
        print("✨ Table creation completed successfully!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    create_tables()
