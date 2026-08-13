
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import threading
from datetime import date

app = Flask(__name__)

# Secret key — set FLASK_SECRET_KEY env var in production
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-only-insecure-key')

# CORS: restrict to origins from env var in production
_raw_origins = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:4200')
_allowed_origins = [o.strip() for o in _raw_origins.split(',') if o.strip()]
CORS(app, origins=_allowed_origins)

# Global variable to track scraping status
scraping_status = {
    'is_running': False,
    'current_project': '',
    'completed': 0,
    'total': 0,
    'errors': []
}

# Global mutex — only one scraper may run at a time (prevents portal rate-limiting)
_global_scrape_lock  = threading.Lock()
_active_scraper_name: str | None = None


def _acquire_global_lock(scraper_name: str) -> bool:
    """Try to acquire the global scrape lock. Returns True if acquired, False if busy."""
    global _active_scraper_name
    if _global_scrape_lock.acquire(blocking=False):
        _active_scraper_name = scraper_name
        return True
    return False


def _release_global_lock():
    global _active_scraper_name
    _active_scraper_name = None
    try:
        _global_scrape_lock.release()
    except RuntimeError:
        pass  # already released

def background_bulk_scrape(start_idx):
    """Run bulk scraping in background thread"""
    global scraping_status
    try:
        import rera_detail_scraper
        from pathlib import Path

        # Load pin code filter from preferences (single pincode = restrict detail scrape too)
        pin_code_filter = None
        if os.path.exists(SCRAPE_PREFERENCES_FILE):
            with open(SCRAPE_PREFERENCES_FILE, 'r', encoding='utf-8') as pf:
                prefs = json.load(pf)
            pincodes = [p.strip() for p in prefs.get('pincodes', []) if p.strip()]
            if len(pincodes) == 1:
                pin_code_filter = pincodes[0]
                print(f"[Bulk Scrape] Pin code filter active: {pin_code_filter}")

        # Try to set up floor-plan downloader (optional — won't break scrape if missing)
        fpd = None
        fp_session = None
        try:
            import download_project_docs as _fpd
            from captcha_solver import CaptchaSolver
            _solver = CaptchaSolver()
            _solver.initialize_session()
            fpd = _fpd
            fp_session = _solver.session
            print("[Bulk Scrape] Floor-plan downloader ready")
        except Exception as fe:
            print(f"[Bulk Scrape] Floor-plan downloader unavailable (will skip): {fe}")

        with open(PROJECT_NAMES_FILE, 'r', encoding='utf-8') as f:
            projects = json.load(f)
        
        scraping_status['total'] = len(projects) - start_idx
        scraping_status['is_running'] = True
        
        for idx in range(start_idx, len(projects)):
            project = projects[idx]
            scraping_status['current_project'] = project
            
            try:
                print(f"[Bulk Scrape] Processing {idx + 1}/{len(projects)}: {project}")
                rera_detail_scraper.main(project, pin_code_filter=pin_code_filter)
                scraping_status['completed'] = idx - start_idx + 1
                print(f"[Bulk Scrape] Completed RERA scrape for {project}")

                # Download floor plan images (safe — any error here is non-fatal)
                if fpd and fp_session:
                    project_dir = Path(SCRAPED_PROJECTS_PATH) / project
                    if project_dir.exists():
                        try:
                            print(f"[Bulk Scrape] Downloading floor plans for {project}...")
                            fpd.process_project(project_dir, fp_session)
                        except Exception as fe:
                            print(f"[Bulk Scrape] Floor plan download skipped for {project}: {fe}")

            except Exception as e:
                error_msg = f"Failed {project}: {str(e)}"
                print(f"[Bulk Scrape] {error_msg}")
                scraping_status['errors'].append(error_msg)
        
        scraping_status['is_running'] = False
        scraping_status['current_project'] = ''
        print(f"[Bulk Scrape] FINISHED - Completed {scraping_status['completed']}/{scraping_status['total']}")
        
    except Exception as e:
        scraping_status['is_running'] = False
        scraping_status['errors'].append(f"Fatal error: {str(e)}")
        print(f"[Bulk Scrape] FATAL ERROR: {str(e)}")
    finally:
        _release_global_lock()

