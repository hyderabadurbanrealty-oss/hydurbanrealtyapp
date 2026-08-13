"""
download_project_docs.py
========================
Downloads RERA documents (Sanctioned Building Plan, Approval Layout Plan, etc.)
for already-scraped projects and converts them to PNG images for display in the app.

Usage:
  python download_project_docs.py                  # process all projects
  python download_project_docs.py "BHUVI BLOCK B"  # process one project

Requirements:
  pip install pymupdf selenium webdriver-manager beautifulsoup4 requests

How it works:
  1. Reads the saved page_source.html for each project
  2. Extracts UPID (Upload ID) for target documents
  3. POSTs to RERA /Preview/GetUserDocumentIframe to get base64 PDF
  4. Converts each PDF page to a PNG image using pymupdf
  5. Saves images in scraped_projects/<Project>/floor-plans/
"""

import os
import re
import sys
import json
import time
from pathlib import Path
from bs4 import BeautifulSoup

from captcha_solver import CaptchaSolver

SCRAPED_PROJECTS_PATH = Path(__file__).parent / "scraped_projects"
RERA_BASE = "https://rerait.telangana.gov.in"

# Documents we want to download and their output label
TARGET_DOCS = {
    "Copy of Sanctioned Building Plan": "building-plan",
    "Copy of Approval Layout Plan":     "layout-plan",
    "Copy of Approval Layout plan":     "layout-plan",  # case variant
    "Commencement Certificate/ Building permit": "commencement-cert",
    "Commencement Certificates for each building in each phase": "commencement-cert",
}

# Resolution for rendered PNG images (higher = better quality, larger files)
DPI = 150


def get_project_id_from_page(soup):
    """Extract the division/project ID from the hidden ProjectID input."""
    tag = soup.find("input", id="ProjectID")
    if tag:
        val = tag.get("value", "")
        parts = val.split("/")
        return parts[1] if len(parts) > 1 else "1"
    return "1"


def get_action_from_page(soup):
    """Determine if it's a SEARCH page or preview page."""
    tag = soup.find("input", id="Action")
    return tag.get("value", "PREVIEW") if tag else "PREVIEW"


def extract_doc_upids(soup):
    """
    Parse all document rows from page_source.html and return a dict:
    { 'Copy of Sanctioned Building Plan': [upid1, upid2, ...], ... }
    Registers each UPID under BOTH the span's title attribute AND its text
    content, because RERA uses them inconsistently across doc types.
    Only UPID != -1 are included.
    """
    docs = {}
    for tr in soup.find_all("tr"):
        name_span = tr.find("span", title=True)
        upid_inp = tr.find("input", id=re.compile(r"^UPID_\d+$"))
        if not (name_span and upid_inp):
            continue
        upid = upid_inp.get("value", "-1").strip()
        if not upid or upid == "-1":
            continue
        # Both the title attribute and the span text can hold the doc name
        candidates = {
            name_span.get("title", "").strip(),
            name_span.get_text(separator=" ", strip=True),
        }
        for doc_name in candidates:
            if doc_name:
                docs.setdefault(doc_name, [])
                if upid not in docs[doc_name]:
                    docs[doc_name].append(upid)
    return docs


