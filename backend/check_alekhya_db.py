import psycopg2

DB_URL = "postgresql://postgres.qjgwnbszmojzgwmafvuc:LZGJwY0ryKkFKH5P@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres"

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

cur.execute("""
    SELECT id, project_name, project_status, locality, pin_code, 
           promoter_name, total_flats, approved_date, completion_date,
           total_area_sqmt, built_up_area_sqmt
    FROM projects 
    WHERE LOWER(project_name) LIKE '%alekhya%'
""")

rows = cur.fetchall()

if rows:
    print(f"\nFound {len(rows)} project(s) with 'Alekhya' in name:\n")
    print("=" * 120)
    for r in rows:
        print(f"ID: {r[0]}")
        print(f"Name: {r[1]}")
        print(f"Status: {r[2]}")
        print(f"Location: {r[3]}, Pincode: {r[4]}")
        print(f"Promoter: {r[5]}")
        print(f"Total Flats: {r[6]}")
        print(f"Approved Date: {r[7]}")
        print(f"Completion Date: {r[8]}")
        print(f"Total Area: {r[9]} sqm")
        print(f"Built-up Area: {r[10]} sqm")
        print("=" * 120)
else:
    print("\n❌ No projects found with 'Alekhya' in the database")

cur.close()
conn.close()
