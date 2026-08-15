"""
fetch_property_images.py
========================
Fetches actual property building photos by scraping the developer
websites and property portals directly using known project URLs.

Also clears bad/logo images already stored.

Run:  python fetch_property_images.py
"""
import json, re, time, requests, psycopg2
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
}

def sanitize_id(name): return re.sub(r'[<>:"/\\|?*]', '_', name)

# ── Direct source URLs for each project ──────────────────────────────────────
# Each entry: project_name → list of (source_url, css_selector_or_pattern)
PROJECT_SOURCES = {
    "PRESTIGE BEVERLY HILLS": [
        "https://www.prestigeconstructions.com/residential-projects/prestige-beverly-hills",
    ],
    "Prestige Clairemont": [
        "https://www.prestigeconstructions.com/residential-projects/prestige-clairemont",
    ],
    "MY HOME 99": [
        "https://www.myhomegroup.in/my-home-99",
        "https://www.99acres.com/my-home-99-kokapet-hyderabad-pppf",
    ],
    "MY HOME TARKSHYA": [
        "https://www.myhomegroup.in/my-home-tarkshya",
    ],
    "TRUMP TOWERS HYDERABAD": [
        "https://www.trumptowershyderabad.com",
        "https://www.99acres.com/trump-towers-hyderabad-kokapet-hyderabad-pppf",
    ],
    "RAJAPUSHPA PRISTINIA": [
        "https://www.rajapushpa.com/project/rajapushpa-pristinia",
    ],
    "RAJAPUSHPA CASA LUXURA": [
        "https://www.rajapushpa.com/project/rajapushpa-casa-luxura",
    ],
    "RAJAPUSHPA PROVINCIA": [
        "https://www.rajapushpa.com/project/rajapushpa-provincia",
    ],
    "NORTHSTAR ALLURA": [
        "https://www.northstarhomes.in/northstar-allura",
    ],
    "NAVANAAMI ONE": [
        "https://www.99acres.com/navanaami-one-kokapet-hyderabad-pppf",
    ],
    "POULOMI 90": [
        "https://www.99acres.com/poulomi-90-kokapet-hyderabad-pppf",
    ],
    "JAYABHERI THE NIRVANA": [
        "https://www.jayabheri.com/the-nirvana",
        "https://www.99acres.com/jayabheri-the-nirvana-gopanapally-hyderabad-pppf",
    ],
    "JAYABHERI THE SAHASRA": [
        "https://www.jayabheri.com/the-sahasra",
    ],
    "ALEKHYA RISE": [
        "https://www.99acres.com/alekhya-rise-narsingi-hyderabad-pppf",
    ],
    "Elemental Earthwoods": [
        "https://www.99acres.com/elemental-earthwoods-kokapet-hyderabad-pppf",
    ],
    "TRENDSET ALLURE": [
        "https://www.99acres.com/trendset-allure-kokapet-hyderabad-pppf",
    ],
    "MARVEL HEIGHTS": [
        "https://www.99acres.com/marvel-heights-narsingi-hyderabad-pppf",
    ],
    "RV ANKURA": [
        "https://www.99acres.com/rv-ankura-manchirevula-hyderabad-pppf",
    ],
    "SRM PRIDE": [
        "https://www.99acres.com/srm-pride-gandipet-hyderabad-pppf",
    ],
    "SSD ADITYA NEST": [
        "https://www.99acres.com/ssd-aditya-nest-narsingi-hyderabad-pppf",
    ],
    "SURYA VITA NEST": [
        "https://www.99acres.com/surya-vita-nest-kokapet-hyderabad-pppf",
    ],
}

