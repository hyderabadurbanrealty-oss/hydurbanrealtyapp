
import requests
import sys
import os
import csv
import json
import re
import time
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs


# ── PostgreSQL helpers ─────────────────────────────────────────────────────────

def save_project_to_db(conn, project_id: str, data: dict) -> None:
    """Upsert a scraped RERA project into the projects table.

    Uses ON CONFLICT (id) DO UPDATE so running the scraper twice for the same
    project produces exactly one row (idempotent).

    Args:
        conn: An open psycopg2 connection.
        project_id: The sanitized project folder name used as the primary key.
        data: The extracted project data dict (raw_data payload).
    """
    def _safe_int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO projects (
                id, project_name, project_status, project_type,
                district, mandal, locality, pin_code, village,
                total_flats, total_booked, raw_data, scraped_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
            ON CONFLICT (id) DO UPDATE SET
                raw_data   = EXCLUDED.raw_data,
                updated_at = NOW()
            """,
            (
                project_id,
                data.get("Project Name"),
                data.get("Project Status"),
                data.get("Project Type"),
                data.get("District"),
                data.get("Mandal"),
                data.get("Locality"),
                data.get("Pin Code"),
                data.get("Village/City/Town"),
                _safe_int(data.get("totalFlats", 0)),
                _safe_int(data.get("totalBookedFlats", 0)),
                json.dumps(data),
            ),
        )
    conn.commit()

# Import for Selenium and Browser automation
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# Import the existing solver
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from captcha_solver import CaptchaSolver
from db_utils import get_connection

def _extract_flat(data: dict, key: str) -> str:
    """Search for *key* in *data*, including one level of nested dicts.

    Useful for fields like 'District' that may live inside a section dict
    (e.g. data['Address Details']['District']) rather than at the top level.
    Returns the string value if found, otherwise an empty string.
    """
    # Direct top-level hit
    if key in data:
        val = data[key]
        if isinstance(val, (str, int, float)):
            return str(val)

    # Search one level deep inside nested dicts
    for v in data.values():
        if isinstance(v, dict) and key in v:
            inner = v[key]
            if isinstance(inner, (str, int, float)):
                return str(inner)

    return ''


def save_project_to_db(conn, project_id: str, data: dict) -> None:
    """Upsert a scraped project row into the ``projects`` table.

    Uses ``INSERT … ON CONFLICT (id) DO UPDATE`` so that re-running the
    scraper for the same project is fully idempotent.  All writes use
    parameterized queries via psycopg2 to prevent SQL injection.

    Args:
        conn: An open psycopg2 connection (caller owns lifecycle).
        project_id: The sanitized project name used as the primary key.
        data: The raw dict returned by ``scrape_detail_page()``.
    """
    # ── Structured field extraction ──────────────────────────────────────
    project_name       = data.get('Project Name', '')
    project_status     = _extract_flat(data, 'Project Status')
    project_type       = _extract_flat(data, 'Project Type')
    district           = _extract_flat(data, 'District')
    mandal             = _extract_flat(data, 'Mandal')
    locality           = _extract_flat(data, 'Locality')
    pin_code           = _extract_flat(data, 'Pin Code')
    village            = _extract_flat(data, 'Village/City/Town')
    promoter_name      = _extract_flat(data, 'Name')           # org name sits under 'Name' not 'Promoter Name'
    org_type           = _extract_flat(data, 'Organization Type')
    bank_name          = _extract_flat(data, 'Bank Name')
    branch_name        = _extract_flat(data, 'Branch Name')
    plan_approval_number = _extract_flat(data, 'Plan Approval Number')
    survey_number      = _extract_flat(data, 'Survey Number')

    # Integer fields – default to 0 if missing or non-numeric
    def _int(val, default=0):
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    total_flats   = _int(data.get('totalFlats') or _extract_flat(data, 'Total Building Units (as per approved plan)'))
    total_booked  = _int(data.get('totalBookedFlats', 0))

    # Numeric field
    saleable_area_raw = _extract_flat(data, 'Saleable Area (Sq.Mt.)')
    try:
        saleable_area_sqmt = float(saleable_area_raw) if saleable_area_raw else None
    except ValueError:
        saleable_area_sqmt = None

    # Boolean fields
    is_msb         = data.get('Is the project an MSB or a High-Rise?', '') == 'Yes'
    has_litigation = data.get('Litigations related to the project ?', '').lower() == 'yes'

    sql = """
        INSERT INTO projects (
            id, project_name, project_status, project_type,
            district, mandal, locality, pin_code, village,
            promoter_name, org_type, bank_name, branch_name,
            plan_approval_number, survey_number,
            is_msb, has_litigation,
            total_flats, total_booked, saleable_area_sqmt,
            raw_data, scraped_at
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s,
            %s, %s, %s,
            %s, NOW()
        )
        ON CONFLICT (id) DO UPDATE SET
            raw_data             = EXCLUDED.raw_data,
            updated_at           = NOW(),
            project_name         = EXCLUDED.project_name,
            project_status       = EXCLUDED.project_status,
            district             = EXCLUDED.district,
            locality             = EXCLUDED.locality,
            pin_code             = EXCLUDED.pin_code
    """

    params = (
        project_id, project_name, project_status, project_type,
        district, mandal, locality, pin_code, village,
        promoter_name, org_type, bank_name, branch_name,
        plan_approval_number, survey_number,
        is_msb, has_litigation,
        total_flats, total_booked, saleable_area_sqmt,
        json.dumps(data),
    )

    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
        print(f"      [DB] Upserted project '{project_id}' into projects table.")
    except Exception as exc:
        print(f"      [DB] Error saving project '{project_id}' to database: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass


def setup_selenium():
    """Initialize a headless Chrome driver"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-setuid-sandbox")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--single-process")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        print(f"Error setting up Selenium: {e}")
        return None

