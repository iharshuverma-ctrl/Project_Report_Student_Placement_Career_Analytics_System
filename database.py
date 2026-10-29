"""
database.py - MySQL connection handling and small query helpers.

Every query in the project goes through these helpers, and every helper uses
PARAMETERIZED queries (%s placeholders). User input is never pasted into SQL
strings, which prevents SQL injection.

Run this file directly to test the database connection:
    python database.py
"""
from contextlib import contextmanager
from decimal import Decimal

import mysql.connector
import pandas as pd
from mysql.connector import Error, pooling

from config import Config


class DatabaseError(Exception):
    """Raised with a user-friendly message when MySQL is unavailable or a query fails."""


_pool = None


def _get_pool():
    """Create the connection pool once and reuse it."""
    global _pool
    if _pool is None:
        try:
            _pool = pooling.MySQLConnectionPool(
                pool_name="placement_pool",
                pool_size=5,
                pool_reset_session=True,
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME,
                autocommit=False,
                charset="utf8mb4",
                collation="utf8mb4_unicode_ci",
            )
        except Error as exc:
            raise DatabaseError(
                "Could not connect to the MySQL database "
                f"'{Config.DB_NAME}' on {Config.DB_HOST}:{Config.DB_PORT}. "
                "Check that MySQL Server is running and that the credentials in .env are correct. "
                f"(MySQL said: {exc.msg})"
            ) from exc
    return _pool


@contextmanager
def get_connection():
    """Borrow a connection from the pool and always give it back."""
    try:
        conn = _get_pool().get_connection()
    except Error as exc:
        raise DatabaseError(f"Database connection failed: {exc.msg}") from exc
    try:
        yield conn
    finally:
        conn.close()


def _clean_value(value):
    """Convert MySQL Decimal values to float so they work with JSON and pandas."""
    if isinstance(value, Decimal):
        return float(value)
    return value


def _clean_rows(rows):
    return [{k: _clean_value(v) for k, v in row.items()} for row in rows]


def fetch_all(sql, params=None):
    """Run a SELECT and return a list of dictionaries."""
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(sql, params or ())
            return _clean_rows(cur.fetchall())
        except Error as exc:
            raise DatabaseError(f"Query failed: {exc.msg}") from exc
        finally:
            cur.close()


def fetch_one(sql, params=None):
    """Run a SELECT and return the first row (or None)."""
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def fetch_df(sql, params=None):
    """Run a SELECT and return a pandas DataFrame (empty DataFrame with columns if no rows)."""
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(sql, params or ())
            rows = _clean_rows(cur.fetchall())
            columns = [c[0] for c in cur.description] if cur.description else []
            return pd.DataFrame(rows, columns=columns)
        except Error as exc:
            raise DatabaseError(f"Query failed: {exc.msg}") from exc
        finally:
            cur.close()


def execute(sql, params=None):
    """Run a single INSERT / UPDATE / DELETE and commit. Returns the number of affected rows."""
    with transaction() as cur:
        cur.execute(sql, params or ())
        return cur.rowcount


@contextmanager
def transaction():
    """
    Run several statements as ONE transaction:

        with transaction() as cur:
            cur.execute("INSERT ...", (...))
            cur.execute("INSERT ...", (...))

    If anything fails, every statement is rolled back.
    """
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        try:
            yield cur
            conn.commit()
        except Error as exc:
            conn.rollback()
            raise DatabaseError(f"Database update failed: {exc.msg}") from exc
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


def test_connection():
    """Return (True, message) if the database is reachable and the schema exists."""
    try:
        row = fetch_one("SELECT VERSION() AS version, DATABASE() AS db")
        counts = fetch_one(
            "SELECT (SELECT COUNT(*) FROM students) AS students, "
            "(SELECT COUNT(*) FROM companies) AS companies, "
            "(SELECT COUNT(*) FROM placements) AS placements"
        )
        return True, (
            f"Connected to MySQL {row['version']} - database '{row['db']}' "
            f"({counts['students']} students, {counts['companies']} companies, "
            f"{counts['placements']} placement records)"
        )
    except DatabaseError as exc:
        return False, str(exc)


if __name__ == "__main__":
    ok, message = test_connection()
    print(("SUCCESS: " if ok else "ERROR: ") + message)
