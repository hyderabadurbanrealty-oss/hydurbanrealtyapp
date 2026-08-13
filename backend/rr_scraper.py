"""
Ready Reckoner (Unit Rate) scraper for IGRS Telangana.
Targets /UnitRateMV/getDistrictList.htm â€” the real Market Value Search form.
Uses only our known project mandals/localities for targeted lookups.

Run: python rr_scraper.py --diagnose     (opens Chrome, shows form + XHR calls)
     python rr_scraper.py                (scrapes unit rates for our localities)
     python rr_scraper.py --district HYD (only Hyderabad district)
"""
import os, sys, json, time, logging, argparse, re
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select


def _save_unit_rates_to_db(conn, rates: list) -> int:
    """Truncate unit_rates and re-insert all records (replace semantics).

    Running this N times with the same data produces the same final table state
    as running it once — satisfying the idempotency property.

    Args:
        conn: An open psycopg2 connection.
        rates: List of rate dicts from the scraper.

    Returns:
        Number of rows inserted.
    """
    if not rates:
        return 0
    rows = [
        (
            r.get("district"),
            r.get("mandal"),
            r.get("locality") or r.get("village"),
            r.get("search_type", "apartment"),
            r.get("unit_rate_sqft"),
        )
        for r in rates
    ]
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE unit_rates")
        cur.executemany(
            """
            INSERT INTO unit_rates (district, mandal, locality, search_type, unit_rate_sqft, scraped_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            """,
            rows,
        )
    conn.commit()
    return len(rows)
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

try:
    from webdriver_manager.chrome import ChromeDriverManager
    USE_WDM = True
except ImportError:
    USE_WDM = False


# ── Database write ─────────────────────────────────────────────────────────────

def save_unit_rates_to_db(conn, unit_rates: list):
    """Replace all unit_rates rows with the new dataset (truncate + re-insert).

    This is idempotent: running N times produces the same final DB state as running once.
    """
    if not unit_rates:
        return 0

    with conn.cursor() as cur:
        # Truncate existing data
        cur.execute("TRUNCATE TABLE unit_rates RESTART IDENTITY")

        # Re-insert new dataset
        for rate in unit_rates:
            cur.execute("""
                INSERT INTO unit_rates (
                    district, mandal, locality, search_type,
                    unit_rate_sqft, scraped_at
                ) VALUES (%s, %s, %s, %s, %s, NOW())
            """, (
                rate.get('district'),
                rate.get('mandal'),
                rate.get('locality') or rate.get('village', ''),
                rate.get('search_type', 'apartment'),
                rate.get('unit_rate_sqft'),
            ))
        conn.commit()

    print(f"[DB] Replaced unit_rates table with {len(unit_rates)} new rows.")
    return len(unit_rates)

# â”€â”€ Config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
BASE_URL    = "https://registration.telangana.gov.in"
MV_FORM_URL = f"{BASE_URL}/UnitRateMV/getDistrictList.htm"   # â† real form URL
OUTPUT_FILE = Path(__file__).parent / "scraped_projects" / "unit_rates.json"
LOG_FILE    = Path(__file__).parent / "rr_scrape.log"
DIAG_DIR    = Path(__file__).parent / "igrs_diagnostics"

ELEMENT_WAIT = 30
SELECT_WAIT  = 15   # seconds to wait for a dropdown to populate

# â”€â”€ Our known mandals grouped by IGRS district code â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Extracted from Address Details in scraped RERA project data (290 projects)
# Key = IGRS district code, Value = list of mandal names to look up
TARGET_MANDALS = {
    "HYDERABAD": [
        "AMEERPET", "ASIF NAGAR", "Amberpet", "Golconda",
        "KHAIRTABAD", "Nampally", "Saidabad",
        "Serilingampally", "Serilingampalle",  # IGRS uses both spellings
        "Shaikpet", "Balanagar",
    ],
    "RANGAREDDY": [
        "Balapur", "Gandipet", "Ibrahimpatnam", "Kadthal", "Kandukur",
        "Kothur", "Maheshwaram", "Rajendranagar", "Saroornagar",
        "Serilingampally", "Serilingampalle",  # IGRS uses both spellings
        "Shaikpet", "Shankarpalle", "Yacharam",
    ],
    "MEDCHAL-MALKAJGIRI": [
        "Alwal", "Bachupally", "Dundigal Gandimaisamma", "Ghatkesar",
        "Kapra", "Kukatpally", "Malkajgiri", "Medchal", "Qutballapur", "Uppal",
    ],
    "SANGAREDDY": [
        "AMEENPUR", "KANDI", "PATANCHERU", "RC PURAM", "SADASIVPET",
    ],
}

# ── Pincode → IGRS district normalisation map ────────────────────────────────
# Keys are lowercased RERA district values; values are IGRS district keys
DISTRICT_NORM: dict[str, str] = {
    "hyderabad":            "HYDERABAD",
    "ranga reddy":          "RANGAREDDY",
    "rangareddy":           "RANGAREDDY",
    "medchal-malkajgiri":   "MEDCHAL-MALKAJGIRI",
    "medchal malkajgiri":   "MEDCHAL-MALKAJGIRI",
    "medchal":              "MEDCHAL-MALKAJGIRI",
    "sangareddy":           "SANGAREDDY",
}

SCRAPE_PREFS_FILE  = Path(__file__).parent / "scrape_preferences.json"
SCRAPED_PROJ_DIR   = Path(__file__).parent / "scraped_projects"


def load_pincode_preferences() -> list[str]:
    """Read pincodes from scrape_preferences.json. Returns [] if file missing."""
    if SCRAPE_PREFS_FILE.exists():
        try:
            data = json.loads(SCRAPE_PREFS_FILE.read_text(encoding="utf-8"))
            return [p.strip() for p in data.get("pincodes", []) if p.strip()]
        except Exception as e:
            log.warning(f"Could not read scrape_preferences.json: {e}")
    return []