def get_hidden_fields(soup):
    """Extract all hidden form fields from the page"""
    fields = {}
    for input_tag in soup.find_all("input", type="hidden"):
        name = input_tag.get("name")
        value = input_tag.get("value", "")
        if name:
            fields[name] = value
    return fields

def sanitize_filename(filename):
    """Remove invalid characters from filename"""
    # Remove invalid characters for Windows filenames
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

def create_project_folder(project_name, base_dir="scraped_projects"):
    """Create a folder for the project and return the path"""
    safe_name = sanitize_filename(project_name)
    project_path = Path(base_dir) / safe_name
    project_path.mkdir(parents=True, exist_ok=True)
    return project_path

def download_file(session, url, save_path):
    """Download a file from URL to save_path"""
    try:
        response = session.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"      Error downloading {url}: {e}")
        return False

def extract_detail_page_data(soup, detail_url):
    """
    Extract all data from the detail page and record available document names.
    Returns a dictionary with all the extracted data.
    """
    data = {}
    
    # helper to clean text
    def clean(text):
        return re.sub(r'\s+', ' ', text).strip() if text else ""

    # 1. Extract non-table Label/Value pairs (Address details, etc.)
    # Often these are in div.row > div > label
    for panel in soup.find_all('div', class_=re.compile(r'x_panel|container')):
        section_title = ""
        header = panel.find(['h2', 'h3', 'h4', 'h5', 'strong'])
        if header:
            section_title = clean(header.text)
        
        if not section_title: continue
        
        # Look for label-value patterns in this panel
        panel_data = {}
        labels = panel.find_all('label')
        for label in labels:
            key = clean(label.text).replace(':', '')
            if not key: continue
            
            # The value is usually the next sibling's text or the parent's next sibling
            parent_div = label.find_parent('div')
            value = ""
            if parent_div:
                next_div = parent_div.find_next_sibling('div')
                if next_div:
                    value = clean(next_div.text)
            
            if key and value and value != key:
                panel_data[key] = value
        
        if panel_data:
            if section_title in data:
                if isinstance(data[section_title], dict):
                    data[section_title].update(panel_data)
                else:
                    data[f"{section_title}_Info"] = panel_data
            else:
                data[section_title] = panel_data

    # 2. Identify Sections and Extract Tables
    all_tables = soup.find_all('table')
    for idx, table in enumerate(all_tables):
        section_title = ""
        prev_h = table.find_previous(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'label', 'b', 'strong'])
        if prev_h:
            section_title = clean(prev_h.text).replace(':', '')
        
        if not section_title:
            section_title = f"Section_{idx}"
            
        rows = table.find_all('tr')
        if not rows: continue
        
        first_row_cols = rows[0].find_all(['td', 'th'])
        if len(first_row_cols) == 2:
            kv_dict = {}
            for row in rows:
                cols = row.find_all(['td', 'th'])
                if len(cols) == 2:
                    k = clean(cols[0].text).replace(':', '')
                    v = clean(cols[1].text)
                    if k: kv_dict[k] = v
            
            if kv_dict:
                if section_title in data:
                    if isinstance(data[section_title], dict):
                        data[section_title].update(kv_dict)
                    else:
                        data[f"{section_title}_{idx}"] = kv_dict
                else:
                    data[section_title] = kv_dict
                    if 'ProjectID' in kv_dict:
                        data['ProjectID'] = kv_dict['ProjectID']
        else:
            headers = [clean(th.text) for th in rows[0].find_all(['td', 'th'])]
            headers = [h if h else f"Col_{i}" for i, h in enumerate(headers)]
            
            grid_list = []
            for row in rows[1:]:
                cols = row.find_all(['td', 'th'])
                if len(cols) == len(headers):
                    row_dict = {headers[i]: clean(col.text) for i, col in enumerate(cols)}
                    grid_list.append(row_dict)
            
            if grid_list:
                data[section_title] = grid_list

    # 2b. Special case: Building Details section has up to 3 distinct tables:
    #   (i)  Tower summary  — columns include "Number of Basement", "Number of Podium", "Total Parking Area"
    #   (ii) Floor/Apartment breakdown — columns include "Floor ID", "Saleable Area", "Apartment Type"
    #   (iii) Construction progress — columns are "Tasks / Activity", "Percentage of Work"  ← already caught above
    # We scan all tables explicitly for the first two so they are never confused.

    # (i) Tower summary table
    if 'Building Tower Details' not in data:
        for table in soup.find_all('table'):
            first_row = table.find('tr')
            if not first_row:
                continue
            hdrs = [clean(cell.get_text()) for cell in first_row.find_all(['td', 'th'])]
            hdrs_lower = [h.lower() for h in hdrs]
            tower_signals = ('number of basement', 'number of podium', 'total parking area', 'number of slab', 'number of stilt')
            if any(any(sig in h for h in hdrs_lower) for sig in tower_signals):
                rows = table.find_all('tr')
                parsed = []
                for row in rows[1:]:
                    cols = row.find_all(['td', 'th'])
                    if not cols:
                        continue
                    # Pad or trim to match header length
                    row_dict = {}
                    for i, h in enumerate(hdrs):
                        row_dict[h] = clean(cols[i].get_text()) if i < len(cols) else ''
                    parsed.append(row_dict)
                # Filter out junk rows: embedded floor breakdown text blobs and non-tower rows
                valid = []
                for row_dict in parsed:
                    # Skip blob rows (e.g. floor breakdown nested as one giant cell)
                    if any(len(v) > 200 for v in row_dict.values()):
                        continue
                    # Skip rows whose 'Name' column contains floor-breakdown signals
                    name_val = row_dict.get('Name', '').lower()
                    if any(sig in name_val for sig in ('floor id', 'saleable area', 'apartment type', 'mortgage area')):
                        continue
                    # Skip rows where 'Name' is 'True'/'False' (floor breakdown Mortgage Area values)
                    if row_dict.get('Name', '') in ('True', 'False'):
                        continue
                    # Skip pure header repetition rows (Sr.No. is not a digit)
                    sr = row_dict.get('Sr.No.', '').strip()
                    if sr and not sr.isdigit():
                        continue
                    valid.append(row_dict)
                if valid:
                    data['Building Tower Details'] = valid
                    break

    # (ii) Floor / Apartment breakdown table
    if 'Floor Breakdown' not in data:
        for table in soup.find_all('table'):
            first_row = table.find('tr')
            if not first_row:
                continue
            hdrs = [clean(cell.get_text()) for cell in first_row.find_all(['td', 'th'])]
            hdrs_lower = [h.lower() for h in hdrs]
            floor_signals = ('floor id', 'saleable area', 'apartment type', 'number of apartment', 'number of booked')
            if any(any(sig in h for h in hdrs_lower) for sig in floor_signals):
                rows = table.find_all('tr')
                parsed = []
                for row in rows[1:]:
                    cols = row.find_all(['td', 'th'])
                    if not cols:
                        continue
                    row_dict = {hdrs[i]: clean(cols[i].get_text()) for i in range(min(len(hdrs), len(cols)))}
                    parsed.append(row_dict)
                if parsed:
                    data['Floor Breakdown'] = parsed
                    break

    # 3. Record available document names (no download — names are enough for compliance display)
    doc_groups = {}
    for input_tag in soup.find_all('input', {'name': re.compile(r'^Doc\.')}):
        name = input_tag.get('name')
        id_attr = input_tag.get('id', '')
        match = re.search(r'_(\d+)$', id_attr)
        suffix = match.group(1) if match else "0"
        if suffix not in doc_groups:
            doc_groups[suffix] = {}
        prop_name = name.replace('Doc.', '')
        doc_groups[suffix][prop_name] = input_tag.get('value', '')

    available_docs = []
    seen_ids = set()

    # From grouped hidden inputs
    for suffix, props in doc_groups.items():
        doc_id = props.get('ID')
        if doc_id and doc_id != '-1' and doc_id not in seen_ids:
            doc_name = props.get('DocumentName', '').strip()
            if doc_name:
                available_docs.append(doc_name)
                seen_ids.add(doc_id)

    # From inline Doc_ID inputs next to View buttons
    for doc_id_tag in soup.find_all('input', {'id': 'Doc_ID'}):
        val = doc_id_tag.get('value')
        if val and val != '-1' and val not in seen_ids:
            parent_td = doc_id_tag.find_parent('td')
            if parent_td:
                prev_td = parent_td.find_previous_sibling('td')
                doc_name = prev_td.text.strip() if prev_td else ''
                if doc_name:
                    available_docs.append(doc_name)
                    seen_ids.add(val)

    data['availableDocuments'] = available_docs
    print(f"      Recorded {len(available_docs)} available document names (no download).")

    # 4. Final metadata
    data['_metadata'] = {
        'total_documents_found': len(available_docs),
        'extraction_timestamp': str(time.time())
    }

    return data

