"""
dork_property_images.py
========================
Uses Google dorking to find actual property images from developer
websites and legitimate real estate portals.

Dork queries like:
  site:prestige.in "prestige beverly hills" filetype:jpg
  site:myhomegroup.in "tarkshya" filetype:jpg
  inurl:kokapet "trump towers" ext:jpg -logo

Run:  python dork_property_images.py
"""
import json, re, time, requests, psycopg2, random
from pathlib import Path
from bs4 import BeautifulSoup

prefs    = json.loads(Path("scrape_preferences.json").read_text())
DB_URL   = prefs["db_connection"]
SUPA_URL = "https://qjgwnbszmojzgwmafvuc.supabase.co"
SUPA_KEY = prefs["supabase_service_key"]
BUCKET   = "property-media"

UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

def sanitize_id(name): return re.sub(r'[<>:"/\\|?*]', '_', name)

# Crafted Google dork queries for each project — targets developer/news sites
DORK_QUERIES = {
    "PRESTIGE BEVERLY HILLS": [
        'site:prestige.in "beverly hills" kokapet',
        '"prestige beverly hills" hyderabad filetype:jpg',
        '"prestige beverly hills" kokapet apartment building',
    ],
    "Prestige Clairemont": [
        'site:prestige.in "clairemont"',
        '"prestige clairemont" kokapet hyderabad apartment',
    ],
    "MY HOME 99": [
        'site:myhomegroup.in "my home 99"',
        '"my home 99" kokapet hyderabad luxury apartment',
    ],
    "MY HOME TARKSHYA": [
        'site:myhomegroup.in "tarkshya"',
        '"my home tarkshya" kokapet hyderabad',
    ],
    "TRUMP TOWERS HYDERABAD": [
        'site:trumptowershyderabad.com',
        '"trump towers hyderabad" kokapet luxury apartments exterior',
    ],
    "RAJAPUSHPA PRISTINIA": [
        'site:rajapushpa.com "pristinia"',
        '"rajapushpa pristinia" kokapet hyderabad apartment exterior',
    ],
    "RAJAPUSHPA CASA LUXURA": [
        'site:rajapushpa.com "casa luxura"',
        '"rajapushpa casa luxura" neopolis hyderabad',
    ],
    "RAJAPUSHPA PROVINCIA": [
        'site:rajapushpa.com "provincia"',
        '"rajapushpa provincia" narsingi hyderabad apartment',
    ],
    "NORTHSTAR ALLURA": [
        'site:northstarhomes.in "allura"',
        '"northstar allura" narsingi hyderabad apartment exterior',
    ],
    "NAVANAAMI ONE": [
        '"navanaami one" kokapet hyderabad apartment building',
        '"navanaami" hyderabad residential project',
    ],
    "POULOMI 90": [
        '"poulomi 90" kokapet hyderabad apartment',
        'site:poulomi.com "90"',
    ],
    "JAYABHERI THE NIRVANA": [
        'site:jayabheri.com "nirvana"',
        '"jayabheri nirvana" hyderabad apartment exterior',
    ],
    "JAYABHERI THE SAHASRA": [
        'site:jayabheri.com "sahasra"',
        '"jayabheri sahasra" hyderabad apartment',
    ],
    "ALEKHYA RISE": [
        '"alekhya rise" narsingi hyderabad apartment exterior',
        'site:alekhya.in "rise"',
    ],
    "Elemental Earthwoods": [
        '"elemental earthwoods" kokapet hyderabad',
        'site:elementalgroup.in "earthwoods"',
    ],
    "TRENDSET ALLURE": [
        '"trendset allure" kokapet hyderabad apartment',
        'site:trendset.in "allure"',
    ],
    "MARVEL HEIGHTS": [
        '"marvel heights" narsingi hyderabad apartment',
        'site:marvelinfra.com "heights"',
    ],
    "RV ANKURA": [
        '"rv ankura" manchirevula hyderabad apartment',
        '"rv ankura" hyderabad residential project exterior',
    ],
    "SRM PRIDE": [
        '"srm pride" gandipet hyderabad apartment',
        '"srm pride" hyderabad residential building',
    ],
    "SSD ADITYA NEST": [
        '"ssd aditya nest" narsingi hyderabad',
        '"aditya nest" hyderabad apartment exterior',
    ],
    "SURYA VITA NEST": [
        '"surya vita nest" kokapet hyderabad',
        '"surya vita" hyderabad apartment building',
    ],
}

