import psycopg2

conn = psycopg2.connect('postgresql://postgres:yxOePamK9RLkgd99@db.qjgwnbszmojzgwmafvuc.supabase.co:5432/postgres')
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
tables = cur.fetchall()
print('Existing tables:')
for t in tables:
    print(' ', t[0])

# Check projects count if exists
try:
    cur.execute("SELECT COUNT(*) FROM projects")
    print('projects rows:', cur.fetchone()[0])
except Exception as e:
    print('projects table error:', e)

conn.close()
