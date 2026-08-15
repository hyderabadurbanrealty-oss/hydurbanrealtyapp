"""Scrape images from confirmed working developer sites."""
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

SOURCES = {
    "TRUMP TOWERS HYDERABAD": ["https://www.trumptowershyderabad.com/"],
    "RAJAPUSHPA PRISTINIA":   ["https://www.rajapushpa.com/project/rajapushpa-pristinia/"],
    "RAJAPUSHPA CASA LUXURA": ["https://www.rajapushpa.com/project/rajapushpa-casa-luxura/"],
    "RAJAPUSHPA PROVINCIA":   ["https://www.rajapushpa.com/project/rajapushpa-provincia/"],
    "NORTHSTAR ALLURA":       ["https://www.northstarhomes.in/northstar-allura/"],
}

def is_good_image(url):
    u = url.lower()
    if not any(e in u for e in [".jpg",".jpeg",".png",".webp"]): return False
    bad = ["logo","icon","favicon","qr","sprite","avatar","placeholder",
           "flag","badge","whatsapp","facebook","twitter","instagram",
           "1x1","pixel","data:image","button","arrow","close","menu"]
    return not any(b in u for b in bad)

def download_upload(url, path):
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200 or len(r.content) < 30000: return None
        ct = r.headers.get("content-type","image/jpeg").split(";")[0].strip()
        if "image" not in ct: return None
        up = requests.post(f"{SUPA_URL}/storage/v1/object/{BUCKET}/{path}",
            headers={"Authorization": f"Bearer {SUPA_KEY}","apikey": SUPA_KEY,"Content-Type": ct},
            data=r.content, timeout=30)
        if up.status_code in (200,201,409):
            return f"{SUPA_URL}/storage/v1/object/public/{BUCKET}/{path}"
    except: pass
    return None

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--window-size=1920,1080")
opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
driver.set_page_load_timeout(30)

conn = psycopg2.connect(DB_URL)
cur  = conn.cursor()
cur.execute("SELECT id, project_name FROM projects")
projects = {r[1]: r[0] for r in cur.fetchall()}

total = 0

for project_name, urls in SOURCES.items():
    pid = projects.get(project_name)
    if not pid: continue

    print(f"\n[{project_name}]")
    all_imgs = []

    for url in urls:
        print(f"  Loading: {url}")
        try:
            driver.get(url)
            time.sleep(6)

            # Trigger all lazy loading by scrolling in steps
            total_height = driver.execute_script("return document.body.scrollHeight")
            for scroll_y in range(0, total_height, 300):
                driver.execute_script(f"window.scrollTo(0, {scroll_y})")
                time.sleep(0.3)
            time.sleep(3)

            # Force all lazy images to load via JS
            driver.execute_script("""
                document.querySelectorAll('img[data-src], img[data-lazy], img[data-lazy-src], img[data-original]').forEach(img => {
                    const src = img.dataset.src || img.dataset.lazy || img.dataset.lazySrc || img.dataset.original;
                    if (src) img.src = src;
                });
                // Also trigger IntersectionObserver-based lazy loaders
                document.querySelectorAll('img').forEach(img => {
                    img.dispatchEvent(new Event('load'));
                });
            """)
            time.sleep(2)

            for img in driver.find_elements(By.TAG_NAME, "img"):
                for attr in ["src", "data-src", "data-lazy", "data-original", "data-lazy-src", "data-srcset"]:
                    src = img.get_attribute(attr) or ""
                    if src and src.startswith("http") and is_good_image(src):
                        all_imgs.append(src)
                        break

            # Extract all image URLs from page source directly
            page_src = driver.page_source
            all_srcs = re.findall(
                r'(?:src|data-src|data-lazy|data-original)=["\']?(https?://[^"\'<>\s]+\.(?:jpg|jpeg|png|webp))["\']?',
                page_src
            )
            for s in all_srcs:
                if is_good_image(s):
                    all_imgs.append(s)

            # CSS background images
            bg_matches = re.findall(
                r'url\(["\']?(https?://[^"\'<>\s)]+\.(?:jpg|jpeg|png|webp))["\']?\)',
                page_src
            )
            for s in bg_matches:
                if is_good_image(s):
                    all_imgs.append(s)

            # Try OG image
            try:
                og = driver.find_element(By.XPATH, '//meta[@property="og:image"]')
                src = og.get_attribute("content") or ""
                if src and is_good_image(src):
                    all_imgs.insert(0, src)  # OG image first
            except: pass

        except Exception as e:
            print(f"  Error: {e}")

    # Deduplicate
    seen = set()
    unique = [x for x in all_imgs if not (x in seen or seen.add(x))]
    print(f"  Found {len(unique)} images")

    pid_safe = sanitize_id(project_name)
    uploaded = 0

    for i, img_url in enumerate(unique[:4]):
        ext = ".webp" if ".webp" in img_url.lower() else ".jpg"
        path = f"{pid_safe}/images/real_{i+1}{ext}"
        print(f"  [{i+1}] {img_url[:60]}...", end=" ", flush=True)
        pub = download_upload(img_url, path)
        if not pub: print("skipped"); continue

        # Remove placeholder if uploading real image
        if uploaded == 0:
            cur.execute("DELETE FROM project_media WHERE project_id=%s AND media_type='image' AND file_name LIKE 'placeholder_%'", (pid,))
            conn.commit()

        cur.execute("""INSERT INTO project_media
            (id,project_id,media_type,title,file_url,file_name,file_size,mime_type,sort_order)
            VALUES (gen_random_uuid(),%s,'image',%s,%s,%s,200000,'image/jpeg',%s)
            ON CONFLICT DO NOTHING""",
            (pid, f"{project_name} Photo {i+1}", pub, f"real_{i+1}{ext}", i))
        conn.commit()
        print("✓")
        uploaded += 1
        total += 1
        time.sleep(1)

    print(f"  → {uploaded} real photos saved")
    time.sleep(3)

driver.quit()
cur.close()
conn.close()
print(f"\nDone — {total} real property photos uploaded")
