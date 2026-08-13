"""
Database connection utilities for hydurban.

Connection string configuration:
  - Primary: add a "db_connection" key to scrape_preferences.json with the
    PostgreSQL connection string, e.g.:
        "db_connection": "postgresql://hydurban_app:password@localhost:5432/hydurban"
  - Fallback: set the DATABASE_URL environment variable to the same format.
"""

import json
import os

import psycopg2

_PREFS_PATH = os.path.join(os.path.dirname(__file__), "scrape_preferences.json")


def get_connection_string() -> str:
    """Return the PostgreSQL connection string.

    Lookup order:
    1. "db_connection" key in scrape_preferences.json (next to this file)
    2. DATABASE_URL environment variable

    Raises:
        ValueError: if neither source provides a connection string.
    """
    # Try scrape_preferences.json first
    try:
        with open(_PREFS_PATH, "r", encoding="utf-8") as fh:
            prefs = json.load(fh)
        conn_str = prefs.get("db_connection")
        if conn_str:
            return conn_str
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Fall back to environment variable
    conn_str = os.environ.get("DATABASE_URL")
    if conn_str:
        return conn_str

    raise ValueError(
        "No database connection string found. "
        'Add a "db_connection" key to scrape_preferences.json or set the '
        "DATABASE_URL environment variable. "
        "Expected format: postgresql://hydurban_app:password@localhost:5432/hydurban"
    )


def get_connection() -> "psycopg2.extensions.connection":
    """Open and return a psycopg2 database connection.

    The caller is responsible for closing the connection (or using it as a
    context manager).

    Returns:
        An open psycopg2 connection object.

    Raises:
        ValueError: if no connection string is configured.
        psycopg2.OperationalError: if the connection cannot be established.
    """
    conn_str = get_connection_string()
    return psycopg2.connect(conn_str)


# ── Scrape run tracking ────────────────────────────────────────────────────────

def start_scrape_run(conn, scraper_name: str) -> int:
    """Insert a scrape_runs row with status='running' and return the new run id.

    Args:
        conn: An open psycopg2 connection.
        scraper_name: One of 'rera', 'sro', 'rr'.

    Returns:
        The integer primary key of the new scrape_runs row.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO scrape_runs (scraper, status, started_at, total, completed, errors)
            VALUES (%s, 'running', NOW(), 0, 0, '[]'::jsonb)
            RETURNING id
            """,
            (scraper_name,),
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    return run_id


def finish_scrape_run(conn, run_id: int, total: int, completed: int) -> None:
    """Update a scrape_runs row to status='completed'.

    Args:
        conn: An open psycopg2 connection.
        run_id: The id returned by start_scrape_run.
        total: Total number of items attempted.
        completed: Number of items successfully processed.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE scrape_runs
            SET status = 'completed', finished_at = NOW(), total = %s, completed = %s
            WHERE id = %s
            """,
            (total, completed, run_id),
        )
    conn.commit()


def fail_scrape_run(conn, run_id: int, error: str) -> None:
    """Update a scrape_runs row to status='failed', appending the error detail.

    Args:
        conn: An open psycopg2 connection.
        run_id: The id returned by start_scrape_run.
        error: A human-readable description of the fatal error.
    """
    import json as _json
    import datetime as _dt

    error_entry = _json.dumps([{
        "error": error,
        "at": _dt.datetime.utcnow().isoformat() + "Z",
    }])
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE scrape_runs
            SET status = 'failed', finished_at = NOW(),
                errors = errors || %s::jsonb
            WHERE id = %s
            """,
            (error_entry, run_id),
        )
    conn.commit()


def start_scrape_run(conn, scraper_name: str) -> int:
    """Insert a new scrape_runs row with status='running'. Returns the run id."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO scrape_runs (scraper, status, started_at, total, completed, errors)
            VALUES (%s, 'running', NOW(), 0, 0, '[]')
            RETURNING id
            """,
            (scraper_name,)
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    return run_id


def finish_scrape_run(conn, run_id: int, total: int, completed: int) -> None:
    """Mark a scrape run as completed with final counts."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE scrape_runs
            SET status = 'completed',
                finished_at = NOW(),
                total = %s,
                completed = %s
            WHERE id = %s
            """,
            (total, completed, run_id)
        )
    conn.commit()


def fail_scrape_run(conn, run_id: int, error: str) -> None:
    """Mark a scrape run as failed and append the error to the errors JSONB array."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE scrape_runs
            SET status = 'failed',
                finished_at = NOW(),
                errors = errors || %s::jsonb
            WHERE id = %s
            """,
            (json.dumps([{"error": error, "at": __import__('datetime').datetime.utcnow().isoformat()}]), run_id)
        )
    conn.commit()
