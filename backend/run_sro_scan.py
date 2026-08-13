"""
Multi-year SRO trend scan — collects data for 2021-2025 across SROs derived
from the pincodes in scrape_preferences.json.

To cover a new area: add its pincode to scrape_preferences.json.
The scraper will automatically pick up the correct SROs via get_active_sros().
"""
import sys, time, json, requests
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))
from sro_transaction_scraper import (
    login_and_get_cookies, fetch_doc, build_quarterly_summary,
    build_village_summary, _save, DATA_DIR, REQUEST_DELAY,
    get_active_sros,
)

N_DOCS  = 1200   # ~4 months of docs per year (covers ~1 full quarter)
YEARS   = [2021, 2022, 2023, 2024, 2025]

# Derive SROs dynamically from scrape_preferences.json — no hardcoded list
SROS_TO_SCAN = get_active_sros()
print(f"Active SROs for this scan ({len(SROS_TO_SCAN)}): {[s['name'] for s in SROS_TO_SCAN]}")

print("Logging in to IGRS portal...")
cookies = login_and_get_cookies()
if not cookies:
    print("Login failed"); sys.exit(1)

session = requests.Session()
session.cookies.update(cookies)
session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
session.headers["Referer"]    = "https://registration.telangana.gov.in/districtList.htm"

all_records = []
t_start = time.time()

for sro in SROS_TO_SCAN:
    for year in YEARS:
        print(f"\nSRO: {sro['name']}  Year: {year}  (docs 1-{N_DOCS})")
        found = []
        for docno in range(1, N_DOCS + 1):
            rec = fetch_doc(session, sro["dist_code"], sro["sro_code"], docno, year)
            if rec:
                rec["sro_name"] = sro["name"]
                rec["district"] = sro["district"]
                found.append(rec)
            time.sleep(REQUEST_DELAY)
            if docno % 100 == 0:
                elapsed = time.time() - t_start
                print(f"  {docno}/{N_DOCS} docs, {len(found)} apt sales, "
                      f"{elapsed:.0f}s elapsed")
        print(f"  => {len(found)} apartment sale deeds")
        all_records.extend(found)

        # Save after each SRO+year
        out = DATA_DIR / "sro_transactions.json"
        _save(all_records, out)

elapsed_total = time.time() - t_start
print(f"\n=== DONE: {len(all_records)} records, {elapsed_total:.0f}s ===")
print("\nQuarterly summary:")
for q in build_quarterly_summary(all_records):
    print(f"  {q['sro']:20s} {q['quarter']}  count={q['count']:3d}  "
          f"avg=Rs{q['avg_price_sqft']:,.0f}/sqft  "
          f"range=[{q['min_price_sqft']:,.0f} - {q['max_price_sqft']:,.0f}]")
