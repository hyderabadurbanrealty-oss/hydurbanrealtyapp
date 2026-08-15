"""
scrape_property_thumbnails.py
==============================
Fetches property thumbnail images using Bing Image Search (no API key)
with session rotation to avoid rate limits.

Run:  python scrape_property_thumbnails.py
"""
import json, re, time, requests, psycopg2, random
from pathlib import Path
from bs4 import BeautifulSoup

BACKEND_DIR = Path(__file__).parent
prefs    = json.loads((BACKEND_DIR / "scrape_preferences.json").read_text())
DB_URL   = prefs.get("db_connection", "")
SUPA_URL = "https://qjgwnbszmojzgwmafvuc.supabase.co"
SUPA_KEY = prefs.get("supabase_service_key", "")
BUCKET   = "property-media"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

def sanitize_id(name): return re.sub(r'[<>:"/\\|?*]', '_', name)

def bing_image_search(query: str) -> str | None:
    """Scrape Bing Images for a property photo."""
    ua = random.choice(USER_AGENTS)
    headers = {"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"}
    url = f"https://www.bing.com/images/search?q={requests.utils.quote(query)}&form=HDRSC2&first=1"
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        # Extract murl (media URL) values from Bing's JSON embedded in page
        matches = re.findall(r'"murl":"(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', resp.text)
        for img_url in matches[:8]:
            # Skip known bad patterns
            if any(s in img_url.lower() for s in ['logo', 'icon', 'favicon', 'sprite']):
                continue
            return img_url
        # Fallback: any image URL in page
        matches2 = re.findall(r'(https?://[^\s"\'<>]+\.(?:jpg|jpeg|png))', resp.text)
        for img_url in matches2[:5]:
            if 'bing.com' not in img_url and len(img_url) < 300:
                return img_url
    except Exception as e:
        print(f"    bing error: {e}")
    return None

def download_and_upload(image_url: str, project_id: str) -> str | None:
    try:
        resp = requests.get(image_url, timeout=20,
            headers={"User-Agent": random.choice(USER_AGENTS)})
        if resp.status_code != 200: return None
        ct  = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        ext = ".jpg" if "jpeg" in ct or "jpg" in ct else ".png" if "png" in ct else ".jpg"
        storage_path = f"{project_id}/images/thumbnail{ext}"
        up = requests.post(f"{SUPA_URL}/storage/v1/object/{BUCKET}/{storage_path}",
            headers={"Authorization": f"Bearer {SUPA_KEY}", "apikey": SUPA_KEY, "Content-Type": ct},
            data=resp.content, timeout=30)
        if up.status_code in (200, 201, 409):
            return f"{SUPA_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"
    except Exception as e:
        print(f"    upload error: {e}")
    return None

def main():
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()
    cur.execute("SELECT id, project_name FROM projects ORDER BY project_name")
    projects = cur.fetchall()
    print(f"Processing {len(projects)} projects...\n")

    uploaded = skipped = failed = 0
    queries_map = {
        "ALEKHYA RISE":           "Alekhya Rise apartments Kokapet Hyderabad",
        "Elemental Earthwoods":   "Elemental Earthwoods apartment Kokapet Hyderabad",
        "JAYABHERI THE NIRVANA":  "Jayabheri Nirvana apartments Gopanapally Hyderabad",
        "JAYABHERI THE SAHASRA":  "Jayabheri Sahasra apartments Gopanpalle Hyderabad",
        "MARVEL HEIGHTS":         "Marvel Heights apartments Narsingi Hyderabad",
        "MY HOME 99":             "My Home 99 apartments Kokapet Hyderabad",
        "MY HOME TARKSHYA":       "My Home Tarkshya Kokapet Hyderabad luxury apartments",
        "NAVANAAMI ONE":          "Navanaami One apartments Kokapet Hyderabad",
        "NORTHSTAR ALLURA":       "Northstar Allura apartments Narsingi Hyderabad",
        "POULOMI 90":             "Poulomi 90 apartments Kokapet Hyderabad",
        "PRESTIGE BEVERLY HILLS": "Prestige Beverly Hills Kokapet Hyderabad apartments",
        "Prestige Clairemont":    "Prestige Clairemont Kokapet Hyderabad apartments",
        "RAJAPUSHPA CASA LUXURA": "Rajapushpa Casa Luxura Neopolis Hyderabad",
        "RAJAPUSHPA PRISTINIA":   "Rajapushpa Pristinia Kokapet Hyderabad",
        "RAJAPUSHPA PROVINCIA":   "Rajapushpa Provincia Narsingi Hyderabad",
        "RV ANKURA":              "RV Ankura Manchirevula Hyderabad apartments",
        "SRM PRIDE":              "SRM Pride Gandipet Hyderabad apartments",
        "SSD ADITYA NEST":        "SSD Aditya Nest Narsingi Hyderabad",
        "SURYA VITA NEST":        "Surya Vita Nest Hyderabad apartments",
        "TRENDSET ALLURE":        "Trendset Allure Kokapet Hyderabad",
        "TRUMP TOWERS HYDERABAD": "Trump Towers Hyderabad Kokapet luxury apartments",
    }

    for project_id, project_name in projects:
        cur.execute("SELECT id FROM project_media WHERE project_id=%s AND media_type='image' LIMIT 1", (project_id,))
        if cur.fetchone():
            print(f"  SKIP  {project_name}")
            skipped += 1
            continue

        query = queries_map.get(project_name, f"{project_name} Hyderabad apartment")
        print(f"  [{project_name}] searching...", end=" ", flush=True)
        image_url = bing_image_search(query)

        if not image_url:
            print("not found")
            failed += 1
            time.sleep(3)
            continue

        print(f"uploading...", end=" ", flush=True)
        public_url = download_and_upload(image_url, sanitize_id(project_name))

        if not public_url:
            print("failed")
            failed += 1
            time.sleep(3)
            continue

        cur.execute("""
            INSERT INTO project_media (id, project_id, media_type, title, file_url, file_name, file_size, mime_type, sort_order)
            VALUES (gen_random_uuid(), %s, 'image', %s, %s, 'thumbnail.jpg', 0, 'image/jpeg', -1)
            ON CONFLICT DO NOTHING
        """, (project_id, f"{project_name} — Property View", public_url))
        conn.commit()
        print(f"✓")
        uploaded += 1
        time.sleep(4 + random.uniform(0, 2))

    cur.close()
    conn.close()
    print(f"\nDone — {uploaded} uploaded, {skipped} skipped, {failed} failed")