def extract_images_from_page(url: str) -> list[str]:
    """Fetch a page and extract large property images."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return []

        text = resp.text
        soup = BeautifulSoup(text, "html.parser")
        imgs = set()

        # 1. Open Graph images (best quality, usually the hero shot)
        for meta in soup.find_all("meta", property=lambda p: p and "og:image" in p):
            src = meta.get("content", "")
            if src and is_property_image(src):
                imgs.add(src)

        # 2. JSON-LD schema images
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                for key in ["image", "photo", "thumbnail"]:
                    val = data.get(key, "")
                    if isinstance(val, str) and is_property_image(val):
                        imgs.add(val)
                    elif isinstance(val, list):
                        for v in val:
                            if isinstance(v, str) and is_property_image(v):
                                imgs.add(v)
            except: pass

        # 3. Large img tags with CDN URLs
        for img in soup.find_all("img"):
            src = (img.get("src") or img.get("data-src") or
                   img.get("data-lazy-src") or img.get("data-original") or "")
            if src and is_property_image(src):
                imgs.add(src)

        # 4. CSS background images in style attributes
        bg_matches = re.findall(
            r'background(?:-image)?:\s*url\(["\']?(https?://[^"\'<>\s)]+\.(?:jpg|jpeg|webp|png))["\']?\)',
            text
        )
        for src in bg_matches:
            if is_property_image(src):
                imgs.add(src)

        return list(imgs)[:6]

    except Exception as e:
        print(f"    page error: {e}")
        return []

def is_property_image(url: str) -> bool:
    """Return True if URL looks like a real property photo (not logo/icon/UI)."""
    url_lower = url.lower()
    # Must be an image
    if not any(ext in url_lower for ext in [".jpg", ".jpeg", ".png", ".webp"]):
        return False
    # Block bad patterns
    bad = ["logo", "icon", "favicon", "qr", "qrcode", "app-", "playstore",
           "appstore", "google-play", "sprite", "avatar", "profile",
           "agent", "placeholder", "banner-small", "thumb-50", "thumb-100",
           "flag", "badge", "award", "certificate", "social", "share",
           "whatsapp", "facebook", "twitter", "instagram", "youtube"]
    if any(b in url_lower for b in bad):
        return False
    return True

def download_and_upload(image_url: str, storage_path: str) -> str | None:
    try:
        r = requests.get(image_url, headers=HEADERS, timeout=25, stream=True)
        if r.status_code != 200: return None
        content = r.content
        ct = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        if not any(t in ct for t in ["image/jpeg","image/jpg","image/png","image/webp"]):
            return None
        if len(content) < 20000:  # skip images < 20KB — likely logos
            return None

        up = requests.post(
            f"{SUPA_URL}/storage/v1/object/{BUCKET}/{storage_path}",
            headers={"Authorization": f"Bearer {SUPA_KEY}", "apikey": SUPA_KEY, "Content-Type": ct},
            data=content, timeout=30
        )
        if up.status_code in (200, 201, 409):
            return f"{SUPA_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"
    except Exception as e:
        print(f"    upload error: {e}")
    return None

def clear_bad_images(cur, conn, project_id: str):
    """Remove previously stored thumbnail images that are likely logos/bad."""
    cur.execute(
        "DELETE FROM project_media WHERE project_id=%s AND media_type='image' AND file_size=0",
        (project_id,)
    )
    conn.commit()

def main():
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()

    cur.execute("SELECT id, project_name FROM projects ORDER BY project_name")
    projects = {r[1]: r[0] for r in cur.fetchall()}

    total_uploaded = 0

    for project_name, urls in PROJECT_SOURCES.items():
        project_id = projects.get(project_name)
        if not project_id:
            print(f"  NOT IN DB: {project_name}")
            continue

        # Clear zero-size bad images
        clear_bad_images(cur, conn, project_id)

        cur.execute(
            "SELECT COUNT(*) FROM project_media WHERE project_id=%s AND media_type='image'",
            (project_id,)
        )
        existing = cur.fetchone()[0]
        if existing >= 3:
            print(f"  SKIP  {project_name} ({existing} images already)")
            continue

        print(f"\n[{project_name}]")
        all_imgs = []

        for url in urls:
            print(f"  Fetching: {url[:60]}...")
            imgs = extract_images_from_page(url)
            print(f"  Found {len(imgs)} candidate images")
            all_imgs.extend(imgs)
            if len(all_imgs) >= 4: break
            time.sleep(2)

        if not all_imgs:
            print(f"  No property images found")
            continue

        pid_safe = sanitize_id(project_name)
        uploaded = 0

        for i, img_url in enumerate(all_imgs[:4]):
            ext = ".webp" if ".webp" in img_url.lower() else ".png" if ".png" in img_url.lower() else ".jpg"
            storage_path = f"{pid_safe}/images/photo_{i+1}{ext}"
            print(f"  [{i+1}] Uploading {img_url[:50]}...", end=" ", flush=True)
            pub = download_and_upload(img_url, storage_path)
            if not pub:
                print("skipped")
                continue
            cur.execute("""
                INSERT INTO project_media
                    (id,project_id,media_type,title,file_url,file_name,file_size,mime_type,sort_order)
                VALUES (gen_random_uuid(),%s,'image',%s,%s,%s,50000,'image/jpeg',%s)
                ON CONFLICT DO NOTHING
            """, (project_id, f"{project_name} Photo {i+1}", pub, f"photo_{i+1}{ext}", i))
            conn.commit()
            print("✓")
            uploaded += 1
            total_uploaded += 1
            time.sleep(1)

        print(f"  → {uploaded} images saved for {project_name}")
        time.sleep(3)

    cur.close()
    conn.close()
    print(f"\n{'='*60}")
    print(f"Total: {total_uploaded} new property images uploaded to Supabase")

if __name__ == "__main__":
    main()
