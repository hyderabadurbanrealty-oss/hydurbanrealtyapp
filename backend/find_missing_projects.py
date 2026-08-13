"""
Compares all_projects_data.json against what's in the projects table
and exports any missing/failed projects to missing_projects.csv
"""
import csv
import json
import os
import re
import psycopg2
from pathlib import Path

BACKEND_DIR = Path(__file__).parent
ALL_DATA_FILE = BACKEND_DIR / "scraped_projects" / "all_projects_data.json"
SCRAPED_DIR   = BACKEND_DIR / "scraped_projects"
OUTPUT_CSV    = BACKEND_DIR / "missing_projects.csv"

DB_URL = "postgresql://postgres:yxOePamK9RLkgd99@db.qjgwnbszmojzgwmafvuc.supabase.co:5432/postgres"

def sanitize(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def _extract(data: dict, key: str):
    if key in data:
        v = data[key]
        if isinstance(v, (str, int, float)):
            return str(v)
    for v in data.values():
        if isinstance(v, dict) and key in v:
            inner = v[key]
            if isinstance(inner, (str, int, float)):
                return str(inner)
    return ""

# ── 1. Get all project IDs currently in DB ────────────────────────────────────
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("SELECT id, project_name, district, locality, project_status, pin_code, mandal, promoter_name FROM projects")
db_rows = {row[0]: row for row in cur.fetchall()}
print(f"Projects in DB: {len(db_rows)}")

# ── 2. Collect all known source project names from scraped folders ─────────────
scraped_ids = {}
for proj_dir in sorted(SCRAPED_DIR.iterdir()):
    if not proj_dir.is_dir():
        continue
    pid = sanitize(proj_dir.name)
    scraped_ids[pid] = proj_dir

print(f"Scraped folders: {len(scraped_ids)}")

# ── 3. Collect entries from all_projects_data.json ────────────────────────────
all_json_projects = []
if ALL_DATA_FILE.exists():
    raw = json.loads(ALL_DATA_FILE.read_text(encoding="utf-8"))
    # all_projects_data.json may be a list or a single dict
    if isinstance(raw, list):
        all_json_projects = raw
    elif isinstance(raw, dict):
        all_json_projects = [raw]
    print(f"Entries in all_projects_data.json: {len(all_json_projects)}")

# Build set of project names from all_projects_data.json
all_json_ids = {}
for entry in all_json_projects:
    proj_name = _extract(entry, "Project Name")
    if proj_name:
        pid = sanitize(proj_name)
        all_json_ids[pid] = {
            "project_name": proj_name,
            "district": _extract(entry, "District"),
            "mandal": _extract(entry, "Mandal"),
            "locality": _extract(entry, "Locality"),
            "pin_code": _extract(entry, "Pin Code"),
            "status": _extract(entry, "Project Status"),
            "promoter": _extract(entry, "Name"),
        }

# ── 4. Build missing list ─────────────────────────────────────────────────────
missing = []

# Case A: scraped folder exists but NOT in DB
for pid, proj_dir in scraped_ids.items():
    json_path = proj_dir / "view_page_data.json"
    if not json_path.exists():
        missing.append({
            "reason": "Scraped folder exists but no view_page_data.json",
            "project_id": pid,
            "project_name": proj_dir.name,
            "district": "", "mandal": "", "locality": "",
            "pin_code": "", "status": "", "promoter": "",
        })
    elif pid not in db_rows:
        # Read basic info from json
        try:
            d = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            d = {}
        missing.append({
            "reason": "Has view_page_data.json but NOT in DB",
            "project_id": pid,
            "project_name": _extract(d, "Project Name") or proj_dir.name,
            "district": _extract(d, "District"),
            "mandal": _extract(d, "Mandal"),
            "locality": _extract(d, "Locality"),
            "pin_code": _extract(d, "Pin Code"),
            "status": _extract(d, "Project Status"),
            "promoter": _extract(d, "Name"),
        })

# Case B: in all_projects_data.json but NOT in DB and NOT in scraped folders
for pid, info in all_json_ids.items():
    if pid not in db_rows and pid not in scraped_ids:
        missing.append({
            "reason": "In all_projects_data.json only — no scraped folder, not in DB",
            "project_id": pid,
            "project_name": info["project_name"],
            "district": info["district"],
            "mandal": info["mandal"],
            "locality": info["locality"],
            "pin_code": info["pin_code"],
            "status": info["status"],
            "promoter": info["promoter"],
        })

# ── 5. Write CSV ──────────────────────────────────────────────────────────────
fieldnames = ["reason","project_id","project_name","district","mandal","locality","pin_code","status","promoter"]

if missing:
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(missing)
    print(f"\n{len(missing)} missing project(s) written to: {OUTPUT_CSV}")
else:
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        f.write(",".join(fieldnames) + "\n")
        f.write("NO MISSING PROJECTS - All data successfully inserted in DB,,,,,,,,\n")
    print(f"\nAll projects are in the DB. Written to: {OUTPUT_CSV}")

# ── 6. Print DB contents ──────────────────────────────────────────────────────
print(f"\nProjects currently in DB ({len(db_rows)}):")
for pid, row in sorted(db_rows.items()):
    print(f"  {row[1]:45s} | {row[2] or '':20s} | {row[3] or '':20s} | {row[4] or ''}")

cur.close()
conn.close()