if __name__ == "__main__":
    main()

import json
import re
import time
import requests
import psycopg2
from pathlib import Path

try:
    from ddgs import DDGS
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "ddgs"])
    from ddgs import DDGS

BACKEND_DIR = Path(__file__).parent
PREFS_FILE  = BACKEND_DIR / "scrape_preferences.json"

prefs    = json.loads(PREFS_FILE.read_text())
DB_URL   = prefs.get("db_connection", "")
SUPA_URL = "https://qjgwnbszmojzgwmafvuc.supabase.co"
SUPA_KEY = prefs.get("supabase_service_key", "")
BUCKET   = "property-media"

def sanitize_id(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def search_image(project_name: str, retries: int = 3) -> str | None:
    """Search DuckDuckGo for a property image with retry on rate limit."""
    queries = [
        f"{project_name} Hyderabad apartment exterior",
        f"{project_name} Hyderabad real estate",
        f"{project_name} apartment Kokapet Hyderabad",
    ]
    for attempt in range(retries):
        try:
            query = queries[min(attempt, len(queries) - 1)]
            results = list(DDGS().images(
                query,
                max_results=5,
                size="Large",
                type_image="photo",
            ))
            for r in results:
                url = r.get("image", "")
                w   = r.get("width",  0)
                h   = r.get("height", 0)
                if url and w >= 400 and h >= 280:
                    return url
            return None
        except Exception as e:
            msg = str(e)
            if "Ratelimit" in msg or "429" in msg or "403" in msg:
                wait = 30 * (attempt + 1)
                print(f"\n    rate-limited, waiting {wait}s...", end=" ", flush=True)
                time.sleep(wait)
            else:
                print(f"\n    error: {e}", end=" ", flush=True)
                return None
    return None

def download_and_upload(image_url: str, project_id: str) -> str | None:
    """Download image from URL and upload to Supabase Storage."""
    try:
        resp = requests.get(
            image_url, timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        if resp.status_code != 200:
            return None

        ct  = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        ext = ".jpg" if "jpeg" in ct else ".png" if "png" in ct else ".webp" if "webp" in ct else ".jpg"

        storage_path = f"{project_id}/images/thumbnail{ext}"
        upload_url   = f"{SUPA_URL}/storage/v1/object/{BUCKET}/{storage_path}"

        up_resp = requests.post(
            upload_url,
            headers={"Authorization": f"Bearer {SUPA_KEY}", "apikey": SUPA_KEY, "Content-Type": ct},
            data=resp.content, timeout=30
        )

        if up_resp.status_code in (200, 201, 409):
            return f"{SUPA_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"
        else:
            print(f"\n    upload failed {up_resp.status_code}", end=" ")
    except Exception as e:
        print(f"\n    error: {e}", end=" ")
    return None

def main():
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()

    cur.execute("SELECT id, project_name FROM projects ORDER BY project_name")
    projects = cur.fetchall()
    print(f"Processing {len(projects)} projects (with 5s delay between requests)...\n")

    uploaded = skipped = failed = 0

    for project_id, project_name in projects:
        cur.execute(
            "SELECT id FROM project_media WHERE project_id=%s AND media_type='image' LIMIT 1",
            (project_id,)
        )
        if cur.fetchone():
            print(f"  SKIP  {project_name}")
            skipped += 1
            continue

        print(f"  [{project_name}] searching...", end=" ", flush=True)
        image_url = search_image(project_name)

        if not image_url:
            print("not found")
            failed += 1
            time.sleep(5)
            continue

        print(f"uploading...", end=" ", flush=True)
        public_url = download_and_upload(image_url, sanitize_id(project_name))

        if not public_url:
            print("failed")
            failed += 1
            time.sleep(5)
            continue

        cur.execute("""
            INSERT INTO project_media
                (id, project_id, media_type, title, file_url, file_name, file_size, mime_type, sort_order)
            VALUES (gen_random_uuid(), %s, 'image', %s, %s, 'thumbnail.jpg', 0, 'image/jpeg', -1)
            ON CONFLICT DO NOTHING
        """, (project_id, f"{project_name} — Property View", public_url))
        conn.commit()
        print(f"✓")
        uploaded += 1
        time.sleep(5)  # respectful delay

    cur.close()
    conn.close()
    print(f"\nDone — {uploaded} uploaded, {skipped} skipped, {failed} failed")

if __name__ == "__main__":
    main()


BACKEND_DIR = Path(__file__).parent
PREFS_FILE  = BACKEND_DIR / "scrape_preferences.json"

prefs    = json.loads(PREFS_FILE.read_text())
DB_URL   = prefs.get("db_connection", "")
SUPA_URL = "https://qjgwnbszmojzgwmafvuc.supabase.co"
SUPA_KEY = prefs.get("supabase_service_key", "")
BUCKET   = "property-media"

def sanitize_id(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def search_image(project_name: str) -> str | None:
    """Search DuckDuckGo for property image — no API key needed."""
    query = f"{project_name} Hyderabad apartment project exterior"
    try:
        with DDGS() as ddgs:
            results = list(ddgs.images(
                query,
                max_results=5,
                size="Large",
                type_image="photo",
                safesearch="moderate"
            ))
        for r in results:
            url = r.get("image", "")
            w   = r.get("width",  0)
            h   = r.get("height", 0)
            # Skip tiny images, logos, icons
            if url and w >= 400 and h >= 280:
                return url
    except Exception as e:
        print(f"  Search error: {e}")
    return None

def download_and_upload(image_url: str, project_id: str) -> str | None:
    """Download image from URL and upload to Supabase Storage."""
    try:
        resp = requests.get(
            image_url, timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        if resp.status_code != 200:
            return None

        ct  = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        ext = ".jpg" if "jpeg" in ct else ".png" if "png" in ct else ".webp" if "webp" in ct else ".jpg"

        storage_path = f"{project_id}/images/thumbnail{ext}"
        upload_url   = f"{SUPA_URL}/storage/v1/object/{BUCKET}/{storage_path}"

        up_resp = requests.post(
            upload_url,
            headers={
                "Authorization": f"Bearer {SUPA_KEY}",
                "apikey":        SUPA_KEY,
                "Content-Type":  ct,
            },
            data=resp.content,
            timeout=30
        )

        if up_resp.status_code in (200, 201):
            return f"{SUPA_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"
        elif up_resp.status_code == 409:
            # Already exists — return public URL anyway
            return f"{SUPA_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"
        else:
            print(f"  Upload failed {up_resp.status_code}: {up_resp.text[:80]}")
    except Exception as e:
        print(f"  Download/upload error: {e}")
    return None

def main():
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()

    cur.execute("SELECT id, project_name FROM projects ORDER BY project_name")
    projects = cur.fetchall()
    print(f"Processing {len(projects)} projects...\n")

    uploaded = skipped = failed = 0

    for project_id, project_name in projects:
        # Skip if already has a thumbnail image
        cur.execute(
            "SELECT id FROM project_media WHERE project_id=%s AND media_type='image' LIMIT 1",
            (project_id,)
        )
        if cur.fetchone():
            print(f"  SKIP  {project_name} — already has image")
            skipped += 1
            continue

        print(f"  Searching: {project_name}...", end=" ", flush=True)
        image_url = search_image(project_name)

        if not image_url:
            print("no image found")
            failed += 1
            time.sleep(2)
            continue

        print(f"found → uploading...", end=" ", flush=True)
        public_url = download_and_upload(image_url, sanitize_id(project_name))

        if not public_url:
            print("upload failed")
            failed += 1
            time.sleep(2)
            continue

        # Insert into project_media with sort_order=-1 so it appears first
        cur.execute("""
            INSERT INTO project_media
                (id, project_id, media_type, title, file_url, file_name, file_size, mime_type, sort_order)
            VALUES
                (gen_random_uuid(), %s, 'image', %s, %s, 'thumbnail.jpg', 0, 'image/jpeg', -1)
            ON CONFLICT DO NOTHING
        """, (project_id, f"{project_name} — Property View", public_url))
        conn.commit()
        print(f"✓")
        uploaded += 1

        # Polite delay between requests
        time.sleep(2.5)

    cur.close()
    conn.close()

    print(f"\n{'='*60}")
    print(f"Done — {uploaded} uploaded, {skipped} already had images, {failed} failed")
    print(f"\nVerify in Supabase → Storage → {BUCKET}")

if __name__ == "__main__":
    main()
