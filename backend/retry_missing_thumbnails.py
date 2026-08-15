"""Retry thumbnails for the 4 projects that failed."""
import json, re, time, requests, psycopg2, random
from pathlib import Path

prefs    = json.loads(Path("scrape_preferences.json").read_text())
DB_URL   = prefs["db_connection"]
SUPA_URL = "https://qjgwnbszmojzgwmafvuc.supabase.co"
SUPA_KEY = prefs["supabase_service_key"]
BUCKET   = "property-media"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def sanitize_id(name): return re.sub(r'[<>:"/\\|?*]', '_', name)

QUERIES = {
    "MARVEL HEIGHTS":  "luxury apartment building Narsingi Hyderabad exterior",
    "SRM PRIDE":       "SRM Pride Gandipet Hyderabad apartment building",
    "SSD ADITYA NEST": "apartment complex Narsingi Hyderabad residential",
    "SURYA VITA NEST": "residential apartment Hyderabad Kokapet modern building",
}

def bing_search(query):
    url = f"https://www.bing.com/images/search?q={requests.utils.quote(query)}&form=HDRSC2"
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=15)
    if resp.status_code != 200: return None
    matches = re.findall(r'"murl":"(https?://[^"]+\.(?:jpg|jpeg|png))"', resp.text)
    for m in matches[:10]:
        if not any(s in m.lower() for s in ['logo','icon','favicon']):
            return m
    return None

def upload(url, project_id):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    if r.status_code != 200: return None
    ct = r.headers.get("content-type","image/jpeg").split(";")[0].strip()
    ext = ".jpg" if "jpeg" in ct or "jpg" in ct else ".png"
    path = f"{project_id}/images/thumbnail{ext}"
    up = requests.post(f"{SUPA_URL}/storage/v1/object/{BUCKET}/{path}",
        headers={"Authorization": f"Bearer {SUPA_KEY}", "apikey": SUPA_KEY, "Content-Type": ct},
        data=r.content, timeout=30)
    if up.status_code in (200,201,409):
        return f"{SUPA_URL}/storage/v1/object/public/{BUCKET}/{path}"
    return None

conn = psycopg2.connect(DB_URL)
cur  = conn.cursor()

for name, query in QUERIES.items():
    cur.execute("SELECT id FROM projects WHERE project_name=%s", (name,))
    row = cur.fetchone()
    if not row: print(f"  NOT FOUND: {name}"); continue
    pid = row[0]

    cur.execute("SELECT id FROM project_media WHERE project_id=%s AND media_type='image' LIMIT 1", (pid,))
    if cur.fetchone(): print(f"  SKIP {name} — already has image"); continue

    print(f"  [{name}] searching...", end=" ", flush=True)
    img_url = bing_search(query)
    if not img_url: print("not found"); time.sleep(3); continue

    print(f"uploading...", end=" ", flush=True)
    pub = upload(img_url, sanitize_id(name))
    if not pub: print("failed"); time.sleep(3); continue

    cur.execute("""INSERT INTO project_media
        (id,project_id,media_type,title,file_url,file_name,file_size,mime_type,sort_order)
        VALUES (gen_random_uuid(),%s,'image',%s,%s,'thumbnail.jpg',0,'image/jpeg',-1)
        ON CONFLICT DO NOTHING""",
        (pid, f"{name} — Property View", pub))
    conn.commit()
    print(f"✓")
    time.sleep(4)

cur.close(); conn.close()
print("Done")
