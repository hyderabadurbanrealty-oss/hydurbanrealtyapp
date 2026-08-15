"""
scrape_dev_sites.py
====================
Uses Selenium to render developer websites and extract actual
property photos. Handles JS-rendered pages, lazy loading, etc.

Run:  python scrape_dev_sites.py
"""
import json, re, time, requests, psycopg2
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

prefs    = json.loads(Path("scrape_preferences.json").read_text())
DB_URL   = prefs["db_connection"]
SUPA_URL = "https://qjgwnbszmojzgwmafvuc.supabase.co"
SUPA_KEY = prefs["supabase_service_key"]
BUCKET   = "property-media"

def sanitize_id(name): return re.sub(r'[<>:"/\\|?*]', '_', name)

# Developer sites with actual project pages
SOURCES = {
    "PRESTIGE BEVERLY HILLS": [
        "https://www.prestige.in/hyderabad/residential/prestige-beverly-hills",
        "https://www.prestigeconstructions.com/residential-projects/prestige-beverly-hills",
    ],
    "Prestige Clairemont": [
        "https://www.prestige.in/hyderabad/residential/prestige-clairemont",
    ],
    "MY HOME 99": [
        "https://www.myhomegroup.in/my-home-99/",
    ],
    "MY HOME TARKSHYA": [
        "https://www.myhomegroup.in/my-home-tarkshya/",
    ],
    "TRUMP TOWERS HYDERABAD": [
        "https://www.trumptowershyderabad.com/",
    ],
    "RAJAPUSHPA PRISTINIA": [
        "https://www.rajapushpa.com/project/rajapushpa-pristinia/",
    ],
    "RAJAPUSHPA CASA LUXURA": [
        "https://www.rajapushpa.com/project/rajapushpa-casa-luxura/",
    ],
    "RAJAPUSHPA PROVINCIA": [
        "https://www.rajapushpa.com/project/rajapushpa-provincia/",
    ],
    "NORTHSTAR ALLURA": [
        "https://www.northstarhomes.in/northstar-allura/",
    ],
    "JAYABHERI THE NIRVANA": [
        "https://jayabheri.com/the-nirvana/",
    ],
    "JAYABHERI THE SAHASRA": [
        "https://jayabheri.com/the-sahasra/",
    ],
    "NAVANAAMI ONE": [
        "https://www.navanaami.com/navanaami-one/",
    ],
    "POULOMI 90": [
        "https://www.poulomidevelopers.com/poulomi-90/",
    ],
    "ALEKHYA RISE": [
        "https://alekhyagroup.com/alekhya-rise/",
    ],
    "Elemental Earthwoods": [
        "https://elementalgroup.in/earthwoods/",
    ],
    "TRENDSET ALLURE": [
        "https://trendsethomes.in/trendset-allure/",
    ],
    "MARVEL HEIGHTS": [
        "https://marvelinfra.com/marvel-heights/",
    ],
}

def setup_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-gpu")
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    driver.set_page_load_timeout(30)
    return driver

def extract_images_selenium(driver, url: str) -> list[str]:
    """Load page with Selenium and extract large images."""
    imgs = set()
    try:
        driver.get(url)
        time.sleep(4)  # wait for JS to render

        # Scroll down to trigger lazy loading
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2)")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)

        # Get all img elements
        for img in driver.find_elements(By.TAG_NAME, "img"):
            src = (img.get_attribute("src") or
                   img.get_attribute("data-src") or
                   img.get_attribute("data-lazy-src") or
                   img.get_attribute("data-original") or "")
            if src and is_good_image(src):
                imgs.add(src)

        # Also check CSS background images
        elements = driver.find_elements(By.XPATH, "//*[@style]")
        for el in elements:
            style = el.get_attribute("style") or ""
            bg = re.findall(r'url\(["\']?(https?://[^"\'<>\s)]+\.(?:jpg|jpeg|png|webp))["\']?\)', style)
            for url_match in bg:
                if is_good_image(url_match):
                    imgs.add(url_match)

        # Get OG image from meta
        try:
            og = driver.find_element(By.XPATH, '//meta[@property="og:image"]')
            src = og.get_attribute("content") or ""
            if src and is_good_image(src):
                imgs.add(src)
        except: pass

    except Exception as e:
        print(f"    selenium error: {e}")

    return list(imgs)[:8]

