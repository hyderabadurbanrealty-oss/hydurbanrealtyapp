"""
compress_supabase_media.py
==========================
Download every image from the Supabase 'property-media' bucket, compress /
convert it, re-upload in-place, and update all DB columns that reference the
old URL.

Handles:
  • JPEG/JPG  → re-compress at TARGET_JPEG_QUALITY (default 72)
  • PNG       → convert to WebP at TARGET_WEBP_QUALITY (default 80)
  • WebP      → re-compress at TARGET_WEBP_QUALITY if above threshold
  • Everything else (PDF, doc, etc.) → skipped

Safety:
  • --dry-run  : list what WOULD be done, no writes
  • Only processes files where estimated savings ≥ MIN_SAVING_PCT (default 10 %)
  • Writes a CSV log of every action to compress_log_<timestamp>.csv
  • Reconnects to DB every 50 files to handle long-running jobs

Usage:
  pip install requests psycopg2-binary Pillow
  python compress_supabase_media.py              # live run
  python compress_supabase_media.py --dry-run    # preview only

Config is read from scrape_preferences.json (same file every other script uses).
Override any value with environment variables:
  SUPABASE_URL, SUPABASE_SERVICE_KEY, DATABASE_URL
"""

import argparse
import csv
import io
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import psycopg2
import requests
from PIL import Image

# ── Config ────────────────────────────────────────────────────────────────────
PREFS_FILE = Path(__file__).parent / "scrape_preferences.json"

with open(PREFS_FILE, "r") as _f:
    _prefs = json.load(_f)

SUPABASE_URL  = _prefs.get("supabase_url",         os.environ.get("SUPABASE_URL",         "https://qjgwnbszmojzgwmafvuc.supabase.co")).rstrip("/")
SERVICE_KEY   = _prefs.get("supabase_service_key", os.environ.get("SUPABASE_SERVICE_KEY", ""))
DB_URL        = _prefs.get("db_connection",        os.environ.get("DATABASE_URL",         ""))
BUCKET        = _prefs.get("supabase_bucket",      "property-media")

if not SERVICE_KEY:
    sys.exit("ERROR: supabase_service_key missing in scrape_preferences.json / SUPABASE_SERVICE_KEY env var")
if not DB_URL:
    sys.exit("ERROR: db_connection missing in scrape_preferences.json / DATABASE_URL env var")

# ── Tuning ────────────────────────────────────────────────────────────────────
TARGET_JPEG_QUALITY = 72      # Quality for JPEG output  (was typically 85-95)
TARGET_WEBP_QUALITY = 80      # Quality for WebP output
MAX_DIMENSION       = 2400    # Down-scale any side larger than this (pixels)
MIN_SAVING_PCT      = 10      # Skip if savings would be < this %
MIN_FILE_SIZE_KB    = 80      # Skip files already smaller than this (KB)
LIST_PAGE_SIZE      = 1000    # Files per Supabase list request
REQUEST_TIMEOUT     = 40      # Seconds for download/upload HTTP calls
RATE_LIMIT_SLEEP    = 0.25    # Seconds between uploads (be polite)

# ── Helpers ───────────────────────────────────────────────────────────────────
STORAGE_HEADERS = {
    "Authorization": f"Bearer {SERVICE_KEY}",
    "apikey":        SERVICE_KEY,
}

