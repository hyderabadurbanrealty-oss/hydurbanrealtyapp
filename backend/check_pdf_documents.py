"""
Check which PDF documents exist in the project_media table.
Shows project names and their associated PDF files.

Run: python check_pdf_documents.py
"""
import json
import os
from pathlib import Path
import psycopg2

PREFS_FILE = Path(__file__).parent / "scrape_preferences.json"

# Load DB connection from scrape_preferences.json
with open(PREFS_FILE, "r") as f:
    prefs = json.load(f)

DB_URL = prefs.get("db_connection", os.environ.get("DATABASE_URL", ""))

if not DB_URL:
    print("ERROR: Set db_connection in scrape_preferences.json or DATABASE_URL env var")
    exit(1)

def main():
    print("Connecting to database...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Query for floor plan and document media
    cur.execute("""
        SELECT 
            pm.project_id,
            p.project_name,
            pm.media_type,
            pm.title,
            pm.file_name,
            pm.mime_type,
            COUNT(*) OVER (PARTITION BY pm.project_id, pm.media_type) as type_count
        FROM project_media pm
        LEFT JOIN projects p ON pm.project_id = p.id
        WHERE pm.media_type IN ('document', 'floorplan')
        ORDER BY p.project_name, pm.media_type, pm.title
        LIMIT 50
    """)
    
    records = cur.fetchall()
    
    if not records:
        print("\n❌ No documents or floor plans found in database!")
    else:
        print(f"\n✅ Found {len(records)} document/floorplan records (showing first 50):")
        print("=" * 100)
        
        current_project = None
        for project_id, project_name, media_type, title, file_name, mime_type, type_count in records:
            if project_name != current_project:
                current_project = project_name
                print(f"\n📁 {project_name or project_id}")
            
            print(f"   • [{media_type}] {title}")
            print(f"     MIME: {mime_type} | File: {file_name}")
            if project_name == current_project:
                # Only print count once per project
                pass

    # Also show total media statistics
    print("\n" + "=" * 100)
    print("MEDIA STATISTICS:")
    cur.execute("""
        SELECT 
            media_type,
            COUNT(*) as count,
            SUM(file_size) as total_size
        FROM project_media
        GROUP BY media_type
        ORDER BY count DESC
    """)
    
    stats = cur.fetchall()
    for media_type, count, total_size in stats:
        size_mb = (total_size / (1024 * 1024)) if total_size else 0
        print(f"  {media_type}: {count} files ({size_mb:.2f} MB)")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
