"""
Complete Storage Migration - Lists all files and migrates them
"""

import requests
import time
from pathlib import Path

# Source Supabase
SOURCE_URL = "https://qjgwnbszmojzgwmafvuc.supabase.co"
SOURCE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFqZ3duYnN6bW9qemd3bWFmdnVjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjQ4NDY2MCwiZXhwIjoyMTAyMDYwNjYwfQ.pkyFMWdt0vtfUHVY_-8sAfO7SC1ygtvJE191cGGhks0"
SOURCE_BUCKET = "property-media"

# Target Supabase
TARGET_URL = "https://rhcepzstokcjuccxhfmm.supabase.co"
TARGET_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJoY2VwenN0b2tjanVjY3hoZm1tIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4ODc3NDA5MywiZXhwIjoyMTA0MzUwMDkzfQ.GrxYNahw_lijo-VJUbdoRT8fMafOpVqOUiQNM63LSCY"
TARGET_BUCKET = "property-media"


def list_all_files(base_url, service_key, bucket, prefix=''):
    """Recursively list all files in bucket."""
    url = f"{base_url}/storage/v1/object/list/{bucket}"
    
    headers = {
        'Authorization': f'Bearer {service_key}',
        'apikey': service_key,
        'Content-Type': 'application/json'
    }
    
    payload = {
        'limit': 1000,
        'offset': 0,
        'sortBy': {'column': 'name', 'order': 'asc'},
        'prefix': prefix
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        print(f"Error listing files: {response.status_code} - {response.text}")
        return []
    
    items = response.json()
    all_files = []
    
    for item in items:
        if not item:
            continue
            
        name = item.get('name', '')
        metadata = item.get('metadata')
        
        # If it's a folder (no metadata or size), recursively list its contents
        if not metadata or (isinstance(metadata, dict) and metadata.get('size', 0) == 0):
            # It's a folder, recurse
            folder_path = f"{prefix}/{name}" if prefix else name
            sub_files = list_all_files(base_url, service_key, bucket, folder_path)
            all_files.extend(sub_files)
        else:
            # It's a file
            file_path = f"{prefix}/{name}" if prefix else name
            all_files.append({
                'path': file_path,
                'name': name,
                'size': metadata.get('size', 0) if isinstance(metadata, dict) else 0
            })
    
    return all_files


def download_file(base_url, service_key, bucket, file_path):
    """Download a file from storage."""
    # Use public URL for download
    public_url = f"{base_url}/storage/v1/object/public/{bucket}/{file_path}"
    
    headers = {
        'Authorization': f'Bearer {service_key}',
        'apikey': service_key
    }
    
    response = requests.get(public_url, headers=headers)
    
    if response.status_code == 200:
        return response.content
    else:
        print(f"  ❌ Download failed: {response.status_code}")
        return None


def upload_file(base_url, service_key, bucket, file_path, file_bytes):
    """Upload a file to storage."""
    url = f"{base_url}/storage/v1/object/{bucket}/{file_path}"
    
    # Determine content type
    ext = file_path.lower().split('.')[-1]
    content_types = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'webp': 'image/webp',
        'pdf': 'application/pdf',
        'gif': 'image/gif'
    }
    content_type = content_types.get(ext, 'application/octet-stream')
    
    headers = {
        'Authorization': f'Bearer {service_key}',
        'apikey': service_key,
        'Content-Type': content_type
    }
    
    response = requests.post(url, data=file_bytes, headers=headers)
    
    if response.status_code in (200, 201):
        return True
    elif response.status_code == 409:
        print(f"  ⚠️  File already exists")
        return True
    else:
        print(f"  ❌ Upload failed: {response.status_code} - {response.text[:100]}")
        return False


def create_bucket(base_url, service_key, bucket_name):
    """Create bucket if it doesn't exist."""
    url = f"{base_url}/storage/v1/bucket"
    
    headers = {
        'Authorization': f'Bearer {service_key}',
        'apikey': service_key,
        'Content-Type': 'application/json'
    }
    
    payload = {
        'id': bucket_name,
        'name': bucket_name,
        'public': True
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code in (200, 201):
        print(f"✅ Created bucket: {bucket_name}")
        return True
    elif response.status_code == 409:
        print(f"✅ Bucket already exists: {bucket_name}")
        return True
    else:
        print(f"⚠️  Bucket creation: {response.status_code} - {response.text}")
        return False


def migrate_storage():
    """Main migration function."""
    print("=" * 70)
    print("🚀 STORAGE MIGRATION")
    print("=" * 70)
    
    # Ensure target bucket exists
    print("\n📦 Checking target bucket...")
    create_bucket(TARGET_URL, TARGET_KEY, TARGET_BUCKET)
    
    # List all files from source
    print(f"\n📂 Listing files from source bucket...")
    files = list_all_files(SOURCE_URL, SOURCE_KEY, SOURCE_BUCKET)
    
    print(f"✅ Found {len(files)} files to migrate")
    
    if len(files) == 0:
        print("No files to migrate!")
        return
    
    # Calculate total size
    total_size = sum(f['size'] for f in files)
    print(f"📊 Total size: {total_size / (1024*1024):.2f} MB\n")
    
    # Migrate each file
    migrated = 0
    failed = 0
    
    for idx, file_info in enumerate(files, 1):
        file_path = file_info['path']
        file_size = file_info['size']
        
        print(f"[{idx}/{len(files)}] {file_path} ({file_size:,} bytes)")
        
        # Download from source
        print(f"  📥 Downloading...")
        file_bytes = download_file(SOURCE_URL, SOURCE_KEY, SOURCE_BUCKET, file_path)
        
        if not file_bytes:
            print(f"  ❌ Download failed")
            failed += 1
            continue
        
        # Upload to target
        print(f"  📤 Uploading...")
        if upload_file(TARGET_URL, TARGET_KEY, TARGET_BUCKET, file_path, file_bytes):
            print(f"  ✅ Migrated successfully")
            migrated += 1
        else:
            failed += 1
        
        # Small delay to avoid rate limiting
        time.sleep(0.2)
        print()
    
    # Summary
    print("=" * 70)
    print("📊 MIGRATION SUMMARY")
    print("=" * 70)
    print(f"✅ Migrated: {migrated}/{len(files)}")
    print(f"❌ Failed:   {failed}/{len(files)}")
    print(f"📊 Success:  {(migrated/len(files)*100):.1f}%")
    print("=" * 70)
    
    if migrated > 0:
        print("\n✨ Storage migration completed!")
        print(f"\n📍 Files are now available at:")
        print(f"   {TARGET_URL}/storage/v1/object/public/{TARGET_BUCKET}/...")


if __name__ == '__main__':
    migrate_storage()