def google_image_search(query: str) -> list[str]:
    """Use Google Image Search with a dork query to find property images."""
    ua = random.choice(UAS)
    # Use Google Images search
    url = f"https://www.google.com/search?q={requests.utils.quote(query)}&tbm=isch&hl=en&gl=in"
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    }
    imgs = []
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return []

        # Extract image URLs from Google's response
        # Google embeds image data in JSON-like structures
        # Pattern 1: data-src or src in img tags
        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract from Google's internal JSON data
        # Google Image search results contain image URLs in various formats
        raw = resp.text

        # Pattern: ["https://...jpg", number, number] — Google's image data
        matches = re.findall(
            r'\["(https?://(?!encrypted)[^"]+\.(?:jpg|jpeg|png|webp))"(?:,\d+){2}\]',
            raw
        )
        for m in matches:
            if is_property_image(m):
                imgs.append(m)

        # Pattern 2: ou":"https://..."
        matches2 = re.findall(r'"ou":"(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', raw)
        for m in matches2:
            if is_property_image(m):
                imgs.append(m)

        # Pattern 3: imgurl= in links
        matches3 = re.findall(r'imgurl=(https?://[^&"]+\.(?:jpg|jpeg|png|webp))', raw)
        for m in matches3:
            m = requests.utils.unquote(m)
            if is_property_image(m):
                imgs.append(m)

    except Exception as e:
        print(f"    google error: {e}")

    # Deduplicate and return
    seen = set()
    result = []
    for img in imgs:
        if img not in seen:
            seen.add(img)
            result.append(img)
    return result[:6]

def is_property_image(url: str) -> bool:
    url_lower = url.lower()
    if not any(ext in url_lower for ext in [".jpg", ".jpeg", ".png", ".webp"]):
        return False
    bad = ["logo", "icon", "favicon", "qr", "app-", "playstore", "appstore",
           "sprite", "avatar", "placeholder", "flag", "badge",
           "whatsapp", "facebook", "twitter", "instagram",
           "gstatic.com", "google.com", "ggpht.com",
           "60x60", "80x80", "100x100", "150x150", "50x50"]
    return not any(b in url_lower for b in bad)

def download_and_upload(image_url: str, storage_path: str) -> str | None:
    try:
        r = requests.get(image_url, timeout=20,
            headers={"User-Agent": random.choice(UAS)})
        if r.status_code != 200: return None
        ct = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        if not any(t in ct for t in ["image/jpeg","image/jpg","image/png","image/webp"]):
            return None
        if len(r.content) < 25000:  # skip < 25KB — likely logo/icon
            return None
        up = requests.post(
            f"{SUPA_URL}/storage/v1/object/{BUCKET}/{storage_path}",
            headers={"Authorization": f"Bearer {SUPA_KEY}", "apikey": SUPA_KEY, "Content-Type": ct},
            data=r.content, timeout=30
        )
        if up.status_code in (200, 201, 409):
            return f"{SUPA_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"
    except Exception as e:
        print(f"    upload error: {e}")
    return None

def main():
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()

    cur.execute("SELECT id, project_name FROM projects ORDER BY project_name")
    projects = {r[1]: r[0] for r in cur.fetchall()}

    total_uploaded = 0

    for project_name, queries in DORK_QUERIES.items():
        project_id = projects.get(project_name)
        if not project_id:
            print(f"  NOT IN DB: {project_name}")
            continue

        # Skip if already has 2+ good images
        cur.execute(
            "SELECT COUNT(*) FROM project_media WHERE project_id=%s AND media_type='image' AND file_size>20000",
            (project_id,)
        )
        count = cur.fetchone()[0]
        if count >= 2:
            print(f"  SKIP  {project_name} ({count} good images)")
            continue

        print(f"\n[{project_name}]")
        all_imgs = []

        for query in queries[:2]:  # try max 2 queries per project
            print(f"  Dork: {query[:60]}")
            imgs = google_image_search(query)
            print(f"  Found {len(imgs)} candidates")
            all_imgs.extend(imgs)
            if len(all_imgs) >= 3: break
            time.sleep(5 + random.uniform(0, 3))  # respectful delay

        if not all_imgs:
            print(f"  No images found")
            time.sleep(3)
            continue

        pid_safe = sanitize_id(project_name)
        uploaded = 0

        for i, img_url in enumerate(all_imgs[:3]):
            ext = ".webp" if ".webp" in img_url.lower() else ".png" if ".png" in img_url.lower() else ".jpg"
            path = f"{pid_safe}/images/dork_{i+1}{ext}"
            print(f"  [{i+1}] {img_url[:55]}...", end=" ", flush=True)
            pub = download_and_upload(img_url, path)
            if not pub:
                print("skipped (small/invalid)")
                continue

            cur.execute("""
                INSERT INTO project_media
                    (id,project_id,media_type,title,file_url,file_name,file_size,mime_type,sort_order)
                VALUES (gen_random_uuid(),%s,'image',%s,%s,%s,100000,'image/jpeg',%s)
                ON CONFLICT DO NOTHING
            """, (project_id, f"{project_name} — Photo {i+1}", pub, f"photo_{i+1}{ext}", i))
            conn.commit()
            print("✓")
            uploaded += 1
            total_uploaded += 1
            time.sleep(1)

        print(f"  → {uploaded} images saved")
        # Longer delay between projects to avoid Google rate limiting
        time.sleep(8 + random.uniform(0, 4))

    cur.close()
    conn.close()
    print(f"\n{'='*60}")
    print(f"Total: {total_uploaded} property images uploaded to Supabase")

if __name__ == "__main__":
    main()
