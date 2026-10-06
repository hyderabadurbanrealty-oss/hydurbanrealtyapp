"""
scrape_500081.py
================
Full pipeline for PIN code 500081 — Madhapur / HITEC City / Cyberabad
(Serilingampally mandal, Ranga Reddy / GHMC area)

What this scrapes:
  1. RERA Telangana  — all registered residential/commercial projects at PIN 500081
  2. SRO transactions — Serilingampally SRO (covers Madhapur, Kondapur, Gachibowli,
                        HITEC City, Raidurg, Nanakramguda, Gopanpalle belt)

Uses the existing credentials from scrape_preferences.json
(igrs_username / igrs_password).

Run:
    python scrape_500081.py --rera          # RERA only
    python scrape_500081.py --sro           # SRO only
    python scrape_500081.py                 # both (default)
    python scrape_500081.py --dry-run       # check counts, no DB writes

Requirements (same as existing pipeline):
    pip install selenium webdriver-manager beautifulsoup4 requests psycopg2-binary
"""

import argparse
import json
import sys
import time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
PREFS_FILE = Path(__file__).parent / "scrape_preferences.json"
prefs      = json.loads(PREFS_FILE.read_text())

PIN_CODE   = "500081"
# Serilingampally SRO covers Madhapur / HITEC City / Kondapur / Gachibowli belt.
# The IGRS SRO name used in the scraper matches the dropdown value on the site.
SRO_NAME   = "Serilingampalli"
YEARS      = ["2023", "2024", "2025", "2026"]   # scrape recent years

def banner(title: str) -> None:
    print(f"\n{'='*65}")
    print(f"  {title}")
    print(f"{'='*65}\n")


# ── 1. RERA scrape ────────────────────────────────────────────────────────────
def run_rera(dry_run: bool) -> None:
    banner(f"RERA Telangana — PIN {PIN_CODE} (Madhapur / HITEC City)")

    try:
        from rera_detail_scraper import main as rera_main
    except ImportError as e:
        print(f"  ERROR: cannot import rera_detail_scraper — {e}")
        print("  Make sure you're running from the backend/ directory.")
        return

    if dry_run:
        print("  [DRY-RUN] Would call: rera_main(project_name='%', pin_code_filter='500081')")
        print("  RERA projects at 500081 cover:")
        print("    • Madhapur residential towers")
        print("    • HITEC City commercial + residential mix")
        print("    • Ayyappa Society, VIP Hills, Silicon Valley")
        print("    • Vittal Rao Nagar, Kavuri Hills overlap belt")
        return

    print(f"  Launching RERA scraper for PIN {PIN_CODE}…")
    print("  (Headless Chrome will open; captcha solving may take a few minutes)\n")
    try:
        rera_main(project_name="")
        print(f"\n  ✓ RERA scrape complete for PIN {PIN_CODE}")
    except Exception as e:
        print(f"\n  ✗ RERA scrape failed: {e}")
        raise


# ── 2. SRO / IGRS scrape ──────────────────────────────────────────────────────
def run_sro(dry_run: bool) -> None:
    banner(f"SRO Transactions — {SRO_NAME} (covers PIN {PIN_CODE} belt)")

    try:
        from sro_transaction_scraper import SROScraper
    except ImportError:
        # Older versions expose a different entry point
        try:
            from run_sro_scan import main as sro_main
            if dry_run:
                print(f"  [DRY-RUN] Would call run_sro_scan for SRO '{SRO_NAME}', years {YEARS}")
                return
            for year in YEARS:
                print(f"  Scraping {SRO_NAME} — {year}…")
                try:
                    sro_main(sro_name=SRO_NAME, year=year)
                    print(f"    ✓ {year} done")
                except Exception as e:
                    print(f"    ✗ {year} failed: {e}")
            return
        except ImportError as e:
            print(f"  ERROR: cannot import SRO scraper — {e}")
            return

    if dry_run:
        print(f"  [DRY-RUN] Would scrape SRO '{SRO_NAME}' for years: {YEARS}")
        print("  Serilingampalli SRO covers property registrations in:")
        print("    • Madhapur village  (HITEC City core)")
        print("    • Kondapur")
        print("    • Gachibowli")
        print("    • Raidurg / Nanakramguda")
        print("    • Gopanpalle / Kothaguda")
        return

    for year in YEARS:
        print(f"\n  Scraping {SRO_NAME} — {year} …")
        try:
            scraper = SROScraper(sro_name=SRO_NAME, year=year, prefs=prefs)
            count   = scraper.run()
            print(f"    ✓ {year}: {count} transactions saved")
            time.sleep(2)   # polite pause between years
        except Exception as e:
            print(f"    ✗ {year}: {e}")


# ── 3. Post-scrape summary ────────────────────────────────────────────────────
def print_summary() -> None:
    banner("Post-scrape DB summary")
    try:
        import psycopg2
        conn = psycopg2.connect(prefs["db_connection"])
        cur  = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM projects WHERE pin_code = %s", (PIN_CODE,))
        rera_count = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*), MIN(reg_date), MAX(reg_date)
            FROM sro_transactions
            WHERE village ILIKE '%madhapur%'
               OR village ILIKE '%kondapur%'
               OR village ILIKE '%gachibowli%'
               OR village ILIKE '%raidurg%'
               OR village ILIKE '%hitec%'
               OR sro_name ILIKE '%serilingamp%'
        """)
        row = cur.fetchone()
        sro_count, sro_min, sro_max = row if row else (0, None, None)

        cur.close()
        conn.close()

        print(f"  RERA projects at PIN {PIN_CODE}  : {rera_count}")
        print(f"  SRO transactions (Serilingampalli): {sro_count}")
        if sro_min:
            print(f"  SRO date range               : {sro_min} → {sro_max}")
    except Exception as e:
        print(f"  DB summary failed: {e}")


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Scrape RERA + SRO data for PIN {PIN_CODE} (Madhapur / HITEC City)"
    )
    parser.add_argument("--rera",    action="store_true", help="Run RERA scrape only")
    parser.add_argument("--sro",     action="store_true", help="Run SRO scrape only")
    parser.add_argument("--dry-run", action="store_true", help="Preview only — no writes")
    args = parser.parse_args()

    run_both = not args.rera and not args.sro

    print(f"\nTarget: PIN {PIN_CODE} — Madhapur / HITEC City / Cyberabad")
    print(f"SRO   : {SRO_NAME}")
    print(f"Mode  : {'DRY-RUN' if args.dry_run else 'LIVE'}\n")

    if args.rera or run_both:
        run_rera(dry_run=args.dry_run)

    if args.sro or run_both:
        run_sro(dry_run=args.dry_run)

    if not args.dry_run:
        print_summary()


if __name__ == "__main__":
    main()