SCRAPE_PREFERENCES_FILE = os.path.join(os.path.dirname(__file__), 'scrape_preferences.json')
PROJECT_NAMES_FILE = os.path.join(os.path.dirname(__file__), 'all_project_names.json')

@app.route('/api/scrape-preferences', methods=['GET'])
def get_scrape_preferences():
    """Return saved scrape preferences (pincodes + IGRS credentials)"""
    try:
        if os.path.exists(SCRAPE_PREFERENCES_FILE):
            with open(SCRAPE_PREFERENCES_FILE, 'r', encoding='utf-8') as f:
                prefs = json.load(f)
        else:
            prefs = {'pincodes': []}
        # Always return all fields; mask password as empty string if not set
        return jsonify({
            'pincodes': prefs.get('pincodes', []),
            'igrs_username': prefs.get('igrs_username', ''),
            'igrs_password': prefs.get('igrs_password', ''),
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/scrape-preferences', methods=['POST'])
def save_scrape_preferences():
    """Save scrape preferences (pincodes + IGRS credentials)"""
    try:
        prefs = request.json or {}
        pincodes = [p.strip() for p in prefs.get('pincodes', []) if p.strip()]
        igrs_username = prefs.get('igrs_username', '').strip()
        igrs_password = prefs.get('igrs_password', '')
        data = {
            'pincodes': pincodes,
            'igrs_username': igrs_username,
            'igrs_password': igrs_password,
        }
        with open(SCRAPE_PREFERENCES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return jsonify({'status': 'success', 'message': f'Saved preferences ({len(pincodes)} pincodes).', 'preferences': data})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def _do_fetch_project_names():
    """Shared logic: fetch project names from GIS and save to file. Returns count."""
    prefs = {'pincodes': []}
    if os.path.exists(SCRAPE_PREFERENCES_FILE):
        with open(SCRAPE_PREFERENCES_FILE, 'r', encoding='utf-8') as f:
            prefs = json.load(f)
    import ProjectNameRetriever
    return ProjectNameRetriever.fetch_all_project_names(
        filter_pincodes=prefs.get('pincodes', [])
    )

@app.route('/api/fetch_project_names', methods=['POST'])
def fetch_project_names():
    try:
        result = _do_fetch_project_names()
        return jsonify({'status': 'success', 'message': f'Fetched {result} project names matching your pincodes.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/scrape_project', methods=['POST'])
def scrape_project():
    # Scrape a single project by name
    project_name = request.json.get('project_name')
    try:
        import rera_detail_scraper
        result = rera_detail_scraper.main(project_name)
        return jsonify({'status': 'success', 'result': result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/bulk_scrape', methods=['POST'])
def bulk_scrape():
    """Start bulk scraping in background - returns immediately"""
    print("=" * 60)
    print("[BULK_SCRAPE] ENDPOINT HIT - NEW THREADING CODE!")
    print("=" * 60)
    global scraping_status
    
    if scraping_status['is_running']:
        return jsonify({
            'status': 'error', 
            'message': 'Bulk scraping is already running',
            'scraping_status': scraping_status
        }), 400

    if not _acquire_global_lock('RERA Bulk Scrape'):
        return jsonify({
            'status': 'error',
            'message': f'Another scraper is already running: {_active_scraper_name}. Please wait for it to finish.'
        }), 400
    
    start_idx = request.json.get('start_idx', 0) if request.json else 0

    # Auto-fetch project names if file doesn't exist yet
    if not os.path.exists(PROJECT_NAMES_FILE):
        try:
            print('[Bulk Scrape] all_project_names.json not found — auto-fetching from GIS...')
            count = _do_fetch_project_names()
            print(f'[Bulk Scrape] Auto-fetched {count} project names.')
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Failed to fetch project names automatically: {str(e)}'
            }), 500

    try:
        # Reset status
        scraping_status = {
            'is_running': True,
            'current_project': 'Starting...',
            'completed': 0,
            'total': 0,
            'errors': []
        }
        
        # Start scraping in background thread
        thread = threading.Thread(target=background_bulk_scrape, args=(start_idx,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'status': 'success', 
            'message': f'Bulk scraping started from index {start_idx}. Use /api/scraping_status to check progress.'
        })
    except Exception as e:
        scraping_status['is_running'] = False
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/scraping_status', methods=['GET'])
def get_scraping_status():
    """Get current scraping progress"""
    return jsonify(scraping_status)

# Use scraped_projects folder INSIDE backend directory (where scraper saves data)
SCRAPED_PROJECTS_PATH = os.path.join(os.path.dirname(__file__), 'scraped_projects')
SHORTLISTED_FIELDS = [
    'Project Name', 'Project Status', 'Project Type', 'Approved Date', 'Proposed Date of Completion',
    'Total Area(In sqmts)', 'Net Area(In sqmts)', 'Approved Built up Area (In Sqmts)', 'Mortgage Area (In Sqmts)',
    'Boundaries East', 'Boundaries West', 'Boundaries North', 'Boundaries South',
    'State', 'District', 'Mandal', 'Village/City/Town', 'Pin Code', 'Street', 'Locality', 'Land mark',
    'Name', 'Organization Type', 'Do you have any Past Experience ?', 'Any criminal or police case/ cases pending ?',
    'Authority Name', 'Plan Approval Number', 'Sy.No/TS No.', 'Bank Name', 'Branch Name'
]

def extract_fields(data):
    result = {}
    def flatten(d, prefix=""):
        for k, v in d.items():
            if isinstance(v, dict):
                flatten(v, prefix)
            else:
                key = k if not prefix else k
                if key in SHORTLISTED_FIELDS:
                    result[key] = v
    flatten(data)
    return result

@app.route('/api/projects', methods=['GET'])
def get_projects():
    # PHASE 3: This endpoint is removed. The .NET API is now the sole data API.
    # The Angular frontend must call the .NET API at /api/projects instead.
    # Kept as a stub returning 410 Gone so callers get a clear error.
    return jsonify({
        'error': 'removed',
        'message': 'This endpoint has been removed. Use the .NET API at port 5001 for project data.'
    }), 410


# ──────────────────────────────────────────────────────────────────────────────
# SRO Transaction Scraping
# ──────────────────────────────────────────────────────────────────────────────

SRO_TRANSACTIONS_FILE = os.path.join(os.path.dirname(__file__), 'scraped_projects', 'sro_transactions.json')

sro_scrape_status = {
    'is_running': False,
    'message': 'Idle',
    'total_records': 0,
    'new_records': 0,
    'error': None
}

_sro_data_cache = None
_sro_cache_mtime = 0


def _load_sro_data():
    """Load and cache sro_transactions.json. Returns the full data dict or {}."""
    global _sro_data_cache, _sro_cache_mtime
    if not os.path.exists(SRO_TRANSACTIONS_FILE):
        return {}
    try:
        mt = os.path.getmtime(SRO_TRANSACTIONS_FILE)
        if _sro_data_cache is None or mt > _sro_cache_mtime:
            with open(SRO_TRANSACTIONS_FILE, 'r', encoding='utf-8') as f:
                _sro_data_cache = json.load(f)
            _sro_cache_mtime = mt
        return _sro_data_cache
    except Exception:
        return {}


def _compute_city_quarterly(records: list) -> dict:
    """Compute city-wide quarterly {quarter: {avg_price_sqft, total_volume, count}}."""
    from collections import defaultdict
    buckets = defaultdict(lambda: {'prices': [], 'total_volume': 0, 'count': 0})
    for r in records:
        q = r.get('quarter', '')
        p = r.get('price_per_sqft', 0)
        v = max(r.get('mkt_value', 0), r.get('cons_value', 0))
        if q and p > 0:
            buckets[q]['prices'].append(p)
            buckets[q]['total_volume'] += v
            buckets[q]['count'] += 1
    result = {}
    for q, data in sorted(buckets.items()):
        prices = data['prices']
        result[q] = {
            'avg_price_sqft': round(sum(prices) / len(prices), 1) if prices else 0,
            'median_price_sqft': round(sorted(prices)[len(prices)//2], 1) if prices else 0,
            'total_volume': data['total_volume'],
            'count': data['count'],
        }
    return result


def _compute_village_quarterly(records: list) -> dict:
    """Compute per-village quarterly {village: {quarter: {avg_price_sqft, total_volume, count}}}."""
    from collections import defaultdict
    buckets = defaultdict(lambda: defaultdict(lambda: {'prices': [], 'total_volume': 0, 'count': 0}))
    for r in records:
        q = r.get('quarter', '')
        p = r.get('price_per_sqft', 0)
        v = max(r.get('mkt_value', 0), r.get('cons_value', 0))
        village = r.get('village', '').strip()
        if q and p > 0 and village:
            buckets[village][q]['prices'].append(p)
            buckets[village][q]['total_volume'] += v
            buckets[village][q]['count'] += 1
    result = {}
    for village, quarters in sorted(buckets.items()):
        qdata = {}
        for q, data in sorted(quarters.items()):
            prices = data['prices']
            qdata[q] = {
                'avg_price_sqft': round(sum(prices) / len(prices), 1) if prices else 0,
                'total_volume': data['total_volume'],
                'count': data['count'],
            }
        if qdata:
            result[village] = qdata
    return result


def _run_sro_scrape(sro_names, years):
    global sro_scrape_status
    try:
        import sro_transaction_scraper as sro_mod
        if sro_names:
            # Explicit filter from API caller
            sros_filter = [s for s in sro_mod.TARGET_SROS
                           if any(n.upper() in s['name'].upper() for n in sro_names)]
        else:
            # Derive from scrape_preferences.json pincodes automatically
            sros_filter = sro_mod.get_active_sros()
        sro_scrape_status['message'] = f'Scraping {len(sros_filter)} SROs × {len(years) or len(sro_mod.SCRAPE_YEARS)} years…'
        result_records = sro_mod.run_scraper(sros_filter, years or sro_mod.SCRAPE_YEARS)
        n = len(result_records) if result_records else 0
        sro_scrape_status.update({
            'is_running': False,
            'message': f'Done — {n} apartment sale deed records',
            'total_records': n,
            'new_records': n,
            'error': None
        })
    except Exception as e:
        sro_scrape_status.update({
            'is_running': False,
            'message': 'Error',
            'error': str(e)
        })
    finally:
        _release_global_lock()


@app.route('/api/sro_scrape', methods=['POST'])
def start_sro_scrape():
    """Start SRO transaction scraping in background."""
    global sro_scrape_status
    if sro_scrape_status['is_running']:
        return jsonify({'status': 'error', 'message': 'SRO scraping already running'}), 400

    if not _acquire_global_lock('SRO Transaction Scrape'):
        return jsonify({'status': 'error', 'message': f'Another scraper is already running: {_active_scraper_name}. Please wait.'}), 400

    body      = request.json or {}
    sro_names = body.get('sros', [])
    years     = body.get('years', [])

    sro_scrape_status = {
        'is_running': True,
        'message': 'Starting…',
        'total_records': 0,
        'new_records': 0,
        'error': None
    }
    t = threading.Thread(target=_run_sro_scrape, args=(sro_names, years))
    t.daemon = True
    t.start()
    return jsonify({'status': 'success', 'message': 'SRO scraping started'})


@app.route('/api/sro_scrape/stop', methods=['POST'])
def stop_sro_scrape():
    return jsonify({'status': 'error', 'message': 'Stop not implemented in new scraper'}), 400


@app.route('/api/sro_scrape/status', methods=['GET'])
def get_sro_scrape_status():
    return jsonify(sro_scrape_status)


@app.route('/api/sro_transactions', methods=['GET'])
def get_sro_transactions():
    """Return raw apartment sale deed records."""
    data = _load_sro_data()
    records = data.get('records', [])
    district = request.args.get('district', '').lower()
    village  = request.args.get('village', '').lower()
    year     = request.args.get('year', '')
    if district:
        records = [r for r in records if district in (r.get('district','') or '').lower()]
    if village:
        records = [r for r in records if village in (r.get('village','') or '').lower()]
    if year:
        records = [r for r in records if (r.get('reg_date','') or '').startswith(year)]
    return jsonify(records)


@app.route('/api/sro_transactions/aggregate', methods=['GET'])
def get_sro_aggregate():
    data = _load_sro_data()
    return jsonify({
        'quarterly_by_sro':     data.get('quarterly_by_sro', []),
        'quarterly_by_village': data.get('quarterly_by_village', []),
        'total_records': data.get('total_records', 0),
    })


@app.route('/api/sro/aggregate/city', methods=['GET'])
def sro_aggregate_city():
    """City-wide quarterly aggregation: {quarter: {avg_price_sqft, total_volume, count}}"""
    data    = _load_sro_data()
    records = data.get('records', [])
    if not records:
        return jsonify({})
    return jsonify(_compute_city_quarterly(records))


@app.route('/api/sro/aggregate/locality', methods=['GET'])
def sro_aggregate_locality():
    """Per-village quarterly: {village: {quarter: {avg_price_sqft, total_volume, count}}}"""
    data    = _load_sro_data()
    records = data.get('records', [])
    if not records:
        return jsonify({})
    agg = _compute_village_quarterly(records)
    locality = request.args.get('locality', '')
    if locality:
        for k in agg:
            if locality.lower() in k.lower():
                return jsonify({k: agg[k]})
        return jsonify({})
    return jsonify(agg)


@app.route('/api/sro/rank/price', methods=['GET'])
def sro_rank_price():
    """Top villages by avg price/sqft in latest (or specified) quarter."""
    data    = _load_sro_data()
    records = data.get('records', [])
    if not records:
        return jsonify({'quarter': '', 'rank': []})
    top     = int(request.args.get('top', 10))
    quarter = request.args.get('quarter', '')
    agg     = _compute_village_quarterly(records)
    if not quarter:
        all_qs = {q for vd in agg.values() for q in vd}
        quarter = max(all_qs) if all_qs else ''
    if not quarter:
        return jsonify({'quarter': '', 'rank': []})
    rank = sorted(
        [{'locality': village,
          'avg_price_sqft': vdata[quarter]['avg_price_sqft'],
          'count': vdata[quarter]['count']}
         for village, vdata in agg.items()
         if quarter in vdata and vdata[quarter].get('avg_price_sqft', 0) > 0],
        key=lambda x: x['avg_price_sqft'], reverse=True
    )[:top]
    return jsonify({'quarter': quarter, 'rank': rank})


@app.route('/api/sro/rank/volume', methods=['GET'])
def sro_rank_volume():
    """Top villages by transaction volume in latest (or specified) quarter."""
    data    = _load_sro_data()
    records = data.get('records', [])
    if not records:
        return jsonify({'quarter': '', 'rank': []})
    top     = int(request.args.get('top', 10))
    quarter = request.args.get('quarter', '')
    agg     = _compute_village_quarterly(records)
    if not quarter:
        all_qs = {q for vd in agg.values() for q in vd}
        quarter = max(all_qs) if all_qs else ''
    if not quarter:
        return jsonify({'quarter': '', 'rank': []})
    rank = sorted(
        [{'locality': village,
          'total_volume': vdata[quarter].get('total_volume', 0),
          'count': vdata[quarter].get('count', 0)}
         for village, vdata in agg.items()
         if quarter in vdata],
        key=lambda x: x['total_volume'], reverse=True
    )[:top]
    return jsonify({'quarter': quarter, 'rank': rank})


@app.route('/api/sro/scrape/status', methods=['GET'])
def sro_scrape_status_v2():
    return jsonify(sro_scrape_status)


@app.route('/api/sro/scrape', methods=['POST'])
def start_sro_scrape_v2():
    return start_sro_scrape()


@app.route('/api/sro/scrape/stop', methods=['POST'])
def stop_sro_scrape_v2():
    return stop_sro_scrape()


# ──────────────────────────────────────────────────────────────────────────────
# Ready Reckoner (Unit Rate) Scraping — IGRS Telangana
# ──────────────────────────────────────────────────────────────────────────────

UNIT_RATES_FILE = os.path.join(os.path.dirname(__file__), 'scraped_projects', 'unit_rates.json')

rr_scrape_status = {
    'is_running':   False,
    'message':      'Idle',
    'total_records': 0,
    'pincodes':     [],
    'error':        None,
}

_active_rr_scraper = None


def _run_rr_scrape(pincodes: list):
    global rr_scrape_status, _active_rr_scraper
    try:
        import rr_scraper as rr
        scraper = rr.RRApiScraper(
            pincodes=pincodes if pincodes else None,
            progress_callback=lambda msg: rr_scrape_status.update({'message': msg})
        )
        _active_rr_scraper = scraper
        results = scraper.run()
        rr_scrape_status.update({
            'is_running':    False,
            'message':       f'Done — {len(results)} unit-rate records saved',
            'total_records': len(results),
            'error':         None,
        })
    except Exception as e:
        rr_scrape_status.update({
            'is_running': False,
            'message':    'Error',
            'error':      str(e),
        })
    finally:
        _active_rr_scraper = None
        _release_global_lock()


@app.route('/api/rr_scrape', methods=['POST'])
def start_rr_scrape():
    """Start Ready Reckoner unit-rate scraping in background."""
    global rr_scrape_status
    if rr_scrape_status['is_running']:
        return jsonify({'status': 'error', 'message': 'RR scraping already running'}), 400

    if not _acquire_global_lock('Ready Reckoner Scrape'):
        return jsonify({'status': 'error', 'message': f'Another scraper is already running: {_active_scraper_name}. Please wait.'}), 400

    body     = request.json or {}
    pincodes = body.get('pincodes', [])

    # Read from preferences file if not supplied
    if not pincodes and os.path.exists(SCRAPE_PREFERENCES_FILE):
        with open(SCRAPE_PREFERENCES_FILE, 'r', encoding='utf-8') as f:
            pincodes = json.load(f).get('pincodes', [])

    rr_scrape_status = {
        'is_running':    True,
        'message':       'Starting…',
        'total_records': 0,
        'pincodes':      pincodes,
        'error':         None,
    }
    t = threading.Thread(target=_run_rr_scrape, args=(pincodes,))
    t.daemon = True
    t.start()
    return jsonify({'status': 'success', 'message': 'RR scraping started',
                    'pincodes': pincodes})


@app.route('/api/rr_scrape/stop', methods=['POST'])
def stop_rr_scrape():
    global _active_rr_scraper
    if _active_rr_scraper:
        _active_rr_scraper.request_stop()
        return jsonify({'status': 'success', 'message': 'Stop requested'})
    return jsonify({'status': 'error', 'message': 'No active RR scraper'}), 400


@app.route('/api/rr_scrape/status', methods=['GET'])
def get_rr_scrape_status():
    return jsonify(rr_scrape_status)


@app.route('/api/unit_rates', methods=['GET'])
def get_unit_rates():
    """
    Return scraped unit rates.
    Optional query params: district, mandal, locality
    """
    if not os.path.exists(UNIT_RATES_FILE):
        return jsonify({'scraped_at': None, 'total': 0, 'records': []})

    with open(UNIT_RATES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    records = data.get('records', [])

    district = request.args.get('district', '').lower()
    mandal   = request.args.get('mandal',   '').lower()
    locality = request.args.get('locality', '').lower()

    if district:
        records = [r for r in records if district in (r.get('district') or '').lower()]
    if mandal:
        records = [r for r in records if mandal in (r.get('mandal') or '').lower()]
    if locality:
        records = [r for r in records if locality in (r.get('locality') or '').lower()]

    return jsonify({'scraped_at': data.get('scraped_at'), 'total': len(records), 'records': records})


@app.route('/api/unit_rates/summary', methods=['GET'])
def get_unit_rates_summary():
    """
    Returns a per-mandal summary with both land_rate_sqft and apartment_rate_sqft.
    Records without search_type field are treated as apartment (backward compat).
    """
    if not os.path.exists(UNIT_RATES_FILE):
        return jsonify([])

    with open(UNIT_RATES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    from collections import defaultdict
    land_agg  = defaultdict(list)
    apt_agg   = defaultdict(list)
    district_map = {}

    for r in data.get('records', []):
        mandal   = (r.get('mandal') or r.get('locality') or r.get('village') or 'Unknown').strip().upper()
        district = (r.get('district') or '').strip().upper()
        rate     = r.get('unit_rate_sqft')
        if not rate or rate <= 100:
            continue
        district_map[mandal] = district
        stype = r.get('search_type', 'apartment')
        if stype == 'land':
            land_agg[mandal].append(rate)
        else:
            apt_agg[mandal].append(rate)

    all_mandals = set(land_agg.keys()) | set(apt_agg.keys())
    summary = []
    for mandal in all_mandals:
        land_rates = land_agg.get(mandal, [])
        apt_rates  = apt_agg.get(mandal, [])
        apt_avg    = round(sum(apt_rates) / len(apt_rates), 0) if apt_rates else None
        land_avg   = round(sum(land_rates) / len(land_rates), 0) if land_rates else None
        summary.append({
            'mandal':              mandal,
            'locality':            mandal,   # backward compat alias
            'district':            district_map.get(mandal, ''),
            'apartment_rate_sqft': apt_avg,
            'land_rate_sqft':      land_avg,
            'avg_rate_sqft':       apt_avg or land_avg or 0,  # backward compat
            'count':               len(land_rates) + len(apt_rates),
        })

    summary.sort(key=lambda x: x['avg_rate_sqft'], reverse=True)
    return jsonify(summary)


@app.route('/api/sro_project_units', methods=['GET'])
def get_sro_project_units():
    """
    Return registration/sales status for a RERA project matched against SRO apartment registrations.
    Returns total registered units (deeds), unique flat numbers, and quarterly breakdown.
    Query param: name = RERA project name
    """
    import re

    def _norm(s: str) -> str:
        s = s.upper()
        s = re.sub(r'["\'\u201c\u201d\u2018\u2019]', '', s)
        s = re.sub(r'\b(BLOCK|TOWER|PHASE|WING|BLK|TWR|SECTOR)[\s\-]*[A-Z0-9]+\b', '', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return s

    name = request.args.get('name', '').strip()
    if not name or len(name) < 4:
        return jsonify({'found': False, 'total_registered': 0, 'by_quarter': [], 'matched_apartments': []})

    query_norm = _norm(name)
    if len(query_norm) < 4:
        return jsonify({'found': False, 'total_registered': 0, 'by_quarter': [], 'matched_apartments': []})

    data    = _load_sro_data()
    records = data.get('records', [])

    matched = [
        r for r in records
        if (lambda a: a == query_norm or a.startswith(query_norm + ' ') or query_norm in a)(_norm(r.get('apartment', '')))
    ]

    if not matched:
        return jsonify({'found': False, 'total_registered': 0, 'by_quarter': [], 'matched_apartments': []})

    from collections import defaultdict
    quarter_counts: dict = defaultdict(lambda: {'count': 0, 'flat_nos': set(), 'total_value': 0})
    all_flat_nos = set()
    total_value = 0

    for r in matched:
        q = r.get('quarter', 'Unknown')
        flat_no = str(r.get('flat_no', '')).strip()
        value = max(r.get('mkt_value', 0) or 0, r.get('cons_value', 0) or 0)
        quarter_counts[q]['count'] += 1
        if flat_no:
            quarter_counts[q]['flat_nos'].add(flat_no)
            all_flat_nos.add(flat_no)
        quarter_counts[q]['total_value'] += value
        total_value += value

    by_quarter = sorted([
        {
            'quarter': q,
            'count': d['count'],
            'unique_flats': len(d['flat_nos']),
            'total_value_cr': round(d['total_value'] / 1e7, 2)
        }
        for q, d in quarter_counts.items()
    ], key=lambda x: x['quarter'])

    # Most recent quarter
    recent = by_quarter[-1] if by_quarter else {}
    matched_apts = sorted({r.get('apartment', '') for r in matched})[:20]

    return jsonify({
        'found': True,
        'total_registered': len(matched),
        'unique_flats_registered': len(all_flat_nos),
        'total_value_cr': round(total_value / 1e7, 2),
        'by_quarter': by_quarter,
        'recent_quarter': recent.get('quarter', ''),
        'recent_count': recent.get('count', 0),
        'matched_apartments': matched_apts,
    })


@app.route('/api/sro_project_trend', methods=['GET'])
def get_sro_project_trend():
    """
    Return quarterly price trend for a RERA project matched against SRO apartment registrations.
    Query param: name = RERA project name (e.g. "ASBL Lakeside")
    """
    import re

    def _norm(s: str) -> str:
        s = s.upper()
        s = re.sub(r'["\'\u201c\u201d\u2018\u2019]', '', s)
        # remove block/tower/phase/wing suffixes with optional separators and alphanumeric identifiers
        s = re.sub(r'\b(BLOCK|TOWER|PHASE|WING|BLK|TWR|SECTOR)[\s\-]*[A-Z0-9]+\b', '', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return s

    name = request.args.get('name', '').strip()
    if not name or len(name) < 4:
        return jsonify({'found': False, 'quarters': [], 'matched_apartments': [], 'total_transactions': 0})

    query_norm = _norm(name)
    if len(query_norm) < 4:
        return jsonify({'found': False, 'quarters': [], 'matched_apartments': [], 'total_transactions': 0})

    data    = _load_sro_data()
    records = data.get('records', [])

    matched = [
        r for r in records
        if (lambda a: a == query_norm or a.startswith(query_norm + ' ') or query_norm in a)(_norm(r.get('apartment', '')))
    ]

    if not matched:
        return jsonify({'found': False, 'quarters': [], 'matched_apartments': [], 'total_transactions': 0})

    from collections import defaultdict
    buckets: dict = defaultdict(lambda: {'prices': [], 'total_volume': 0, 'count': 0})
    for r in matched:
        q = r.get('quarter', '')
        p = r.get('price_per_sqft', 0)
        v = max(r.get('mkt_value', 0) or 0, r.get('cons_value', 0) or 0)
        if q and p and p > 0:
            buckets[q]['prices'].append(p)
            buckets[q]['total_volume'] += v
            buckets[q]['count'] += 1

    quarters = []
    for q, d in sorted(buckets.items()):
        prices = d['prices']
        quarters.append({
            'quarter': q,
            'avg_price_sqft': round(sum(prices) / len(prices), 0) if prices else 0,
            'count': d['count'],
            'total_volume_cr': round(d['total_volume'] / 1e7, 2),
        })

    matched_apts = sorted({r.get('apartment', '') for r in matched})[:20]

    return jsonify({
        'found': True,
        'quarters': quarters,
        'matched_apartments': matched_apts,
        'total_transactions': len(matched),
    })


if __name__ == '__main__':
    # In production (Railway), PORT is provided via environment variable
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', '').lower() in ['1', 'true', 'yes'])
