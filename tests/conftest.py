"""Shared fixtures.

Database tests run twice: once on SQLite and once on a real PostgreSQL server
started locally with the `pgserver` package. If pgserver isn't installed the
PostgreSQL variants are skipped.
"""

import uuid
from datetime import date

import pandas as pd
import pytest

from finsight import database as db

try:
    import pgserver
except ImportError:  # pragma: no cover
    pgserver = None


@pytest.fixture(scope="session")
def postgres_server(tmp_path_factory):
    if pgserver is None:
        pytest.skip("pgserver not installed")
    server = pgserver.get_server(tmp_path_factory.mktemp("pgdata"), cleanup_mode="stop")
    yield server
    server.cleanup()


@pytest.fixture(params=["sqlite", "postgres"])
def fresh_target(request, tmp_path):
    """An empty, uninitialised database target (file path or postgres URL)."""
    if request.param == "sqlite":
        return tmp_path / "test.db"
    server = request.getfixturevalue("postgres_server")
    name = f"t_{uuid.uuid4().hex[:12]}"
    server.psql(f"CREATE DATABASE {name};")
    base = server.get_uri()  # postgresql://user:pw@host/dbname?...
    prefix, _, rest = base.rpartition("/")
    query = rest.split("?", 1)[1] if "?" in rest else ""
    return f"{prefix}/{name}" + (f"?{query}" if query else "")


@pytest.fixture
def db_path(fresh_target):
    """A fresh, initialised database for each test (SQLite and PostgreSQL)."""
    db.init_db(fresh_target)
    return fresh_target


def make_transactions(rows):
    """Build a transactions DataFrame like database.get_transactions() returns.

    rows: list of (date_str, type, category, amount[, description])
    """
    records = []
    for index, row in enumerate(rows, start=1):
        txn_date, txn_type, category, amount = row[:4]
        description = row[4] if len(row) > 4 else f"txn {index}"
        records.append({
            "id": index, "date": pd.Timestamp(txn_date), "description": description,
            "category": category, "type": txn_type, "amount": float(amount),
            "payment_method": "UPI", "notes": "", "is_sample": 0,
        })
    columns = ["id", "date", "description", "category", "type", "amount", "payment_method", "notes", "is_sample"]
    frame = pd.DataFrame(records, columns=columns)
    frame["date"] = pd.to_datetime(frame["date"])
    frame["amount"] = frame["amount"].astype(float)
    return frame


@pytest.fixture
def today():
    return date(2026, 10, 29)