def build_targets_from_scraped_data(filter_pincodes: list[str] | None = None) -> dict[str, list[str]]:
    """
    Scans all view_page_data.json files in scraped_projects/ and builds a
    district→mandal targets dict filtered to the given pincodes.

    If filter_pincodes is None or empty, reads from scrape_preferences.json.
    Falls back to TARGET_MANDALS if no scraped data found.
    """
    if not filter_pincodes:
        filter_pincodes = load_pincode_preferences()

    if not SCRAPED_PROJ_DIR.exists():
        log.warning("scraped_projects/ not found — using default TARGET_MANDALS")
        return TARGET_MANDALS

    # Build pincode → {igrs_district: set(mandals)} from all scraped projects
    pin_map: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))

    for proj_dir in SCRAPED_PROJ_DIR.iterdir():
        jp = proj_dir / "view_page_data.json"
        if not jp.is_file():
            continue
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
        except Exception:
            continue

        # Flatten the nested JSON to extract address fields
        flat: dict = {}
        def _flatten(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, (dict, list)):
                        _flatten(v)
                    else:
                        flat[k] = str(v).strip()
            elif isinstance(obj, list):
                for item in obj:
                    _flatten(item)
        _flatten(data)

        pincode  = flat.get("Pin Code", "").strip()
        district = flat.get("District", "").strip().lower()
        mandal   = flat.get("Mandal", "").strip().upper()

        if not pincode or not district or not mandal:
            continue

        igrs_dist = DISTRICT_NORM.get(district)
        if not igrs_dist:
            continue

        pin_map[pincode][igrs_dist].add(mandal)

    if not pin_map:
        log.warning("No pincode/mandal data found in scraped projects — using default TARGET_MANDALS")
        return TARGET_MANDALS

    # Filter to preference pincodes
    active_pincodes = [p for p in filter_pincodes if p in pin_map]
    unmatched       = [p for p in filter_pincodes if p not in pin_map]
    if unmatched:
        log.warning(f"These pincodes have no scraped RERA data: {unmatched}")
        # Include them with best-effort lookup by falling back to full TARGET_MANDALS for
        # districts that appear in those pincodes (we can't know the mandal, skip)

    if not active_pincodes and filter_pincodes:
        log.warning("None of the preference pincodes matched scraped data — using full TARGET_MANDALS")
        return TARGET_MANDALS

    # Merge all mandals across matched pincodes
    merged: dict[str, set] = defaultdict(set)
    for pin in active_pincodes:
        for igrs_dist, mandals in pin_map[pin].items():
            merged[igrs_dist].update(mandals)

    # Ensure each district's list is sorted and deduplicated
    result = {dist: sorted(mandals) for dist, mandals in merged.items() if mandals}

    # For unmatched pincodes, log and skip (no mandal info available)
    log.info(f"Built targets from pincodes {filter_pincodes}: "
             f"{sum(len(v) for v in result.values())} mandals across {len(result)} districts")
    return result


ELEMENT_WAIT = 25

DIAG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("RRScraper")

# â”€â”€ Driver â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def build_driver(headless=True):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--log-level=3")
    opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    if USE_WDM:
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    return webdriver.Chrome(options=opts)

# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def get_xhr_urls(driver):
    """Return all XHR/Fetch URLs from CDP performance log."""
    urls = []
    try:
        for entry in driver.get_log("performance"):
            msg = json.loads(entry["message"])["message"]
            if msg.get("method") == "Network.requestWillBeSent":
                p = msg.get("params", {})
                if p.get("type") in ("XHR", "Fetch"):
                    url = p.get("request", {}).get("url", "")
                    if "registration.telangana.gov.in" in url:
                        urls.append(url)
    except Exception as e:
        log.debug(f"XHR log error: {e}")
    return urls


def dump_page(driver, tag="dump"):
    """Save current page source to diagnostics folder."""
    ts  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = DIAG_DIR / f"{tag}_{ts}.html"
    out.write_text(driver.page_source, encoding="utf-8")
    log.info(f"Page saved: {out}")
    return out


