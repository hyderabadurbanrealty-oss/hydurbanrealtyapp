"""
run_full_pipeline.py
====================
Full end-to-end pipeline for PIN code 500075:
  1. Scrape all RERA projects for PIN 500075
  2. Download + convert PDF documents to PNG floor plans
  3. Import/upsert all projects to Supabase DB
  4. Upload all floor plan images to Supabase Storage + project_media table

Run:  python run_full_pipeline.py

Requirements: pip install selenium webdriver-manager beautifulsoup4 requests pymupdf psycopg2-binary
"""

import subprocess
import sys
import json
import re
import time
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).parent
SCRAPED_DIR = BACKEND_DIR / "scraped_projects"
PREFS_FILE  = BACKEND_DIR / "scrape_preferences.json"

with open(PREFS_FILE) as f:
    prefs = json.load(f)

PIN_CODE    = "500075"
DB_URL      = prefs.get("db_connection", "")
SUPA_KEY    = prefs.get("supabase_service_key", "")
SUPA_URL    = "https://qjgwnbszmojzgwmafvuc.supabase.co"
BUCKET      = "property-media"

print("=" * 60)
print(f"HydUrban Full Pipeline — PIN {PIN_CODE}")
print("=" * 60)

# ── Step 1: Scrape RERA projects ──────────────────────────────────────────────
print("\n[STEP 1] Scraping RERA projects for PIN code", PIN_CODE)
print("         This will open a headless browser and scrape the RERA site.")
print("         Expected time: 5-30 minutes depending on number of projects.\n")

try:
    from rera_detail_scraper import main as scrape_main
    scrape_main(project_name="%", pin_code_filter=PIN_CODE)
    print("\n[STEP 1] ✓ Scraping complete")
except Exception as e:
    print(f"\n[STEP 1] ✗ Scraping failed: {e}")
    print("         You may need to run this manually: python rera_detail_scraper.py")

# ── Step 2: Download PDF documents & convert to PNGs ─────────────────────────
print("\n[STEP 2] Downloading RERA documents and converting to floor plan images...")
try:
    from download_project_docs import main as docs_main
    docs_main()
    print("\n[STEP 2] ✓ Document download complete")
except Exception as e:
    print(f"\n[STEP 2] ✗ Document download failed: {e}")
    print("         You may need: pip install pymupdf")

# ── Step 3: Import all projects to Supabase DB ────────────────────────────────
print("\n[STEP 3] Importing all scraped projects to Supabase DB...")
try:
    from import_scraped_to_db import main as import_main
    import_main()
    print("\n[STEP 3] ✓ DB import complete")
except Exception as e:
    print(f"\n[STEP 3] ✗ DB import failed: {e}")

# ── Step 4: Upload floor plans to Supabase Storage ───────────────────────────
print("\n[STEP 4] Uploading floor plan images to Supabase Storage...")

import requests
import psycopg2
import mimetypes

def sanitize_id(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def upload_to_supabase(local_path: Path, storage_path: str) -> str | None:
    url  = f"{SUPA_URL}/storage/v1/object/{BUCKET}/{storage_path}"
    mime = mimetypes.guess_type(str(local_path))[0] or "image/png"
    headers = {
        "Authorization": f"Bearer {SUPA_KEY}",
        "apikey": SUPA_KEY,
        "Content-Type": mime,
    }
    with open(local_path, "rb") as f:
        resp = requests.post(url, headers=headers, data=f)
    if resp.status_code in (200, 201, 409):
        return f"{SUPA_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"
    print(f"  UPLOAD FAILED {resp.status_code}: {resp.text[:100]}")
    return None

conn = psycopg2.connect(DB_URL)
cur  = conn.cursor()
cur.execute("SELECT id FROM projects")
db_ids = {r[0] for r in cur.fetchall()}

uploaded = skipped = failed = 0

for proj_dir in sorted(SCRAPED_DIR.iterdir()):
    if not proj_dir.is_dir():
        continue
    project_id = sanitize_id(proj_dir.name)
    if project_id not in db_ids:
        continue

    fp_dir = proj_dir / "floor-plans"
    if not fp_dir.exists():
        continue

    images = sorted(fp_dir.glob("*.png")) + sorted(fp_dir.glob("*.jpg"))
    if not images:
        continue

    print(f"  {proj_dir.name} — {len(images)} images")
    for img_path in images:
        cur.execute(
            "SELECT id FROM project_media WHERE project_id=%s AND file_name=%s",
            (project_id, img_path.name)
        )
        if cur.fetchone():
            skipped += 1
            continue

        fname_lower = img_path.name.lower()
        if "floor" in fname_lower or "building-plan" in fname_lower or "layout" in fname_lower:
            media_type = "floorplan"
        elif "commencement" in fname_lower or "cert" in fname_lower:
            media_type = "document"
        else:
            media_type = "floorplan"

        storage_path = f"{project_id}/{media_type}s/{img_path.name}"
        public_url   = upload_to_supabase(img_path, storage_path)
        if not public_url:
            failed += 1
            continue

        title = img_path.stem.replace("-", " ").replace("_", " ").title()
        cur.execute("""
            INSERT INTO project_media
                (id, project_id, media_type, title, file_url, file_name, file_size, mime_type, sort_order)
            VALUES
                (gen_random_uuid(), %s, %s, %s, %s, %s, %s, 'image/png', 0)
            ON CONFLICT DO NOTHING
        """, (project_id, media_type, title, public_url, img_path.name, img_path.stat().st_size))

        print(f"    ✓ {img_path.name}")
        uploaded += 1

    conn.commit()

cur.close()
conn.close()

print(f"\n[STEP 4] ✓ Upload complete — {uploaded} uploaded, {skipped} skipped, {failed} failed")

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("Pipeline complete!")
print(f"  Projects in DB:    check Supabase → Table Editor → projects")
print(f"  Media in storage:  check Supabase → Storage → {BUCKET}")
print(f"  Media records:     check Supabase → Table Editor → project_media")
print("=" * 60)
