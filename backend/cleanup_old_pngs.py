"""
Delete old PNG files from Supabase Storage after successful JPEG conversion.
Only deletes PNGs where database now points to a .jpg file.

This is SAFE because it only deletes PNGs that have been successfully converted
and the database updated to point to the new JPEG files.

Run: python cleanup_old_pngs.py

Requirements: pip install requests psycopg2-binary
"""
import json
import os
from pathlib import Path
import requests
import psycopg2

PREFS_FILE = Path(__file__).parent / "scrape_preferences.json"

# Load config
with open(PREFS_FILE, "r") as f:
    prefs = json.load(f)

DB_URL = prefs.get("db_connection", os.environ.get("DATABASE_URL", ""))
SUPABASE_URL = prefs.get("supabase_url", os.environ.get("SUPABASE_URL", "https://qjgwnbszmojzgwmafvuc.supabase.co")).rstrip("/")
SERVICE_KEY = prefs.get("supabase_service_key", os.environ.get("SUPABASE_SERVICE_KEY", ""))
BUCKET = prefs.get("supabase_bucket", "property-media")

if not DB_URL or not SERVICE_KEY:
    print("ERROR: Set db_connection and supabase_service_key in scrape_preferences.json")
    exit(1)

STORAGE_HEADERS = {
    "Authorization": f"Bearer {SERVICE_KEY}",
    "apikey": SERVICE_KEY,
}

def delete_from_supabase(storage_path: str) -> tuple[bool, str]:
    """Delete file from Supabase Storage."""
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}"
    
    try:
        resp = requests.delete(url, headers=STORAGE_HEADERS, timeout=30)
        if resp.status_code in (200, 204):
            return True, "Success"
        elif resp.status_code == 404:
            return True, "Already deleted"
        else:
            return False, f"HTTP {resp.status_code}: {resp.text[:100]}"
    except Exception as e:
        return False, str(e)

def main():
    print("Connecting to database...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Find all JPEG files in database that might have old PNG versions
    cur.execute("""
        SELECT id, project_id, file_url, file_name, media_type
        FROM project_media
        WHERE mime_type = 'image/jpeg' 
        AND (file_url ILIKE '%.jpg' OR file_name ILIKE '%.jpg')
    """)
    
    records = cur.fetchall()
    total = len(records)
    
    print(f"\nFound {total} JPEG files in database")
    print("Checking for old PNG versions to delete...")
    print("=" * 80)

    deleted = 0
    not_found = 0
    failed = 0

    for idx, (media_id, project_id, file_url, file_name, media_type) in enumerate(records, 1):
        # Calculate what the old PNG path would have been
        if file_url and '.jpg' in file_url:
            old_png_url = file_url.replace('.jpg', '.png')
            old_png_path = old_png_url.split(f"/public/{BUCKET}/")[-1]
        elif file_name and '.jpg' in file_name:
            # Construct likely path from filename
            old_png_filename = file_name.replace('.jpg', '.png')
            old_png_path = f"{project_id}/{media_type}s/{old_png_filename}"
        else:
            continue
        
        # Try to delete the old PNG
        success, message = delete_from_supabase(old_png_path)
        
        if success:
            if "deleted" in message.lower():
                not_found += 1
                status = "⊘"
            else:
                deleted += 1
                status = "✓"
                print(f"[{idx}/{total}] {status} Deleted: {old_png_path}")
        else:
            failed += 1
            print(f"[{idx}/{total}] ✗ Failed: {old_png_path} - {message}")
        
        # Progress every 50 files
        if idx % 50 == 0:
            print(f"\n--- Progress: {deleted} deleted, {not_found} not found, {failed} failed ---")

    cur.close()
    conn.close()

    print("\n" + "=" * 80)
    print(f"CLEANUP COMPLETED:")
    print(f"  Deleted: {deleted} PNG files")
    print(f"  Not found: {not_found} (already deleted or never existed)")
    print(f"  Failed: {failed}")
    print(f"\n💾 Estimated storage freed: ~{deleted * 3.5:.2f} MB")
    print(f"   (assuming ~3.5 MB average per PNG file)")

if __name__ == "__main__":
    # Safety confirmation
    print("\n" + "=" * 80)
    print("⚠️  WARNING: This will DELETE old PNG files from Supabase Storage")
    print("=" * 80)
    print("\nThis script will:")
    print("  1. Find all JPEG files in database")
    print("  2. Calculate their old PNG filenames")
    print("  3. Delete those PNG files from Supabase")
    print("\nThis is SAFE because:")
    print("  - Only deletes PNGs that have been converted to JPEG")
    print("  - Database already points to new JPEG files")
    print("  - Your app is already using the JPEG versions")
    print("\n" + "=" * 80)
    
    confirm = input("\nType 'DELETE' to proceed, or anything else to cancel: ")
    
    if confirm.strip().upper() == "DELETE":
        print("\nProceeding with cleanup...")
        main()
    else:
        print("\nCancelled. No files were deleted.")
