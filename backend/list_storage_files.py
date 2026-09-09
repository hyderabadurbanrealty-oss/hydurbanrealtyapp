"""
List all files in Supabase storage bucket.
"""

import requests
import json

SOURCE_URL = "https://qjgwnbszmojzgwmafvuc.supabase.co"
SOURCE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFqZ3duYnN6bW9qemd3bWFmdnVjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjQ4NDY2MCwiZXhwIjoyMTAyMDYwNjYwfQ.pkyFMWdt0vtfUHVY_-8sAfO7SC1ygtvJE191cGGhks0"
BUCKET = "property-media"

def list_files(prefix=''):
    """List files in storage bucket."""
    url = f"{SOURCE_URL}/storage/v1/object/list/{BUCKET}"
    
    headers = {
        'Authorization': f'Bearer {SOURCE_SERVICE_KEY}',
        'apikey': SOURCE_SERVICE_KEY,
        'Content-Type': 'application/json'
    }
    
    payload = {
        'limit': 1000,
        'offset': 0,
        'sortBy': {'column': 'name', 'order': 'asc'},
        'prefix': prefix
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return []

print("🔍 Listing files in storage bucket...")
files = list_files()

print(f"\n📊 Found {len(files)} files\n")

# Group by type
by_type = {}
total_size = 0

for file in files:
    if not file:
        continue
        
    name = file.get('name', '')
    metadata = file.get('metadata') or {}
    size = metadata.get('size', 0) if isinstance(metadata, dict) else 0
    
    total_size += size
    
    ext = name.split('.')[-1].lower() if '.' in name else 'unknown'
    if ext not in by_type:
        by_type[ext] = {'count': 0, 'size': 0}
    
    by_type[ext]['count'] += 1
    by_type[ext]['size'] += size
    
    print(f"  {name:<60} {size:>10,} bytes")

print("\n" + "="*70)
print("📊 SUMMARY BY FILE TYPE")
print("="*70)

for ext, info in sorted(by_type.items()):
    size_mb = info['size'] / (1024*1024)
    print(f"  {ext:<10} {info['count']:>5} files  {size_mb:>10,.2f} MB")

print("-"*70)
total_mb = total_size / (1024*1024)
print(f"  {'TOTAL':<10} {len(files):>5} files  {total_mb:>10,.2f} MB")
print("="*70)
