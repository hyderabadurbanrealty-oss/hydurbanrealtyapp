"""
Re-compress existing JPEG images to reduce storage further.
Downloads JPEG from Supabase, re-compresses with lower quality, and re-uploads.

This can save an additional 20-40% on already converted JPEG files.

Run: python compress_jpegs.py

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
    exit(1)

STORAGE_HEADERS = {
    "Authorization": f"Bearer {SERVICE_KEY}",
    "apikey": SERVICE_KEY,
}

# Compression settings
TARGET_QUALITY = 70  # More aggressive compression (was 85 in conversion)
MIN_SIZE_KB = 500    # Only compress files larger than 500KB

def download_image(url: str) -> bytes | None:
    """Download image from URL."""
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            return resp.content
        else:
            print(f"  ✗ Download failed {resp.status_code}")
            return None
    except Exception as e:
        print(f"  ✗ Download error: {e}")
        return None

def compress_jpeg(jpeg_bytes: bytes) -> bytes | None:
    """Re-compress JPEG with lower quality."""
    try:
        img = Image.open(io.BytesIO(jpeg_bytes))
        
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Save with lower quality
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=TARGET_QUALITY, optimize=True)
        compressed_bytes = output.getvalue()
        
        return compressed_bytes
    except Exception as e:
        print(f"  ✗ Compression error: {e}")
        return None

def upload_to_supabase(jpeg_bytes: bytes, storage_path: str) -> str | None:
    """Upload compressed JPEG to Supabase Storage."""
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}"
    
    try:
        # Delete old file first
        requests.delete(url, headers=STORAGE_HEADERS)
        
        # Upload new compressed version
        resp = requests.post(
            url,
            headers={**STORAGE_HEADERS, "Content-Type": "image/jpeg"},
            data=jpeg_bytes
        )
        
        if resp.status_code in (200, 201):
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"
            return public_url
        else:
            print(f"  ✗ Upload failed {resp.status_code}: {resp.text[:100]}")
            return None
    except Exception as e:
        print(f"  ✗ Upload error: {e}")
        return None

def main():
    print("Connecting to database...")
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    # Get all JPEG images larger than MIN_SIZE_KB
    cur.execute("""
        SELECT id, project_id, file_url, file_name, file_size, media_type, title
        FROM project_media
        WHERE mime_type = 'image/jpeg' AND file_size > %s
        ORDER BY file_size DESC
    """, (MIN_SIZE_KB * 1024,))
    
    records = cur.fetchall()
    total = len(records)
    print(f"\nFound {total} JPEG images to compress (>{MIN_SIZE_KB}KB)")
    print(f"Target quality: {TARGET_QUALITY}")
    print("=" * 80)

    cur.close()
    conn.close()

    compressed = 0
    failed = 0
    skipped = 0
    total_saved = 0

    for idx, (media_id, project_id, file_url, file_name, file_size, media_type, title) in enumerate(records, 1):
        print(f"\n[{idx}/{total}] {title or file_name} ({file_size/1024:.1f} KB)")
        
        # Reconnect every 10 images
        if idx % 10 == 1 or idx == 1:
            try:
                conn = psycopg2.connect(DB_URL)
                cur = conn.cursor()
            except Exception as e:
                print(f"  ✗ DB connection error: {e}")
                failed += 1
                continue
        
        # Download JPEG
        jpeg_bytes = download_image(file_url)
        if not jpeg_bytes:
            failed += 1
            continue
        
        original_size = len(jpeg_bytes)
        
        # Re-compress
        compressed_bytes = compress_jpeg(jpeg_bytes)
        if not compressed_bytes:
            failed += 1
            continue
        
        compressed_size = len(compressed_bytes)
        saved = original_size - compressed_size
        saved_pct = (saved / original_size * 100) if original_size > 0 else 0
        
        # Skip if savings are minimal (less than 5%)
        if saved_pct < 5:
            print(f"  ⊘ Skipped (only {saved_pct:.1f}% savings)")
            skipped += 1
            continue
        
        print(f"  Size: {original_size/1024:.1f} KB → {compressed_size/1024:.1f} KB (saved {saved_pct:.1f}%)")
        
        # Get storage path
        storage_path = file_url.split(f"/public/{BUCKET}/")[-1]
        
        # Upload compressed version
        new_file_url = upload_to_supabase(compressed_bytes, storage_path)
        if not new_file_url:
            failed += 1
            continue
        
        # Update database with new file size
        try:
            cur.execute("""
                UPDATE project_media
                SET file_size = %s
                WHERE id = %s
            """, (compressed_size, media_id))
            conn.commit()
        except Exception as e:
            print(f"  ✗ DB update error: {e}")
            conn.rollback()
            try:
                cur.close()
                conn.close()
                conn = psycopg2.connect(DB_URL)
                cur = conn.cursor()
            except:
                pass
            failed += 1
            continue
        
        compressed += 1
        total_saved += saved
        
        print(f"  ✓ Compressed and uploaded")
        
        # Progress every 10 records
        if idx % 10 == 0:
            print(f"\n--- Progress: {compressed} compressed, {failed} failed, {skipped} skipped ---")
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
    print(f"  Compressed: {compressed}")
    print(f"  Failed: {failed}")
    print(f"  Skipped: {skipped} (< 5% savings)")
    print(f"  Total saved: {total_saved / (1024*1024):.2f} MB")
    print(f"  Average savings: {(total_saved / compressed / 1024):.1f} KB per file" if compressed > 0 else "")

if __name__ == "__main__":
    main()
