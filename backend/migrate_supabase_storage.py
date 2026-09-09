"""
Migrate Storage files from current Supabase to new Supabase.

This script migrates all files from the property-media bucket:
- Downloads files from source
- Uploads to target
- Updates database URLs

Usage:
    python migrate_supabase_storage.py [--dry-run]
"""

import requests
import psycopg2
import argparse
from pathlib import Path
from datetime import datetime
import time

# ═══════════════════════════════════════════════════════════════════════════
# SOURCE SUPABASE
# ═══════════════════════════════════════════════════════════════════════════
SOURCE_URL = "https://qjgwnbszmojzgwmafvuc.supabase.co"
SOURCE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFqZ3duYnN6bW9qemd3bWFmdnVjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjQ4NDY2MCwiZXhwIjoyMTAyMDYwNjYwfQ.pkyFMWdt0vtfUHVY_-8sAfO7SC1ygtvJE191cGGhks0"
SOURCE_BUCKET = "property-media"

SOURCE_DB = {
    'host': 'aws-0-ap-northeast-1.pooler.supabase.com',
    'port': 5432,
    'database': 'postgres',
    'user': 'postgres.qjgwnbszmojzgwmafvuc',
    'password': 'LZGJwY0ryKkFKH5P',
    'sslmode': 'require'
}

# ═══════════════════════════════════════════════════════════════════════════
# TARGET SUPABASE
# ═══════════════════════════════════════════════════════════════════════════
TARGET_URL = "https://rhcepzstokcjuccxhfmm.supabase.co"
TARGET_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJoY2VwenN0b2tjanVjY3hoZm1tIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4ODc3NDA5MywiZXhwIjoyMTA0MzUwMDkzfQ.GrxYNahw_lijo-VJUbdoRT8fMafOpVqOUiQNM63LSCY"
TARGET_BUCKET = "property-media"

TARGET_DB = {
    'host': 'aws-0-ap-south-1.pooler.supabase.com',
    'port': 6543,
    'database': 'postgres',
    'user': 'postgres.rhcepzstokcjuccxhfmm',
    'password': 'HyduUban@!986',
    'sslmode': 'require'
}


def get_all_media_files(db_config):
    """Get all media files from database."""
    print("📂 Fetching media files from database...")
    
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, project_id, file_url, thumbnail_url, media_type, title
        FROM media
        ORDER BY id
    """)
    
    files = cur.fetchall()
    cur.close()
    conn.close()
    
    print(f"✅ Found {len(files)} media files")
    return files


def download_file(url: str, service_key: str) -> bytes:
    """Download file from Supabase storage."""
    headers = {
        'Authorization': f'Bearer {service_key}',
        'apikey': service_key
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.content


def upload_file(url: str, file_bytes: bytes, service_key: str, mime_type: str = 'image/jpeg') -> bool:
    """Upload file to Supabase storage."""
    headers = {
        'Authorization': f'Bearer {service_key}',
        'apikey': service_key,
        'Content-Type': mime_type
    }
    
    response = requests.post(url, data=file_bytes, headers=headers)
    return response.status_code in (200, 201)


def extract_storage_path(url: str) -> str:
    """Extract storage path from Supabase URL."""
    # Format: https://qjgwnbszmojzgwmafvuc.supabase.co/storage/v1/object/public/property-media/path/to/file.jpg
    if '/property-media/' in url:
        return url.split('/property-media/')[1]
    return None


def migrate_storage(dry_run: bool = False):
    """Migrate all storage files."""
    print("=" * 70)
    print("🚀 SUPABASE STORAGE MIGRATION")
    print("=" * 70)
    print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not SOURCE_SERVICE_KEY or not TARGET_SERVICE_KEY:
        print("\n❌ ERROR: Service keys not configured!")
        print("   Please add SOURCE_SERVICE_KEY and TARGET_SERVICE_KEY in the script")
        print("   Get them from: Supabase Dashboard → Settings → API → service_role key")
        return
    
    if dry_run:
        print("\n⚠️  DRY RUN MODE - No actual migration will occur\n")
    
    # Get all media files
    media_files = get_all_media_files(SOURCE_DB)
    
    migrated = 0
    failed = 0
    skipped = 0
    
    for idx, (media_id, project_id, file_url, thumbnail_url, media_type, title) in enumerate(media_files, 1):
        print(f"\n[{idx}/{len(media_files)}] Processing: {title or media_id}")
        
        # Migrate main file
        if file_url:
            storage_path = extract_storage_path(file_url)
            if storage_path:
                print(f"  📥 Downloading: {storage_path}")
                
                if not dry_run:
                    try:
                        # Download from source
                        file_bytes = download_file(file_url, SOURCE_SERVICE_KEY)
                        
                        # Upload to target
                        target_url = f"{TARGET_URL}/storage/v1/object/{TARGET_BUCKET}/{storage_path}"
                        mime_type = 'application/pdf' if storage_path.endswith('.pdf') else 'image/jpeg'
                        
                        if upload_file(target_url, file_bytes, TARGET_SERVICE_KEY, mime_type):
                            print(f"  ✅ Uploaded to target")
                            migrated += 1
                        else:
                            print(f"  ❌ Upload failed")
                            failed += 1
                        
                        # Small delay to avoid rate limiting
                        time.sleep(0.1)
                        
                    except Exception as e:
                        print(f"  ❌ Error: {e}")
                        failed += 1
                else:
                    print(f"  ✅ Would migrate (dry-run)")
                    migrated += 1
            else:
                print(f"  ⏭️  Invalid URL format - skipping")
                skipped += 1
        
        # Migrate thumbnail if exists
        if thumbnail_url:
            storage_path = extract_storage_path(thumbnail_url)
            if storage_path and not dry_run:
                try:
                    file_bytes = download_file(thumbnail_url, SOURCE_SERVICE_KEY)
                    target_url = f"{TARGET_URL}/storage/v1/object/{TARGET_BUCKET}/{storage_path}"
                    upload_file(target_url, file_bytes, TARGET_SERVICE_KEY, 'image/jpeg')
                    time.sleep(0.1)
                except:
                    pass  # Thumbnails are optional
    
    # Print summary
    print("\n" + "=" * 70)
    print("📊 MIGRATION SUMMARY")
    print("=" * 70)
    print(f"✅ Migrated: {migrated}")
    print(f"❌ Failed:   {failed}")
    print(f"⏭️  Skipped:  {skipped}")
    print(f"📊 Total:    {len(media_files)}")
    print("=" * 70)
    print(f"📅 Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not dry_run and migrated > 0:
        print("\n⚠️  IMPORTANT: Update file URLs in target database!")
        print(f"   Old URL: {SOURCE_URL}")
        print(f"   New URL: {TARGET_URL}")
        print("\n   Run this SQL on target database:")
        print(f"""
   UPDATE media 
   SET 
       file_url = REPLACE(file_url, '{SOURCE_URL}', '{TARGET_URL}'),
       thumbnail_url = REPLACE(thumbnail_url, '{SOURCE_URL}', '{TARGET_URL}')
   WHERE file_url LIKE '{SOURCE_URL}%' OR thumbnail_url LIKE '{SOURCE_URL}%';
        """)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migrate Supabase storage')
    parser.add_argument('--dry-run', action='store_true', help='Test run without actual migration')
    
    args = parser.parse_args()
    
    migrate_storage(dry_run=args.dry_run)