def is_good_image(url: str) -> bool:
    url_lower = url.lower()
    if not any(ext in url_lower for ext in [".jpg", ".jpeg", ".png", ".webp"]):
        return False
    bad = ["logo", "icon", "favicon", "qr", "app-", "playstore", "appstore",
           "sprite", "avatar", "placeholder", "flag", "badge", "award",
           "whatsapp", "facebook", "twitter", "instagram", "youtube",
           "map", "chart", "graph", "team", "staff", "person", "people",
           "1x1", "pixel", "blank", "transparent", "gif", "svg",
           "data:image"]
    return not any(b in url_lower for b in bad)

def download_and_upload(image_url: str, storage_path: str) -> str | None:
    try:
        r = requests.get(image_url, timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        if r.status_code != 200: return None
        ct = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        if not any(t in ct for t in ["image/jpeg","image/jpg","image/png","image/webp"]):
            return None
        if len(r.content) < 30000:  # skip < 30KB
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
    conn   = psycopg2.connect(DB_URL)
    cur    = conn.cursor()
    driver = setup_driver()
    print("Browser ready.\n")

    cur.execute("SELECT id, project_name FROM projects")
    projects = {r[1]: r[0] for r in cur.fetchall()}
    total_uploaded = 0

    for project_name, urls in SOURCES.items():
        pid = projects.get(project_name)
        if not pid:
            print(f"  NOT IN DB: {project_name}")
            continue

        # Skip if already has 2+ real images (size > 30KB)
        cur.execute(
            "SELECT COUNT(*) FROM project_media WHERE project_id=%s AND media_type='image' AND file_size>30000",
            (pid,)
        )
        if cur.fetchone()[0] >= 2:
            print(f"  SKIP  {project_name} (already has good images)")
            continue

        print(f"\n[{project_name}]")
        all_imgs = []

        for url in urls[:2]:
            print(f"  Loading: {url}")
            imgs = extract_images_selenium(driver, url)
            print(f"  Found {len(imgs)} candidate images")
            all_imgs.extend(imgs)
            if len(all_imgs) >= 4: break
            time.sleep(3)

        if not all_imgs:
            print(f"  No images found on developer site")
            continue

        pid_safe = sanitize_id(project_name)
        uploaded = 0

        for i, img_url in enumerate(all_imgs[:4]):
            ext = ".webp" if ".webp" in img_url.lower() else ".png" if ".png" in img_url.lower() else ".jpg"
            path = f"{pid_safe}/images/devsite_{i+1}{ext}"
            print(f"  [{i+1}] {img_url[:55]}...", end=" ", flush=True)
            pub = download_and_upload(img_url, path)
            if not pub:
                print("skipped")
                continue

            # Remove existing placeholders for this project
            if i == 0:
                cur.execute(
                    "DELETE FROM project_media WHERE project_id=%s AND media_type='image' AND file_name LIKE 'placeholder_%'",
                    (pid,)
                )
                conn.commit()

            cur.execute("""
                INSERT INTO project_media
                    (id,project_id,media_type,title,file_url,file_name,file_size,mime_type,sort_order)
                VALUES (gen_random_uuid(),%s,'image',%s,%s,%s,%s,'image/jpeg',%s)
                ON CONFLICT DO NOTHING
            """, (pid, f"{project_name} — {i+1}", pub, f"devsite_{i+1}{ext}", 150000, i))
            conn.commit()
            print("✓")
            uploaded += 1
            total_uploaded += 1
            time.sleep(1)

        print(f"  → {uploaded} real property photos saved")
        time.sleep(4)

    driver.quit()
    cur.close()
    conn.close()
    print(f"\n{'='*60}")
    print(f"Total: {total_uploaded} real property images uploaded")

if __name__ == "__main__":
    main()