def scrape_detail_page(session, driver, detail_url, project_name):
    """
    Navigate to the detail page using Selenium, extract structured data,
    and record available document names in the JSON. No files are downloaded.
    Returns the extracted data dictionary.
    """
    print(f"\n   Processing: {project_name}")
    
    # Create project folder
    project_folder = create_project_folder(project_name)
    print(f"      Folder: {project_folder}")
    
    # Construct full detail page URL
    if not detail_url.startswith('http'):
        detail_url = f"https://rerait.telangana.gov.in{detail_url}"
    
    print(f"      URL: {detail_url[:80]}...")
    
    try:
        # 1. Transfer cookies from requests session to Selenium
        if driver.current_url == "data:," or "telangana.gov.in" not in driver.current_url:
             driver.get("https://rerait.telangana.gov.in/SearchList/Search")
             
        driver.delete_all_cookies()
        for cookie in session.cookies:
            driver.add_cookie({
                'name': cookie.name,
                'value': cookie.value,
                'domain': 'rerait.telangana.gov.in', # Explicitly set domain
                'path': cookie.path
            })
            
        # 2. Navigate to the detail page
        driver.get(detail_url)
        
        # 3. Wait for content
        time.sleep(5) # Give it time for AJAX

        # Optional: Save raw HTML for debugging (helps diagnose missing table extraction)
        try:
            with open(project_folder / "page_source.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
        except Exception:
            pass
            
        # 4. Extract data
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        extracted_data = extract_detail_page_data(soup, detail_url)
        extracted_data['Project Name'] = project_name
        
        # Save extraction results to disk
        with open(project_folder / "view_page_data.json", "w", encoding="utf-8") as f:
            json.dump(extracted_data, f, indent=2)

        # DB write is handled by main() after PIN filtering — do not write here.
        return extracted_data
        
    except Exception as e:
        print(f"      [!] Error processing detail page: {e}")
        return None

def main(project_name=None, pin_codes=None, district_id="24"):
    """
    Args:
        project_name: RERA project name search term. Empty = all projects.
        pin_codes:    Set of PIN codes to save (e.g. {"500081","500075"}).
                      None = save all PINs in the district.
        district_id:  RERA district dropdown value.
                      24 = Rangareddy, 25 = Hyderabad. Default: 24.
    """
    # None means not provided at all (interactive mode), "" means explicit "all"
    if project_name is None:
        project_name = input("[?] Enter Project Name to search (leave blank for all): ").strip()

    # % is rejected by server validation (special char) — use empty string for all projects
    if project_name == "%":
        project_name = ""

    if pin_codes:
        print(f"[i] PIN filter: will only save projects whose PIN is in {sorted(pin_codes)}")
    print(f"[i] District filter: {district_id} ({'Rangareddy' if district_id=='24' else 'Hyderabad' if district_id=='25' else district_id})")

    # Best-effort scrape run tracking
    _db_conn = None
    _run_id = None
    try:
        from db_utils import get_connection, start_scrape_run
        _db_conn = get_connection()
        _run_id = start_scrape_run(_db_conn, "rera")
    except Exception:
        pass

    # Try to open DB connection (graceful degradation if not configured)
    db_conn = None
    existing_ids = set()
    try:
        db_conn = get_connection()
        print("[DB] Connected to PostgreSQL.")
        # Pre-load existing project IDs so we can skip already-scraped ones
        with db_conn.cursor() as _cur:
            _cur.execute("SELECT id FROM projects")
            existing_ids = {row[0] for row in _cur.fetchall()}
        print(f"[DB] {len(existing_ids)} existing projects loaded — these will be skipped.")
    except Exception as db_err:
        print(f"[DB] Warning: Could not connect to DB — {db_err}. Writes will be skipped.")

    # Initialize the solver (which sets up the session and SSL context)
    solver = CaptchaSolver()
    
    # 1. Initialize Session & Get extraction token
    print("[1/6] Initializing session and fetching page...")
    if not solver.initialize_session():
        print("Failed to initialize session.")
        return

    # We need to parse the initial page to get the RequestVerificationToken
    try:
        resp = solver.session.get("https://rerait.telangana.gov.in/SearchList/Search")
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Extract hidden fields (Tokens, etc)
        payload = get_hidden_fields(soup)
        print(f"      Extracted {len(payload)} hidden fields.")
        
    except Exception as e:
        print(f"Error fetching initial page: {e}")
        return

    # 2–5. Captcha retry loop (up to 5 attempts — RERA silently returns
    #       "No Records Found" when the captcha is wrong)
    MAX_CAPTCHA_ATTEMPTS = 10
    extracted_data = []
    search_succeeded = False

    for captcha_attempt in range(1, MAX_CAPTCHA_ATTEMPTS + 1):
        # 2. Download fresh captcha each attempt
        print(f"[2/6] Downloading Captcha (attempt {captcha_attempt}/{MAX_CAPTCHA_ATTEMPTS})...")
        captcha_filename = "captcha_fast.png"
        if not solver.download_captcha(captcha_filename):
            print("Failed to download captcha.")
            continue

        # 3. Solve Captcha
        print("[3/6] Solving Captcha...")
        captcha_text = solver.solve_captcha(captcha_filename)

        # Build candidates: try I↔J swaps first since the RERA italic font
        # makes J look identical to I — the swap is correct more often than not.
        candidates = []
        if captcha_text:
            print(f"      Auto-solved: {captcha_text}")
            alt_ij = captcha_text.replace('I', 'J') if 'I' in captcha_text else None
            alt_ji = captcha_text.replace('J', 'I') if 'J' in captcha_text else None
            # Try I→J first (most common confusion), then raw, then J→I
            if alt_ij and alt_ij != captcha_text:
                candidates.append(alt_ij)
                print(f"      I→J variant (trying first): {alt_ij}")
            candidates.append(captcha_text)
            if alt_ji and alt_ji != captcha_text and alt_ji not in candidates:
                candidates.append(alt_ji)
                print(f"      J→I variant: {alt_ji}")
        else:
            print("      Auto-solve failed.")

        # Manual entry fallback — show the captcha image path so user can read it
        print(f"      [Manual fallback] Captcha saved at: {captcha_filename}")
        print(f"      Press Enter to skip manual entry, or type the captcha text: ", end="", flush=True)
        try:
            import sys
            manual = ""
            # Only prompt if running interactively (not piped)
            if sys.stdin.isatty():
                manual = input().strip().upper()
            if manual and manual not in candidates:
                candidates.insert(0, manual)  # try manual first
                print(f"      Using manual entry: {manual}")
        except Exception:
            pass

        if not candidates:
            print("      No captcha candidates — retrying...")
            solver.initialize_session()
            try:
                resp2 = solver.session.get("https://rerait.telangana.gov.in/SearchList/Search")
                resp2.raise_for_status()
                soup2 = BeautifulSoup(resp2.text, 'html.parser')
                payload = get_hidden_fields(soup2)
            except Exception:
                pass
            continue

        # 5. Execute POST — try each candidate captcha in its own POST
        search_url = "https://rerait.telangana.gov.in/SearchList/Search"
        extracted_data = []
        search_found = False

        for candidate in candidates:
            print(f"[4/6] Searching '{project_name}' — captcha='{candidate}' (attempt {captcha_attempt})...")

            # Build payload: start from current hidden fields then overlay form values.
            # Division and State MUST be present — server rejects without them.
            post_payload = dict(payload)
            post_payload.update({
                "Type":                "Promoter",
                "Project":             project_name,
                "Promoter":            "",
                "AgentName":           "",
                "CertiNo":             "",
                "Division":            "",
                "District":            district_id,
                "Taluka":              "",
                "Village":             "",
                "State":               "",
                "CompletionDate_From": "",
                "CompletionDate_To":   "",
                "PType":               "",
                "PlotBearing":         "",
                "Captcha":             candidate,
                "Command":             "Search",
                "pageTraverse":        "1",
            })

            try:
                current_page = 1
                total_pages = 1

                while current_page <= total_pages:
                    if current_page > 1:
                        print(f"      Fetching page {current_page} of {total_pages}...")
                        post_payload['pageTraverse'] = str(current_page)
                        post_payload.pop('Command', None)

                    post_resp = solver.session.post(search_url, data=post_payload)
                    post_resp.raise_for_status()

                    result_soup = BeautifulSoup(post_resp.text, 'html.parser')

                    new_hidden = get_hidden_fields(result_soup)
                    if new_hidden:
                        post_payload.update(new_hidden)
                        payload.update(new_hidden)

                    if current_page == 1:
                        total_pages_input = result_soup.find('input', {'id': 'TotalPages'})
                        if total_pages_input:
                            try:
                                total_pages = int(total_pages_input.get('value', '1'))
                                print(f"      Total records spread across {total_pages} pages.")
                            except Exception:
                                total_pages = 1

                    grid_div = result_soup.find(id="gridview")
                    table = grid_div.find('table') if grid_div else result_soup.find('table')

                    if not table:
                        if current_page == 1:
                            # Check if tbody is genuinely empty (not just the always-present hidden label)
                            tbody = result_soup.find('tbody')
                            tbody_rows = tbody.find_all('tr') if tbody else []
                            if len(tbody_rows) == 0:
                                print(f"[-] Candidate '{candidate}': empty result set — trying next captcha...")
                                # Re-init session for a fresh captcha
                                solver.initialize_session()
                                try:
                                    resp3 = solver.session.get("https://rerait.telangana.gov.in/SearchList/Search")
                                    resp3.raise_for_status()
                                    soup3 = BeautifulSoup(resp3.text, 'html.parser')
                                    payload = get_hidden_fields(soup3)
                                except Exception:
                                    pass
                            else:
                                print("[-] No table found but tbody has rows — unexpected state.")
                        break

                    headers = []
                    thead = table.find('thead')
                    if thead:
                        headers = [th.text.strip() for th in thead.find_all('th')]

                    rows = table.find_all('tr')
                    if not headers and rows:
                        headers = [td.text.strip() for td in rows[0].find_all(['td', 'th'])]
                        rows = rows[1:]

                    page_records = 0
                    for row in rows:
                        cols = row.find_all('td')
                        if not cols:
                            continue

                        row_data = {}
                        for col_idx, col in enumerate(cols):
                            key = headers[col_idx] if col_idx < len(headers) else f"Column_{col_idx}"
                            row_data[key] = col.text.strip()

                            view_link = col.find('a', class_='btn-primary', string='View')
                            if view_link and view_link.get('href'):
                                row_data[f"{key}_ViewLink"] = view_link.get('href')

                        extracted_data.append(row_data)
                        page_records += 1

                    print(f"      Page {current_page}: Found {page_records} records.")
                    current_page += 1

                if extracted_data:
                    search_succeeded = True
                    search_found = True
                    break  # captcha was correct — stop trying other candidates

            except Exception as search_err:
                print(f"      Search error on attempt {captcha_attempt}: {search_err}")

        if search_found:
            break  # good captcha found — exit the outer retry loop

    if not search_succeeded and not extracted_data:
        if captcha_attempt >= MAX_CAPTCHA_ATTEMPTS:
            print(f"[-] Failed to get search results after {MAX_CAPTCHA_ATTEMPTS} captcha attempts.")
        return

    if not extracted_data:
        print("[-] No results found after all captcha attempts.")
        return

    print(f"[+] Successfully collected {len(extracted_data)} total results.")

    # Initialize Browser for high-fidelity detail page capture
    print("[5/6] Initializing browser for detail pages...")
    driver = setup_selenium()

    if not driver:
        print("[-] Fatal Error: Could not initialize Selenium WebDriver. Please check if Chrome is installed and updated.")
        print("    Saving collected search results before exiting...")
        with open("scraped_projects/all_projects_search_results.json", "w", encoding="utf-8") as f:
            json.dump(extracted_data, f, indent=2)
        return

    # 6. Process detail pages
    print("[6/6] Processing detail pages...")
    results = []

    for idx, result in enumerate(extracted_data, 1):
        proj_name = ""
        # Try to find project name in columns like "Project Name" or similar
        for k, v in result.items():
            if "Project" in k and "Name" in k:
                proj_name = v
                break
        if not proj_name:
            proj_name = result.get('Project', f'Unknown_Project_{idx}')

        # Skip projects already in DB (use sanitized name as ID, same as save_project_to_db)
        proj_id = sanitize_filename(proj_name)

        # Find the View link
        view_url = None
        for key, value in result.items():
            if 'ViewLink' in key:
                view_url = value
                break

        if view_url:
            try:
                data = scrape_detail_page(solver.session, driver, view_url, proj_name)
                if data:
                    # PIN filter — only save if project PIN is in the target set
                    if pin_codes:
                        scraped_pin = (
                            data.get('Pin Code') or
                            _extract_flat(data, 'Pin Code') or ''
                        ).strip()
                        if scraped_pin not in pin_codes:
                            print(f"      [~] Skip '{proj_name}' — PIN {scraped_pin!r} not in target set")
                            # Clean up folder for non-target projects to save disk
                            import shutil as _shutil
                            _folder = create_project_folder(proj_name)
                            if _folder.exists():
                                _shutil.rmtree(_folder)
                            continue
                    results.append(data)
                    existing_ids.add(proj_id)  # mark as done for this session
                    if db_conn:
                        try:
                            save_project_to_db(db_conn, sanitize_filename(proj_name), data)
                        except Exception as db_err:
                            print(f"      [DB] Error saving to DB: {db_err}")
            except Exception as e:
                print(f"      [!] Error processing {proj_name}: {e}")
        else:
            print(f"      [-] No view link found for {proj_name}")

        # Checkpoint save after every project
        with open("scraped_projects/all_projects_data.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"      [checkpoint] {idx}/{len(extracted_data)} done, {len(results)} saved so far")

    # ── All projects processed — cleanup ──────────────────────────────────
    if driver:
        driver.quit()

    print(f"\n[DONE] Processed {len(results)} projects. See 'scraped_projects' folder.")

    # Update scrape run as completed
    if _db_conn and _run_id:
        try:
            from db_utils import finish_scrape_run
            finish_scrape_run(_db_conn, _run_id, total=len(extracted_data), completed=len(results))
            _db_conn.close()
        except Exception:
            pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Scrape RERA project detail pages.")
    parser.add_argument("--project",   help="Project name search term (omit for all)", default=None)
    parser.add_argument("--district",  help="RERA district ID: 24=Rangareddy, 25=Hyderabad (default: 24)", default="24")
    parser.add_argument("--pin-codes", dest="pin_codes",
                        help="Comma-separated PIN codes to save, e.g. 500081,500075. Omit to save all.",
                        default=None)
    args = parser.parse_args()

    _pin_set = None
    if args.pin_codes:
        _pin_set = {p.strip() for p in args.pin_codes.split(",") if p.strip()}

    main(project_name=args.project, pin_codes=_pin_set, district_id=args.district)
    
