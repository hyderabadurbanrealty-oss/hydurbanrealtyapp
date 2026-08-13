import psycopg2

DB_URL = "postgresql://postgres:yxOePamK9RLkgd99@db.qjgwnbszmojzgwmafvuc.supabase.co:5432/postgres"

print("Connecting...")
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM projects")
count = cur.fetchone()[0]
print(f"projects count: {count}")

if count > 0:
    cur.execute("SELECT id, project_name, district, locality, project_status, pin_code FROM projects ORDER BY id")
    rows = cur.fetchall()
    for r in rows:
        print(r)
else:
    print("Table is empty - checking if table exists...")
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    print("Tables:", [r[0] for r in cur.fetchall()])

conn.close()
