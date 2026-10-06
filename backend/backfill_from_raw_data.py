"""
backfill_from_raw_data.py
=========================
Re-extracts structured columns from raw_data JSONB for all projects
where columns like district/locality/pin_code are NULL.

Run: python backfill_from_raw_data.py
"""
import sys
sys.path.insert(0, '.')
from db_utils import get_connection

def _extract(data: dict, key: str) -> str:
    """Search for key at top level then one level deep in nested dicts."""
    if key in data:
        v = data[key]
        if isinstance(v, (str, int, float)):
            return str(v).strip()
    for v in data.values():
        if isinstance(v, dict) and key in v:
            inner = v[key]
            if isinstance(inner, (str, int, float)):
                return str(inner).strip()
    return ''

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

conn = get_connection()
cur = conn.cursor()

# Get all projects
cur.execute("SELECT id, raw_data FROM projects")
rows = cur.fetchall()
print(f"Found {len(rows)} projects to backfill.\n")

updated = 0
skipped = 0

for project_id, raw_data in rows:
    if not raw_data:
        print(f"  SKIP {project_id!r} — no raw_data")
        skipped += 1
        continue

    d = raw_data  # psycopg2 returns JSONB as dict already

    district       = _extract(d, 'District')
    mandal         = _extract(d, 'Mandal')
    locality       = _extract(d, 'Locality')
    pin_code       = _extract(d, 'Pin Code')
    village        = _extract(d, 'Village/City/Town')
    project_status = _extract(d, 'Project Status')
    project_type   = _extract(d, 'Project Type')
    promoter_name  = _extract(d, 'Name')  # 'Name' = promoter org name
    org_type       = _extract(d, 'Organization Type')
    bank_name      = _extract(d, 'Bank Name')
    branch_name    = _extract(d, 'Branch Name')
    plan_approval  = _extract(d, 'Plan Approval Number')
    survey_number  = _extract(d, 'Sy.No/TS No.')
    is_msb         = _extract(d, 'Is the project an MSB or a High-Rise?').lower() == 'yes'
    has_litigation = _extract(d, 'Litigations related to the project ?').lower() == 'yes'
    total_flats    = safe_int(d.get('totalFlats') or _extract(d, 'Total Building Units (as per approved plan)'))
    total_booked   = safe_int(d.get('totalBookedFlats'))
    saleable_area  = safe_float(_extract(d, 'Saleable Area (Sq.Mt.)'))
    project_name   = d.get('Project Name') or _extract(d, 'Project Name') or project_id

    cur.execute("""
        UPDATE projects SET
            project_name         = %s,
            project_status       = NULLIF(%s, ''),
            project_type         = NULLIF(%s, ''),
            district             = NULLIF(%s, ''),
            mandal               = NULLIF(%s, ''),
            locality             = NULLIF(%s, ''),
            pin_code             = NULLIF(%s, ''),
            village              = NULLIF(%s, ''),
            promoter_name        = NULLIF(%s, ''),
            org_type             = NULLIF(%s, ''),
            bank_name            = NULLIF(%s, ''),
            branch_name          = NULLIF(%s, ''),
            plan_approval_number = NULLIF(%s, ''),
            survey_number        = NULLIF(%s, ''),
            is_msb               = %s,
            has_litigation       = %s,
            total_flats          = NULLIF(%s, 0),
            total_booked         = NULLIF(%s, 0),
            saleable_area_sqmt   = %s,
            updated_at           = NOW()
        WHERE id = %s
    """, (
        project_name, project_status, project_type,
        district, mandal, locality, pin_code, village,
        promoter_name, org_type, bank_name, branch_name,
        plan_approval, survey_number,
        is_msb, has_litigation,
        total_flats, total_booked, saleable_area,
        project_id
    ))
    print(f"  OK  {project_id!r:50s} pin={pin_code!r} district={district!r} mandal={mandal!r}")
    updated += 1

conn.commit()
conn.close()
print(f"\nDone — {updated} updated, {skipped} skipped.")
