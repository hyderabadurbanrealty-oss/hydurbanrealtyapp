"""
Scrape RERA documents for a specific project and upload directly to Supabase.
Usage: python scrape_and_upload_project_docs.py "MARVEL HEIGHTS"
"""
import os
import re
import sys
import json
import time
import base64
import mimetypes
from pathlib import Path
from io import BytesIO
import requests
import psycopg2
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────
PREFS_FILE = Path(__file__).parent / "scrape_preferences.json"
with open(PREFS_FILE, "r") as f:
    prefs = json.load(f)

DB_URL = prefs.get("db_connection", os.environ.get("DATABASE_URL", ""))
SUPABASE_URL = prefs.get("supabase_url", "https://qjgwnbszmojzgwmafvuc.supabase.co").rstrip("/")
SERVICE_KEY = prefs.get("supabase_service_key", os.environ.get("SUPABASE_SERVICE_KEY", ""))
BUCKET = prefs.get("supabase_bucket", "property-media")

if not SERVICE_KEY:
    print("ERROR: Set supabase_service_key in scrape_preferences.json")
    exit(1)

STORAGE_HEADERS = {
    "Authorization": f"Bearer {SERVICE_KEY}",
    "apikey": SERVICE_KEY,
}

RERA_BASE = "https://rerait.telangana.gov.in"

# Documents to download
TARGET_DOCS = {
    "Copy of Sanctioned Building Plan": "Building Plan",
    "Copy of Approval Layout Plan": "Layout Plan",
    "Commencement Certificate/ Building permit": "Commencement Certificate",
    "Commencement Certificates for each building in each phase": "Commencement Certificate",
    "Copy of the legal title report": "Legal Title Report",
    "Declaration in FORM B": "Declaration FORM B",
    "Copy of Board Resolution for appointment of Authorized Signatory in case of other than individual": "Board Resolution",
}


def sanitize_filename(name: str) -> str:
    """Sanitize filename for storage."""
    return re.sub(r'[<>:"/\\|?*]', '_', name)


def extract_doc_upids(html_content: str) -> dict:
    """Extract UPID (upload IDs) from RERA HTML."""
    soup = BeautifulSoup(html_content, 'html.parser')
    docs = {}
    
    for tr in soup.find_all("tr"):
        name_span = tr.find("span", title=True)
        upid_inp = tr.find("input", id=re.compile(r"^UPID_\d+$"))
        
        if not (name_span and upid_inp):
            continue
            
        upid = upid_inp.get("value", "-1").strip()
        if not upid or upid == "-1":
            continue
            
        # Get document name from title or text
        doc_name = name_span.get("title", "").strip() or name_span.get_text(separator=" ", strip=True)
        
        if doc_name:
            docs.setdefault(doc_name, [])
            if upid not in docs[doc_name]:
                docs[doc_name].append(upid)
    
    return docs


def fetch_document_from_rera(session: requests.Session, upid: str, division: str = "1") -> bytes | None:
    """Fetch document PDF from RERA."""
    try:
        # Step 1: Get iframe URL
        url1 = f"{RERA_BASE}/Preview/GetUserDocumentIframe"
        data = {"UPID": upid, "ProjectID": f"0/{division}"}
        
        resp1 = session.post(url1, data=data, timeout=30, verify=False)
        if resp1.status_code != 200:
            return None
            
        # Extract iframe src
        soup = BeautifulSoup(resp1.text, 'html.parser')
        iframe = soup.find("iframe", id="iframeDocument")
        if not iframe or not iframe.get("src"):
            return None
            
        src = iframe["src"]
        if src.startswith("data:application/pdf;base64,"):
            # Direct base64 PDF
            b64_data = src.split(",", 1)[1]
            return base64.b64decode(b64_data)
        elif src.startswith("/Preview/"):
            # Relative URL - fetch it
            url2 = RERA_BASE + src
            resp2 = session.get(url2, timeout=30, verify=False)
            if resp2.status_code == 200:
                return resp2.content
                
        return None
    except Exception as e:
        print(f"  Error fetching UPID {upid}: {e}")
        return None


