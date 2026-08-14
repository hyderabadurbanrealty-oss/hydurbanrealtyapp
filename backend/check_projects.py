import psycopg2, json
from pathlib import Path
prefs = json.loads(Path('scrape_preferences.json').read_text())
conn = psycopg2.connect(prefs['db_connection'])
cur = conn.cursor()
cur.execute('SELECT id, project_name, project_status, locality FROM projects ORDER BY project_name')
rows = cur.fetchall()
print(f'Projects in DB: {len(rows)}')
for r in rows:
    print(f"  {r[1]:<45} | {r[3] or ''}")
cur.execute('SELECT COUNT(*) FROM project_media')
print(f'\nproject_media rows: {cur.fetchone()[0]}')
cur.execute('SELECT media_type, COUNT(*) FROM project_media GROUP BY media_type')
for r in cur.fetchall():
    print(f'  {r[0]}: {r[1]}')
conn.close()
