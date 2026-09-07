"""
Download PNG images from Supabase, convert to JPEG, and re-upload.
Updates database with new file URLs and MIME types.

This reduces storage by ~70-80% by converting PNG to JPEG with quality=85.

Run: python convert_pngs_to_jpeg.py

Requirements: pip install requests psycopg2-binary Pillow
"""
import json
import os
import io
from pathlib import Path
from PIL import Image
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

if not DB_URL:
    print("ERROR: Set db_connection in scrape_preferences.json or DATABASE_URL env var")
    exit(1)

if not SERVICE_KEY:
    print("ERROR: Set supabase_service_key in scrape_preferences.json or SUPABASE_SERVICE_KEY env var")
    print("\nTo get your Supabase service key:")
    print("1. Go to https://supabase.com/dashboard/project/qjgwnbszmojzgwmafvuc/settings/api")
    print("2. Copy the 'service_role' key (NOT the anon public key)")
    print("3. Add it to backend/scrape_preferences.json as 'supabase_service_key'")
    print("   OR set environment variable: SUPABASE_SERVICE_KEY")
    exit(1)

STORAGE_HEADERS = {
    "Authorization": f"Bearer {SERVICE_KEY}",
    "apikey": SERVICE_KEY,
}

JPEG_QUALITY = 85  # Good balance between quality and size

def download_image(url: str) -> bytes | None:
    """Download image from URL."""
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            return resp.content
        else:
            print(f"  ✗ Download failed {resp.status_code}: {url}")
            return None
    except Exception as e:
        print(f"  ✗ Download error: {e}")
        return None

def convert_png_to_jpeg(png_bytes: bytes) -> bytes | None:
    """Convert PNG bytes to JPEG bytes."""
    try:
        # Open PNG image
        img = Image.open(io.BytesIO(png_bytes))
        
        # Convert RGBA to RGB if needed
        if img.mode in ('RGBA', 'LA', 'P'):
            # Create white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Save as JPEG
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=JPEG_QUALITY, optimize=True)
        jpeg_bytes = output.getvalue()
        
        return jpeg_bytes
    except Exception as e:
        print(f"  ✗ Conversion error: {e}")
        return None

def upload_to_supabase(jpeg_bytes: bytes, storage_path: str) -> str | None:
    """Upload JPEG to Supabase Storage."""
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}"
    
    try:
        resp = requests.post(
            url,
            headers={**STORAGE_HEADERS, "Content-Type": "image/jpeg"},
            data=jpeg_bytes
        )
        
        if resp.status_code in (200, 201):
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"
            return public_url
        elif resp.status_code == 409:
            # Already exists - return URL anyway
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"
            return public_url
        else:
            print(f"  ✗ Upload failed {resp.status_code}: {resp.text[:100]}")
            return None
    except Exception as e:
        print(f"  ✗ Upload error: {e}")
        return None

def delete_from_supabase(storage_path: str) -> bool:
    """Delete old PNG from Supabase Storage."""
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}"
    
    try:
        resp = requests.delete(url, headers=STORAGE_HEADERS)
        return resp.status_code in (200, 204)
    except:
        return False

def main():
    print("Connecting to database...")
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False  # Manual commit control
    cur = conn.cursor()

    # Get all PNG images that haven't been converted yet
    cur.execute("""
        SELECT id, project_id, file_url, file_name, media_type, title
        FROM project_media
        WHERE mime_type = 'image/png' AND (file_url ILIKE '%.png' OR file_name ILIKE '%.png')
        ORDER BY project_id
    """)
    
    records = cur.fetchall()
    total = len(records)
    print(f"\nFound {total} PNG images to convert")
    print("=" * 80)

    cur.close()
    conn.close()

    converted = 0
    failed = 0
    skipped = 0
    total_saved = 0

    for idx, (media_id, project_id, file_url, file_name, media_type, title) in enumerate(records, 1):
        print(f"\n[{idx}/{total}] {title or file_name}")
        
        # Reconnect to database for each batch to avoid timeout
        if idx % 10 == 1 or idx == 1:
            try:
                conn = psycopg2.connect(DB_URL)
                cur = conn.cursor()
            except Exception as e:
                print(f"  ✗ DB connection error: {e}")
                failed += 1
                continue
        
        # Download PNG
        png_bytes = download_image(file_url)
        if not png_bytes:
            failed += 1
            continue
        
        original_size = len(png_bytes)
        
        # Convert to JPEG
        jpeg_bytes = convert_png_to_jpeg(png_bytes)
        if not jpeg_bytes:
            failed += 1
            continue
        
        jpeg_size = len(jpeg_bytes)
        saved = original_size - jpeg_size
        saved_pct = (saved / original_size * 100) if original_size > 0 else 0
        
        print(f"  Size: {original_size/1024:.1f} KB → {jpeg_size/1024:.1f} KB (saved {saved_pct:.1f}%)")
        
        # Generate new storage path (replace .png with .jpg)
        old_storage_path = file_url.split(f"/public/{BUCKET}/")[-1]
        new_file_name = file_name.replace('.png', '.jpg') if file_name else f"{media_id}.jpg"
        new_storage_path = old_storage_path.replace('.png', '.jpg')
        
        # Upload JPEG
        new_file_url = upload_to_supabase(jpeg_bytes, new_storage_path)
        if not new_file_url:
            failed += 1
            continue
        
        # Update database
        try:
            cur.execute("""
                UPDATE project_media
                SET file_url = %s, file_name = %s, mime_type = 'image/jpeg', file_size = %s
                WHERE id = %s
            """, (new_file_url, new_file_name, jpeg_size, media_id))
            conn.commit()
        except Exception as e:
            print(f"  ✗ DB update error: {e}")
            conn.rollback()
            # Try to reconnect
            try:
                cur.close()
                conn.close()
                conn = psycopg2.connect(DB_URL)
                cur = conn.cursor()
            except:
                pass
            failed += 1
            continue
        
        converted += 1
        total_saved += saved
        
        print(f"  ✓ Converted and uploaded")
        
        # Progress update every 10 records
        if idx % 10 == 0:
            print(f"\n--- Progress: {converted} converted, {failed} failed, {skipped} skipped ---")
            # Close and reconnect
            try:
                cur.close()
                conn.close()
            except:
                pass

    # Final cleanup
    try:
        cur.close()
        conn.close()
    except:
        pass

    print("\n" + "=" * 80)
    print(f"COMPLETED:")
    print(f"  Converted: {converted}")
    print(f"  Failed: {failed}")
    print(f"  Skipped: {skipped}")
    print(f"  Total saved: {total_saved / (1024*1024):.2f} MB")
    print(f"  Average savings: {(total_saved / converted / 1024):.1f} KB per file" if converted > 0 else "")

if __name__ == "__main__":
    main()
