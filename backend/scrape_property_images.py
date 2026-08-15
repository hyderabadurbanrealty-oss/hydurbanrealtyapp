"""
scrape_property_images.py
==========================
Scrapes actual property photos from 99acres and MagicBricks
for each project and uploads multiple images to Supabase Storage.

Deletes existing thumbnail-only images and replaces with real photos.

Run:  python scrape_property_images.py
"""
import json, re, time, requests, psycopg2, random
from pathlib import Path
from bs4 import BeautifulSoup

prefs    = json.loads(Path("scrape_preferences.json").read_text())
DB_URL   = prefs["db_connection"]
SUPA_URL = "https://qjgwnbszmojzgwmafvuc.supabase.co"
SUPA_KEY = prefs["supabase_service_key"]
BUCKET   = "property-media"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

def sanitize_id(name): return re.sub(r'[<>:"/\\|?*]', '_', name)

def search_99acres(project_name: str, locality: str = "Kokapet Hyderabad") -> list[str]:
    """Search 99acres for property images."""
    query = f"{project_name} {locality}"
    url   = f"https://www.99acres.com/search/property/buy/hyderabad?search_text={requests.utils.quote(query)}"
    imgs  = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200: return []
        soup = BeautifulSoup(resp.text, "html.parser")
        # Extract OG images and large property images
        for meta in soup.find_all("meta", property="og:image"):
            src = meta.get("content", "")
            if src and "99acres" in src and src not in imgs:
                imgs.append(src)
        # Extract from img tags — filter for large property photos
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            if (src and "99acres" in src and
                any(ext in src.lower() for ext in [".jpg", ".jpeg", ".webp"]) and
                "logo" not in src.lower() and
                src not in imgs):
                imgs.append(src)
    except Exception as e:
        pass
    return imgs[:5]

def search_magicbricks(project_name: str) -> list[str]:
    """Search MagicBricks for property images."""
    query = f"{project_name} hyderabad"
    url   = f"https://www.magicbricks.com/property-for-sale/residential-real-estate?proptype=Multistorey-Apartment,Builder-Floor-Apartment,Penthouse&cityName=Hyderabad&keyword={requests.utils.quote(query)}"
    imgs  = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200: return []
        # Extract CDN image URLs
        matches = re.findall(r'(https://cdn\.staticmb\.com/[^"\'<>\s]+\.(?:jpg|jpeg|webp))', resp.text)
        for m in matches:
            if "logo" not in m.lower() and "icon" not in m.lower() and m not in imgs:
                imgs.append(m)
    except Exception as e:
        pass
    return imgs[:5]

def scrape_developer_site(project_name: str) -> list[str]:
    """Try to find images from Google's cached results for the project."""
    queries = [
        f"site:prestige.in {project_name}" if "PRESTIGE" in project_name.upper() else None,
        f"site:myhomegroup.in {project_name}" if "MY HOME" in project_name.upper() else None,
        f"site:rajapushpa.com {project_name}" if "RAJAPUSHPA" in project_name.upper() else None,
    ]
    return []  # placeholder for specific developer scraping

def download_and_upload(image_url: str, storage_path: str) -> str | None:
    """Download image and upload to Supabase Storage."""
    try:
        r = requests.get(image_url, headers=HEADERS, timeout=20)
        if r.status_code != 200: return None

        content_type = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        # Only accept actual images
        if not any(t in content_type for t in ["image/jpeg", "image/jpg", "image/png", "image/webp"]):
            return None
        # Skip very small files (likely logos/icons < 10KB)
        if len(r.content) < 10000:
            return None

        upload_url = f"{SUPA_URL}/storage/v1/object/{BUCKET}/{storage_path}"
        up = requests.post(upload_url,
            headers={"Authorization": f"Bearer {SUPA_KEY}", "apikey": SUPA_KEY, "Content-Type": content_type},
            data=r.content, timeout=30)

        if up.status_code in (200, 201, 409):
            return f"{SUPA_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"
    except Exception as e:
        print(f"    error: {e}")
    return None

