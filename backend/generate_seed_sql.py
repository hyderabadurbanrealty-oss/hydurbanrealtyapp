"""
Generates a seed SQL file (seed_projects.sql) from all scraped view_page_data.json files.
Run:  python generate_seed_sql.py
Then paste the output seed_projects.sql into Supabase SQL Editor.
"""
import json
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent
SCRAPED_DIR = BACKEND_DIR / "scraped_projects"
OUTPUT_FILE = BACKEND_DIR / "seed_projects.sql"


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


def esc(val):
    """Escape a string value for SQL single-quote safety."""
    if val is None:
        return "NULL"
    return "'" + str(val).replace("'", "''") + "'"


def esc_bool(val: bool):
    return "TRUE" if val else "FALSE"


def esc_numeric(val):
    return str(val) if val is not None else "NULL"


def parse_date(val: str):
    """Convert DD/MM/YYYY to YYYY-MM-DD, return NULL if unparseable."""
    if not val:
        return "NULL"
    try:
        parts = val.strip().split("/")
        if len(parts) == 3:
            d, m, y = parts
            return f"'{y}-{m.zfill(2)}-{d.zfill(2)}'"
    except Exception:
        pass
    return "NULL"


def main():
    rows = []

    for proj_dir in sorted(SCRAPED_DIR.iterdir()):
        if not proj_dir.is_dir():
            continue
        json_path = proj_dir / "view_page_data.json"
        if not json_path.exists():
            print(f"  SKIP  {proj_dir.name}  (no view_page_data.json)", file=sys.stderr)
            continue

        project_id = sanitize(proj_dir.name)
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if "Project Name" not in data or not data["Project Name"]:
                data["Project Name"] = proj_dir.name

            raw_json = json.dumps(data).replace("'", "''")

            approved_date = parse_date(_extract(data, "Approved Date"))
            completion_date = parse_date(_extract(data, "Proposed Date of Completion"))
            revised_date = parse_date(_extract(data, "Revised Date of Completion"))

            is_msb = _extract(data, "Is the project an MSB or a High-Rise?").lower() == "yes"
            has_lit = _extract(data, "Litigations related to the project ?").lower() == "yes"

            total_area   = safe_float(_extract(data, "Total Area(In sqmts)"))
            net_area     = safe_float(_extract(data, "Net Area(In sqmts)"))
            built_up     = safe_float(_extract(data, "Approved Built up Area (In Sqmts)"))
            mortgage     = safe_float(_extract(data, "Mortgage Area (In Sqmts)"))
            saleable     = safe_float(_extract(data, "Saleable Area (Sq.Mt.)"))
            total_flats  = safe_int(data.get("totalFlats", 0))
            total_booked = safe_int(data.get("totalBookedFlats", 0))

            sql = f"""INSERT INTO projects (
    id, project_name, project_status, project_type,
    district, mandal, locality, pin_code, village,
    approved_date, completion_date, revised_completion_date,
    total_area_sqmt, net_area_sqmt, built_up_area_sqmt, mortgage_area_sqmt,
    promoter_name, org_type, bank_name, branch_name,
    plan_approval_number, survey_number,
    is_msb, has_litigation,
    total_flats, total_booked, saleable_area_sqmt,
    raw_data, scraped_at
) VALUES (
    {esc(project_id)},
    {esc(data.get("Project Name", project_id))},
    {esc(_extract(data, "Project Status"))},
    {esc(_extract(data, "Project Type"))},
    {esc(_extract(data, "District"))},
    {esc(_extract(data, "Mandal"))},
    {esc(_extract(data, "Locality"))},
    {esc(_extract(data, "Pin Code"))},
    {esc(_extract(data, "Village/City/Town"))},
    {approved_date},
    {completion_date},
    {revised_date},
    {esc_numeric(total_area)},
    {esc_numeric(net_area)},
    {esc_numeric(built_up)},
    {esc_numeric(mortgage)},
    {esc(_extract(data, "Name"))},
    {esc(_extract(data, "Organization Type"))},
    {esc(_extract(data, "Bank Name"))},
    {esc(_extract(data, "Branch Name"))},
    {esc(_extract(data, "Plan Approval Number"))},
    {esc(_extract(data, "Sy.No/TS No."))},
    {esc_bool(is_msb)},
    {esc_bool(has_lit)},
    {total_flats},
    {total_booked},
    {esc_numeric(saleable)},
    '{raw_json}'::jsonb,
    NOW()
)
ON CONFLICT (id) DO UPDATE SET
    raw_data       = EXCLUDED.raw_data,
    updated_at     = NOW(),
    project_name   = EXCLUDED.project_name,
    project_status = EXCLUDED.project_status,
    district       = EXCLUDED.district,
    locality       = EXCLUDED.locality,
    pin_code       = EXCLUDED.pin_code;
"""
            rows.append(sql)
            print(f"  OK    {project_id}", file=sys.stderr)

        except Exception as e:
            print(f"  FAIL  {project_id}: {e}", file=sys.stderr)

    header = "-- =============================================================================\n"
    header += "-- seed_projects.sql — Auto-generated from scraped_projects/\n"
    header += f"-- Projects: {len(rows)}\n"
    header += "-- Paste into Supabase SQL Editor and Run\n"
    header += "-- =============================================================================\n\n"

    OUTPUT_FILE.write_text(header + "\n".join(rows), encoding="utf-8")
    print(f"\nWrote {len(rows)} INSERT statements to {OUTPUT_FILE}", file=sys.stderr)
    print(str(OUTPUT_FILE))


if __name__ == "__main__":
    main()
