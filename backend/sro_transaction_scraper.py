"""
SRO Transaction Scraper - production version using requests-based bulk document iteration.

Usage:
    python sro_transaction_scraper.py test [SRO_NAME] [YEAR] [N_DOCS]
    python sro_transaction_scraper.py full [SRO_NAME] [YEAR]
"""
import json, re, io, time, logging, sys
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

# ── Database import (optional — graceful degradation if not configured) ───────
try:
    from db_utils import get_connection, start_scrape_run, finish_scrape_run, fail_scrape_run
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False


def _parse_numeric(val):
    """Parse a numeric value from a string, stripping currency symbols and commas."""
    if val is None:
        return None
    try:
        return float(str(val).replace(",", "").replace("Rs", "").replace("₹", "").strip())
    except (TypeError, ValueError):
        return None


def save_sro_transactions_to_db(conn, transactions: list) -> int:
    """Insert SRO transaction records using ON CONFLICT DO NOTHING for idempotency.

    Args:
        conn: An open psycopg2 connection.
        transactions: List of transaction dicts from the scraper.

    Returns:
        Number of rows attempted.
    """
    if not transactions:
        return 0
    rows = []
    for t in transactions:
        rows.append((
            t.get("sro_name"),
            t.get("district"),
            t.get("village"),
            t.get("apartment"),
            t.get("flat_no"),
            t.get("reg_date") or None,
            t.get("quarter"),
            _parse_numeric(t.get("mkt_value")),
            _parse_numeric(t.get("cons_value")),
            _parse_numeric(t.get("price_per_sqft")),
        ))
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO sro_transactions
                (sro_name, district, village, apartment, flat_no,
                 reg_date, quarter, mkt_value, cons_value, price_per_sqft, scraped_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT DO NOTHING
            """,
            rows,
        )
    conn.commit()
    return len(rows)

import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from PIL import Image, ImageFilter, ImageEnhance
import pytesseract
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

BASE_URL       = "https://registration.telangana.gov.in"
DEED_ENDPOINT  = f"{BASE_URL}/getDeedDetails.htm"
DATA_DIR       = Path(__file__).parent / "scraped_projects"
LOG_DIR        = Path(__file__).parent / "igrs_diagnostics"
LOG_DIR.mkdir(exist_ok=True)

# ── Master SRO registry ────────────────────────────────────────────────────────
# To add new SROs: find dist_code + sro_code on the IGRS portal
# (registration.telangana.gov.in → districtList) then add an entry here.
# The scraper will automatically include the new SRO for any pincode whose
# RERA mandal maps to it via MANDAL_TO_SRO_NAME below.
TARGET_SROS = [
    # ── Rangareddy district ────────────────────────────────────────────────
    {"name": "SERILINGAMPALLI", "district": "RANGAREDDY",  "dist_code": "15_1", "sro_code": "1522"},
    {"name": "RAJENDRA NAGAR",  "district": "RANGAREDDY",  "dist_code": "15_1", "sro_code": "1518"},
    {"name": "L.B.NAGAR",       "district": "RANGAREDDY",  "dist_code": "15_1", "sro_code": "1527"},
    {"name": "GANDIPET",        "district": "RANGAREDDY",  "dist_code": "15_1", "sro_code": "1525"},
    {"name": "SAROORNAGAR",     "district": "RANGAREDDY",  "dist_code": "15_1", "sro_code": "1513"},
    {"name": "SHAMSHABAD",      "district": "RANGAREDDY",  "dist_code": "15_1", "sro_code": "1520"},
    # ── Hyderabad district ─────────────────────────────────────────────────
    {"name": "BANJARAHILLS",    "district": "HYDERABAD",   "dist_code": "16_1", "sro_code": "1604"},
    {"name": "S.R.NAGAR",       "district": "HYDERABAD",   "dist_code": "16_1", "sro_code": "1611"},
    {"name": "MAREDPALLY",      "district": "HYDERABAD",   "dist_code": "16_1", "sro_code": "1605"},
    # ── TODO: add when SRO codes are confirmed from IGRS portal ────────────
    # {"name": "AMEENPUR",       "district": "SANGAREDDY",  "dist_code": "??",   "sro_code": "????"},
    # {"name": "BACHUPALLY",     "district": "MEDCHAL",     "dist_code": "??",   "sro_code": "????"},
    # {"name": "RC PURAM",       "district": "MEDCHAL",     "dist_code": "??",   "sro_code": "????"},
    # {"name": "KUKATPALLY",     "district": "MEDCHAL",     "dist_code": "??",   "sro_code": "????"},
]

# ── Mandal name (as in RERA data) → SRO name in TARGET_SROS ────────────────
# Keys are lowercase, stripped. Add variants as they appear in RERA Address Details.
# When you add a new SRO to TARGET_SROS above, map all its mandal name variants here.
MANDAL_TO_SRO_NAME: dict[str, str] = {
    # Serilingampalli
    "serilingampally":          "SERILINGAMPALLI",
    "serilingampalli":          "SERILINGAMPALLI",
    "kondapur":                 "SERILINGAMPALLI",
    "raidurg":                  "SERILINGAMPALLI",
    "hafeezpet":                "SERILINGAMPALLI",
    "haffizpet":                "SERILINGAMPALLI",
    "narsingi":                 "SERILINGAMPALLI",
    "hi tech city":             "SERILINGAMPALLI",
    "hitech city":              "SERILINGAMPALLI",
    "madhapur":                 "SERILINGAMPALLI",
    "gachibowli":               "SERILINGAMPALLI",
    "kokapet":                  "SERILINGAMPALLI",
    "nanakramguda":             "SERILINGAMPALLI",
    "manikonda":                "SERILINGAMPALLI",
    "puppalaguda":              "SERILINGAMPALLI",
    "peeramcheru":              "SERILINGAMPALLI",
    # Rajendra Nagar
    "rajendranagar":            "RAJENDRA NAGAR",
    "rajendra nagar":           "RAJENDRA NAGAR",
    "bandlaguda":               "RAJENDRA NAGAR",
    "budvel":                   "RAJENDRA NAGAR",
    # LB Nagar
    "lb nagar":                 "L.B.NAGAR",
    "lbnagar":                  "L.B.NAGAR",
    "hayathnagar":              "L.B.NAGAR",
    "saroornagar":              "SAROORNAGAR",
    # Gandipet
    "gandipet":                 "GANDIPET",
    "tellapur":                 "GANDIPET",
    "mokila":                   "GANDIPET",
    "shankarpalle":             "GANDIPET",
    "osman nagar":              "GANDIPET",
    # Saroornagar
    "saroornagar":              "SAROORNAGAR",
    "saidabad":                 "SAROORNAGAR",
    "malakpet":                 "SAROORNAGAR",
    # Shamshabad
    "shamshabad":               "SHAMSHABAD",
    "balapur":                  "SHAMSHABAD",
    "yadagirigutta":            "SHAMSHABAD",
    "mamidipally":              "SHAMSHABAD",
    "kandukur":                 "SHAMSHABAD",
    "maheshwaram":              "SHAMSHABAD",
    "kothur":                   "SHAMSHABAD",
    "kadthal":                  "SHAMSHABAD",
    # Banjarahills (Hyderabad dist) — covers Shaikpet mandal area
    "shaikpet":                 "BANJARAHILLS",
    "banjarahills":             "BANJARAHILLS",
    "banjara hills":            "BANJARAHILLS",
    "jubilee hills":            "BANJARAHILLS",
    "khairtabad":               "BANJARAHILLS",
    "golconda":                 "BANJARAHILLS",
    "asif nagar":               "BANJARAHILLS",
    "nampally":                 "BANJARAHILLS",
    "karwan":                   "BANJARAHILLS",
    # S.R.Nagar (Hyderabad dist)
    "sr nagar":                 "S.R.NAGAR",
    "s.r.nagar":                "S.R.NAGAR",
    "ameerpet":                 "S.R.NAGAR",
    "balanagar":                "S.R.NAGAR",
    "kukatpally":               "S.R.NAGAR",
    "rc puram":                 "S.R.NAGAR",
    "ramachandrapuram":         "S.R.NAGAR",
    "bachupally":               "S.R.NAGAR",
    "ameenpur":                 "S.R.NAGAR",
    "chandanagar":              "S.R.NAGAR",
    "chanda nagar":             "S.R.NAGAR",
    "madeenaguda":              "S.R.NAGAR",
    "miyapur":                  "S.R.NAGAR",
    "nizampet":                 "S.R.NAGAR",
    "kompally":                 "S.R.NAGAR",
    "dundigal":                 "S.R.NAGAR",
    "dundigal gandimaisamma":   "S.R.NAGAR",
    "qutballapur":              "S.R.NAGAR",
    "medchal":                  "S.R.NAGAR",
    # Maredpally (Hyderabad dist) — Secunderabad/east Hyderabad
    "maredpally":               "MAREDPALLY",
    "secunderabad":             "MAREDPALLY",
    "uppal":                    "MAREDPALLY",
    "malkajgiri":               "MAREDPALLY",
    "alwal":                    "MAREDPALLY",
    "kapra":                    "MAREDPALLY",
    "keesara":                  "MAREDPALLY",
    "ghatkesar":                "MAREDPALLY",
    "ibrahimpatnam":            "MAREDPALLY",
}


def get_active_sros(pincodes: list[str] | None = None) -> list[dict]:
    """
    Derive which SROs to scrape based on pincodes in scrape_preferences.json.

    Steps:
      1. If pincodes not supplied, read from scrape_preferences.json.
      2. Scan RERA scraped project JSON files to find all mandals for those pincodes.
      3. Map mandals -> SRO names via MANDAL_TO_SRO_NAME.
      4. Return matching entries from TARGET_SROS.
      5. Fallback: if no mandals matched (e.g. fresh install), return all TARGET_SROS.

    To add coverage for a new pincode area:
      - Ensure its SRO entry is in TARGET_SROS (with correct dist_code/sro_code).
      - Add its mandal name(s) to MANDAL_TO_SRO_NAME.
      - No other code changes needed.
    """
    _prefs_path = Path(__file__).parent / "scrape_preferences.json"
    _rera_dir   = Path(__file__).parent / "scraped_projects"

    if pincodes is None:
        try:
            prefs = json.loads(_prefs_path.read_text(encoding="utf-8"))
            pincodes = [str(p).strip() for p in prefs.get("pincodes", []) if str(p).strip()]
        except Exception:
            pincodes = []

    if not pincodes:
        log.info("get_active_sros: no pincodes configured — using all TARGET_SROS")
        return TARGET_SROS

    pin_set = set(pincodes)

    # Collect mandals for matching pincodes from RERA scraped data
    found_mandals: set[str] = set()
    for jf in _rera_dir.rglob("*.json"):
        if jf.name in ("all_projects_data.json", "unit_rates.json", "sro_transactions.json"):
            continue
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
            entries = data if isinstance(data, list) else [data]
            for p in entries:
                addr = p.get("Address Details", {})
                pin  = str(addr.get("Pin Code") or "").strip()
                if pin in pin_set:
                    mandal = str(addr.get("Mandal") or "").strip().lower()
                    if mandal:
                        found_mandals.add(mandal)
        except Exception:
            pass

    if not found_mandals:
        log.warning("get_active_sros: pincodes %s not found in RERA data — using all TARGET_SROS", pin_set)
        return TARGET_SROS

    # Map mandals -> SRO names
    sro_names_needed: set[str] = set()
    unmapped: set[str] = set()
    for mandal in found_mandals:
        sro_name = MANDAL_TO_SRO_NAME.get(mandal)
        if sro_name:
            sro_names_needed.add(sro_name)
        else:
            unmapped.add(mandal)

    if unmapped:
        log.warning(
            "get_active_sros: mandals not yet in MANDAL_TO_SRO_NAME — add their SRO codes to "
            "TARGET_SROS and map them: %s", sorted(unmapped)
        )

    # Filter TARGET_SROS to only those needed
    active = [s for s in TARGET_SROS if s["name"] in sro_names_needed]
    if not active:
        log.warning("get_active_sros: no TARGET_SROS matched — using all TARGET_SROS as fallback")
        return TARGET_SROS

    log.info("get_active_sros: pincodes=%s  mandals=%s  SROs=%s",
             sorted(pin_set), sorted(found_mandals), [s["name"] for s in active])
    return active

SCRAPE_YEARS  = [2021, 2022, 2023, 2024, 2025]
BATCH_THREADS = 12
REQUEST_DELAY = 0.2

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "sro_scrape.log", encoding="utf-8"),
        logging.StreamHandler()
    ])
log = logging.getLogger(__name__)


def _load_creds():
    p = Path(__file__).parent / "scrape_preferences.json"
    if p.exists():
        d = json.loads(p.read_text())
        return d.get("igrs_username",""), d.get("igrs_password","")
    return "", ""


def _ocr_captcha(driver):
    sess = requests.Session()
    for ck in driver.get_cookies():
        sess.cookies.set(ck["name"], ck["value"])
    r = sess.get(f"{BASE_URL}/Captcha.jpg", timeout=10)
    if r.status_code != 200:
        return ""
    img = Image.open(io.BytesIO(r.content)).convert("L")
    img = img.resize((img.width*3, img.height*3), Image.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(3)
    img = img.point(lambda p: 0 if p < 128 else 255)
    img = img.filter(ImageFilter.MedianFilter(3))
    text = pytesseract.image_to_string(img,
        config="--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    ).strip()
    return re.sub(r"[^A-Za-z0-9]", "", text)


def login_and_get_cookies() -> dict:
    """Selenium login → return session cookies for requests."""
    username, password = _load_creds()
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,800")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    cookies = {}
    try:
        driver.get(f"{BASE_URL}/districtList.htm")
        # Wait up to 20s for the username field to be present
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        for attempt in range(8):
            # Dismiss any lingering alert first
            try:
                driver.switch_to.alert.accept()
            except Exception:
                pass

            # Select user type via JavaScript — value '1' = Citizen (confirmed by debug)
            try:
                driver.execute_script("""
                    var sel = document.getElementById('user_type');
                    if (sel) {
                        sel.value = '1';
                        sel.dispatchEvent(new Event('change'));
                    }
                """)
                # Wait for username to become visible after user_type change
                WebDriverWait(driver, 8).until(
                    EC.visibility_of_element_located((By.ID, "username"))
                )
                time.sleep(1)  # extra settle time
            except Exception as e:
                log.warning(f"user_type JS selection failed: {e}")

            # Fill fields via Selenium send_keys (more reliable than JS .value after visibility confirmed)
            try:
                u_el = driver.find_element(By.ID, "username")
                u_el.clear()
                u_el.send_keys(username)
                p_el = driver.find_element(By.ID, "password")
                p_el.clear()
                p_el.send_keys(password)
            except Exception as e:
                log.warning(f"Field fill failed: {e}")
                continue
            cap = _ocr_captcha(driver)
            log.info(f"Login attempt {attempt+1}: captcha={cap!r}")
            if not cap:
                driver.get(f"{BASE_URL}/districtList.htm")
                WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "username")))
                continue
            driver.execute_script(f"document.getElementById('captcha').value = '{cap}';")
            try:
                driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            except Exception:
                driver.find_element(By.ID, "myForm").submit()
            time.sleep(6)
            # Dismiss any alert that appeared after submit
            try:
                driver.switch_to.alert.accept()
                time.sleep(2)
            except Exception:
                pass
            body = driver.find_element(By.TAG_NAME, "body").text.lower()
            if any(x in body for x in ["welcome","logout","encumbrance"]):
                log.info("Login successful")
                cookies = {c["name"]:c["value"] for c in driver.get_cookies()}
                return cookies
            elif "invalid captcha" in body:
                log.warning("Invalid captcha — retrying")
                driver.get(f"{BASE_URL}/districtList.htm")
                WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "username")))
            elif "invalid password" in body:
                log.error("Invalid credentials"); return {}
    finally:
        driver.quit()
    return cookies


def fetch_doc(session: requests.Session, dist_code: str, sro_code: str,
              doc_no: int, year: int) -> Optional[dict]:
    """POST getDeedDetails.htm for one document. Returns parsed record or None."""
    payload = {"deedsel":"1", "districtCode":dist_code, "sroCode":sro_code,
               "doctno":str(doc_no), "regyear":str(year)}
    try:
        resp = session.post(DEED_ENDPOINT, data=payload, timeout=15)
        if resp.status_code != 200: return None
    except Exception as e:
        log.debug(f"Request error doc {doc_no}/{year}: {e}"); return None
    if "not found in the Records" in resp.text: return None
    return parse_deed_html(resp.text, doc_no, year, dist_code, sro_code)


def parse_deed_html(html: str, doc_no: int, year: int,
                    dist_code: str, sro_code: str) -> Optional[dict]:
    """Parse a getDeedDetails response. Returns apartment sale deed record or None."""
    soup = BeautifulSoup(html, "html.parser")
    rows = [tr for tr in soup.select("table tr")[1:] if tr.find("td")]
    if not rows: return None
    cells = [td.get_text(" ", strip=True) for td in rows[0].find_all("td")]
    if len(cells) < 5: return None

    desc         = cells[1] if len(cells) > 1 else ""
    dates_cell   = cells[2] if len(cells) > 2 else ""
    nature_cell  = cells[3] if len(cells) > 3 else ""

    # Only keep Sale Deeds of apartments
    if "0101" not in nature_cell or "Sale Deed" not in nature_cell: return None
    if "APARTMENT:" not in desc.upper(): return None

    record = {"doc_no": doc_no, "year": year, "dist_code": dist_code, "sro_code": sro_code}

    col_m  = re.search(r"VILL/COL:\s*([A-Z0-9 ()/-]+?)/", desc)
    col2_m = re.search(r"VILL/COL:\s*(.+?)\s+(?:W-B|SURVEY|PLOT|HOUSE|APARTMENT|EXTENT)", desc, re.IGNORECASE)
    apt_m  = re.search(r"APARTMENT:\s*(.+?)\s+FLAT:", desc, re.IGNORECASE)
    flat_m = re.search(r"FLAT:\s*(\S+)", desc, re.IGNORECASE)
    sqft_m = re.search(r"BUILT:\s*([\d.]+)\s*SQ", desc, re.IGNORECASE)
    sqyd_m = re.search(r"EXTENT:\s*([\d.]+)\s*SQ", desc, re.IGNORECASE)

    village_raw = col_m.group(1) if col_m else (col2_m.group(1) if col2_m else "")
    # Village is before '/' in "VILL/COL: VILLAGE/COLONY"
    if "/" in village_raw:
        village_raw = village_raw.split("/")[0]
    record["village"]    = village_raw.strip()
    record["apartment"]  = apt_m.group(1).strip()  if apt_m  else ""
    record["flat_no"]    = flat_m.group(1).strip()  if flat_m else ""
    record["built_sqft"] = float(sqft_m.group(1))   if sqft_m else 0.0
    record["extent_sqyd"]= float(sqyd_m.group(1))   if sqyd_m else 0.0

    mkt_m = re.search(r"Mkt\.Value:Rs\.\s*([\d,]+)", nature_cell)
    con_m = re.search(r"Cons\.Value:Rs\.\s*([\d,]+)", nature_cell)
    record["mkt_value"]  = int(mkt_m.group(1).replace(",","")) if mkt_m else 0
    record["cons_value"] = int(con_m.group(1).replace(",","")) if con_m else 0

    price = max(record["mkt_value"], record["cons_value"])
    record["price_per_sqft"] = round(price / record["built_sqft"], 1) if record["built_sqft"] > 0 else 0.0

    reg_m = re.search(r"\(R\)\s*(\d{2}-\d{2}-\d{4})", dates_cell)
    if reg_m:
        try:
            dt = datetime.strptime(reg_m.group(1), "%d-%m-%Y")
            record["reg_date"] = dt.strftime("%Y-%m-%d")
            record["quarter"]  = f"{dt.year}-Q{(dt.month-1)//3+1}"
        except Exception:
            record["reg_date"] = record["quarter"] = ""
    else:
        record["reg_date"] = record["quarter"] = ""

    if record["price_per_sqft"] <= 0 or record["built_sqft"] < 100: return None
    return record


def find_max_doc(session, dist_code, sro_code, year, upper=20000):
    """Binary search for highest valid document number in (SRO, year)."""
    lo, hi = 1, upper
    while lo < hi:
        mid = (lo + hi + 1) // 2
        payload = {"deedsel":"1","districtCode":dist_code,"sroCode":sro_code,
                   "doctno":str(mid),"regyear":str(year)}
        try:
            r = session.post(DEED_ENDPOINT, data=payload, timeout=15)
            exists = "not found in the Records" not in r.text
        except Exception:
            exists = False
        if exists:
            lo = mid
        else:
            hi = mid - 1
        time.sleep(REQUEST_DELAY)
    return lo


def scrape_sro_year(session, sro: dict, year: int, max_doc: int = None) -> list:
    """Fetch all apartment Sale Deeds for one SRO+year."""
    dist_code = sro["dist_code"]
    sro_code  = sro["sro_code"]
    sro_name  = sro["name"]

    if max_doc is None:
        log.info(f"  Binary-searching max doc for {sro_name} {year}...")
        max_doc = find_max_doc(session, dist_code, sro_code, year)
        log.info(f"  max_doc={max_doc}")

    if max_doc == 0:
        log.info(f"  No docs for {sro_name} {year}")
        return []

    records = []
    processed = 0
    batch_size = BATCH_THREADS * 10

    def fetch_one(dn):
        time.sleep(REQUEST_DELAY)
        return dn, fetch_doc(session, dist_code, sro_code, dn, year)

    with ThreadPoolExecutor(max_workers=BATCH_THREADS) as pool:
        for i in range(0, max_doc, batch_size):
            batch = range(i+1, min(i+batch_size+1, max_doc+1))
            futures = {pool.submit(fetch_one, d): d for d in batch}
            for fut in as_completed(futures):
                dn, rec = fut.result()
                processed += 1
                if rec:
                    rec["sro_name"] = sro_name
                    rec["district"] = sro["district"]
                    records.append(rec)
                if processed % 500 == 0:
                    log.info(f"    [{sro_name} {year}] {processed}/{max_doc}, {len(records)} apt sales")

    log.info(f"  {sro_name} {year}: {len(records)} apt sale deeds from {max_doc} total docs")
    return records


def build_quarterly_summary(records: list) -> list:
    buckets: dict = {}
    for r in records:
        if not r.get("quarter") or r.get("price_per_sqft", 0) <= 0: continue
        key = (r["district"], r.get("sro_name",""), r["quarter"])
        if key not in buckets: buckets[key] = {"prices":[], "count":0}
        buckets[key]["prices"].append(r["price_per_sqft"])
        buckets[key]["count"] += 1
    summary = []
    for (district, sro, quarter), data in sorted(buckets.items()):
        p = sorted(data["prices"])
        n = len(p)
        summary.append({
            "district": district, "sro": sro, "quarter": quarter,
            "count": data["count"],
            "avg_price_sqft":    round(sum(p)/n, 1),
            "median_price_sqft": round(p[n//2], 1),
            "min_price_sqft":    round(p[0], 1),
            "max_price_sqft":    round(p[-1], 1),
        })
    return summary


def build_village_summary(records: list) -> list:
    buckets: dict = {}
    for r in records:
        if not r.get("quarter") or r.get("price_per_sqft", 0) <= 0: continue
        village = r.get("village","").strip()
        if not village: continue
        key = (r["district"], r.get("sro_name",""), village, r["quarter"])
        if key not in buckets: buckets[key] = {"prices":[], "count":0}
        buckets[key]["prices"].append(r["price_per_sqft"])
        buckets[key]["count"] += 1
    summary = []
    for (district, sro, village, quarter), data in sorted(buckets.items()):
        p = sorted(data["prices"])
        if len(p) < 2: continue
        summary.append({
            "district": district, "sro": sro, "village": village,
            "quarter": quarter, "count": data["count"],
            "avg_price_sqft":    round(sum(p)/len(p), 1),
            "median_price_sqft": round(p[len(p)//2], 1),
        })
    return summary


def _save(records: list, path):
    path = Path(path)
    data = {
        "scraped_at": datetime.now().isoformat(),
        "total_records": len(records),
        "records": records,
        "quarterly_by_sro": build_quarterly_summary(records),
        "quarterly_by_village": build_village_summary(records),
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"Saved {len(records)} records → {path}")


def run_scraper(sros=None, years=None):
    sros  = sros  or TARGET_SROS
    years = years or SCRAPE_YEARS
    log.info(f"=== SRO Scraper: {[s['name'] for s in sros]}, years={years} ===")
    cookies = login_and_get_cookies()
    if not cookies: log.error("Login failed"); return

    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=BATCH_THREADS, pool_maxsize=BATCH_THREADS)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.cookies.update(cookies)
    session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    session.headers["Referer"]    = f"{BASE_URL}/districtList.htm"

    out_path = DATA_DIR / "sro_transactions.json"
    all_records = []
    existing_keys: set = set()
    if out_path.exists():
        try:
            ex = json.loads(out_path.read_text(encoding="utf-8"))
            all_records = ex.get("records", [])
            existing_keys = {(r.get("sro_code"), r.get("doc_no"), r.get("year")) for r in all_records}
            log.info(f"Loaded {len(all_records)} existing records")
        except Exception: pass

    for sro in sros:
        sro_existing_count = sum(1 for r in all_records if r.get('sro_name') == sro['name'])
        if sro_existing_count > 0:
            log.info(f"Skipping {sro['name']} — {sro_existing_count} records already exist")
            continue
        for year in years:
            log.info(f"\n--- {sro['name']} {year} ---")
            new_recs = scrape_sro_year(session, sro, year)
            for r in new_recs:
                k = (r.get("sro_code"), r.get("doc_no"), r.get("year"))
                if k not in existing_keys:
                    all_records.append(r); existing_keys.add(k)
            _save(all_records, out_path)

    log.info(f"\n=== DONE: {len(all_records)} total apartment sale deeds ===")

    # Best-effort write to PostgreSQL
    if _DB_AVAILABLE and all_records:
        _db_conn = None
        _run_id = None
        try:
            _db_conn = get_connection()
            _run_id = start_scrape_run(_db_conn, "sro")
            saved = save_sro_transactions_to_db(_db_conn, all_records)
            finish_scrape_run(_db_conn, _run_id, total=len(all_records), completed=saved)
            log.info(f"[DB] Inserted {saved} SRO transaction records to PostgreSQL.")
        except Exception as _db_err:
            log.warning(f"[DB] Could not write SRO transactions to DB: {_db_err}")
            if _db_conn and _run_id:
                try:
                    fail_scrape_run(_db_conn, _run_id, str(_db_err))
                except Exception:
                    pass
        finally:
            if _db_conn:
                try:
                    _db_conn.close()
                except Exception:
                    pass

    return all_records


def quick_test(sro_code="1522", dist_code="15_1", sro_name="SERILINGAMPALLI",
               district="RANGAREDDY", year=2025, n_docs=50):
    """Fetch first n_docs for one SRO+year and print apartment sale deeds."""
    log.info(f"Quick test: {sro_name} {year}, first {n_docs} docs")
    cookies = login_and_get_cookies()
    if not cookies: log.error("Login failed"); return

    session = requests.Session()
    session.cookies.update(cookies)
    session.headers["User-Agent"] = "Mozilla/5.0"
    session.headers["Referer"]    = f"{BASE_URL}/districtList.htm"

    found = []
    for docno in range(1, n_docs+1):
        rec = fetch_doc(session, dist_code, sro_code, docno, year)
        if rec:
            rec["sro_name"] = sro_name; rec["district"] = district
            found.append(rec)
            print(f"  Doc {docno:4d}: {rec.get('apartment',''):40s} | "
                  f"{rec.get('village',''):20s} | "
                  f"{rec.get('built_sqft',0):6.0f} sqft @ "
                  f"Rs{rec.get('price_per_sqft',0):,.0f}/sqft | "
                  f"{rec.get('reg_date','')}")
        time.sleep(REQUEST_DELAY)

    print(f"\n{len(found)} apartment sale deeds in first {n_docs} docs")
    if found:
        out = DATA_DIR / "sro_transactions.json"
        _save(found, out)
        print(f"Saved → {out}")
        print("\nQuarterly summary:")
        for q in build_quarterly_summary(found):
            print(f"  {q}")


if __name__ == "__main__":
    # Usage:
    #   full [SRO_NAME] [YEAR]          -- full scrape
    #   test [SRO_NAME] [YEAR] [N_DOCS] -- quick test (default: SERILINGAMPALLI 2025 50)
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "test"

    if mode == "full":
        filter_name = sys.argv[2].upper() if len(sys.argv) > 2 else ""
        filter_year = [int(sys.argv[3])] if len(sys.argv) > 3 else SCRAPE_YEARS
        sros_arg = [s for s in TARGET_SROS if not filter_name or filter_name in s["name"].upper()]
        run_scraper(sros_arg, filter_year)
    else:
        # test mode — positional: [test] [SRO_NAME] [YEAR] [N_DOCS]
        sro_arg  = sys.argv[2].upper() if len(sys.argv) > 2 else "SERILINGAMPALLI"
        year_arg = int(sys.argv[3]) if len(sys.argv) > 3 else 2025
        ndocs    = int(sys.argv[4]) if len(sys.argv) > 4 else 50
        sro_info = next((s for s in TARGET_SROS if sro_arg in s["name"].upper()), TARGET_SROS[0])
        quick_test(sro_info["sro_code"], sro_info["dist_code"], sro_info["name"],
                   sro_info["district"], year_arg, ndocs)
