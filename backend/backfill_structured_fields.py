"""
Backfills structured columns (total_flats, total_booked, approved_date,
completion_date, promoter_name, etc.) from raw_data JSONB for all projects.

Run:  python backfill_structured_fields.py
"""
import psycopg2, json, re
from pathlib import Path
from datetime import date

prefs = json.loads(Path('scrape_preferences.json').read_text())
conn  = psycopg2.connect(prefs['db_connection'])
cur   = conn.cursor()

cur.execute("SELECT id, raw_data FROM projects")
rows = cur.fetchall()
print(f"Backfilling {len(rows)} projects...")

def _extract(data: dict, key: str) -> str:
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

def parse_date(s: str):
    if not s: return None
    try:
        parts = s.strip().split('/')
        if len(parts) == 3:
            d, m, y = parts
            return date(int(y), int(m), int(d))
    except Exception:
        pass
    return None

def safe_float(v):
    try: return float(v) if v else None
    except: return None

updated = 0
for project_id, raw_data in rows:
    if isinstance(raw_data, str):
        data = json.loads(raw_data)
    else:
        data = raw_data

    # ── Extract flat counts from Floor Breakdown ──────────────────────────
    total_flats  = 0
    total_booked = 0
    floor_breakdown = data.get('Floor Breakdown', [])
    if isinstance(floor_breakdown, list):
        for row in floor_breakdown:
            if not isinstance(row, dict): continue
            has_apt  = row.get('Apartment Type') or row.get('Floor ID') or row.get('Saleable Area (in Sqmts)')
            if not has_apt: continue
            units_str  = row.get('Number of Apartment') or row.get('Number of Apartments', '0')
            booked_str = row.get('Number of Booked Apartment') or row.get('Number of Booked Apartments', '0')
            try: total_flats  += int(units_str)
            except: pass
            try: total_booked += int(booked_str)
            except: pass

    # Fallback: blob pattern in Building Tower Details
    if total_flats == 0:
        tower_details = data.get('Building Tower Details', [])
        blob_pattern = re.compile(r'\d+\s+\d+\s+(?:True|False)\s+\S+\s+[\d.]+\s+(\d+)\s+(\d+)')
        for t in (tower_details if isinstance(tower_details, list) else []):
            name = t.get('Name', '') if isinstance(t, dict) else ''
            if len(name) < 200: continue
            for m in blob_pattern.finditer(name):
                try: total_flats  += int(m.group(1))
                except: pass
                try: total_booked += int(m.group(2))
                except: pass

    # ── Dates ─────────────────────────────────────────────────────────────
    approved_date  = parse_date(_extract(data, 'Approved Date'))
    completion_date = parse_date(_extract(data, 'Proposed Date of Completion'))
    revised_date   = parse_date(_extract(data, 'Revised Proposed Date of Completion'))

    # ── Other structured fields ───────────────────────────────────────────
    promoter_name  = _extract(data, 'Name')
    org_type       = _extract(data, 'Organization Type')
    bank_name      = _extract(data, 'Bank Name')
    branch_name    = _extract(data, 'Branch Name')
    plan_approval  = _extract(data, 'Plan Approval Number')
    survey_no      = _extract(data, 'Sy.No/TS No.')
    total_area     = safe_float(_extract(data, 'Total Area(In sqmts)'))
    net_area       = safe_float(_extract(data, 'Net Area(In sqmts)'))
    built_up       = safe_float(_extract(data, 'Approved Built up Area (In Sqmts)'))
    mortgage       = safe_float(_extract(data, 'Mortgage Area (In Sqmts)'))
    saleable       = safe_float(_extract(data, 'Saleable Area (Sq.Mt.)'))
    is_msb         = _extract(data, 'Is the project an MSB or a High-Rise?').lower() == 'yes'
    has_litigation = _extract(data, 'Litigations related to the project ?').lower() == 'yes'
    village        = _extract(data, 'Village/City/Town')
    mandal         = _extract(data, 'Mandal')
    district       = _extract(data, 'District')
    locality       = _extract(data, 'Locality')
    pin_code       = _extract(data, 'Pin Code')
    project_type   = _extract(data, 'Project Type')
    project_status = _extract(data, 'Project Status')

    cur.execute("""
        UPDATE projects SET
            total_flats             = %s,
            total_booked            = %s,
            approved_date           = %s,
            completion_date         = %s,
            revised_completion_date = %s,
            promoter_name           = %s,
            org_type                = %s,
            bank_name               = %s,
            branch_name             = %s,
            plan_approval_number    = %s,
            survey_number           = %s,
            total_area_sqmt         = %s,
            net_area_sqmt           = %s,
            built_up_area_sqmt      = %s,
            mortgage_area_sqmt      = %s,
            saleable_area_sqmt      = %s,
            is_msb                  = %s,
            has_litigation          = %s,
            village                 = COALESCE(NULLIF(village,''), %s),
            mandal                  = COALESCE(NULLIF(mandal,''), %s),
            district                = COALESCE(NULLIF(district,''), %s),
            locality                = COALESCE(NULLIF(locality,''), %s),
            pin_code                = COALESCE(NULLIF(pin_code,''), %s),
            project_type            = COALESCE(NULLIF(project_type,''), %s),
            project_status          = COALESCE(NULLIF(project_status,''), %s),
            updated_at              = NOW()
        WHERE id = %s
    """, (
        total_flats, total_booked,
        approved_date, completion_date, revised_date,
        promoter_name, org_type, bank_name, branch_name,
        plan_approval, survey_no,
        total_area, net_area, built_up, mortgage, saleable,
        is_msb, has_litigation,
        village, mandal, district, locality, pin_code,
        project_type, project_status,
        project_id
    ))
    print(f"  ✓ {project_id:<40} flats={total_flats} booked={total_booked} approved={approved_date}")
    updated += 1

conn.commit()
conn.close()
print(f"\nDone — {updated} projects backfilled.")
