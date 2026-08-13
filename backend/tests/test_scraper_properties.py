"""
Property-Based Tests for Python Scraper Database Writes
========================================================

**Validates: Requirements 2.1**

This module contains property-based tests for the RERA scraper's
``save_project_to_db()`` upsert logic. Because the tests must run without a
live PostgreSQL database, psycopg2 connections and cursors are fully mocked via
``unittest.mock``. Idempotency is verified by inspecting the SQL calls made to
the mock cursor rather than querying an actual DB.

Conceptual live-DB version
--------------------------
In a live-database test the assertion would be:

    1. Call ``save_project_to_db(conn, project_id, payload_v1)``
    2. Call ``save_project_to_db(conn, project_id, payload_v2)``
    3. ``cur.execute("SELECT COUNT(*) FROM projects WHERE id = %s", (project_id,))``
       → assert fetchone()[0] == 1   (exactly one row — no duplicates)
    4. ``cur.execute("SELECT raw_data FROM projects WHERE id = %s", (project_id,))``
       raw = fetchone()[0]
       → assert raw == payload_v2   (second write wins — ON CONFLICT DO UPDATE)

The mock-based tests below validate the same semantic guarantees by asserting
that the correct SQL (containing the ON CONFLICT … DO UPDATE clause) was issued
on each call, and that the second call carries the updated raw_data payload.
"""

import json
import sys
import os
import unittest
from unittest.mock import MagicMock, patch, call
import pytest

# ---------------------------------------------------------------------------
# Ensure backend/ is importable regardless of where pytest is invoked from
# ---------------------------------------------------------------------------
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


# ---------------------------------------------------------------------------
# Hypothesis (property-based testing library) setup
# ---------------------------------------------------------------------------
try:
    from hypothesis import given, settings, assume
    import hypothesis.strategies as st
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Import the function under test
# The file defines save_project_to_db twice; Python keeps the *last* definition
# so we always get the most complete version.
# ---------------------------------------------------------------------------
# We import selectively to avoid triggering top-level Selenium imports that
# would fail in a CI environment without a browser.  We use importlib to load
# the module with the heavy imports mocked out.
import importlib
import types


def _import_save_project_to_db():
    """Import save_project_to_db from rera_detail_scraper with heavy deps mocked."""
    # Build a minimal stub module to satisfy Selenium/captcha imports
    selenium_stub = types.ModuleType("selenium")
    selenium_stub.webdriver = types.ModuleType("selenium.webdriver")
    selenium_stub.webdriver.chrome = types.ModuleType("selenium.webdriver.chrome")
    selenium_stub.webdriver.chrome.options = types.ModuleType("selenium.webdriver.chrome.options")
    selenium_stub.webdriver.chrome.options.Options = MagicMock()
    selenium_stub.webdriver.chrome.service = types.ModuleType("selenium.webdriver.chrome.service")
    selenium_stub.webdriver.chrome.service.Service = MagicMock()
    selenium_stub.webdriver.support = types.ModuleType("selenium.webdriver.support")
    selenium_stub.webdriver.support.ui = types.ModuleType("selenium.webdriver.support.ui")
    selenium_stub.webdriver.support.ui.WebDriverWait = MagicMock()
    selenium_stub.webdriver.support.expected_conditions = MagicMock()
    selenium_stub.webdriver.common = types.ModuleType("selenium.webdriver.common")
    selenium_stub.webdriver.common.by = types.ModuleType("selenium.webdriver.common.by")
    selenium_stub.webdriver.common.by.By = MagicMock()
    selenium_stub.webdriver.Chrome = MagicMock()
    selenium_stub.webdriver.support.expected_conditions = MagicMock()

    wdm_stub = types.ModuleType("webdriver_manager")
    wdm_chrome_stub = types.ModuleType("webdriver_manager.chrome")
    wdm_chrome_stub.ChromeDriverManager = MagicMock()

    captcha_stub = types.ModuleType("captcha_solver")
    captcha_stub.CaptchaSolver = MagicMock()

    bs4_stub = types.ModuleType("bs4")
    bs4_stub.BeautifulSoup = MagicMock()

    requests_stub = types.ModuleType("requests")

    db_utils_stub = types.ModuleType("db_utils")
    db_utils_stub.get_connection = MagicMock()

    mocks = {
        "selenium": selenium_stub,
        "selenium.webdriver": selenium_stub.webdriver,
        "selenium.webdriver.chrome": selenium_stub.webdriver.chrome,
        "selenium.webdriver.chrome.options": selenium_stub.webdriver.chrome.options,
        "selenium.webdriver.chrome.service": selenium_stub.webdriver.chrome.service,
        "selenium.webdriver.support": selenium_stub.webdriver.support,
        "selenium.webdriver.support.ui": selenium_stub.webdriver.support.ui,
        "selenium.webdriver.support.expected_conditions": MagicMock(),
        "selenium.webdriver.common": selenium_stub.webdriver.common,
        "selenium.webdriver.common.by": selenium_stub.webdriver.common.by,
        "webdriver_manager": wdm_stub,
        "webdriver_manager.chrome": wdm_chrome_stub,
        "captcha_solver": captcha_stub,
        "bs4": bs4_stub,
        "requests": requests_stub,
        "db_utils": db_utils_stub,
    }

    with patch.dict(sys.modules, mocks):
        spec = importlib.util.spec_from_file_location(
            "rera_detail_scraper",
            os.path.join(_BACKEND_DIR, "rera_detail_scraper.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

    return mod.save_project_to_db


save_project_to_db = _import_save_project_to_db()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_conn():
    """Return a mock psycopg2 connection with a usable cursor context manager."""
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    # Make `with conn.cursor() as cur:` work
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


def _extract_execute_calls(mock_cursor):
    """Return all positional args passed to cursor.execute()."""
    return [c.args for c in mock_cursor.execute.call_args_list]


UPSERT_KEYWORD = "ON CONFLICT"

SAMPLE_PROJECT_ID = "test_project_abc"

PAYLOAD_V1 = {
    "Project Name": "Test Project ABC",
    "Project Status": "Ongoing",
    "District": "Rangareddy",
    "Mandal": "Kondapur",
    "Locality": "Madhapur",
    "Pin Code": "500075",
    "Village/City/Town": "Hyderabad",
    "totalFlats": "120",
    "totalBookedFlats": "45",
    "version": "v1",
}

PAYLOAD_V2 = {
    **PAYLOAD_V1,
    "Project Status": "Completed",
    "totalBookedFlats": "120",
    "version": "v2",
}


# ===========================================================================
# Property 1: Scraper Upsert Idempotency
# ===========================================================================
# **Validates: Requirements 2.1**
#
# For any project data payload, running save_project_to_db() twice for the
# same project_id must:
#   a) issue the upsert SQL (ON CONFLICT … DO UPDATE) on each call, and
#   b) pass the second call's raw_data as the payload (second write wins).
# ===========================================================================


class TestUpsertIdempotency(unittest.TestCase):
    """
    Property 1 — Scraper Upsert Idempotency

    **Validates: Requirements 2.1**
    """

    def _call_twice(self, project_id, payload_v1, payload_v2):
        """Helper: call save_project_to_db twice and return the cursor mock."""
        mock_conn, mock_cursor = _make_mock_conn()
        save_project_to_db(mock_conn, project_id, payload_v1)
        save_project_to_db(mock_conn, project_id, payload_v2)
        return mock_cursor

    # ------------------------------------------------------------------
    # Test A: Upsert SQL is called exactly twice
    # ------------------------------------------------------------------
    def test_upsert_called_twice_for_same_project_id(self):
        """Calling save_project_to_db twice must issue the upsert SQL twice."""
        mock_cursor = self._call_twice(SAMPLE_PROJECT_ID, PAYLOAD_V1, PAYLOAD_V2)
        calls = _extract_execute_calls(mock_cursor)
        self.assertEqual(
            len(calls),
            2,
            f"Expected cursor.execute() to be called twice, got {len(calls)} times.",
        )

    # ------------------------------------------------------------------
    # Test B: Both SQL calls contain the ON CONFLICT … DO UPDATE clause
    # ------------------------------------------------------------------
    def test_both_calls_use_on_conflict_upsert_sql(self):
        """Both SQL executions must include ON CONFLICT to guarantee idempotency."""
        mock_cursor = self._call_twice(SAMPLE_PROJECT_ID, PAYLOAD_V1, PAYLOAD_V2)
        calls = _extract_execute_calls(mock_cursor)
        for idx, (sql, *_) in enumerate(calls):
            self.assertIn(
                UPSERT_KEYWORD,
                sql.upper(),
                f"Call #{idx + 1} SQL is missing 'ON CONFLICT': {sql[:200]}",
            )

    # ------------------------------------------------------------------
    # Test C: ON CONFLICT targets the primary key (id column)
    # ------------------------------------------------------------------
    def test_on_conflict_targets_id_column(self):
        """ON CONFLICT must be ON CONFLICT (id) — targeting the PK."""
        mock_cursor = self._call_twice(SAMPLE_PROJECT_ID, PAYLOAD_V1, PAYLOAD_V2)
        calls = _extract_execute_calls(mock_cursor)
        for idx, (sql, *_) in enumerate(calls):
            self.assertIn(
                "ON CONFLICT (id)",
                sql,
                f"Call #{idx + 1} SQL does not use ON CONFLICT (id): {sql[:200]}",
            )

    # ------------------------------------------------------------------
    # Test D: DO UPDATE SET includes raw_data
    # ------------------------------------------------------------------
    def test_on_conflict_updates_raw_data(self):
        """The DO UPDATE clause must set raw_data so the latest scrape wins."""
        mock_cursor = self._call_twice(SAMPLE_PROJECT_ID, PAYLOAD_V1, PAYLOAD_V2)
        calls = _extract_execute_calls(mock_cursor)
        for idx, (sql, *_) in enumerate(calls):
            self.assertIn(
                "raw_data",
                sql,
                f"Call #{idx + 1} SQL does not update raw_data: {sql[:200]}",
            )
            self.assertIn(
                "DO UPDATE",
                sql.upper(),
                f"Call #{idx + 1} SQL is missing DO UPDATE clause: {sql[:200]}",
            )

    # ------------------------------------------------------------------
    # Test E: The second call carries the updated raw_data (second write wins)
    # ------------------------------------------------------------------
    def test_second_call_carries_updated_raw_data(self):
        """
        The second invocation's SQL parameters must contain the second payload,
        not the first — confirming that the most-recent scrape data would win
        in a real DB via ON CONFLICT DO UPDATE SET raw_data = EXCLUDED.raw_data.
        """
        mock_cursor = self._call_twice(SAMPLE_PROJECT_ID, PAYLOAD_V1, PAYLOAD_V2)
        calls = _extract_execute_calls(mock_cursor)

        # The last positional param should be json.dumps(payload)
        _, *params_v2 = calls[1]
        raw_data_param = params_v2[0][-1]  # last param in the tuple
        deserialized = json.loads(raw_data_param)
        self.assertEqual(
            deserialized.get("version"),
            "v2",
            "Second call must carry the v2 payload (most recent scrape wins).",
        )

    # ------------------------------------------------------------------
    # Test F: project_id is passed as the first SQL parameter on both calls
    # ------------------------------------------------------------------
    def test_project_id_is_first_parameter_on_both_calls(self):
        """project_id must be the first bind parameter in both execute calls."""
        mock_cursor = self._call_twice(SAMPLE_PROJECT_ID, PAYLOAD_V1, PAYLOAD_V2)
        calls = _extract_execute_calls(mock_cursor)
        for idx, (_, params) in enumerate(calls):
            self.assertEqual(
                params[0],
                SAMPLE_PROJECT_ID,
                f"Call #{idx + 1}: first SQL param should be project_id='{SAMPLE_PROJECT_ID}'.",
            )

    # ------------------------------------------------------------------
    # Test G: conn.commit() is called after each save
    # ------------------------------------------------------------------
    def test_commit_called_after_each_save(self):
        """conn.commit() must be called after each upsert to persist the write."""
        mock_conn, _ = _make_mock_conn()
        save_project_to_db(mock_conn, SAMPLE_PROJECT_ID, PAYLOAD_V1)
        save_project_to_db(mock_conn, SAMPLE_PROJECT_ID, PAYLOAD_V2)
        self.assertEqual(
            mock_conn.commit.call_count,
            2,
            f"conn.commit() should be called twice, got {mock_conn.commit.call_count}.",
        )

    # ------------------------------------------------------------------
    # Test H: Different project_ids produce independent upserts
    # ------------------------------------------------------------------
    def test_different_project_ids_each_get_their_own_upsert(self):
        """
        Two distinct project IDs must each produce a separate upsert with
        their own id bound as the first parameter.
        """
        mock_conn, mock_cursor = _make_mock_conn()
        save_project_to_db(mock_conn, "project_alpha", PAYLOAD_V1)
        save_project_to_db(mock_conn, "project_beta", PAYLOAD_V2)

        calls = _extract_execute_calls(mock_cursor)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1][0], "project_alpha")
        self.assertEqual(calls[1][1][0], "project_beta")


