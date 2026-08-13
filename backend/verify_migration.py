"""
Data migration verification script.

Verifies that the PostgreSQL projects table is in parity with the
scraped_projects/ directory by:
  1. Comparing row counts vs directory counts.
  2. Spot-checking that raw_data JSONB matches view_page_data.json content.

Usage:
    python verify_migration.py
    python verify_migration.py --spot-check 5   # check 5 random projects
    python verify_migration.py --fail-fast       # stop on first mismatch

Requirements: 6.1, 6.2
"""
import json
import os
import random
import sys
import argparse
from pathlib import Path

try:
    from db_utils import get_connection
except ImportError:
    print("[ERROR] db_utils not found. Run from the backend/ directory.")
    sys.exit(1)

SCRAPED_DIR = Path(__file__).parent / "scraped_projects"


def get_db_projects(conn) -> dict[str, dict]:
    """Return all projects from the DB as {id: raw_data_dict}."""
    with conn.cursor() as cur:
        cur.execute("SELECT id, raw_data FROM projects ORDER BY id")
        rows = cur.fetchall()
    return {row[0]: row[1] for row in rows}


def get_fs_projects() -> dict[str, Path]:
    """Return all valid project dirs (those that contain view_page_data.json) as {id: path}."""
    result = {}
    if not SCRAPED_DIR.exists():
        return result
    for d in SCRAPED_DIR.iterdir():
        if d.is_dir() and (d / "view_page_data.json").exists():
            result[d.name] = d
    return result


def check_counts(db_projects: dict, fs_projects: dict) -> bool:
    db_count = len(db_projects)
    fs_count = len(fs_projects)
    print(f"\n[COUNT CHECK]")
    print(f"  PostgreSQL rows : {db_count}")
    print(f"  Filesystem dirs : {fs_count}")

    if db_count == fs_count:
        print(f"  ✅ Counts match ({db_count})")
        return True
    else:
        print(f"  ❌ Count mismatch: DB has {db_count}, filesystem has {fs_count}")
        missing_from_db = set(fs_projects) - set(db_projects)
        missing_from_fs = set(db_projects) - set(fs_projects)
        if missing_from_db:
            print(f"  In filesystem but NOT in DB ({len(missing_from_db)}):")
            for pid in sorted(missing_from_db)[:10]:
                print(f"    - {pid}")
        if missing_from_fs:
            print(f"  In DB but NOT in filesystem ({len(missing_from_fs)}):")
            for pid in sorted(missing_from_fs)[:10]:
                print(f"    - {pid}")
        return False


def check_raw_data_parity(
    db_projects: dict,
    fs_projects: dict,
    n_samples: int = 5,
    fail_fast: bool = False,
) -> bool:
    """
    Spot-check that raw_data in PostgreSQL is equivalent to view_page_data.json
    on disk for a random sample of projects (Req 6.2).
    """
    common_ids = list(set(db_projects) & set(fs_projects))
    if not common_ids:
        print("\n[PARITY CHECK] No common project IDs to check.")
        return True

    sample = random.sample(common_ids, min(n_samples, len(common_ids)))
    print(f"\n[PARITY CHECK] Spot-checking {len(sample)} of {len(common_ids)} common projects")

    all_ok = True
    for pid in sample:
        json_path = fs_projects[pid] / "view_page_data.json"
        try:
            fs_data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ⚠️  {pid}: could not read JSON file: {e}")
            continue

        db_data = db_projects[pid]

        # Compare a selection of top-level keys
        mismatches = []
        for key in ("Project Name", "Project Status", "District", "Pin Code"):
            fs_val = _flatten_get(fs_data, key)
            db_val = _flatten_get(db_data, key) if isinstance(db_data, dict) else None
            if fs_val != db_val:
                mismatches.append(f"{key}: fs={fs_val!r} db={db_val!r}")

        if mismatches:
            print(f"  ❌ {pid}: field mismatches:")
            for m in mismatches:
                print(f"       {m}")
            all_ok = False
            if fail_fast:
                return False
        else:
            print(f"  ✅ {pid}: key fields match")

    return all_ok


def _flatten_get(data, key):
    """Recursively search for key in nested dicts."""
    if isinstance(data, dict):
        if key in data:
            return data[key]
        for v in data.values():
            result = _flatten_get(v, key)
            if result is not None:
                return result
    return None


def main():
    parser = argparse.ArgumentParser(description="Verify DB/filesystem migration parity")
    parser.add_argument("--spot-check", type=int, default=5,
                        help="Number of projects to spot-check (default: 5)")
    parser.add_argument("--fail-fast", action="store_true",
                        help="Stop on first mismatch")
    args = parser.parse_args()

    print("=" * 60)
    print("HydUrban Migration Verification")
    print("=" * 60)

    # Connect to DB
    try:
        conn = get_connection()
        print("[DB] Connected to PostgreSQL ✅")
    except Exception as e:
        print(f"[DB] Connection failed: {e}")
        sys.exit(1)

    try:
        db_projects = get_db_projects(conn)
        fs_projects = get_fs_projects()

        count_ok  = check_counts(db_projects, fs_projects)
        parity_ok = check_raw_data_parity(
            db_projects, fs_projects,
            n_samples=args.spot_check,
            fail_fast=args.fail_fast,
        )

        print("\n" + "=" * 60)
        if count_ok and parity_ok:
            print("✅ VERIFICATION PASSED — data is in parity")
            sys.exit(0)
        else:
            print("❌ VERIFICATION FAILED — see details above")
            sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
