import psycopg2, json
from pathlib import Path

prefs = json.loads(Path('scrape_preferences.json').read_text())
conn = psycopg2.connect(prefs['db_connection'])
cur = conn.cursor()

cur.execute("""
    SELECT 
        id, project_name, project_status, project_type,
        district, locality, pin_code, mandal,
        total_flats, total_booked, saleable_area_sqmt,
        promoter_name, bank_name,
        approved_date, completion_date,
        is_msb, has_litigation,
        jsonb_array_length(COALESCE(raw_data->'Floor Breakdown', '[]'::jsonb)) AS floor_breakdown_rows,
        jsonb_array_length(COALESCE(raw_data->'Building Tower Details', '[]'::jsonb)) AS tower_rows,
        jsonb_array_length(COALESCE(raw_data->'availableDocuments', '[]'::jsonb)) AS doc_count
    FROM projects 
    ORDER BY project_name
""")

rows = cur.fetchall()
print(f"{'PROJECT':<35} {'STATUS':<15} {'FLATS':>6} {'BOOKED':>6} {'FLOORS':>6} {'TOWERS':>6} {'DOCS':>5}")
print("-" * 90)
for r in rows:
    print(f"{r[1]:<35} {(r[2] or ''):<15} {r[8] or 0:>6} {r[9] or 0:>6} {r[17] or 0:>6} {r[18] or 0:>6} {r[19] or 0:>5}")

# Check what's missing
print("\n--- MISSING FIELDS ---")
cur.execute("""
    SELECT id, project_name,
        CASE WHEN total_flats IS NULL OR total_flats = 0 THEN 'missing_flats' END,
        CASE WHEN promoter_name IS NULL OR promoter_name = '' THEN 'missing_promoter' END,
        CASE WHEN approved_date IS NULL THEN 'missing_approved_date' END,
        CASE WHEN raw_data IS NULL THEN 'missing_raw_data' END
    FROM projects
    WHERE total_flats IS NULL OR total_flats = 0
       OR promoter_name IS NULL OR promoter_name = ''
       OR approved_date IS NULL
""")
missing = cur.fetchall()
if missing:
    for r in missing:
        issues = [x for x in r[2:] if x]
        print(f"  {r[1]}: {', '.join(issues)}")
else:
    print("  All projects have complete core fields ✓")

# Media summary
cur.execute("SELECT project_id, COUNT(*) FROM project_media GROUP BY project_id ORDER BY project_id")
media = dict(cur.fetchall())
print(f"\n--- MEDIA COVERAGE ({len(media)} projects have media) ---")
cur.execute("SELECT id, project_name FROM projects ORDER BY project_name")
for pid, pname in cur.fetchall():
    count = media.get(pid, 0)
    status = "✓" if count > 0 else "✗ NO MEDIA"
    print(f"  {pname:<40} {count:>3} files  {status}")

conn.close()