def _storage_list(prefix: str = "", offset: int = 0) -> list[dict]:
    """One page of files from the bucket."""
    url = f"{SUPABASE_URL}/storage/v1/object/list/{BUCKET}"
    r = requests.post(url, headers=STORAGE_HEADERS, json={
        "limit":  LIST_PAGE_SIZE,
        "offset": offset,
        "prefix": prefix,
        "sortBy": {"column": "name", "order": "asc"},
    }, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json()


def list_all_files() -> list[dict]:
    """Recursively paginate through ALL files in the bucket, descending into folders."""
    all_files: list[dict] = []

    def _recurse(prefix: str) -> None:
        offset = 0
        while True:
            page = _storage_list(prefix=prefix, offset=offset)
            if not page:
                break
            for item in page:
                if not item or not isinstance(item, dict):
                    continue
                name = item.get("name", "")
                metadata = item.get("metadata")
                # Supabase returns folder placeholders as items with no metadata
                # or with size == 0 and no file extension → descend into them
                is_folder = (
                    metadata is None
                    or (isinstance(metadata, dict) and metadata.get("size", 0) == 0 and "." not in name)
                )
                if is_folder:
                    # Recurse into the folder
                    sub_prefix = f"{prefix}{name}/" if prefix else f"{name}/"
                    _recurse(sub_prefix)
                else:
                    # It's a real file — attach full path for callers
                    item["_full_path"] = f"{prefix}{name}" if prefix else name
                    all_files.append(item)
            if len(page) < LIST_PAGE_SIZE:
                break
            offset += LIST_PAGE_SIZE
            time.sleep(0.1)

    _recurse("")
    return all_files


def download(url: str) -> bytes | None:
    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        return r.content if r.status_code == 200 else None
    except Exception as e:
        print(f"    ✗ download error: {e}")
        return None


def compress_image(raw: bytes, original_name: str) -> tuple[bytes | None, str]:
    """
    Returns (compressed_bytes, new_mime_type).
    PNGs → WebP.  JPEG/WebP → re-compressed same format.
    Returns (None, '') on failure or when savings are negligible.
    """
    ext = Path(original_name).suffix.lower()
    try:
        img = Image.open(io.BytesIO(raw))

        # Down-scale if needed
        w, h = img.size
        if max(w, h) > MAX_DIMENSION:
            scale = MAX_DIMENSION / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        # Always work in RGB (removes alpha for JPEG compat, fine for real-estate)
        if img.mode in ("RGBA", "P", "LA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode in ("RGBA", "LA"):
                bg.paste(img, mask=img.split()[-1])
            else:
                bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

        buf = io.BytesIO()
        if ext == ".png":
            img.save(buf, format="WEBP", quality=TARGET_WEBP_QUALITY, method=6)
            mime = "image/webp"
        elif ext in (".jpg", ".jpeg"):
            img.save(buf, format="JPEG", quality=TARGET_JPEG_QUALITY, optimize=True, progressive=True)
            mime = "image/jpeg"
        elif ext == ".webp":
            img.save(buf, format="WEBP", quality=TARGET_WEBP_QUALITY, method=6)
            mime = "image/webp"
        else:
            return None, ""

        return buf.getvalue(), mime
    except Exception as e:
        print(f"    ✗ compress error: {e}")
        return None, ""


def upload(data: bytes, storage_path: str, mime: str) -> bool:
    """Delete old file, upload new bytes at same path."""
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}"
    # Delete first (Supabase Storage doesn't support upsert in all tiers)
    requests.delete(url, headers=STORAGE_HEADERS, timeout=REQUEST_TIMEOUT)
    r = requests.post(url, headers={**STORAGE_HEADERS, "Content-Type": mime},
                      data=data, timeout=REQUEST_TIMEOUT)
    return r.status_code in (200, 201)


def make_public_url(storage_path: str) -> str:
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"


def db_connect() -> psycopg2.extensions.connection:
    return psycopg2.connect(DB_URL)


def update_db_urls(old_url: str, new_url: str, conn) -> int:
    """
    Update every DB column that stores Supabase image URLs.
    Returns total rows affected.
    """
    if old_url == new_url:
        return 0

    affected = 0
    cur = conn.cursor()

    # 1. project_media – direct URL column
    cur.execute("UPDATE project_media SET file_url = %s WHERE file_url = %s",
                (new_url, old_url))
    affected += cur.rowcount

    # 2. projects – thumbnail column
    cur.execute("UPDATE projects SET thumbnail = %s WHERE thumbnail = %s",
                (new_url, old_url))
    affected += cur.rowcount

    # 3. resale_listings – images is a JSON array; replace the URL inside it
    cur.execute("""
        UPDATE resale_listings
        SET images = REPLACE(images::text, %s, %s)::jsonb
        WHERE images::text LIKE %s
    """, (old_url, new_url, f"%{old_url}%"))
    affected += cur.rowcount

    conn.commit()
    cur.close()
    return affected


# ── Main ──────────────────────────────────────────────────────────────────────
def main(dry_run: bool) -> None:
    mode_label = "DRY-RUN" if dry_run else "LIVE"
    print(f"\n{'='*70}")
    print(f"  Supabase Media Compressor  [{mode_label}]")
    print(f"  Bucket : {BUCKET}")
    print(f"  Target : JPEG q{TARGET_JPEG_QUALITY} · WebP q{TARGET_WEBP_QUALITY} · max {MAX_DIMENSION}px")
    print(f"  Skip   : < {MIN_FILE_SIZE_KB} KB or < {MIN_SAVING_PCT}% savings")
    print(f"{'='*70}\n")

    # ── 1. List all files ─────────────────────────────────────────────────
    print("Listing all files in bucket…")
    all_files = list_all_files()
    print(f"  Found {len(all_files)} objects total\n")

    # Filter to compressible images
    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
    candidates = []
    for f in all_files:
        if not f or not isinstance(f, dict):
            continue
        full_path = f.get("_full_path") or f.get("name", "")
        if Path(full_path).suffix.lower() not in IMAGE_EXTS:
            continue
        meta = f.get("metadata") or {}
        size = meta.get("size", 0) if isinstance(meta, dict) else 0
        if size < MIN_FILE_SIZE_KB * 1024:
            continue
        f["size"] = size   # normalise for later use
        candidates.append(f)

    print(f"  {len(candidates)} images eligible (>= {MIN_FILE_SIZE_KB} KB)\n")

    # ── 2. Set up log CSV ─────────────────────────────────────────────────
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(__file__).parent / f"compress_log_{ts}.csv"
    log_rows: list[dict] = []

    # ── 3. DB connection ──────────────────────────────────────────────────
    conn = None
    if not dry_run:
        conn = db_connect()

    # ── 4. Process each file ──────────────────────────────────────────────
    total_orig   = 0
    total_new    = 0
    ok_count     = 0
    skip_count   = 0
    fail_count   = 0

    for idx, item in enumerate(candidates, 1):
        storage_path = item.get("_full_path") or item["name"]
        orig_size    = item["size"]
        public_url   = make_public_url(storage_path)
        ext          = Path(storage_path).suffix.lower()

        print(f"[{idx:>4}/{len(candidates)}] {storage_path}")
        print(f"           orig {orig_size/1024:>7.1f} KB", end="")

        # Download
        raw = download(public_url)
        if raw is None:
            print("  ✗ download failed")
            fail_count += 1
            log_rows.append({"path": storage_path, "status": "download_failed",
                             "orig_kb": f"{orig_size/1024:.1f}", "new_kb": "", "saved_pct": ""})
            continue

        # Compress
        new_bytes, new_mime = compress_image(raw, storage_path)
        if new_bytes is None:
            print("  ✗ compress failed")
            fail_count += 1
            log_rows.append({"path": storage_path, "status": "compress_failed",
                             "orig_kb": f"{orig_size/1024:.1f}", "new_kb": "", "saved_pct": ""})
            continue

        new_size  = len(new_bytes)
        saved     = orig_size - new_size
        saved_pct = saved / orig_size * 100 if orig_size else 0

        print(f"  →  {new_size/1024:>7.1f} KB  ({saved_pct:+.1f}%)", end="")

        if saved_pct < MIN_SAVING_PCT:
            print("  ⊘ skipped")
            skip_count += 1
            log_rows.append({"path": storage_path, "status": "skipped_low_saving",
                             "orig_kb": f"{orig_size/1024:.1f}",
                             "new_kb":  f"{new_size/1024:.1f}",
                             "saved_pct": f"{saved_pct:.1f}"})
            continue

        total_orig += orig_size
        total_new  += new_size

        if dry_run:
            print("  ✓ [DRY-RUN]")
            ok_count += 1
            log_rows.append({"path": storage_path, "status": "would_compress",
                             "orig_kb": f"{orig_size/1024:.1f}",
                             "new_kb":  f"{new_size/1024:.1f}",
                             "saved_pct": f"{saved_pct:.1f}"})
            continue

        # Build new storage path (PNG → .webp extension)
        if ext == ".png":
            new_storage_path = str(Path(storage_path).with_suffix(".webp"))
        else:
            new_storage_path = storage_path
        new_public_url = make_public_url(new_storage_path)

        # Upload
        ok = upload(new_bytes, new_storage_path, new_mime)
        if not ok:
            print("  ✗ upload failed")
            fail_count += 1
            log_rows.append({"path": storage_path, "status": "upload_failed",
                             "orig_kb": f"{orig_size/1024:.1f}",
                             "new_kb":  f"{new_size/1024:.1f}",
                             "saved_pct": f"{saved_pct:.1f}"})
            continue

        # If PNG was converted, delete the old .png file
        if ext == ".png" and new_storage_path != storage_path:
            old_url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}"
            requests.delete(old_url, headers=STORAGE_HEADERS, timeout=REQUEST_TIMEOUT)

        # Update DB
        db_rows = 0
        try:
            # Reconnect every 50 files to avoid stale connections
            if idx % 50 == 1:
                try:
                    conn.close()
                except Exception:
                    pass
                conn = db_connect()
            db_rows = update_db_urls(public_url, new_public_url, conn)
        except Exception as e:
            print(f"\n    ⚠ DB update error: {e}")
            try:
                conn.close()
            except Exception:
                pass
            conn = db_connect()

        ok_count += 1
        print(f"  ✓  db_rows={db_rows}")
        log_rows.append({"path": storage_path, "status": "compressed",
                         "orig_kb": f"{orig_size/1024:.1f}",
                         "new_kb":  f"{new_size/1024:.1f}",
                         "saved_pct": f"{saved_pct:.1f}",
                         "new_path": new_storage_path,
                         "db_rows": db_rows})

        time.sleep(RATE_LIMIT_SLEEP)

    # ── 5. Close DB ───────────────────────────────────────────────────────
    if conn:
        try:
            conn.close()
        except Exception:
            pass

    # ── 6. Write CSV log ──────────────────────────────────────────────────
    if log_rows:
        fields = ["path", "status", "orig_kb", "new_kb", "saved_pct", "new_path", "db_rows"]
        with open(log_path, "w", newline="", encoding="utf-8") as lf:
            writer = csv.DictWriter(lf, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(log_rows)
        print(f"\n  Log written → {log_path.name}")

    # ── 7. Summary ────────────────────────────────────────────────────────
    saved_total = total_orig - total_new
    print(f"\n{'='*70}")
    print(f"  {'[DRY-RUN] ' if dry_run else ''}SUMMARY")
    print(f"{'='*70}")
    print(f"  Compressed : {ok_count}")
    print(f"  Skipped    : {skip_count}  (< {MIN_SAVING_PCT}% savings or too small)")
    print(f"  Failed     : {fail_count}")
    if ok_count:
        pct = saved_total / total_orig * 100 if total_orig else 0
        print(f"  Space saved: {saved_total/(1024*1024):.2f} MB  ({pct:.1f}% of processed files)")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compress Supabase property-media images in-place")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview what would be done — no files are written")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