# ---------------------------------------------------------------------------
# Property-based variant using Hypothesis (runs only if Hypothesis is installed)
# ---------------------------------------------------------------------------

if HYPOTHESIS_AVAILABLE:

    # Strategy: realistic project ID (non-empty, filesystem-safe string)
    project_id_strategy = st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="_-",
        ),
        min_size=1,
        max_size=64,
    )

    # Strategy: project data dict with required keys
    project_data_strategy = st.fixed_dictionaries(
        {
            "Project Name": st.text(min_size=1, max_size=100),
            "Project Status": st.sampled_from(["Ongoing", "Completed", "Lapsed"]),
            "District": st.text(min_size=1, max_size=50),
            "Mandal": st.text(min_size=1, max_size=50),
            "Locality": st.text(min_size=1, max_size=50),
            "Pin Code": st.from_regex(r"[0-9]{6}", fullmatch=True),
            "Village/City/Town": st.text(min_size=1, max_size=50),
            "totalFlats": st.integers(min_value=0, max_value=10000).map(str),
            "totalBookedFlats": st.integers(min_value=0, max_value=10000).map(str),
        }
    )

    class TestUpsertIdempotencyHypothesis(unittest.TestCase):
        """
        Property 1 (Hypothesis) — Scraper Upsert Idempotency across arbitrary inputs

        **Validates: Requirements 2.1**
        """

        @given(
            project_id=project_id_strategy,
            payload_v1=project_data_strategy,
            payload_v2=project_data_strategy,
        )
        @settings(max_examples=50)
        def test_upsert_sql_always_contains_on_conflict(
            self, project_id, payload_v1, payload_v2
        ):
            """
            For ANY project_id and ANY two payloads, both executions must use
            the ON CONFLICT (id) DO UPDATE upsert pattern.

            **Validates: Requirements 2.1**
            """
            mock_conn, mock_cursor = _make_mock_conn()
            save_project_to_db(mock_conn, project_id, payload_v1)
            save_project_to_db(mock_conn, project_id, payload_v2)

            calls = _extract_execute_calls(mock_cursor)
            # Must have issued exactly 2 SQL executions
            assert len(calls) == 2, (
                f"Expected 2 execute() calls, got {len(calls)}."
            )
            for idx, (sql, *_) in enumerate(calls):
                assert "ON CONFLICT (id)" in sql, (
                    f"Call #{idx + 1} missing ON CONFLICT (id): {sql[:200]}"
                )
                assert "DO UPDATE" in sql.upper(), (
                    f"Call #{idx + 1} missing DO UPDATE clause: {sql[:200]}"
                )

        @given(
            project_id=project_id_strategy,
            payload_v1=project_data_strategy,
            payload_v2=project_data_strategy,
        )
        @settings(max_examples=50)
        def test_second_call_raw_data_reflects_second_payload(
            self, project_id, payload_v1, payload_v2
        ):
            """
            For ANY two distinct payloads, the second call must serialise
            payload_v2 as the raw_data parameter — the most-recent scrape wins.

            **Validates: Requirements 2.1**
            """
            mock_conn, mock_cursor = _make_mock_conn()
            save_project_to_db(mock_conn, project_id, payload_v1)
            save_project_to_db(mock_conn, project_id, payload_v2)

            calls = _extract_execute_calls(mock_cursor)
            assert len(calls) == 2

            _, params_v1 = calls[0]
            _, params_v2 = calls[1]

            raw_v1 = json.loads(params_v1[-1])
            raw_v2 = json.loads(params_v2[-1])

            # The second call's raw_data must equal payload_v2
            assert raw_v2.get("Project Name") == payload_v2.get("Project Name"), (
                "Second call raw_data must reflect payload_v2's Project Name."
            )
            # The first call's raw_data must equal payload_v1
            assert raw_v1.get("Project Name") == payload_v1.get("Project Name"), (
                "First call raw_data must reflect payload_v1's Project Name."
            )

        @given(
            project_id=project_id_strategy,
            payload=project_data_strategy,
        )
        @settings(max_examples=50)
        def test_commit_always_called_after_each_save(self, project_id, payload):
            """
            For ANY project_id and payload, conn.commit() must be called once
            per save_project_to_db() invocation.

            **Validates: Requirements 2.1**
            """
            mock_conn, _ = _make_mock_conn()
            save_project_to_db(mock_conn, project_id, payload)
            assert mock_conn.commit.call_count == 1

            save_project_to_db(mock_conn, project_id, payload)
            assert mock_conn.commit.call_count == 2


# ===========================================================================
# Property 2: SRO Insert Idempotency
# ===========================================================================
# **Validates: Requirements 2.2**
#
# For any SRO transaction batch, inserting the same batch into
# `sro_transactions` a second time must:
#   a) issue the INSERT … ON CONFLICT DO NOTHING SQL on both calls, and
#   b) pass the same row data on both calls (row count attempted equals
#      a single insert — no extra or duplicated rows produced by the caller).
#
# Conceptual live-DB version
# --------------------------
#   1. Call save_sro_transactions_to_db(conn, batch)
#   2. Call save_sro_transactions_to_db(conn, batch)
#   3. SELECT COUNT(*) FROM sro_transactions WHERE sro_name = <name>
#      → assert fetchone()[0] == len(batch)   (no duplicates)
#
# The mock-based tests validate the same semantic guarantee by asserting
# that the correct SQL (containing ON CONFLICT DO NOTHING) was issued on
# each call and that the row data is identical across both calls.
# ===========================================================================