def upload_to_supabase(file_bytes: bytes, storage_path: str, mime_type: str) -> str | None:
    """Upload file to Supabase Storage."""
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}"
    
    try:
        resp = requests.post(
            url,
            headers={**STORAGE_HEADERS, "Content-Type": mime_type},
            data=file_bytes,
            timeout=60
        )
        
        if resp.status_code in (200, 201):
            return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"
        elif resp.status_code == 409:
            # Already exists
            return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"
        else:
            print(f"  Upload failed {resp.status_code}: {resp.text[:100]}")
            return None
    except Exception as e:
        print(f"  Upload error: {e}")
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python scrape_and_upload_project_docs.py 'PROJECT NAME'")
        print("Example: python scrape_and_upload_project_docs.py 'MARVEL HEIGHTS'")
        exit(1)
    
    project_name = sys.argv[1]
    print(f"Scraping documents for: {project_name}")
    
    # Connect to database
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # Get project ID
    cur.execute("SELECT id FROM projects WHERE project_name ILIKE %s", (project_name,))
    row = cur.fetchone()
    if not row:
        print(f"ERROR: Project '{project_name}' not found in database")
        cur.close()
        conn.close()
        exit(1)
    
    project_id = row[0]
    print(f"Found project ID: {project_id}")
    
    # Get RERA registration number from raw_data JSONB
    cur.execute("""
        SELECT 
            raw_data->>'Registration Number' as reg_num,
            raw_data->>'RERA Registration Number' as rera_num,
            id
        FROM projects 
        WHERE id = %s
    """, (project_id,))
    
    row = cur.fetchone()
    rera_no = row[0] or row[1] or row[2]  # Try Registration Number, RERA Registration Number, or use ID
    
    if not rera_no:
        print("ERROR: No RERA registration number found")
        cur.close()
        conn.close()
        exit(1)
    
    print(f"RERA Number: {rera_no}")
    
    # Create session
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    
    # Search for project on RERA
    print("Searching RERA website...")
    search_url = f"{RERA_BASE}/Search/Hosteldetails?id={rera_no}"
    
    try:
        resp = session.get(search_url, timeout=30, verify=False)
        if resp.status_code != 200:
            print(f"ERROR: Failed to load RERA page: {resp.status_code}")
            exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        exit(1)
    
    # Extract document UPIDs
    print("Extracting document references...")
    doc_upids = extract_doc_upids(resp.text)
    
    if not doc_upids:
        print("No documents found on RERA page")
        cur.close()
        conn.close()
        exit(0)
    
    print(f"Found {len(doc_upids)} document types")
    
    # Download and upload each document
    uploaded_count = 0
    failed_count = 0
    
    for doc_name, upids in doc_upids.items():
        # Check if this is a target document
        display_name = TARGET_DOCS.get(doc_name, doc_name)
        
        print(f"\n{display_name}:")
        
        for idx, upid in enumerate(upids, 1):
            print(f"  Downloading part {idx}/{len(upids)}...")
            
            # Fetch from RERA
            pdf_bytes = fetch_document_from_rera(session, upid)
            
            if not pdf_bytes:
                print(f"    ✗ Failed to download")
                failed_count += 1
                continue
            
            # Generate filename
            safe_name = sanitize_filename(display_name)
            if len(upids) > 1:
                filename = f"{safe_name}_P{idx}.pdf"
            else:
                filename = f"{safe_name}.pdf"
            
            # Upload to Supabase
            storage_path = f"{project_id}/documents/{filename}"
            public_url = upload_to_supabase(pdf_bytes, storage_path, "application/pdf")
            
            if not public_url:
                print(f"    ✗ Failed to upload")
                failed_count += 1
                continue
            
            # Insert into database
            file_size = len(pdf_bytes)
            title = f"{display_name}" + (f" P{idx}" if len(upids) > 1 else "")
            
            cur.execute("""
                INSERT INTO project_media 
                    (id, project_id, media_type, title, file_url, file_name, file_size, mime_type, sort_order)
                VALUES 
                    (gen_random_uuid(), %s, 'document', %s, %s, %s, %s, 'application/pdf', %s)
                ON CONFLICT DO NOTHING
            """, (project_id, title, public_url, filename, file_size, idx))
            
            conn.commit()
            
            print(f"    ✓ Uploaded ({file_size / 1024:.1f} KB)")
            uploaded_count += 1
            
            # Rate limiting
            time.sleep(1)
    
    cur.close()
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"COMPLETED:")
    print(f"  Uploaded: {uploaded_count}")
    print(f"  Failed: {failed_count}")
    print(f"\nDocuments are now available in the app!")


if __name__ == "__main__":
    main()