def main():
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()

    # Project → locality mapping for better search
    localities = {
        "ALEKHYA RISE": "Kokapet Narsingi Hyderabad",
        "Elemental Earthwoods": "Kokapet Hyderabad",
        "JAYABHERI THE NIRVANA": "Gopanapally Hyderabad",
        "JAYABHERI THE SAHASRA": "Gopanpalle Hyderabad",
        "MARVEL HEIGHTS": "Narsingi Hyderabad",
        "MY HOME 99": "Kokapet Hyderabad",
        "MY HOME TARKSHYA": "Kokapet Hyderabad",
        "NAVANAAMI ONE": "Kokapet Hyderabad",
        "NORTHSTAR ALLURA": "Narsingi Hyderabad",
        "POULOMI 90": "Kokapet Hyderabad",
        "PRESTIGE BEVERLY HILLS": "Golden Mile Kokapet Hyderabad",
        "Prestige Clairemont": "Kokapet Hyderabad",
        "RAJAPUSHPA CASA LUXURA": "Neopolis Hyderabad",
        "RAJAPUSHPA PRISTINIA": "Kokapet Hyderabad",
        "RAJAPUSHPA PROVINCIA": "Narsingi Hyderabad",
        "RV ANKURA": "Manchirevula Hyderabad",
        "SRM PRIDE": "Gandipet Hyderabad",
        "SSD ADITYA NEST": "Narsingi Hyderabad",
        "SURYA VITA NEST": "Kokapet Hyderabad",
        "TRENDSET ALLURE": "Kokapet Hyderabad",
        "TRUMP TOWERS HYDERABAD": "Kokapet Hyderabad",
    }

    cur.execute("SELECT id, project_name FROM projects ORDER BY project_name")
    projects = cur.fetchall()
    print(f"Scraping property images for {len(projects)} projects...\n")

    for project_id, project_name in projects:
        # Check existing image count
        cur.execute(
            "SELECT COUNT(*), array_agg(id) FROM project_media WHERE project_id=%s AND media_type='image'",
            (project_id,)
        )
        row = cur.fetchone()
        img_count = row[0]
        existing_ids = row[1] or []

        print(f"\n[{project_name}] existing images: {img_count}")

        # Delete thumbnail-only entries that might be logos (file_size=0)
        if img_count > 0:
            cur.execute(
                "DELETE FROM project_media WHERE project_id=%s AND media_type='image' AND file_size=0",
                (project_id,)
            )
            conn.commit()

        locality = localities.get(project_name, "Hyderabad")

        # Try 99acres first
        imgs = search_99acres(project_name, locality)
        source = "99acres"

        # Fallback to MagicBricks
        if not imgs:
            imgs = search_magicbricks(project_name)
            source = "magicbricks"

        if not imgs:
            print(f"  No images found from any source")
            time.sleep(3)
            continue

        print(f"  Found {len(imgs)} images from {source}")
        uploaded = 0
        pid_safe = sanitize_id(project_name)

        for i, img_url in enumerate(imgs[:4]):  # max 4 images per project
            print(f"  [{i+1}] {img_url[:60]}... ", end="", flush=True)
            ext = ".jpg"
            if ".webp" in img_url.lower(): ext = ".webp"
            elif ".png" in img_url.lower(): ext = ".png"

            storage_path = f"{pid_safe}/images/{source}_{i+1}{ext}"
            public_url   = download_and_upload(img_url, storage_path)

            if not public_url:
                print("skipped (small/invalid)")
                continue

            # Check if this URL already exists
            cur.execute("SELECT id FROM project_media WHERE project_id=%s AND file_url=%s", (project_id, public_url))
            if cur.fetchone():
                print("already exists")
                continue

            title = f"{project_name} — Photo {i+1}"
            cur.execute("""
                INSERT INTO project_media
                    (id, project_id, media_type, title, file_url, file_name, file_size, mime_type, sort_order)
                VALUES (gen_random_uuid(), %s, 'image', %s, %s, %s, %s, 'image/jpeg', %s)
                ON CONFLICT DO NOTHING
            """, (project_id, title, public_url, f"{source}_{i+1}{ext}", len(requests.get(img_url, timeout=5).content) if uploaded==0 else 0, i))
            conn.commit()
            print("✓")
            uploaded += 1
            time.sleep(1)

        print(f"  → {uploaded} new images added")
        time.sleep(4)

    cur.close()
    conn.close()
    print("\nDone!")

if __name__ == "__main__":
    main()
