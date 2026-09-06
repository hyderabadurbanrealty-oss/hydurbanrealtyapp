"""
Uploads all scraped floor plan images to Supabase Storage
and inserts rows into the project_media table.

Run:  python upload_floorplans_to_supabase.py

Requirements:  pip install requests psycopg2-binary
"""
import os
import re
import json
import mimetypes
from pathlib import Path

import requests
import psycopg2

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL    = "https://qjgwnbszmojzgwmafvuc.supabase.co"
BUCKET          = "property-media"
SCRAPED_DIR     = Path(__file__).parent / "scraped_projects"
PREFS_FILE      = Path(__file__).parent / "scrape_preferences.json"

# Load DB connection and Supabase service key from scrape_preferences.json
with open(PREFS_FILE, "r") as f:
    prefs = json.load(f)

DB_URL       = prefs.get("db_connection", os.environ.get("DATABASE_URL", ""))
SERVICE_KEY  = prefs.get("supabase_service_key", os.environ.get("SUPABASE_SERVICE_KEY", ""))

if not SERVICE_KEY:
    print("ERROR: Set supabase_service_key in scrape_preferences.json or SUPABASE_SERVICE_KEY env var")
    print("Get it from: Supabase → Settings → API → service_role key")
    exit(1)

STORAGE_HEADERS = {
    "Authorization": f"Bearer {SERVICE_KEY}",
    "apikey": SERVICE_KEY,
}

def sanitize_id(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def upload_to_supabase(local_path: Path, storage_path: str) -> str | None:
    """Upload file to Supabase Storage, return public URL or None on failure."""
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}"
    mime = mimetypes.guess_type(str(local_path))[0] or "image/png"
    
    with open(local_path, "rb") as f:
        resp = requests.post(url, headers={**STORAGE_HEADERS, "Content-Type": mime}, data=f)
    
    if resp.status_code in (200, 201):
        return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"
    elif resp.status_code == 409:
        # Already exists — return the public URL anyway
        return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"
    else:
        print(f"  UPLOAD FAILED {resp.status_code}: {resp.text[:100]}")
        return None

def main():
    print(f"Connecting to DB...")
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()

    # Get all project IDs already in DB
    cur.execute("SELECT id FROM projects")
    db_project_ids = {row[0] for row in cur.fetchall()}
    print(f"Found {len(db_project_ids)} projects in DB")

    total_uploaded = 0
    total_skipped  = 0
    total_failed   = 0

    for proj_dir in sorted(SCRAPED_DIR.iterdir()):
        if not proj_dir.is_dir():
            continue

        project_id = sanitize_id(proj_dir.name)
        if project_id not in db_project_ids:
            print(f"  SKIP {proj_dir.name} — not in projects table")
            continue

        floor_plan_dir = proj_dir / "floor-plans"
        if not floor_plan_dir.exists():
            continue

        images = (sorted(floor_plan_dir.glob("*.png")) + 
                 sorted(floor_plan_dir.glob("*.jpg")) + 
                 sorted(floor_plan_dir.glob("*.pdf")))
        if not images:
            continue

        print(f"\n{proj_dir.name} — {len(images)} images")

        for img_path in images:
            # Check if already in project_media
            cur.execute(
                "SELECT id FROM project_media WHERE project_id=%s AND file_name=%s",
                (project_id, img_path.name)
            )
            if cur.fetchone():
                total_skipped += 1
                continue

            # Determine media type from filename
            fname = img_path.name.lower()
            if "floor" in fname or "building-plan" in fname:
                media_type = "floorplan"
            elif "commencement" in fname or "cert" in fname:
                media_type = "document"
            else:
                media_type = "floorplan"

            # Upload to Supabase Storage
            storage_path = f"{project_id}/{media_type}s/{img_path.name}"
            public_url   = upload_to_supabase(img_path, storage_path)

            if not public_url:
                total_failed += 1
                continue

            # Insert into project_media with correct MIME type
            file_size = img_path.stat().st_size
            title     = img_path.stem.replace("-", " ").replace("_", " ").title()
            mime_type = mimetypes.guess_type(str(img_path))[0] or "image/png"
            
            cur.execute("""
                INSERT INTO project_media
                    (id, project_id, media_type, title, file_url, file_name, file_size, mime_type, sort_order)
                VALUES
                    (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, 0)
                ON CONFLICT DO NOTHING
            """, (project_id, media_type, title, public_url, img_path.name, file_size, mime_type))

            print(f"  ✓ {img_path.name} → {public_url}")
            total_uploaded += 1

        conn.commit()

    cur.close()
    conn.close()

    print(f"\n{'='*60}")
    print(f"Done — {total_uploaded} uploaded, {total_skipped} skipped (already exists), {total_failed} failed")

if __name__ == "__main__":
    main()
