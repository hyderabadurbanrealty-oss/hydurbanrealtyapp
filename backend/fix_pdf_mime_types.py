"""
Fix MIME types in project_media table for PDF files that were incorrectly stored as 'image/png'.

This script updates records where:
- mime_type is 'image/png' but
- file_name ends with .pdf or file_url contains .pdf

Run: python fix_pdf_mime_types.py
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

    # Find all records with wrong MIME type for PDFs
    cur.execute("""
        SELECT id, file_name, file_url, mime_type, media_type
        FROM project_media
        WHERE mime_type = 'image/png'
        AND (file_name ILIKE '%.pdf' OR file_url ILIKE '%.pdf')
    """)
    
    records = cur.fetchall()
    print(f"Found {len(records)} PDF files with incorrect MIME type")

    if not records:
        print("No records to fix!")
        cur.close()
        conn.close()
        return

    # Update each record
    fixed_count = 0
    for record_id, file_name, file_url, old_mime, media_type in records:
        print(f"  Fixing: {file_name or file_url}")
        
        # Update MIME type to application/pdf
        cur.execute("""
            UPDATE project_media
            SET mime_type = 'application/pdf'
            WHERE id = %s
        """, (record_id,))
        
        # Also ensure media_type is 'document' for PDFs
        if media_type != 'document':
            print(f"    Also updating media_type from '{media_type}' to 'document'")
            cur.execute("""
                UPDATE project_media
                SET media_type = 'document'
                WHERE id = %s
            """, (record_id,))
        
        fixed_count += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n{'='*60}")
    print(f"✓ Fixed {fixed_count} PDF records")
    print(f"All PDF files now have correct MIME type: application/pdf")

if __name__ == "__main__":
    main()