def _import_save_sro_transactions_to_db():
    """Import save_sro_transactions_to_db from sro_transaction_scraper with heavy deps mocked."""
    selenium_stub = types.ModuleType("selenium")
    selenium_stub.webdriver = types.ModuleType("selenium.webdriver")
    selenium_stub.webdriver.chrome = types.ModuleType("selenium.webdriver.chrome")
    selenium_stub.webdriver.chrome.options = types.ModuleType("selenium.webdriver.chrome.options")
    selenium_stub.webdriver.chrome.options.Options = MagicMock()
    selenium_stub.webdriver.chrome.service = types.ModuleType("selenium.webdriver.chrome.service")
    selenium_stub.webdriver.chrome.service.Service = MagicMock()
    selenium_stub.webdriver.support = types.ModuleType("selenium.webdriver.support")
    selenium_stub.webdriver.support.ui = types.ModuleType("selenium.webdriver.support.ui")
    selenium_stub.webdriver.support.ui.WebDriverWait = MagicMock()
    selenium_stub.webdriver.support.ui.Select = MagicMock()
    selenium_stub.webdriver.support.expected_conditions = MagicMock()
    selenium_stub.webdriver.common = types.ModuleType("selenium.webdriver.common")
    selenium_stub.webdriver.common.by = types.ModuleType("selenium.webdriver.common.by")
    selenium_stub.webdriver.common.by.By = MagicMock()
    selenium_stub.webdriver.Chrome = MagicMock()
    selenium_stub.webdriver.support.expected_conditions = MagicMock()
    selenium_stub.common = types.ModuleType("selenium.common")
    selenium_stub.common.exceptions = types.ModuleType("selenium.common.exceptions")
    selenium_stub.common.exceptions.TimeoutException = Exception
    selenium_stub.common.exceptions.NoSuchElementException = Exception
    selenium_stub.common.exceptions.StaleElementReferenceException = Exception

    wdm_stub = types.ModuleType("webdriver_manager")
    wdm_chrome_stub = types.ModuleType("webdriver_manager.chrome")
    wdm_chrome_stub.ChromeDriverManager = MagicMock()

    bs4_stub = types.ModuleType("bs4")
    bs4_stub.BeautifulSoup = MagicMock()

    requests_stub = types.ModuleType("requests")
    requests_stub.Session = MagicMock()
    requests_stub.adapters = types.ModuleType("requests.adapters")
    requests_stub.adapters.HTTPAdapter = MagicMock()

    pil_stub = types.ModuleType("PIL")
    pil_stub.Image = MagicMock()
    pil_stub.ImageFilter = MagicMock()
    pil_stub.ImageEnhance = MagicMock()

    pytesseract_stub = types.ModuleType("pytesseract")
    pytesseract_stub.image_to_string = MagicMock(return_value="")

    db_utils_stub = types.ModuleType("db_utils")
    db_utils_stub.get_connection = MagicMock()
    db_utils_stub.start_scrape_run = MagicMock()
    db_utils_stub.finish_scrape_run = MagicMock()
    db_utils_stub.fail_scrape_run = MagicMock()

    mocks = {
        "selenium": selenium_stub,
        "selenium.webdriver": selenium_stub.webdriver,
        "selenium.webdriver.chrome": selenium_stub.webdriver.chrome,
        "selenium.webdriver.chrome.options": selenium_stub.webdriver.chrome.options,
        "selenium.webdriver.chrome.service": selenium_stub.webdriver.chrome.service,
        "selenium.webdriver.support": selenium_stub.webdriver.support,
        "selenium.webdriver.support.ui": selenium_stub.webdriver.support.ui,
        "selenium.webdriver.support.expected_conditions": MagicMock(),
        "selenium.webdriver.common": selenium_stub.webdriver.common,
        "selenium.webdriver.common.by": selenium_stub.webdriver.common.by,
        "selenium.common": selenium_stub.common,
        "selenium.common.exceptions": selenium_stub.common.exceptions,
        "webdriver_manager": wdm_stub,
        "webdriver_manager.chrome": wdm_chrome_stub,
        "bs4": bs4_stub,
        "requests": requests_stub,
        "requests.adapters": requests_stub.adapters,
        "PIL": pil_stub,
        "PIL.Image": pil_stub.Image,
        "PIL.ImageFilter": pil_stub.ImageFilter,
        "PIL.ImageEnhance": pil_stub.ImageEnhance,
        "pytesseract": pytesseract_stub,
        "db_utils": db_utils_stub,
    }

    with patch.dict(sys.modules, mocks):
        spec = importlib.util.spec_from_file_location(
            "sro_transaction_scraper",
            os.path.join(_BACKEND_DIR, "sro_transaction_scraper.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

    return mod.save_sro_transactions_to_db


save_sro_transactions_to_db = _import_save_sro_transactions_to_db()


def _make_sro_mock_conn():
    """Return a mock psycopg2 connection suitable for executemany-based insert."""
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


ON_CONFLICT_DO_NOTHING = "ON CONFLICT DO NOTHING"

SAMPLE_SRO_BATCH = [
    {
        "sro_name": "SERILINGAMPALLI",
        "district": "RANGAREDDY",
        "village": "KONDAPUR",
        "apartment": "NATURE VALLEY BLOCK A",
        "flat_no": "301",
        "reg_date": "2024-03-15",
        "quarter": "2024-Q1",
        "mkt_value": 8500000,
        "cons_value": 9000000,
        "price_per_sqft": 6200.5,
    },
    {
        "sro_name": "SERILINGAMPALLI",
        "district": "RANGAREDDY",
        "village": "MADHAPUR",
        "apartment": "EMERALD TOWERS",
        "flat_no": "502",
        "reg_date": "2024-04-10",
        "quarter": "2024-Q2",
        "mkt_value": 12000000,
        "cons_value": 12500000,
        "price_per_sqft": 7800.0,
    },
]


class TestSROInsertIdempotency(unittest.TestCase):
    """
    Property 2 — SRO Insert Idempotency

    **Validates: Requirements 2.2**

    Verifies that inserting the same SRO transaction batch twice produces the
    same SQL calls and row data as a single insert, confirming ON CONFLICT DO
    NOTHING semantics without a live database.
    """

    def _insert_twice(self, batch):
        """Helper: call save_sro_transactions_to_db twice with the same batch."""
        mock_conn, mock_cursor = _make_sro_mock_conn()
        save_sro_transactions_to_db(mock_conn, batch)
        save_sro_transactions_to_db(mock_conn, batch)
        return mock_conn, mock_cursor

    # ------------------------------------------------------------------
    # Test A: executemany is called exactly twice (once per insert call)
    # ------------------------------------------------------------------
    def test_executemany_called_twice_for_double_insert(self):
        """Inserting the same batch twice must call cursor.executemany() exactly twice."""
        _, mock_cursor = self._insert_twice(SAMPLE_SRO_BATCH)
        self.assertEqual(
            mock_cursor.executemany.call_count,
            2,
            f"Expected cursor.executemany() twice, got {mock_cursor.executemany.call_count}.",
        )

    # ------------------------------------------------------------------
    # Test B: Both SQL calls contain ON CONFLICT DO NOTHING
    # ------------------------------------------------------------------
    def test_both_calls_use_on_conflict_do_nothing(self):
        """Both executemany SQL strings must contain ON CONFLICT DO NOTHING."""
        _, mock_cursor = self._insert_twice(SAMPLE_SRO_BATCH)
        for idx, call_args in enumerate(mock_cursor.executemany.call_args_list):
            sql = call_args.args[0]
            self.assertIn(
                ON_CONFLICT_DO_NOTHING,
                sql,
                f"Call #{idx + 1} SQL missing 'ON CONFLICT DO NOTHING': {sql[:300]}",
            )

    # ------------------------------------------------------------------
    # Test C: Both calls pass identical row data (same batch, same rows)
    # ------------------------------------------------------------------
    def test_both_calls_pass_identical_row_data(self):
        """Inserting the same batch twice must pass identical rows on both calls."""
        _, mock_cursor = self._insert_twice(SAMPLE_SRO_BATCH)
        calls = mock_cursor.executemany.call_args_list
        rows_call_1 = calls[0].args[1]
        rows_call_2 = calls[1].args[1]
        self.assertEqual(
            rows_call_1,
            rows_call_2,
            "Both insert calls must pass the same row data (idempotent batch).",
        )

    # ------------------------------------------------------------------
    # Test D: Row count returned equals len(batch) on both calls
    # ------------------------------------------------------------------
    def test_return_value_equals_batch_length_on_both_calls(self):
        """
        save_sro_transactions_to_db() must return len(batch) on each call —
        the number of rows *attempted*, not the number actually inserted.
        ON CONFLICT DO NOTHING means the DB silently skips duplicates;
        the caller always passes the full batch.
        """
        mock_conn, _ = _make_sro_mock_conn()
        result_1 = save_sro_transactions_to_db(mock_conn, SAMPLE_SRO_BATCH)
        result_2 = save_sro_transactions_to_db(mock_conn, SAMPLE_SRO_BATCH)
        self.assertEqual(result_1, len(SAMPLE_SRO_BATCH))
        self.assertEqual(result_2, len(SAMPLE_SRO_BATCH),
                         "Second insert must return the same row count as the first.")

    # ------------------------------------------------------------------
    # Test E: conn.commit() is called after each insert
    # ------------------------------------------------------------------
    def test_commit_called_after_each_insert(self):
        """conn.commit() must be called once per save_sro_transactions_to_db() call."""
        mock_conn, _ = _make_sro_mock_conn()
        save_sro_transactions_to_db(mock_conn, SAMPLE_SRO_BATCH)
        save_sro_transactions_to_db(mock_conn, SAMPLE_SRO_BATCH)
        self.assertEqual(
            mock_conn.commit.call_count,
            2,
            f"conn.commit() must be called twice, got {mock_conn.commit.call_count}.",
        )

    # ------------------------------------------------------------------
    # Test F: Empty batch is a no-op (returns 0, no SQL issued)
    # ------------------------------------------------------------------
    def test_empty_batch_is_noop(self):
        """An empty batch must return 0 and issue no SQL calls."""
        mock_conn, mock_cursor = _make_sro_mock_conn()
        result = save_sro_transactions_to_db(mock_conn, [])
        self.assertEqual(result, 0)
        mock_cursor.executemany.assert_not_called()

    # ------------------------------------------------------------------
    # Test G: SQL targets the correct table (sro_transactions)
    # ------------------------------------------------------------------
    def test_sql_targets_sro_transactions_table(self):
        """The INSERT SQL must target the sro_transactions table."""
        _, mock_cursor = self._insert_twice(SAMPLE_SRO_BATCH)
        for idx, call_args in enumerate(mock_cursor.executemany.call_args_list):
            sql = call_args.args[0]
            self.assertIn(
                "sro_transactions",
                sql,
                f"Call #{idx + 1} SQL does not target sro_transactions: {sql[:300]}",
            )

    # ------------------------------------------------------------------
    # Test H: Rows passed to executemany contain all required fields
    # ------------------------------------------------------------------
    def test_rows_contain_all_required_fields(self):
        """
        The tuples passed to executemany must contain exactly 10 values
        (matching the 10 non-SERIAL columns in the INSERT statement).
        """
        _, mock_cursor = self._insert_twice(SAMPLE_SRO_BATCH)
        calls = mock_cursor.executemany.call_args_list
        for idx, call_args in enumerate(calls):
            rows = list(call_args.args[1])
            for row_idx, row in enumerate(rows):
                self.assertEqual(
                    len(row),
                    10,
                    f"Call #{idx+1}, row #{row_idx+1} has {len(row)} fields, expected 10.",
                )


# ---------------------------------------------------------------------------
# Property-based variant using Hypothesis (runs only if Hypothesis is installed)
# ---------------------------------------------------------------------------

if HYPOTHESIS_AVAILABLE:

    # Strategy: individual SRO transaction record
    sro_transaction_strategy = st.fixed_dictionaries({
        "sro_name":      st.sampled_from(["SERILINGAMPALLI", "BANJARAHILLS", "S.R.NAGAR", "GANDIPET"]),
        "district":      st.sampled_from(["RANGAREDDY", "HYDERABAD", "MEDCHAL-MALKAJGIRI"]),
        "village":       st.text(min_size=1, max_size=40),
        "apartment":     st.text(min_size=1, max_size=80),
        "flat_no":       st.text(min_size=1, max_size=10),
        "reg_date":      st.sampled_from(["2024-01-15", "2024-06-30", "2023-12-01", None]),
        "quarter":       st.sampled_from(["2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4", "2023-Q4"]),
        "mkt_value":     st.integers(min_value=1_000_000, max_value=100_000_000),
        "cons_value":    st.integers(min_value=1_000_000, max_value=100_000_000),
        "price_per_sqft": st.floats(min_value=1000.0, max_value=50000.0, allow_nan=False),
    })

    # Strategy: non-empty list of SRO transactions (1–20 records)
    sro_batch_strategy = st.lists(sro_transaction_strategy, min_size=1, max_size=20)

    class TestSROInsertIdempotencyHypothesis(unittest.TestCase):
        """
        Property 2 (Hypothesis) — SRO Insert Idempotency across arbitrary inputs

        **Validates: Requirements 2.2**
        """

        @given(batch=sro_batch_strategy)
        @settings(max_examples=50)
        def test_on_conflict_do_nothing_always_present(self, batch):
            """
            For ANY non-empty SRO batch, both insert calls must use
            ON CONFLICT DO NOTHING in the SQL.

            **Validates: Requirements 2.2**
            """
            mock_conn, mock_cursor = _make_sro_mock_conn()
            save_sro_transactions_to_db(mock_conn, batch)
            save_sro_transactions_to_db(mock_conn, batch)

            assert mock_cursor.executemany.call_count == 2, (
                f"Expected 2 executemany() calls, got {mock_cursor.executemany.call_count}."
            )
            for idx, call_args in enumerate(mock_cursor.executemany.call_args_list):
                sql = call_args.args[0]
                assert ON_CONFLICT_DO_NOTHING in sql, (
                    f"Call #{idx + 1} missing ON CONFLICT DO NOTHING: {sql[:300]}"
                )

        @given(batch=sro_batch_strategy)
        @settings(max_examples=50)
        def test_row_count_returned_equals_batch_size_on_both_calls(self, batch):
            """
            For ANY non-empty batch, the return value of save_sro_transactions_to_db
            must equal len(batch) on both the first and second call.

            **Validates: Requirements 2.2**
            """
            mock_conn, _ = _make_sro_mock_conn()
            result_1 = save_sro_transactions_to_db(mock_conn, batch)
            result_2 = save_sro_transactions_to_db(mock_conn, batch)
            assert result_1 == len(batch), (
                f"First call returned {result_1}, expected {len(batch)}."
            )
            assert result_2 == len(batch), (
                f"Second call returned {result_2}, expected {len(batch)} (idempotent)."
            )

        @given(batch=sro_batch_strategy)
        @settings(max_examples=50)
        def test_identical_rows_passed_on_both_calls(self, batch):
            """
            For ANY batch, the rows passed to executemany on the second call
            must be identical to those on the first call.

            **Validates: Requirements 2.2**
            """
            mock_conn, mock_cursor = _make_sro_mock_conn()
            save_sro_transactions_to_db(mock_conn, batch)
            save_sro_transactions_to_db(mock_conn, batch)

            calls = mock_cursor.executemany.call_args_list
            rows_1 = list(calls[0].args[1])
            rows_2 = list(calls[1].args[1])
            assert rows_1 == rows_2, (
                "Second call must pass the same row data as the first (idempotent)."
            )

        @given(batch=sro_batch_strategy)
        @settings(max_examples=50)
        def test_commit_called_twice_for_double_insert(self, batch):
            """
            For ANY batch, conn.commit() must be called exactly once per
            save_sro_transactions_to_db() invocation.

            **Validates: Requirements 2.2**
            """
            mock_conn, _ = _make_sro_mock_conn()
            save_sro_transactions_to_db(mock_conn, batch)
            assert mock_conn.commit.call_count == 1
            save_sro_transactions_to_db(mock_conn, batch)
            assert mock_conn.commit.call_count == 2


# ===========================================================================
# Property 3: Unit Rates Replace Idempotency
# ===========================================================================
# **Validates: Requirements 2.3**
#
# The RR scraper's save_unit_rates_to_db() uses TRUNCATE + re-INSERT semantics.
# Running it N times with the same dataset must produce the same final table
# state as running it once — confirmed by inspecting the mock SQL calls.
#
# Conceptual live-DB version
# --------------------------
#   1. Call save_unit_rates_to_db(conn, rates) N times
#   2. SELECT COUNT(*) FROM unit_rates → assert == len(rates)  (no duplicates)
#   3. SELECT * FROM unit_rates ORDER BY id → rows match `rates` exactly
#
# The mock-based tests below validate the same semantic guarantee by asserting:
#   a) TRUNCATE TABLE unit_rates is issued on every call (replace semantics)
#   b) INSERT INTO unit_rates is issued for each row on every call
#   c) The row count passed to INSERT is len(rates) on every call
#   d) Return value equals len(rates) on every call
#   e) conn.commit() is called once per invocation
#   f) Empty rates list is a no-op (returns 0, no INSERT issued)
# ===========================================================================


def _import_save_unit_rates_to_db():
    """Import save_unit_rates_to_db from rr_scraper with heavy deps mocked."""
    selenium_stub = types.ModuleType("selenium")
    selenium_stub.webdriver = types.ModuleType("selenium.webdriver")
    selenium_stub.webdriver.chrome = types.ModuleType("selenium.webdriver.chrome")
    selenium_stub.webdriver.chrome.options = types.ModuleType("selenium.webdriver.chrome.options")
    selenium_stub.webdriver.chrome.options.Options = MagicMock()
    selenium_stub.webdriver.chrome.service = types.ModuleType("selenium.webdriver.chrome.service")
    selenium_stub.webdriver.chrome.service.Service = MagicMock()
    selenium_stub.webdriver.support = types.ModuleType("selenium.webdriver.support")
    selenium_stub.webdriver.support.ui = types.ModuleType("selenium.webdriver.support.ui")
    selenium_stub.webdriver.support.ui.WebDriverWait = MagicMock()
    selenium_stub.webdriver.support.ui.Select = MagicMock()
    selenium_stub.webdriver.support.expected_conditions = MagicMock()
    selenium_stub.webdriver.common = types.ModuleType("selenium.webdriver.common")
    selenium_stub.webdriver.common.by = types.ModuleType("selenium.webdriver.common.by")
    selenium_stub.webdriver.common.by.By = MagicMock()
    selenium_stub.webdriver.Chrome = MagicMock()
    selenium_stub.common = types.ModuleType("selenium.common")
    selenium_stub.common.exceptions = types.ModuleType("selenium.common.exceptions")
    selenium_stub.common.exceptions.TimeoutException = Exception
    selenium_stub.common.exceptions.NoSuchElementException = Exception
    selenium_stub.common.exceptions.StaleElementReferenceException = Exception

    wdm_stub = types.ModuleType("webdriver_manager")
    wdm_chrome_stub = types.ModuleType("webdriver_manager.chrome")
    wdm_chrome_stub.ChromeDriverManager = MagicMock()

    requests_stub = types.ModuleType("requests")

    db_utils_stub = types.ModuleType("db_utils")
    db_utils_stub.get_connection = MagicMock()

    mocks = {
        "selenium": selenium_stub,
        "selenium.webdriver": selenium_stub.webdriver,
        "selenium.webdriver.chrome": selenium_stub.webdriver.chrome,
        "selenium.webdriver.chrome.options": selenium_stub.webdriver.chrome.options,
        "selenium.webdriver.chrome.service": selenium_stub.webdriver.chrome.service,
        "selenium.webdriver.support": selenium_stub.webdriver.support,
        "selenium.webdriver.support.ui": selenium_stub.webdriver.support.ui,
        "selenium.webdriver.support.expected_conditions": MagicMock(),
        "selenium.webdriver.common": selenium_stub.webdriver.common,
        "selenium.webdriver.common.by": selenium_stub.webdriver.common.by,
        "selenium.common": selenium_stub.common,
        "selenium.common.exceptions": selenium_stub.common.exceptions,
        "webdriver_manager": wdm_stub,
        "webdriver_manager.chrome": wdm_chrome_stub,
        "requests": requests_stub,
        "db_utils": db_utils_stub,
    }

    with patch.dict(sys.modules, mocks):
        mod_spec = importlib.util.spec_from_file_location(
            "rr_scraper",
            os.path.join(_BACKEND_DIR, "rr_scraper.py"),
        )
        mod = importlib.util.module_from_spec(mod_spec)
        mod_spec.loader.exec_module(mod)

    return mod.save_unit_rates_to_db


save_unit_rates_to_db = _import_save_unit_rates_to_db()


def _make_rr_mock_conn():
    """Return a mock psycopg2 connection suitable for execute-based inserts."""
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


SAMPLE_UNIT_RATES = [
    {
        "district": "RANGAREDDY",
        "mandal": "Serilingampally",
        "locality": "Kondapur",
        "search_type": "apartment",
        "unit_rate_sqft": 6200.5,
    },
    {
        "district": "RANGAREDDY",
        "mandal": "Serilingampally",
        "locality": "Madhapur",
        "search_type": "apartment",
        "unit_rate_sqft": 7800.0,
    },
    {
        "district": "HYDERABAD",
        "mandal": "KHAIRTABAD",
        "village": "Banjara Hills",  # uses 'village' key instead of 'locality'
        "search_type": "apartment",
        "unit_rate_sqft": 9500.0,
    },
]

TRUNCATE_KEYWORD = "TRUNCATE TABLE unit_rates"
INSERT_KEYWORD = "INSERT INTO unit_rates"


class TestUnitRatesReplaceIdempotency(unittest.TestCase):
    """
    Property 3 — Unit Rates Replace Idempotency

    **Validates: Requirements 2.3**

    Verifies that TRUNCATE + re-INSERT semantics guarantee idempotency:
    running save_unit_rates_to_db() N times with the same dataset produces
    the same SQL calls and row count as a single run.
    """

    def _run_n_times(self, rates, n=3):
        """Helper: call save_unit_rates_to_db n times and return conn + cursor mocks."""
        mock_conn, mock_cursor = _make_rr_mock_conn()
        for _ in range(n):
            save_unit_rates_to_db(mock_conn, rates)
        return mock_conn, mock_cursor

    # ------------------------------------------------------------------
    # Test A: TRUNCATE is called on every invocation
    # ------------------------------------------------------------------
    def test_truncate_called_on_every_invocation(self):
        """TRUNCATE TABLE unit_rates must be issued once per call (replace semantics)."""
        n = 3
        _, mock_cursor = self._run_n_times(SAMPLE_UNIT_RATES, n=n)
        truncate_calls = [
            c for c in mock_cursor.execute.call_args_list
            if TRUNCATE_KEYWORD in (c.args[0] if c.args else "")
        ]
        self.assertEqual(
            len(truncate_calls),
            n,
            f"Expected {n} TRUNCATE calls (one per run), got {len(truncate_calls)}.",
        )

    # ------------------------------------------------------------------
    # Test B: SQL contains TRUNCATE TABLE unit_rates (replace semantics)
    # ------------------------------------------------------------------
    def test_truncate_sql_targets_unit_rates_table(self):
        """The TRUNCATE SQL must reference the unit_rates table by name."""
        _, mock_cursor = self._run_n_times(SAMPLE_UNIT_RATES, n=1)
        all_sqls = [c.args[0] for c in mock_cursor.execute.call_args_list if c.args]
        truncate_sqls = [s for s in all_sqls if "TRUNCATE" in s.upper()]
        self.assertTrue(
            len(truncate_sqls) >= 1,
            "Expected at least one TRUNCATE statement in execute() calls.",
        )
        for sql in truncate_sqls:
            self.assertIn(
                "unit_rates",
                sql,
                f"TRUNCATE SQL does not target unit_rates table: {sql}",
            )

    # ------------------------------------------------------------------
    # Test C: SQL contains INSERT INTO unit_rates
    # ------------------------------------------------------------------
    def test_insert_sql_targets_unit_rates_table(self):
        """INSERT SQL must target the unit_rates table."""
        _, mock_cursor = self._run_n_times(SAMPLE_UNIT_RATES, n=1)
        all_sqls = [c.args[0] for c in mock_cursor.execute.call_args_list if c.args]
        insert_sqls = [s for s in all_sqls if "INSERT" in s.upper()]
        self.assertTrue(
            len(insert_sqls) >= 1,
            "Expected at least one INSERT statement in execute() calls.",
        )
        for sql in insert_sqls:
            self.assertIn(
                "unit_rates",
                sql,
                f"INSERT SQL does not target unit_rates table: {sql}",
            )

    # ------------------------------------------------------------------
    # Test D: Row count inserted equals len(rates) on each invocation
    # ------------------------------------------------------------------
    def test_row_count_inserted_equals_rates_length_on_every_call(self):
        """
        For N runs, each run must issue exactly len(rates) INSERT calls —
        confirming replace semantics (truncate old, re-insert all new).
        """
        n = 3
        rates = SAMPLE_UNIT_RATES
        _, mock_cursor = self._run_n_times(rates, n=n)
        all_calls = mock_cursor.execute.call_args_list
        # Each invocation: 1 TRUNCATE + len(rates) INSERTs
        expected_total_calls = n * (1 + len(rates))
        self.assertEqual(
            len(all_calls),
            expected_total_calls,
            f"Expected {expected_total_calls} execute() calls total "
            f"({n} runs × (1 TRUNCATE + {len(rates)} INSERTs)), "
            f"got {len(all_calls)}.",
        )

    # ------------------------------------------------------------------
    # Test E: Return value equals len(rates) on every call
    # ------------------------------------------------------------------
    def test_return_value_equals_rates_length_on_every_call(self):
        """save_unit_rates_to_db() must return len(rates) on each invocation."""
        mock_conn, _ = _make_rr_mock_conn()
        rates = SAMPLE_UNIT_RATES
        for i in range(3):
            result = save_unit_rates_to_db(mock_conn, rates)
            self.assertEqual(
                result,
                len(rates),
                f"Run #{i + 1}: expected return value {len(rates)}, got {result}.",
            )

    # ------------------------------------------------------------------
    # Test F: conn.commit() called once per invocation
    # ------------------------------------------------------------------
    def test_commit_called_once_per_invocation(self):
        """conn.commit() must be called exactly once per save_unit_rates_to_db() call."""
        n = 3
        mock_conn, _ = self._run_n_times(SAMPLE_UNIT_RATES, n=n)
        self.assertEqual(
            mock_conn.commit.call_count,
            n,
            f"conn.commit() should be called {n} times (once per run), "
            f"got {mock_conn.commit.call_count}.",
        )

    # ------------------------------------------------------------------
    # Test G: Empty rates list is a no-op (returns 0, no SQL issued)
    # ------------------------------------------------------------------
    def test_empty_rates_is_noop(self):
        """An empty rates list must return 0 and issue no SQL calls."""
        mock_conn, mock_cursor = _make_rr_mock_conn()
        result = save_unit_rates_to_db(mock_conn, [])
        self.assertEqual(result, 0, "Empty rates should return 0.")
        mock_cursor.execute.assert_not_called()
        mock_conn.commit.assert_not_called()

    # ------------------------------------------------------------------
    # Test H: Single run vs N runs produce the same INSERT row content
    # ------------------------------------------------------------------
    def test_n_runs_produce_same_insert_rows_as_single_run(self):
        """
        Running N times must pass the same INSERT row data as a single run —
        confirming the replace is not cumulative.
        """
        rates = SAMPLE_UNIT_RATES
        mock_conn_1, mock_cursor_1 = _make_rr_mock_conn()
        save_unit_rates_to_db(mock_conn_1, rates)

        mock_conn_n, mock_cursor_n = _make_rr_mock_conn()
        for _ in range(5):
            save_unit_rates_to_db(mock_conn_n, rates)

        # Extract INSERT params from single run
        insert_params_1 = [
            c.args[1] for c in mock_cursor_1.execute.call_args_list
            if c.args and "INSERT" in c.args[0].upper()
        ]
        # Extract INSERT params from Nth run (last run = last len(rates) INSERTs)
        all_insert_calls_n = [
            c.args[1] for c in mock_cursor_n.execute.call_args_list
            if c.args and "INSERT" in c.args[0].upper()
        ]
        # Last batch of INSERTs (from the final run)
        insert_params_last_run = all_insert_calls_n[-len(rates):]

        self.assertEqual(
            insert_params_1,
            insert_params_last_run,
            "INSERT row data from the last of N runs must equal a single run's data.",
        )

    # ------------------------------------------------------------------
    # Test I: locality falls back to 'village' key when locality is absent
    # ------------------------------------------------------------------
    def test_locality_falls_back_to_village_key(self):
        """
        A rate dict with 'village' instead of 'locality' must still produce
        a valid INSERT (the function uses `locality` or `village` as fallback).
        """
        rates_with_village = [
            {
                "district": "HYDERABAD",
                "mandal": "KHAIRTABAD",
                "village": "Banjara Hills",
                "search_type": "apartment",
                "unit_rate_sqft": 9500.0,
            }
        ]
        mock_conn, mock_cursor = _make_rr_mock_conn()
        result = save_unit_rates_to_db(mock_conn, rates_with_village)
        self.assertEqual(result, 1)
        # Verify an INSERT was issued
        insert_calls = [
            c for c in mock_cursor.execute.call_args_list
            if c.args and "INSERT" in c.args[0].upper()
        ]
        self.assertEqual(len(insert_calls), 1)
        # The third positional param is the locality value (district, mandal, locality, ...)
        locality_param = insert_calls[0].args[1][2]
        self.assertEqual(locality_param, "Banjara Hills")


# ---------------------------------------------------------------------------
# Property-based variant using Hypothesis (runs only if Hypothesis is installed)
# ---------------------------------------------------------------------------

if HYPOTHESIS_AVAILABLE:

    # Strategy: individual unit rate record
    unit_rate_strategy = st.fixed_dictionaries({
        "district":      st.sampled_from(["RANGAREDDY", "HYDERABAD", "MEDCHAL-MALKAJGIRI", "SANGAREDDY"]),
        "mandal":        st.text(min_size=1, max_size=40),
        "locality":      st.text(min_size=0, max_size=60),
        "search_type":   st.sampled_from(["apartment", "land"]),
        "unit_rate_sqft": st.floats(min_value=100.0, max_value=2_000_000.0, allow_nan=False),
    })

    # Strategy: non-empty list of unit rates (1–20 records)
    unit_rates_list_strategy = st.lists(unit_rate_strategy, min_size=1, max_size=20)

    # Strategy: run count N (2–5 runs)
    run_count_strategy = st.integers(min_value=2, max_value=5)

    class TestUnitRatesReplaceIdempotencyHypothesis(unittest.TestCase):
        """
        Property 3 (Hypothesis) — Unit Rates Replace Idempotency across arbitrary inputs

        **Validates: Requirements 2.3**
        """

        @given(rates=unit_rates_list_strategy, n=run_count_strategy)
        @settings(max_examples=50)
        def test_truncate_called_on_every_run(self, rates, n):
            """
            For ANY non-empty rates list and ANY run count N, TRUNCATE must
            be issued once per run — confirming replace semantics always hold.

            **Validates: Requirements 2.3**
            """
            mock_conn, mock_cursor = _make_rr_mock_conn()
            for _ in range(n):
                save_unit_rates_to_db(mock_conn, rates)

            truncate_calls = [
                c for c in mock_cursor.execute.call_args_list
                if c.args and "TRUNCATE" in c.args[0].upper() and "unit_rates" in c.args[0]
            ]
            assert len(truncate_calls) == n, (
                f"Expected {n} TRUNCATE calls, got {len(truncate_calls)}."
            )

        @given(rates=unit_rates_list_strategy, n=run_count_strategy)
        @settings(max_examples=50)
        def test_return_value_always_equals_rates_length(self, rates, n):
            """
            For ANY rates list and ANY N, save_unit_rates_to_db() must return
            len(rates) on every call.

            **Validates: Requirements 2.3**
            """
            mock_conn, _ = _make_rr_mock_conn()
            for i in range(n):
                result = save_unit_rates_to_db(mock_conn, rates)
                assert result == len(rates), (
                    f"Run #{i + 1}: expected {len(rates)}, got {result}."
                )

        @given(rates=unit_rates_list_strategy, n=run_count_strategy)
        @settings(max_examples=50)
        def test_commit_called_once_per_run(self, rates, n):
            """
            For ANY rates list and ANY N, conn.commit() must be called
            exactly once per invocation.

            **Validates: Requirements 2.3**
            """
            mock_conn, _ = _make_rr_mock_conn()
            for i in range(n):
                save_unit_rates_to_db(mock_conn, rates)
                assert mock_conn.commit.call_count == i + 1, (
                    f"After run #{i + 1}, commit count should be {i + 1}, "
                    f"got {mock_conn.commit.call_count}."
                )

        @given(rates=unit_rates_list_strategy)
        @settings(max_examples=50)
        def test_last_run_insert_rows_equal_single_run(self, rates):
            """
            For ANY rates list, the INSERT row data from the last of N=3 runs
            must be identical to a single-run's INSERT row data.

            **Validates: Requirements 2.3**
            """
            # Single run
            mock_conn_1, mock_cursor_1 = _make_rr_mock_conn()
            save_unit_rates_to_db(mock_conn_1, rates)
            insert_params_1 = [
                c.args[1] for c in mock_cursor_1.execute.call_args_list
                if c.args and "INSERT" in c.args[0].upper()
            ]

            # N=3 runs
            mock_conn_n, mock_cursor_n = _make_rr_mock_conn()
            for _ in range(3):
                save_unit_rates_to_db(mock_conn_n, rates)
            all_insert_params_n = [
                c.args[1] for c in mock_cursor_n.execute.call_args_list
                if c.args and "INSERT" in c.args[0].upper()
            ]
            # Last batch = final run's INSERT rows
            last_run_insert_params = all_insert_params_n[-len(rates):]

            assert insert_params_1 == last_run_insert_params, (
                "Last run's INSERT row data must equal a single run's data."
            )


# ===========================================================================
# Property 4: Scrape Run Status Consistency
# ===========================================================================
# **Validates: Requirements 2.7, 2.8, 2.9**
#
# For any scraper execution outcome, the terminal `status` value persisted in
# `scrape_runs` must match the actual outcome:
#   - `start_scrape_run` inserts with status='running'
#   - `finish_scrape_run` sets status='completed'
#   - `fail_scrape_run` sets status='failed'
#
# Conceptual live-DB version
# --------------------------
#   1. run_id = start_scrape_run(conn, 'rera')
#      SELECT status FROM scrape_runs WHERE id=run_id → 'running'
#   2. finish_scrape_run(conn, run_id, total=10, completed=10)
#      SELECT status FROM scrape_runs WHERE id=run_id → 'completed'
#   3. fail_scrape_run(conn, run_id, 'fatal error')
#      SELECT status FROM scrape_runs WHERE id=run_id → 'failed'
#
# The mock-based tests validate the same semantic guarantee by asserting that
# the SQL UPDATE carries the correct status literal on each path.
# ===========================================================================

# Import the three helpers directly from db_utils.
# db_utils imports psycopg2 at the top-level; we mock it so the module loads
# in CI / test environments that don't have a live PostgreSQL driver installed.
def _import_db_utils():
    """Import db_utils with psycopg2 stubbed out."""
    psycopg2_stub = types.ModuleType("psycopg2")
    psycopg2_stub.connect = MagicMock()
    psycopg2_stub.extensions = types.ModuleType("psycopg2.extensions")
    psycopg2_stub.extensions.connection = MagicMock()

    with patch.dict(sys.modules, {"psycopg2": psycopg2_stub,
                                   "psycopg2.extensions": psycopg2_stub.extensions}):
        mod_spec = importlib.util.spec_from_file_location(
            "db_utils",
            os.path.join(_BACKEND_DIR, "db_utils.py"),
        )
        mod = importlib.util.module_from_spec(mod_spec)
        mod_spec.loader.exec_module(mod)
    return mod


_db_utils_mod = _import_db_utils()
start_scrape_run = _db_utils_mod.start_scrape_run
finish_scrape_run = _db_utils_mod.finish_scrape_run
fail_scrape_run = _db_utils_mod.fail_scrape_run


def _make_scrape_run_mock_conn(run_id: int = 42):
    """
    Return a mock psycopg2 connection suitable for scrape_run helpers.

    cursor.fetchone() returns (run_id,) so that start_scrape_run can
    read back the new row's primary key.
    """
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (run_id,)
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


def _get_execute_sql_and_params(mock_cursor, call_index: int = 0):
    """Return (sql, params) for the nth cursor.execute() call."""
    c = mock_cursor.execute.call_args_list[call_index]
    sql = c.args[0]
    params = c.args[1] if len(c.args) > 1 else ()
    return sql, params


class TestScrapeRunStatusConsistency(unittest.TestCase):
    """
    Property 4 — Scrape Run Status Consistency

    **Validates: Requirements 2.7, 2.8, 2.9**
    """

    # ------------------------------------------------------------------
    # Test A: start_scrape_run inserts with status='running'
    # ------------------------------------------------------------------
    def test_start_scrape_run_inserts_status_running(self):
        """
        start_scrape_run() must issue an INSERT containing status='running'
        as a literal in the SQL — satisfying Requirement 2.7.
        """
        mock_conn, mock_cursor = _make_scrape_run_mock_conn()
        run_id = start_scrape_run(mock_conn, "rera")

        self.assertEqual(run_id, 42, "start_scrape_run must return the run id from fetchone().")
        self.assertTrue(
            mock_cursor.execute.called,
            "cursor.execute() must be called by start_scrape_run.",
        )
        sql, params = _get_execute_sql_and_params(mock_cursor, 0)
        self.assertIn(
            "INSERT",
            sql.upper(),
            "start_scrape_run must issue an INSERT statement.",
        )
        self.assertIn(
            "scrape_runs",
            sql,
            "INSERT must target the scrape_runs table.",
        )
        self.assertIn(
            "'running'",
            sql,
            "INSERT SQL must embed status='running' as a literal.",
        )
        self.assertIn(
            "RETURNING id",
            sql,
            "INSERT must include RETURNING id so the run_id can be returned.",
        )

    # ------------------------------------------------------------------
    # Test B: start_scrape_run binds scraper_name as first parameter
    # ------------------------------------------------------------------
    def test_start_scrape_run_binds_scraper_name(self):
        """The scraper_name must be passed as the first SQL parameter."""
        for scraper in ("rera", "sro", "rr"):
            mock_conn, mock_cursor = _make_scrape_run_mock_conn()
            start_scrape_run(mock_conn, scraper)
            sql, params = _get_execute_sql_and_params(mock_cursor, 0)
            self.assertEqual(
                params[0],
                scraper,
                f"scraper_name '{scraper}' must be the first bound parameter.",
            )

    # ------------------------------------------------------------------
    # Test C: start_scrape_run calls conn.commit()
    # ------------------------------------------------------------------
    def test_start_scrape_run_commits(self):
        """start_scrape_run() must call conn.commit() after the INSERT."""
        mock_conn, _ = _make_scrape_run_mock_conn()
        start_scrape_run(mock_conn, "sro")
        mock_conn.commit.assert_called_once_with()

    # ------------------------------------------------------------------
    # Test D: finish_scrape_run issues UPDATE with status='completed'
    # ------------------------------------------------------------------
    def test_finish_scrape_run_sets_status_completed(self):
        """
        finish_scrape_run() must issue an UPDATE setting status='completed'
        in the SQL — satisfying Requirement 2.8.
        """
        mock_conn, mock_cursor = _make_scrape_run_mock_conn()
        finish_scrape_run(mock_conn, run_id=42, total=100, completed=100)

        self.assertTrue(
            mock_cursor.execute.called,
            "cursor.execute() must be called by finish_scrape_run.",
        )
        sql, params = _get_execute_sql_and_params(mock_cursor, 0)
        self.assertIn(
            "UPDATE",
            sql.upper(),
            "finish_scrape_run must issue an UPDATE statement.",
        )
        self.assertIn(
            "scrape_runs",
            sql,
            "UPDATE must target the scrape_runs table.",
        )
        self.assertIn(
            "'completed'",
            sql,
            "UPDATE SQL must set status='completed' as a literal.",
        )

    # ------------------------------------------------------------------
    # Test E: finish_scrape_run sets finished_at, total, completed counts
    # ------------------------------------------------------------------
    def test_finish_scrape_run_sets_finished_at_and_counts(self):
        """
        finish_scrape_run() SQL must update finished_at, total, and completed
        columns — satisfying Requirement 2.8.
        """
        mock_conn, mock_cursor = _make_scrape_run_mock_conn()
        finish_scrape_run(mock_conn, run_id=42, total=200, completed=195)

        sql, params = _get_execute_sql_and_params(mock_cursor, 0)
        self.assertIn(
            "finished_at",
            sql,
            "UPDATE must set finished_at.",
        )
        self.assertIn(
            "total",
            sql,
            "UPDATE must set total count.",
        )
        self.assertIn(
            "completed",
            sql,
            "UPDATE must set completed count.",
        )
        # total=200, completed=195, run_id=42 must appear in params (order: total, completed, id)
        params_list = list(params)
        self.assertIn(200, params_list, "total=200 must be a bound parameter.")
        self.assertIn(195, params_list, "completed=195 must be a bound parameter.")
        self.assertIn(42, params_list, "run_id=42 must be a bound parameter.")

    # ------------------------------------------------------------------
    # Test F: finish_scrape_run calls conn.commit()
    # ------------------------------------------------------------------
    def test_finish_scrape_run_commits(self):
        """finish_scrape_run() must call conn.commit() after the UPDATE."""
        mock_conn, _ = _make_scrape_run_mock_conn()
        finish_scrape_run(mock_conn, run_id=1, total=10, completed=10)
        mock_conn.commit.assert_called_once_with()

    # ------------------------------------------------------------------
    # Test G: fail_scrape_run issues UPDATE with status='failed'
    # ------------------------------------------------------------------
    def test_fail_scrape_run_sets_status_failed(self):
        """
        fail_scrape_run() must issue an UPDATE setting status='failed'
        in the SQL — satisfying Requirement 2.9.
        """
        mock_conn, mock_cursor = _make_scrape_run_mock_conn()
        fail_scrape_run(mock_conn, run_id=99, error="Timeout after 30s")

        self.assertTrue(
            mock_cursor.execute.called,
            "cursor.execute() must be called by fail_scrape_run.",
        )
        sql, params = _get_execute_sql_and_params(mock_cursor, 0)
        self.assertIn(
            "UPDATE",
            sql.upper(),
            "fail_scrape_run must issue an UPDATE statement.",
        )
        self.assertIn(
            "scrape_runs",
            sql,
            "UPDATE must target the scrape_runs table.",
        )
        self.assertIn(
            "'failed'",
            sql,
            "UPDATE SQL must set status='failed' as a literal.",
        )

    # ------------------------------------------------------------------
    # Test H: fail_scrape_run appends to errors JSONB array
    # ------------------------------------------------------------------
    def test_fail_scrape_run_appends_error_to_jsonb_array(self):
        """
        fail_scrape_run() must include the JSONB append operator (||) to
        concatenate the new error entry to the existing errors array —
        satisfying Requirement 2.9.
        """
        mock_conn, mock_cursor = _make_scrape_run_mock_conn()
        error_msg = "Database connection lost"
        fail_scrape_run(mock_conn, run_id=99, error=error_msg)

        sql, params = _get_execute_sql_and_params(mock_cursor, 0)
        self.assertIn(
            "errors",
            sql,
            "UPDATE must reference the errors column.",
        )
        self.assertIn(
            "||",
            sql,
            "UPDATE must use the JSONB concatenation operator (||) to append errors.",
        )
        self.assertIn(
            "::jsonb",
            sql,
            "The new error entry must be cast to ::jsonb.",
        )
        # The error message must appear in the JSON blob bound as a parameter
        params_list = list(params)
        error_param_found = any(
            isinstance(p, str) and error_msg in p for p in params_list
        )
        self.assertTrue(
            error_param_found,
            f"Error message '{error_msg}' must be present in the bound SQL parameters.",
        )

    # ------------------------------------------------------------------
    # Test I: fail_scrape_run sets finished_at
    # ------------------------------------------------------------------
    def test_fail_scrape_run_sets_finished_at(self):
        """fail_scrape_run() must set finished_at in the UPDATE SQL."""
        mock_conn, mock_cursor = _make_scrape_run_mock_conn()
        fail_scrape_run(mock_conn, run_id=5, error="scraper crash")

        sql, _ = _get_execute_sql_and_params(mock_cursor, 0)
        self.assertIn(
            "finished_at",
            sql,
            "UPDATE must set finished_at when marking a run as failed.",
        )

    # ------------------------------------------------------------------
    # Test J: fail_scrape_run calls conn.commit()
    # ------------------------------------------------------------------
    def test_fail_scrape_run_commits(self):
        """fail_scrape_run() must call conn.commit() after the UPDATE."""
        mock_conn, _ = _make_scrape_run_mock_conn()
        fail_scrape_run(mock_conn, run_id=7, error="fatal")
        mock_conn.commit.assert_called_once_with()

    # ------------------------------------------------------------------
    # Test K: Full successful run sequence — start → finish → status='completed'
    # ------------------------------------------------------------------
    def test_successful_run_sequence_results_in_completed_status(self):
        """
        Simulating start_scrape_run() + finish_scrape_run() must produce
        exactly two cursor.execute() calls, with the second one setting
        status='completed' — the full successful-run contract.
        """
        mock_conn, mock_cursor = _make_scrape_run_mock_conn(run_id=10)
        run_id = start_scrape_run(mock_conn, "rera")
        finish_scrape_run(mock_conn, run_id=run_id, total=50, completed=50)

        self.assertEqual(
            mock_cursor.execute.call_count,
            2,
            "Successful run must produce exactly 2 cursor.execute() calls (INSERT + UPDATE).",
        )
        # First call: INSERT (status='running')
        sql_start, _ = _get_execute_sql_and_params(mock_cursor, 0)
        self.assertIn("'running'", sql_start, "First call must insert status='running'.")
        # Second call: UPDATE (status='completed')
        sql_finish, _ = _get_execute_sql_and_params(mock_cursor, 1)
        self.assertIn("'completed'", sql_finish, "Second call must update status='completed'.")
        self.assertEqual(mock_conn.commit.call_count, 2, "commit() must be called twice.")

    # ------------------------------------------------------------------
    # Test L: Full failed run sequence — start → fail → status='failed'
    # ------------------------------------------------------------------
    def test_failed_run_sequence_results_in_failed_status(self):
        """
        Simulating start_scrape_run() + fail_scrape_run() must produce
        exactly two cursor.execute() calls, with the second one setting
        status='failed' — the full fatal-error contract.
        """
        mock_conn, mock_cursor = _make_scrape_run_mock_conn(run_id=11)
        run_id = start_scrape_run(mock_conn, "sro")
        fail_scrape_run(mock_conn, run_id=run_id, error="Page load timeout after 60s")

        self.assertEqual(
            mock_cursor.execute.call_count,
            2,
            "Failed run must produce exactly 2 cursor.execute() calls (INSERT + UPDATE).",
        )
        # First call: INSERT (status='running')
        sql_start, _ = _get_execute_sql_and_params(mock_cursor, 0)
        self.assertIn("'running'", sql_start, "First call must insert status='running'.")
        # Second call: UPDATE (status='failed')
        sql_fail, _ = _get_execute_sql_and_params(mock_cursor, 1)
        self.assertIn("'failed'", sql_fail, "Second call must update status='failed'.")
        self.assertEqual(mock_conn.commit.call_count, 2, "commit() must be called twice.")


# ---------------------------------------------------------------------------
# Property-based variant using Hypothesis (runs only if Hypothesis is installed)
# ---------------------------------------------------------------------------

if HYPOTHESIS_AVAILABLE:

    # Strategy: realistic scraper names
    scraper_name_strategy = st.sampled_from(["rera", "sro", "rr"])

    # Strategy: realistic total/completed counts
    total_strategy = st.integers(min_value=0, max_value=10_000)
    completed_strategy = st.integers(min_value=0, max_value=10_000)

    # Strategy: non-empty error messages
    error_msg_strategy = st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd", "Zs"),
            whitelist_characters="._-:/()[]",
        ),
        min_size=1,
        max_size=200,
    )

    # Strategy: positive run IDs
    run_id_strategy = st.integers(min_value=1, max_value=1_000_000)

    class TestScrapeRunStatusConsistencyHypothesis(unittest.TestCase):
        """
        Property 4 (Hypothesis) — Scrape Run Status Consistency across arbitrary inputs

        **Validates: Requirements 2.7, 2.8, 2.9**
        """

        @given(scraper_name=scraper_name_strategy)
        @settings(max_examples=30)
        def test_start_always_inserts_running_status(self, scraper_name):
            """
            For ANY scraper name, start_scrape_run() must always issue an
            INSERT with status='running' as a literal in the SQL.

            **Validates: Requirements 2.7**
            """
            mock_conn, mock_cursor = _make_scrape_run_mock_conn()
            start_scrape_run(mock_conn, scraper_name)

            sql, params = _get_execute_sql_and_params(mock_cursor, 0)
            assert "'running'" in sql, (
                f"start_scrape_run('{scraper_name}') SQL must contain \"'running'\": {sql[:200]}"
            )
            assert params[0] == scraper_name, (
                f"scraper_name must be the first bound parameter, got: {params[0]!r}"
            )

        @given(
            run_id=run_id_strategy,
            total=total_strategy,
            completed=completed_strategy,
        )
        @settings(max_examples=50)
        def test_finish_always_sets_completed_status(self, run_id, total, completed):
            """
            For ANY run_id, total, and completed values, finish_scrape_run()
            must always update status='completed' in the SQL.

            **Validates: Requirements 2.8**
            """
            mock_conn, mock_cursor = _make_scrape_run_mock_conn()
            finish_scrape_run(mock_conn, run_id=run_id, total=total, completed=completed)

            sql, params = _get_execute_sql_and_params(mock_cursor, 0)
            assert "'completed'" in sql, (
                f"finish_scrape_run SQL must contain \"'completed'\": {sql[:200]}"
            )
            params_list = list(params)
            assert total in params_list, (
                f"total={total} must be in bound parameters: {params_list}"
            )
            assert completed in params_list, (
                f"completed={completed} must be in bound parameters: {params_list}"
            )
            assert run_id in params_list, (
                f"run_id={run_id} must be in bound parameters: {params_list}"
            )

        @given(
            run_id=run_id_strategy,
            error=error_msg_strategy,
        )
        @settings(max_examples=50)
        def test_fail_always_sets_failed_status(self, run_id, error):
            """
            For ANY run_id and error message, fail_scrape_run() must always
            update status='failed' in the SQL.

            **Validates: Requirements 2.9**
            """
            mock_conn, mock_cursor = _make_scrape_run_mock_conn()
            fail_scrape_run(mock_conn, run_id=run_id, error=error)

            sql, params = _get_execute_sql_and_params(mock_cursor, 0)
            assert "'failed'" in sql, (
                f"fail_scrape_run SQL must contain \"'failed'\": {sql[:200]}"
            )
            params_list = list(params)
            # json.dumps encodes non-ASCII chars as \uXXXX; check both forms.
            error_json_escaped = json.dumps(error)[1:-1]  # strip surrounding quotes
            error_found = any(
                isinstance(p, str) and (error in p or error_json_escaped in p)
                for p in params_list
            )
            assert error_found, (
                f"Error message must be present in bound parameters: {params_list}"
            )
            assert run_id in params_list, (
                f"run_id={run_id} must be in bound parameters: {params_list}"
            )

        @given(
            scraper_name=scraper_name_strategy,
            total=total_strategy,
            completed=completed_strategy,
        )
        @settings(max_examples=50)
        def test_successful_run_sequence_always_ends_completed(
            self, scraper_name, total, completed
        ):
            """
            For ANY scraper name and ANY (total, completed) counts, a full
            start → finish sequence must always result in status='completed'
            on the second SQL call.

            **Validates: Requirements 2.7, 2.8**
            """
            mock_conn, mock_cursor = _make_scrape_run_mock_conn(run_id=1)
            run_id = start_scrape_run(mock_conn, scraper_name)
            finish_scrape_run(mock_conn, run_id=run_id, total=total, completed=completed)

            assert mock_cursor.execute.call_count == 2, (
                "start + finish must produce exactly 2 execute() calls."
            )
            sql_start, _ = _get_execute_sql_and_params(mock_cursor, 0)
            sql_finish, _ = _get_execute_sql_and_params(mock_cursor, 1)
            assert "'running'" in sql_start, "First call must set status='running'."
            assert "'completed'" in sql_finish, "Second call must set status='completed'."
            assert mock_conn.commit.call_count == 2, "commit() must be called twice."

        @given(
            scraper_name=scraper_name_strategy,
            error=error_msg_strategy,
        )
        @settings(max_examples=50)
        def test_failed_run_sequence_always_ends_failed(self, scraper_name, error):
            """
            For ANY scraper name and ANY error message, a full start → fail
            sequence must always result in status='failed' on the second SQL call.

            **Validates: Requirements 2.7, 2.9**
            """
            mock_conn, mock_cursor = _make_scrape_run_mock_conn(run_id=1)
            run_id = start_scrape_run(mock_conn, scraper_name)
            fail_scrape_run(mock_conn, run_id=run_id, error=error)

            assert mock_cursor.execute.call_count == 2, (
                "start + fail must produce exactly 2 execute() calls."
            )
            sql_start, _ = _get_execute_sql_and_params(mock_cursor, 0)
            sql_fail, _ = _get_execute_sql_and_params(mock_cursor, 1)
            assert "'running'" in sql_start, "First call must set status='running'."
            assert "'failed'" in sql_fail, "Second call must set status='failed'."
            assert mock_conn.commit.call_count == 2, "commit() must be called twice."


if __name__ == "__main__":
    unittest.main()
