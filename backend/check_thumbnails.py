"""
Check if there are any thumbnail URLs in the database
"""

import psycopg2

SOURCE_DB = {
    'host': 'aws-0-ap-northeast-1.pooler.supabase.com',
    'port': 5432,
    'database': 'postgres',
    'user': 'postgres.qjgwnbszmojzgwmafvuc',
    'password': 'LZGJwY0ryKkFKH5P',
    'sslmode': 'require'
}

print("Checking for media with thumbnails in source database...")

conn = psycopg2.connect(**SOURCE_DB)
cur = conn.cursor()

# Check if media table exists
cur.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'media'
    )
""")

if not cur.fetchone()[0]:
    print("❌ No 'media' table found in database")
    cur.close()
    conn.close()
    exit(0)

# Check for records with file_url or thumbnail_url
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(file_url) as with_file_url,
        COUNT(thumbnail_url) as with_thumbnail
    FROM media
""")

result = cur.fetchone()
total, with_file, with_thumb = result

print(f"\n📊 Media Table Statistics:")
print(f"   Total records: {total}")
print(f"   With file_url: {with_file}")
print(f"   With thumbnail_url: {with_thumb}")

if total == 0:
    print("\n✅ No media records to migrate")
else:
    print(f"\n📂 Sample records:")
    cur.execute("""
        SELECT id, project_id, media_type, title, file_url, thumbnail_url
        FROM media
        LIMIT 5
    """)
    
    for row in cur.fetchall():
        print(f"\n  ID: {row[0]}")
        print(f"  Project: {row[1]}")
        print(f"  Type: {row[2]}")
        print(f"  Title: {row[3]}")
        print(f"  File URL: {row[4][:80] if row[4] else 'None'}...")
        print(f"  Thumb URL: {row[5][:80] if row[5] else 'None'}...")

cur.close()
conn.close()