def fetch_doc_bytes(session, upid, division="1", action="PREVIEW"):
    """
    Fetch the raw PDF bytes for a given UPID.
    Step 1: POST to GetUserDocumentIframe → HTML with <iframe src="...">
    Step 2: GET that iframe src → raw PDF bytes
    Returns bytes or None.
    """
    iframe_url = (
        f"{RERA_BASE}/PrintPreview/GetUserDocumentIframe"
        if action == "SEARCH"
        else f"{RERA_BASE}/Preview/GetUserDocumentIframe"
    )
    payload = json.dumps({"ID": int(upid), "Division": int(division), "RoleID": 1, "CurrentUserID": 0})
    try:
        resp = session.post(
            iframe_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        resp.raise_for_status()

        # Parse the <iframe src="..."> from the HTML response
        m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
        if not m:
            print(f"      [!] No iframe src found for UPID {upid}. Response: {resp.text[:200]}")
            return None

        src = m.group(1)
        if src.startswith("/"):
            src = RERA_BASE + src

        # Step 2: fetch the actual PDF
        pdf_resp = session.get(src, timeout=60)
        pdf_resp.raise_for_status()

        content_type = pdf_resp.headers.get("Content-Type", "")
        if "pdf" in content_type or pdf_resp.content[:4] == b"%PDF":
            return pdf_resp.content

        # Some responses wrap it as base64
        text = pdf_resp.text.strip()
        if text.startswith("JVBERi"):
            import base64 as _b64
            return _b64.b64decode(text)

        print(f"      [!] Unexpected PDF response for UPID {upid}: CT={content_type} body={text[:200]}")
        return None

    except Exception as e:
        print(f"      [!] Error fetching UPID {upid}: {e}")
        return None


def pdf_to_images(pdf_bytes, output_dir, label, upid):
    """
    Render each page of a PDF to PNG and save in output_dir.
    Returns list of saved image filenames.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    try:
        import fitz  # pymupdf — imported lazily so missing package doesn't break app startup
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc[page_num]
            mat = fitz.Matrix(DPI / 72, DPI / 72)
            pix = page.get_pixmap(matrix=mat)
            filename = f"{label}-{upid}-p{page_num + 1}.png"
            out_path = output_dir / filename
            pix.save(str(out_path))
            saved.append(filename)
            print(f"      Saved page {page_num + 1}: {filename}")
        doc.close()
    except Exception as e:
        print(f"      [!] PDF rendering error: {e}")

    return saved


def process_project(project_dir, session):
    """Process a single project directory: download & convert target docs."""
    project_name = project_dir.name
    page_source = project_dir / "page_source.html"
    if not page_source.exists():
        print(f"  [skip] No page_source.html: {project_name}")
        return

    print(f"\n[project] {project_name}")
    with open(page_source, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    division = get_project_id_from_page(soup)
    action = get_action_from_page(soup)
    all_upids = extract_doc_upids(soup)

    output_dir = project_dir / "floor-plans"
    manifest_path = project_dir / "floor-plans" / "manifest.json"

    # Load existing manifest to skip already-downloaded docs
    manifest = {}
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

    updated = False
    for doc_name, label in TARGET_DOCS.items():
        upids = all_upids.get(doc_name, [])
        if not upids:
            continue

        for upid in upids:
            key = f"{label}-{upid}"
            if key in manifest:
                print(f"  [skip] Already downloaded: {doc_name} UPID={upid}")
                continue

            print(f"  [fetch] {doc_name} (UPID={upid}, label={label})")
            pdf_bytes = fetch_doc_bytes(session, upid, division, action)
            if not pdf_bytes:
                continue

            pages = pdf_to_images(pdf_bytes, output_dir, label, upid)
            if pages:
                manifest[key] = {
                    "doc_name": doc_name,
                    "label": label,
                    "upid": upid,
                    "pages": pages,
                }
                updated = True
            time.sleep(1)  # polite delay between requests

    if updated:
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"  [ok] Manifest updated: {len(manifest)} entries")
    else:
        print(f"  [ok] Nothing new to download")


def main():
    target_project = sys.argv[1] if len(sys.argv) > 1 else None

    # Initialize an authenticated RERA session
    print("[init] Starting RERA session...")
    solver = CaptchaSolver()
    if not solver.initialize_session():
        print("[!] Failed to initialize RERA session")
        sys.exit(1)
    session = solver.session
    print("[ok] Session ready\n")

    if target_project:
        project_dir = SCRAPED_PROJECTS_PATH / target_project
        if not project_dir.is_dir():
            print(f"[!] Project not found: {project_dir}")
            sys.exit(1)
        process_project(project_dir, session)
    else:
        dirs = sorted([d for d in SCRAPED_PROJECTS_PATH.iterdir() if d.is_dir()])
        print(f"[info] Processing {len(dirs)} projects...\n")
        for project_dir in dirs:
            process_project(project_dir, session)

    print("\n[done]")


if __name__ == "__main__":
    main()
