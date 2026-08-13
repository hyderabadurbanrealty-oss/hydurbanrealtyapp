"""
One-shot import: reads all view_page_data.json files from scraped_projects/
and upserts them into the PostgreSQL projects table.

Run:  python import_scraped_to_db.py
"""
import json
import os
import re
import sys
from pathlib import Path

# ── Locate backend dir and add to path ───────────────────────────────────────
BACKEND_DIR = Path(__file__).parent
SCRAPED_DIR = BACKEND_DIR / "scraped_projects"
sys.path.insert(0, str(BACKEND_DIR))

from db_utils import get_connection

# ── Helpers ───────────────────────────────────────────────────────────────────

def sanitize(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def safe_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default

def safe_float(v):
    try:
        return float(v) if v else None
    except (TypeError, ValueError):
        return None

def _extract(data: dict, key: str):
    """Search for key at top level then one level deep in nested dicts."""
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

def upsert_project(conn, project_id: str, data: dict) -> bool:
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
            %s::jsonb, NOW()
        )
        ON CONFLICT (id) DO UPDATE SET
            raw_data       = EXCLUDED.raw_data,
            updated_at     = NOW(),
            project_name   = EXCLUDED.project_name,
            project_status = EXCLUDED.project_status,
            district       = EXCLUDED.district,
            locality       = EXCLUDED.locality,
            pin_code       = EXCLUDED.pin_code
    """
    params = (
        project_id,
        data.get("Project Name", project_id),
        _extract(data, "Project Status"),
        _extract(data, "Project Type"),
        _extract(data, "District"),
        _extract(data, "Mandal"),
        _extract(data, "Locality"),
        _extract(data, "Pin Code"),
        _extract(data, "Village/City/Town"),
        _extract(data, "Name"),
        _extract(data, "Organization Type"),
        _extract(data, "Bank Name"),
        _extract(data, "Branch Name"),
        _extract(data, "Plan Approval Number"),
        _extract(data, "Sy.No/TS No."),
        _extract(data, "Is the project an MSB or a High-Rise?").lower() == "yes",
        _extract(data, "Litigations related to the project ?").lower() == "yes",
        safe_int(data.get("totalFlats", 0)),
        safe_int(data.get("totalBookedFlats", 0)),
        safe_float(_extract(data, "Saleable Area (Sq.Mt.)")),
        json.dumps(data),
    )
    with conn.cursor() as cur:
        cur.execute(sql, params)
    conn.commit()
    return True

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Connecting to PostgreSQL…")
    conn = get_connection()
    print(f"Connected. Scanning {SCRAPED_DIR}…\n")

    ok = 0
    failed = 0

    for proj_dir in sorted(SCRAPED_DIR.iterdir()):
        if not proj_dir.is_dir():
            continue
        json_path = proj_dir / "view_page_data.json"
        if not json_path.exists():
            print(f"  SKIP  {proj_dir.name}  (no view_page_data.json)")
            continue

        project_id = sanitize(proj_dir.name)
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            # Ensure Project Name is set
            if "Project Name" not in data or not data["Project Name"]:
                data["Project Name"] = proj_dir.name
            upsert_project(conn, project_id, data)
            print(f"  OK    {project_id}")
            ok += 1
        except Exception as e:
            print(f"  FAIL  {project_id}: {e}")
            failed += 1
            try:
                conn.rollback()
            except Exception:
                pass

    conn.close()
    print(f"\nDone — {ok} imported, {failed} failed.")

    # Verify
    conn2 = get_connection()
    with conn2.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM projects")
        count = cur.fetchone()[0]
    conn2.close()
    print(f"projects table now has {count} rows.")

if __name__ == "__main__":
    main()