def wait_for_select_options(driver, sel_id, min_opts=2, timeout=SELECT_WAIT):
    """Wait until a <select> by id has >= min_opts options (beyond placeholder)."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            opts = driver.find_element(By.ID, sel_id).find_elements(By.TAG_NAME, "option")
            if len(opts) >= min_opts:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def js_select_by_text(driver, sel_id, text_fragment):
    """Set a <select> value by matching option text — uses native Selenium Select first,
    then falls back to JS dispatch for compatibility."""
    try:
        elem = driver.find_element(By.ID, sel_id)
        sel  = Select(elem)
        frag = text_fragment.lower()
        for opt in sel.options:
            if frag in opt.text.lower():
                sel.select_by_value(opt.get_attribute('value'))
                # Also fire events to ensure cascades trigger
                driver.execute_script("""
                    var el = document.getElementById(arguments[0]);
                    if (el) {
                        ['change','input'].forEach(function(e){
                            el.dispatchEvent(new Event(e, {bubbles:true}));
                        });
                        if (window.jQuery) jQuery(el).trigger('change');
                    }
                """, sel_id)
                return f"OK:{opt.text}={opt.get_attribute('value')}"
        return f"NOT_FOUND:{text_fragment!r} in {len(sel.options)} opts"
    except NoSuchElementException:
        return f"NO_SELECT:{sel_id}"
    except Exception as e:
        return f"ERR:{e}"

def read_all_select_options(driver, sel_id):
    """Return list of (value, text) for all options in a select."""
    return driver.execute_script(f"""
        var sel = document.getElementById('{sel_id}');
        if (!sel) return [];
        return Array.from(sel.options).map(function(o){{return [o.value, o.text.trim()]}});
    """)


def extract_table_rows(driver):
    """Extract all table rows as list of dicts from page."""
    return driver.execute_script("""
        var rows = [];
        var tables = document.querySelectorAll('table');
        tables.forEach(function(tbl) {
            var headers = [];
            tbl.querySelectorAll('tr').forEach(function(tr, ri) {
                var cells = Array.from(tr.querySelectorAll('th,td')).map(function(c){return c.innerText.trim();});
                if (ri === 0 && tr.querySelectorAll('th').length > 0) {
                    headers = cells;
                } else if (cells.some(function(c){return c.length > 0;})) {
                    var obj = {};
                    cells.forEach(function(c, i){ obj[headers[i] || ('col'+i)] = c; });
                    rows.push(obj);
                }
            });
        });
        return rows;
    """)


# â”€â”€ Diagnose mode â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def diagnose():
    """Open getDistrictList.htm, interact with dropdowns, capture XHR calls."""
    log.info("=== DIAGNOSE MODE: %s ===", MV_FORM_URL)
    driver = build_driver(headless=False)
    try:
        driver.get(MV_FORM_URL)
        log.info("Waiting 6s for JSâ€¦")
        time.sleep(6)

        selects = driver.execute_script("""
            return Array.from(document.querySelectorAll('select')).map(function(s){
                return {id:s.id, name:s.name,
                        opts: Array.from(s.options).map(function(o){return o.value+'|'+o.text;})};
            });
        """)
        log.info("Selects on page: %s", json.dumps(selects, indent=2))

        inputs = driver.execute_script("""
            return Array.from(document.querySelectorAll('input,button')).map(function(e){
                return {tag:e.tagName, type:e.type, id:e.id, name:e.name, value:e.value};
            });
        """)
        log.info("Inputs/Buttons: %s", json.dumps(inputs, indent=2))

        # Try selecting first non-empty option in first select
        if selects:
            for si in selects:
                if si['opts']:
                    for opt in si['opts']:
                        val, txt = opt.split('|', 1)
                        if val not in ('', '0', '-1', 'null'):
                            log.info(f"Trying to select {si['id']} = {txt!r}")
                            r = js_select_by_text(driver, si['id'], txt[:10])
                            log.info(f"  Result: {r}")
                            time.sleep(4)
                            # check if other selects populated
                            after = driver.execute_script("""
                                return Array.from(document.querySelectorAll('select')).map(function(s){
                                    return {id:s.id, optCount:s.options.length};
                                });
                            """)
                            log.info(f"  Selects after change: {after}")
                            # XHR calls
                            xhrs = get_xhr_urls(driver)
                            log.info(f"  XHR calls: {xhrs}")
                            break
                    break

        dump_page(driver, "mv_diagnose")
        input("Press Enter to closeâ€¦")
    finally:
        driver.quit()


# â”€â”€ Core scraper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class RRScraper:
    """
    Scrapes unit rates from /UnitRateMV/getDistrictList.htm.
    Strategy: discover select IDs from the live page, then for each of our
    target districts/mandals, navigate to the form and submit, then parse
    the results table.
    """

    def __init__(self, headless=True, only_district=None):
        self.driver        = build_driver(headless)
        self.wait          = WebDriverWait(self.driver, ELEMENT_WAIT)
        self.results       = []
        self.only_district = only_district  # filter to one district if set
        self._sel_ids      = {}             # discovered select element IDs

    def close(self):
        try: self.driver.quit()
        except: pass

    # â”€â”€ Discovery â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _discover_selects(self):
        """
        Load the form and confirm select IDs.
        From diagnose run we already know:
          districtCode, mandalCode, divCode, villageCode, locality
        We set these directly and verify they exist.
        """
        self.driver.get(MV_FORM_URL)
        time.sleep(5)

        # Known IDs from diagnose (confirmed 2026-03-02)
        self._sel_ids = {
            'district': 'districtCode',
            'mandal':   'mandalCode',
            'village':  'villageCode',
            'locality': 'locality',
        }

        # Verify district select has options
        opts = read_all_select_options(self.driver, 'districtCode')
        if len(opts) < 5:
            log.error(f"districtCode select only has {len(opts)} options â€” page load issue")
            dump_page(self.driver, "discover_fail")
            return False

        log.info(f"Form verified â€” districtCode has {len(opts)} districts")
        return True

    # â”€â”€ Navigation helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _reload_form(self):
        self.driver.get(MV_FORM_URL)
        time.sleep(3)

    def _select_district(self, dist_name):
        sel_id = self._sel_ids.get('district')
        if not sel_id:
            return False
        result = js_select_by_text(self.driver, sel_id, dist_name)
        log.debug(f"    district select '{dist_name}' -> {result}")
        if "NOT_FOUND" in result:
            # Try abbreviated form (e.g. "RANGAREDDY" vs "Ranga Reddy")
            abbr = dist_name.replace('-', '').replace(' ', '')
            result2 = js_select_by_text(self.driver, sel_id, abbr[:8])
            log.debug(f"    district select abbr '{abbr[:8]}' -> {result2}")
            return "OK" in result2
        time.sleep(0.5)
        # Check XHR fired
        xhrs = get_xhr_urls(self.driver)
        if xhrs: log.debug(f"    district XHR: {xhrs[-1]}")
        return "OK" in result

    def _select_mandal(self, mandal_name):
        sel_id = self._sel_ids.get('mandal')
        if not sel_id:
            return False
        ok = wait_for_select_options(self.driver, sel_id, min_opts=2)
        if not ok:
            log.warning(f"    mandal select '{sel_id}' never populated")
            return False
        result = js_select_by_text(self.driver, sel_id, mandal_name)
        log.debug(f"    mandal select â†’ {result}")
        return "OK" in result

    def _submit_form(self):
        """Click the Submit button (name='submit', type='submit')."""
        try:
            btn = self.driver.find_element(By.CSS_SELECTOR, "input[name='submit'][type='submit']")
            btn.click()
            time.sleep(4)
            return True
        except NoSuchElementException:
            # Fallback: any submit
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, "input[type='submit'], button[type='submit']")
                btn.click()
                time.sleep(4)
                return True
            except: pass
        return False

    # â”€â”€ Per-mandal scrape â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _get_all_villages(self):
        """Return all village options from villageCode select."""
        return read_all_select_options(self.driver, 'villageCode')

    def _scrape_mandal(self, dist_name, mandal_name):
        log.info(f"  Scraping {dist_name} / {mandal_name}â€¦")
        self._reload_form()

        # 1. Select district
        if not self._select_district(dist_name):
            log.warning(f"    Could not select district '{dist_name}'")
            return []

        # 2. Wait for mandal dropdown to populate
        if not wait_for_select_options(self.driver, 'mandalCode', min_opts=2, timeout=SELECT_WAIT):
            log.warning(f"    mandalCode never populated for {dist_name}")
            return []

        # 3. Select mandal
        if not self._select_mandal(mandal_name):
            log.warning(f"    Could not select mandal '{mandal_name}' in {dist_name}")
            return []

        time.sleep(1)

        # 4. Wait for villageCode to populate (optional â€” may be empty for some mandals)
        wait_for_select_options(self.driver, 'villageCode', min_opts=2, timeout=8)
        villages = self._get_all_villages()
        log.debug(f"    Villages found: {len(villages)}")

        all_results = []

        # 5. If villages exist, iterate each; otherwise submit with just district+mandal
        village_loop = [v for v in villages if v[0] not in ('', '0', '-1', 'null', None)]
        if not village_loop:
            village_loop = [('', '')]  # one pass without village selection

        for vcode, vname in village_loop[:30]:  # cap at 30 villages per mandal
            if vcode:
                r = js_select_by_text(self.driver, 'villageCode', vname[:10] if vname else '')
                log.debug(f"      village {vname!r} â†’ {r}")
                time.sleep(0.5)

            # 6. Select search type: Apartment (A) for RERA project relevance
            self.driver.execute_script("""
                var ap = document.getElementById('apartment');
                if (ap) { ap.checked = true; ap.dispatchEvent(new Event('change',{bubbles:true})); }
            """)

            # 7. Submit
            if not self._submit_form():
                log.debug(f"      submit failed for village {vname!r}")
                self._reload_form()
                self._select_district(dist_name)
                time.sleep(2)
                wait_for_select_options(self.driver, 'mandalCode', min_opts=2, timeout=SELECT_WAIT)
                self._select_mandal(mandal_name)
                time.sleep(1)
                continue

            # 8. Extract XHR hint
            xhrs = get_xhr_urls(self.driver)
            if xhrs: log.debug(f"      XHR: {xhrs[-1] if xhrs else ''}")

            # 9. Parse results table
            rows = extract_table_rows(self.driver)
            log.debug(f"      table rows: {len(rows)}")
            if rows:
                log.info(f"    [{vname or 'all'}] {len(rows)} rows â€” sample: {rows[0]}")

            for row in rows:
                rate_val  = None
                loc_name  = vname or ""
                for key, val in row.items():
                    kl = key.lower()
                    if any(x in kl for x in ('locality', 'village', 'area', 'name', 'place')):
                        if len(val) > 1: loc_name = val
                    if any(x in kl for x in ('rate', 'value', 'market', 'sqmt', 'sqft', 'rs', 'price')):
                        try:
                            cleaned = val.replace(',', '').replace('â‚¹', '').replace('Rs', '').strip()
                            rate_val = float(cleaned)
                        except: pass
                    # Try any numeric field as fallback
                    if rate_val is None:
                        try:
                            cleaned = val.replace(',', '').strip()
                            f = float(cleaned)
                            if 100 < f < 2_000_000:  # plausible unit rate range
                                rate_val = f
                        except: pass

                if rate_val and rate_val > 100:
                    all_results.append({
                        "district":       dist_name,
                        "mandal":         mandal_name,
                        "village":        vname or "",
                        "locality":       loc_name,
                        "unit_rate_sqmt": rate_val,
                        "unit_rate_sqft": round(rate_val / 10.764, 2),
                        "raw_row":        row,
                        "scraped_at":     datetime.now(timezone.utc).isoformat(),
                    })

            # Reload form for next village iteration
            if vcode and len(village_loop) > 1:
                self._reload_form()
                self._select_district(dist_name)
                time.sleep(2)
                wait_for_select_options(self.driver, 'mandalCode', min_opts=2, timeout=SELECT_WAIT)
                self._select_mandal(mandal_name)
                wait_for_select_options(self.driver, 'villageCode', min_opts=2, timeout=8)
                time.sleep(0.5)

        log.info(f"  Done {dist_name}/{mandal_name}: {len(all_results)} rate records")
        return all_results

    # â”€â”€ Main run â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def run(self):
        log.info("=== UNIT RATE SCRAPE START ===")

        if not self._discover_selects():
            log.error("Form discovery failed â€” cannot proceed")
            return []

        targets = TARGET_MANDALS
        if self.only_district:
            targets = {k: v for k, v in targets.items()
                       if self.only_district.lower() in k.lower()}

        all_results = []
        for dist_name, mandals in targets.items():
            log.info(f"\n=== District: {dist_name} ({len(mandals)} mandals) ===")
            for mandal in mandals:
                rows = self._scrape_mandal(dist_name, mandal)
                all_results.extend(rows)
                time.sleep(1)

        log.info(f"\nTotal records: {len(all_results)}")

        # Save
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        out_data = {
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "total":      len(all_results),
            "records":    all_results,
        }
        OUTPUT_FILE.write_text(json.dumps(out_data, indent=2, ensure_ascii=False), encoding='utf-8')
        log.info(f"Saved to {OUTPUT_FILE}")

        self.close()
        return all_results


# ── API-based scraper (Selenium for session + requests for AJAX) ──────────────

class RRApiScraper:
    """
    Scraper using direct AJAX API calls (discovered via XHR interception).

    Flow:
    1. Selenium -> load form -> capture JSESSIONID
    2. requests GET /UnitRateMV/getMandalListByDistCode?districtcode={dc}
       -> returns `code/name##code/name##...` format
    3. requests GET /UnitRateMV/getVillageListByDistCode
       ?districtcode={dc}&mandalcode={mc}&sType=U
       -> same `code/name##` format
    4. For Hyderabad (16_1): uses locality dropdown, not village
    5. POST /UnitRateMV/unitRateMV with encodestr = base64(JSON.stringify(form))
       -> returns HTML page with unit rate table
    """

    DISTRICT_CODES = {
        "HYDERABAD":          "16_1",
        "RANGAREDDY":         "15_1",
        "MEDCHAL-MALKAJGIRI": "15_2",
        "SANGAREDDY":         "17_2",
    }

    def __init__(self, only_district=None, pincodes: list[str] | None = None,
                 progress_callback=None):
        self.only_district    = only_district
        self.pincodes         = pincodes       # None = read from scrape_preferences.json
        self.progress_cb      = progress_callback or (lambda msg: None)
        self._session         = None
        self._jsid            = None
        self._stop_requested  = False

    def request_stop(self):
        self._stop_requested = True

    # ── Session via Selenium ──────────────────────────────────────────────────

    def _init_session(self):
        log.info("Initialising IGRS session via Selenium…")
        driver = build_driver(headless=True)
        try:
            driver.get(MV_FORM_URL)
            time.sleep(5)
            cookies = {c['name']: c['value'] for c in driver.get_cookies()}
            self._jsid = cookies.get('JSESSIONID', '')
            if not self._jsid:
                import re as _re
                m = _re.search(r';jsessionid=([A-Za-z0-9_!.-]+)', driver.page_source)
                if m: self._jsid = m.group(1)
        finally:
            driver.quit()

        if not self._jsid:
            log.error("No JSESSIONID obtained")
            return False
        log.info(f"JSESSIONID: {self._jsid[:20]}…")

        self._session = requests.Session()
        self._session.cookies.set('JSESSIONID', self._jsid,
                                   domain='registration.telangana.gov.in')
        self._session.headers.update({
            'User-Agent':       'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer':          MV_FORM_URL,
            'X-Requested-With': 'XMLHttpRequest',
            'Accept':           'text/html,application/xhtml+xml,*/*',
        })
        return True

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_pipe_list(text):
        """Parse 'code/name##code/name##...' into list of (code, name) tuples."""
        if not text or not text.strip():
            return []
        items = []
        for part in text.split('##'):
            part = part.strip()
            if '/' in part and part:
                code, _, name = part.partition('/')
                items.append((code.strip(), name.strip()))
        return items

    def _api_get(self, path, params=None):
        url = BASE_URL + path
        try:
            r = self._session.get(url, params=params, timeout=15)
            log.debug(f"  GET {path} params={params} -> {r.status_code} len={len(r.text)} snippet={r.text[:80]!r}")
            if r.status_code == 200:
                return r.text
        except Exception as e:
            log.debug(f"  GET {path}: {e}")
        return ''

    def _api_post(self, path, fields):
        """POST form fields; adds encodestr = base64(JSON) as required by doSubmit.

        getJsonSubmit() in the page does:
            json[this.name] = this.value  (plain {name:value} object)
            encodestr = btoa(JSON.stringify(json))
        so encodestr is base64 of a plain object—encodestr itself is '' in the snapshot.
        """
        import base64, json as _json
        # Build plain {name:value} object with encodestr='' (as captured by serializeArray)
        json_obj = {k: v for k, v in fields.items() if k != 'encodestr'}
        json_obj['encodestr'] = ''
        fields['encodestr'] = base64.b64encode(
            _json.dumps(json_obj).encode('utf-8')
        ).decode('ascii')

        url = BASE_URL + path
        # Must include JSESSIONID in URL path for Java servlet
        url_jsid = f"{url};jsessionid={self._jsid}"
        try:
            r = self._session.post(url_jsid, data=fields, timeout=20)
            if r.status_code == 200:
                return r.text
            log.debug(f"  POST {path} -> {r.status_code}")
        except Exception as e:
            log.debug(f"  POST {path}: {e}")
        try:  # retry without path-encoded session
            r = self._session.post(url, data=fields, timeout=20)
            if r.status_code == 200: return r.text
        except: pass
        return ''

    # ── AJAX helpers ──────────────────────────────────────────────────────────

    def _get_mandals(self, dist_code):
        raw = self._api_get('/UnitRateMV/getMandalListByDistCode',
                            params={'districtcode': dist_code})
        return self._parse_pipe_list(raw)

    def _get_villages(self, dist_code, mandal_code, stype='U'):
        raw = self._api_get('/UnitRateMV/getVillageListByDistCode',
                            params={'districtcode': dist_code,
                                    'mandalcode':   mandal_code,
                                    'sType':        stype})
        return self._parse_pipe_list(raw)

    # HYDERABAD division codes (divCode select)
    HYD_DIVISIONS = ['1600001', '1600002', '1600003']

    def _get_localities_hyd(self, search_text='$'):
        """For Hyderabad: search localities across all 3 divisions.
        codes param: districtCode~loc~ward~block~divcode
        Returns [(div_code, loc_code, loc_name), ...]
        """
        results = []
        for div in self.HYD_DIVISIONS:
            codes = f"16_1~{search_text}~$~$~{div}"
            path = f'/UnitRateMV/getLocationDetails;jsessionid={self._jsid}'
            url = BASE_URL + path
            try:
                r = self._session.get(url, params={'codes': codes}, timeout=15)
                raw = r.text if r.status_code == 200 else ''
            except Exception as e:
                log.debug(f"  getLocationDetails: {e}")
                raw = ''
            if raw and raw.strip() and raw not in ('Malicious', 'Special'):
                for code, name in self._parse_pipe_list(raw):
                    results.append((div, code, name))
        return results

    def _get_rates_hyd(self, div_code, locality_code, locality_name, search_by='A'):
        """Submit form for Hyderabad localities (radio1=l, with divCode)."""
        fields = {
            'districtId':  '16_1',
            'mandalCode':  '00',
            'villageCode': '',
            'divCode':     div_code,
            'locality':    locality_code,
            'locName':     locality_name,
            'rValue':      'U',
            'tFlag':       '',
            'mndlName':    'HYDERABAD',
            'vlgName':     '',
            'RateType':    'U',
            'search_by':   search_by,
            'radio1':      'l',
        }
        html = self._api_post('/UnitRateMV/unitRateMV', fields)
        if not html:
            return []
        if search_by == 'L':
            return self._parse_rate_html_land(html)
        return self._parse_rate_html(html)

    # ── Rate extraction ───────────────────────────────────────────────────────

    def _get_rates(self, dist_code, mandal_code, village_code,
                   mandal_name='', village_name='', loc_code='', loc_name='',
                   search_by='A'):
        """Submit form and return parsed rate rows.
        Field names must match HTML form name= attributes (NOT id= attributes):
          districtCode select -> name='districtId'
          villName hidden    -> name='vlgName'
          rate2 hidden       -> name='RateType'
        search_by: 'A'=Apartment, 'L'=Land
        """
        fields = {
            'districtId':   dist_code,   # name attr of districtCode select
            'mandalCode':   mandal_code,
            'villageCode':  village_code,
            'divCode':      '',
            'locality':     loc_code,
            'locName':      loc_name,
            'rValue':       'U',
            'tFlag':        '',
            'mndlName':     mandal_name,
            'vlgName':      village_name,  # name attr = vlgName, id = villName
            'RateType':     'U',           # name attr = RateType, id = rate2
            'search_by':    search_by,     # A=Apartment, L=Land
        }
        html = self._api_post('/UnitRateMV/unitRateMV', fields)
        if not html:
            return []
        if search_by == 'L':
            return self._parse_rate_html_land(html)
        return self._parse_rate_html(html)

    def _parse_rate_html(self, html):
        """Extract unit rate table rows from HTML response."""
        from html.parser import HTMLParser

    def _parse_rate_html(self, html):
        """Extract unit rate table rows from HTML response.

        Table has a 2-row header (rowspan):
          Row 0: S.No. | Ward-Block | Locality | Apartment value (Rs. per Sq.Ft) | Classification | Effective Date | ...
          Row 1: Ground Floor | First Floor | Other Floors
          Row 2+: data rows with 9 columns total
        Column indices in data rows:
          0=S.No, 1=Ward-Block, 2=Locality, 3=GF_sqft, 4=FF_sqft, 5=OF_sqft, 6=Class, 7=Date, 8=DoorNo
        """
        from html.parser import HTMLParser

        class TblParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.tables, self.cur, self.row, self.cell = [], [], [], []
                self.intd = False
            def handle_starttag(self, t, a):
                if t=='table': self.cur=[]
                elif t=='tr':  self.row=[]
                elif t in ('td','th'): self.intd=True; self.cell=[]
            def handle_endtag(self, t):
                if t in ('td','th'):
                    self.row.append(' '.join(self.cell).strip()); self.intd=False
                elif t=='tr' and self.row:
                    self.cur.append(self.row[:]); self.row=[]
                elif t=='table' and self.cur:
                    self.tables.append(self.cur[:]); self.cur=[]
            def handle_data(self, d):
                if self.intd: self.cell.append(d)

        def parse_rate(v):
            try:
                return float(v.replace(',','').replace('Rs.','').replace('₹','').strip())
            except Exception:
                return None

        p = TblParser(); p.feed(html)
        rows = []
        for tbl in p.tables:
            if len(tbl) < 3: continue
            # Check if this looks like the rate table (header mentions 'Apartment' or 'Sq.Ft')
            header_text = ' '.join(tbl[0]).lower()
            if not any(x in header_text for x in ('apartment', 'sq.ft', 'locality', 'ward')):
                continue
            # Data starts at row 2 (rows 0+1 are merged header)
            for row in tbl[2:]:
                if not any(c.strip() for c in row): continue
                if len(row) < 6: continue
                locality = row[2].strip() if len(row) > 2 else ''
                if not locality or locality == 'S.No.' or locality == 'Locality':
                    continue
                gf  = parse_rate(row[3]) if len(row) > 3 else None
                ff  = parse_rate(row[4]) if len(row) > 4 else None
                of  = parse_rate(row[5]) if len(row) > 5 else None
                # Clean ward_block: collapse whitespace
                ward = ' '.join(row[1].split()) if len(row) > 1 else ''
                eff_date = row[7].strip() if len(row) > 7 else ''
                # Prefer first-floor for apartments; fallback to ground floor
                rate_sqft = ff or gf or of
                if rate_sqft and rate_sqft > 100:
                    rows.append({
                        'locality':        locality,
                        'ward_block':      ward,
                        'rate_gf_sqft':    gf,
                        'rate_ff_sqft':    ff,
                        'rate_of_sqft':    of,
                        'unit_rate_sqft':  rate_sqft,
                        'unit_rate_sqmt':  round(rate_sqft * 10.764, 2),
                        'effective_date':  eff_date,
                    })
        return rows

    def _parse_rate_html_land(self, html):
        """Extract land value rate table rows from HTML response.

        Table header: S.No. | Ward-Block | Locality | Land Value (Rs. per Sq.Mt.) | Effective Date
        Column indices in data rows:
          0=S.No, 1=Ward-Block, 2=Locality, 3=land_rate_sqmt, 4=Classification, 5=Date
        """
        from html.parser import HTMLParser

        class TblParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.tables, self.cur, self.row, self.cell = [], [], [], []
                self.intd = False
            def handle_starttag(self, t, a):
                if t == 'table': self.cur = []
                elif t == 'tr':  self.row = []
                elif t in ('td', 'th'): self.intd = True; self.cell = []
            def handle_endtag(self, t):
                if t in ('td', 'th'):
                    self.row.append(' '.join(self.cell).strip()); self.intd = False
                elif t == 'tr' and self.row:
                    self.cur.append(self.row[:]); self.row = []
                elif t == 'table' and self.cur:
                    self.tables.append(self.cur[:]); self.cur = []
            def handle_data(self, d):
                if self.intd: self.cell.append(d)

        def parse_rate(v):
            try:
                return float(v.replace(',', '').replace('Rs.', '').replace('₹', '').strip())
            except Exception:
                return None

        p = TblParser(); p.feed(html)
        rows = []
        for tbl in p.tables:
            if len(tbl) < 2: continue
            header_text = ' '.join(tbl[0]).lower()
            if not any(x in header_text for x in ('land', 'sq.mt', 'locality', 'ward')):
                continue
            # Data starts at row 1 or 2 depending on header rows
            data_start = 2 if len(tbl) > 2 and any(x in ' '.join(tbl[1]).lower() for x in ('floor', 'ground', 'first')) else 1
            for row in tbl[data_start:]:
                if not any(c.strip() for c in row): continue
                if len(row) < 3: continue
                locality = row[2].strip() if len(row) > 2 else ''
                if not locality or locality in ('S.No.', 'Locality', 'Ward-Block'): continue
                # Land rate: col[3] is sqmt rate; fallback to col[3] as sqft
                rate_sqmt = parse_rate(row[3]) if len(row) > 3 else None
                if not rate_sqmt:
                    # try any numeric col
                    for c in row[3:]:
                        v = parse_rate(c)
                        if v and 100 < v < 5_000_000:
                            rate_sqmt = v
                            break
                if not rate_sqmt or rate_sqmt <= 100:
                    continue
                land_rate_sqft = round(rate_sqmt / 10.764, 2)
                ward = ' '.join(row[1].split()) if len(row) > 1 else ''
                eff_date = row[5].strip() if len(row) > 5 else (row[4].strip() if len(row) > 4 else '')
                rows.append({
                    'locality':         locality,
                    'ward_block':       ward,
                    'land_rate_sqmt':   rate_sqmt,
                    'land_rate_sqft':   land_rate_sqft,
                    'unit_rate_sqft':   land_rate_sqft,
                    'unit_rate_sqmt':   rate_sqmt,
                    'effective_date':   eff_date,
                })
        return rows

    # ── Main run ──────────────────────────────────────────────────────────────

    def run(self):
        log.info("=== API UNIT RATE SCRAPE START ===")
        if not self._init_session():
            return []

        # Build targets from pincode preferences (or use full TARGET_MANDALS)
        if self.pincodes is not None:
            targets = build_targets_from_scraped_data(self.pincodes)
        else:
            targets = build_targets_from_scraped_data()  # reads scrape_preferences.json

        if self.only_district:
            targets = {k: v for k, v in targets.items()
                       if self.only_district.lower() in k.lower()}

        all_results = []

        for search_by in ['A', 'L']:  # A=Apartment, L=Land
            search_type = 'apartment' if search_by == 'A' else 'land'
            log.info(f"\n{'='*60}\n=== Search type: {search_type.upper()} ===\n{'='*60}")
            self.progress_cb(f"Scraping {search_type} rates…")

            for dist_name, target_mandals in targets.items():
                if self._stop_requested:
                    break
                dist_code = self.DISTRICT_CODES.get(dist_name)
                if not dist_code:
                    log.warning(f"No district code for {dist_name}"); continue

                log.info(f"\n=== District: {dist_name} ({dist_code}) [{search_type}] ===")

                # Get mandal list
                api_mandals = self._get_mandals(dist_code)
                mandal_map  = {name.upper(): code for code, name in api_mandals}
                log.info(f"  {len(api_mandals)} mandals from API")

                # HYDERABAD uses locality search (not mandal->village flow)
                if dist_code in ('16_1', '16_2'):
                    for target_locality in target_mandals:
                        search = target_locality.upper()[:6]
                        locs = self._get_localities_hyd(search_text=search)
                        if not locs:
                            log.warning(f"  '{target_locality}' - no localities found")
                            continue
                        log.info(f"  '{target_locality}' -> {len(locs)} matches")
                        for dcode, lcode, lname in locs[:20]:
                            rows = self._get_rates_hyd(dcode, lcode, lname, search_by=search_by)
                            for r in rows:
                                rec = {
                                    "district": dist_name, "mandal": target_locality,
                                    "village": "", "locality": r['locality'],
                                    "ward_block": r.get('ward_block', ''),
                                    "unit_rate_sqft": r['unit_rate_sqft'],
                                    "unit_rate_sqmt": r['unit_rate_sqmt'],
                                    "search_type": search_type,
                                    "effective_date": r.get('effective_date', ''),
                                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                                }
                                if search_type == 'apartment':
                                    rec.update({
                                        "rate_gf_sqft": r.get('rate_gf_sqft'),
                                        "rate_ff_sqft": r.get('rate_ff_sqft'),
                                        "rate_of_sqft": r.get('rate_of_sqft'),
                                    })
                                else:
                                    rec["land_rate_sqmt"] = r.get('land_rate_sqmt')
                                all_results.append(rec)
                            if rows: log.info(f"    [{lname}] {len(rows)} {search_type} rates")
                            time.sleep(0.3)
                    continue  # skip the mandal-village loop below

                for target_mandal in target_mandals:
                    # Fuzzy match mandal name
                    mandal_code, mandal_name = '', ''
                    tu = target_mandal.upper()
                    for name in mandal_map:
                        if tu in name or name in tu or \
                           name.replace(' ','').startswith(tu.replace(' ','')[:6]):
                            mandal_code = mandal_map[name]
                            mandal_name = name
                            break
                    if not mandal_code:
                        log.warning(f"  '{target_mandal}' not matched in API mandals")
                        continue
                    log.info(f"  {target_mandal} -> {mandal_name} ({mandal_code}) [{search_type}]")

                    # Get villages
                    villages = self._get_villages(dist_code, mandal_code)
                    log.info(f"    {len(villages)} villages")

                    if not villages:
                        rows = self._get_rates(dist_code, mandal_code, '',
                                               mandal_name=mandal_name, search_by=search_by)
                        for r in rows:
                            rec = {
                                "district": dist_name, "mandal": target_mandal,
                                "village": "", "locality": r['locality'],
                                "ward_block": r.get('ward_block', ''),
                                "unit_rate_sqft": r['unit_rate_sqft'],
                                "unit_rate_sqmt": r['unit_rate_sqmt'],
                                "search_type": search_type,
                                "effective_date": r.get('effective_date', ''),
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                            }
                            if search_type == 'apartment':
                                rec.update({
                                    "rate_gf_sqft": r.get('rate_gf_sqft'),
                                    "rate_ff_sqft": r.get('rate_ff_sqft'),
                                    "rate_of_sqft": r.get('rate_of_sqft'),
                                })
                            else:
                                rec["land_rate_sqmt"] = r.get('land_rate_sqmt')
                            all_results.append(rec)
                        if rows: log.info(f"    {len(rows)} {search_type} records (no-village)")
                        continue

                    for vcode, vname in villages[:25]:  # cap per mandal
                        rows = self._get_rates(dist_code, mandal_code, vcode,
                                               mandal_name=mandal_name, village_name=vname,
                                               search_by=search_by)
                        for r in rows:
                            rec = {
                                "district": dist_name, "mandal": target_mandal,
                                "village": vname, "locality": r['locality'],
                                "ward_block": r.get('ward_block', ''),
                                "unit_rate_sqft": r['unit_rate_sqft'],
                                "unit_rate_sqmt": r['unit_rate_sqmt'],
                                "search_type": search_type,
                                "effective_date": r.get('effective_date', ''),
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                            }
                            if search_type == 'apartment':
                                rec.update({
                                    "rate_gf_sqft": r.get('rate_gf_sqft'),
                                    "rate_ff_sqft": r.get('rate_ff_sqft'),
                                    "rate_of_sqft": r.get('rate_of_sqft'),
                                })
                            else:
                                rec["land_rate_sqmt"] = r.get('land_rate_sqmt')
                            all_results.append(rec)
                        if rows: log.info(f"    [{vname}] {len(rows)} {search_type} rates")
                        time.sleep(0.3)

        log.info(f"\nTotal records: {len(all_results)}")
        self.progress_cb(f"Done — {len(all_results)} rate records scraped")
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        out = {"scraped_at": datetime.now(timezone.utc).isoformat(),
               "total": len(all_results), "records": all_results}
        OUTPUT_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
        log.info(f"Saved to {OUTPUT_FILE}")

        # Best-effort write to PostgreSQL (truncate + re-insert)
        if all_results:
            _db_conn = None
            _run_id = None
            try:
                from db_utils import get_connection, start_scrape_run, finish_scrape_run, fail_scrape_run
                _db_conn = get_connection()
                _run_id = start_scrape_run(_db_conn, "rr")
                saved = _save_unit_rates_to_db(_db_conn, all_results)
                finish_scrape_run(_db_conn, _run_id, total=len(all_results), completed=saved)
                log.info(f"[DB] Saved {saved} unit rate records to PostgreSQL.")
            except Exception as _db_err:
                log.warning(f"[DB] Could not write unit rates to DB: {_db_err}")
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

        return all_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IGRS Ready Reckoner unit-rate scraper")
    parser.add_argument("--diagnose",   action="store_true",
                        help="Open form in visible Chrome for inspection")
    parser.add_argument("--district",   default=None,
                        help="Limit to one district (e.g. HYDERABAD)")
    parser.add_argument("--test",       action="store_true",
                        help="Quick test: only first mandal per district")
    parser.add_argument("--selenium",   action="store_true",
                        help="Use Selenium form scraper instead of API approach")
    parser.add_argument("--headless",   action="store_true", default=True)
    parser.add_argument("--no-headless", dest="headless", action="store_false")
    parser.add_argument("--pincodes",   nargs="+", default=None,
                        help="Filter mandals by specific pincodes (space-separated). "
                             "Defaults to reading scrape_preferences.json")
    parser.add_argument("--all-mandals", action="store_true",
                        help="Ignore pincode preferences and scrape all TARGET_MANDALS")
    args = parser.parse_args()

    # Determine pincode filter
    if args.all_mandals:
        pincodes_arg = None   # will use full TARGET_MANDALS via build_targets fallback
        # Patch build_targets to always return TARGET_MANDALS when called with no prefs
        _orig_prefs = load_pincode_preferences
        load_pincode_preferences = lambda: []  # type: ignore
    elif args.pincodes:
        pincodes_arg = args.pincodes
    else:
        pincodes_arg = None   # reads scrape_preferences.json automatically

    if args.diagnose:
        diagnose()
    elif args.selenium:
        targets = build_targets_from_scraped_data(pincodes_arg)
        if args.test:
            targets = {k: v[:1] for k, v in targets.items()}
        for k in list(TARGET_MANDALS):
            TARGET_MANDALS[k] = targets.get(k, [])
        scraper = RRScraper(headless=args.headless, only_district=args.district)
        scraper.run()
    else:
        if args.test:
            # patch: limit to 1 mandal per district after targets are built
            import functools
            _orig_build = build_targets_from_scraped_data
            def _test_build(fp=None):
                t = _orig_build(fp)
                return {k: v[:1] for k, v in t.items()}
            import rr_scraper as _self_mod
            _self_mod.build_targets_from_scraped_data = _test_build
        scraper = RRApiScraper(only_district=args.district, pincodes=pincodes_arg)
        scraper.run()
    print(json.dumps({"output": str(OUTPUT_FILE), "records": OUTPUT_FILE.exists()}, indent=2))




