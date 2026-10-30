"""Persistence layer for PostgreSQL (production on Vercel) and SQLite (local/tests).

Every statement is parameterised. Functions take an optional ``db_path`` that
may be a SQLite file path or a ``postgresql://`` URL; when it is omitted the
target comes from the environment:

* ``DATABASE_URL`` or ``POSTGRES_URL``  -> PostgreSQL (e.g. Neon via Vercel)
* running on Vercel without a database -> SQLite in /tmp (temporary, resets)
* otherwise                            -> SQLite at data/finsight.db
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from finsight.validation import (
    ValidationError,
    to_iso_date,
    validate_amount,
    validate_budget,
    validate_goal,
    validate_investment,
    validate_month,
    validate_transaction,
)

try:  # psycopg is only needed when a PostgreSQL URL is configured
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    psycopg = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "finsight.db"

_INTEGRITY_ERRORS: tuple = (sqlite3.IntegrityError,)
if psycopg is not None:
    _INTEGRITY_ERRORS += (psycopg.errors.IntegrityError,)

# When set, get_connection() reuses this connection instead of opening a new one.
_active_connection: ContextVar = ContextVar("finsight_active_connection", default=None)


class DuplicateBudgetError(ValidationError):
    """Raised when a budget already exists for the same month and category."""


# --------------------------------------------------------------------------- #
# Target resolution and connections
# --------------------------------------------------------------------------- #
def find_database_url(env) -> str | None:
    """Find a PostgreSQL URL in the environment.

    Prefers DATABASE_URL / POSTGRES_URL. When a database is connected in Vercel
    with a custom prefix the variables are named e.g. STORAGE_DATABASE_URL, so any
    variable ending in _DATABASE_URL or _POSTGRES_URL is accepted as a fallback.
    Unpooled/direct variants are skipped in favour of pooled URLs, which suit
    serverless functions better.
    """
    for name in ("DATABASE_URL", "POSTGRES_URL"):
        if env.get(name, "").startswith(("postgres://", "postgresql://")):
            return env[name]
    for name in sorted(env):
        if name.endswith(("_DATABASE_URL", "_POSTGRES_URL")) and "UNPOOLED" not in name \
                and env[name].startswith(("postgres://", "postgresql://")):
            return env[name]
    return None


def resolve_db_path(db_path=None) -> str:
    """Return the database target: a postgres URL or a SQLite file path."""
    if db_path is not None:
        return str(db_path)
    url = find_database_url(os.environ)
    if url:
        return url
    if os.environ.get("FINSIGHT_DB_PATH"):
        return os.environ["FINSIGHT_DB_PATH"]
    if os.environ.get("VERCEL"):
        return "/tmp/finsight.db"  # writable but temporary on Vercel
    return str(DEFAULT_DB_PATH)


def is_postgres(target: str) -> bool:
    return target.startswith(("postgres://", "postgresql://"))


def storage_mode(db_path=None) -> str:
    """'postgres', 'temporary' (SQLite on Vercel) or 'local' (SQLite file)."""
    target = resolve_db_path(db_path)
    if is_postgres(target):
        return "postgres"
    return "temporary" if target.startswith("/tmp/") else "local"


class _Connection:
    """Thin wrapper giving SQLite and psycopg the same small API."""

    def __init__(self, raw, postgres: bool):
        self.raw = raw
        self.postgres = postgres

    def execute(self, sql: str, params=()):
        if self.postgres:
            sql = sql.replace("?", "%s")
        cursor = self.raw.cursor()
        cursor.execute(sql, tuple(params))
        return cursor

    def fetchone(self, sql: str, params=()):
        row = self.execute(sql, params).fetchone()
        return dict(row) if row is not None else None

    def fetchall(self, sql: str, params=()):
        return [dict(row) for row in self.execute(sql, params).fetchall()]

    def dataframe(self, sql: str, params=()) -> pd.DataFrame:
        cursor = self.execute(sql, params)
        columns = [col[0] for col in cursor.description]
        return pd.DataFrame([dict(row) for row in cursor.fetchall()], columns=columns)


def _open(target: str) -> _Connection:
    if is_postgres(target):
        if psycopg is None:
            raise RuntimeError("psycopg is required for PostgreSQL. Install requirements.txt.")
        # prepare_threshold=None keeps it compatible with pooled (PgBouncer) URLs.
        raw = psycopg.connect(target, row_factory=dict_row, prepare_threshold=None)
        return _Connection(raw, postgres=True)
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(path)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA foreign_keys = ON")
    return _Connection(raw, postgres=False)


@contextmanager
def get_connection(db_path=None):
    """Yield a connection; commit on success, roll back on error.

    Inside ``session()`` the shared connection is reused and committed once at the end.
    """
    active = _active_connection.get()
    if active is not None:
        yield active
        return
    conn = _open(resolve_db_path(db_path))
    try:
        yield conn
        conn.raw.commit()
    except Exception:
        conn.raw.rollback()
        raise
    finally:
        conn.raw.close()


@contextmanager
def session(db_path=None):
    """Run several operations on one connection and one transaction.

    Used for bulk work such as loading sample data, where opening a new network
    connection per insert would be slow on a hosted database.
    """
    if _active_connection.get() is not None:
        yield
        return
    conn = _open(resolve_db_path(db_path))
    token = _active_connection.set(conn)
    try:
        yield
        conn.raw.commit()
    except Exception:
        conn.raw.rollback()
        raise
    finally:
        _active_connection.reset(token)
        conn.raw.close()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #
# {ID} and {REAL} are replaced per database: SQLite uses INTEGER PRIMARY KEY
# AUTOINCREMENT and REAL; PostgreSQL uses an identity column and DOUBLE PRECISION
# (PostgreSQL's REAL is only 6 significant digits, too few for money).
SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id              {ID},
    date            TEXT    NOT NULL,
    description     TEXT    NOT NULL,
    category        TEXT    NOT NULL,
    type            TEXT    NOT NULL CHECK (type IN ('Income', 'Expense')),
    amount          {REAL}  NOT NULL CHECK (amount > 0),
    payment_method  TEXT    NOT NULL,
    notes           TEXT    NOT NULL DEFAULT '',
    is_sample       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions (date);
CREATE TABLE IF NOT EXISTS budgets (
    id          {ID},
    month       TEXT    NOT NULL,
    category    TEXT    NOT NULL,
    amount      {REAL}  NOT NULL CHECK (amount > 0),
    is_sample   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL,
    UNIQUE (month, category)
);
CREATE TABLE IF NOT EXISTS savings_goals (
    id              {ID},
    name            TEXT    NOT NULL,
    target_amount   {REAL}  NOT NULL CHECK (target_amount > 0),
    target_date     TEXT,
    description     TEXT    NOT NULL DEFAULT '',
    is_sample       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS goal_contributions (
    id          {ID},
    goal_id     INTEGER NOT NULL REFERENCES savings_goals (id) ON DELETE CASCADE,
    date        TEXT    NOT NULL,
    amount      {REAL}  NOT NULL,
    kind        TEXT    NOT NULL DEFAULT 'contribution' CHECK (kind IN ('contribution', 'adjustment')),
    note        TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contributions_goal ON goal_contributions (goal_id);
CREATE TABLE IF NOT EXISTS investments (
    id                {ID},
    name              TEXT    NOT NULL,
    category          TEXT    NOT NULL,
    valuation_mode    TEXT    NOT NULL CHECK (valuation_mode IN ('units', 'fixed')),
    quantity          {REAL},
    purchase_price    {REAL},
    current_price     {REAL},
    invested_amount   {REAL},
    current_value     {REAL},
    purchase_date     TEXT    NOT NULL,
    price_updated_at  TEXT    NOT NULL,
    notes             TEXT    NOT NULL DEFAULT '',
    is_sample         INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
)
"""

DATA_TABLES = ["goal_contributions", "transactions", "budgets", "savings_goals", "investments"]
RECORD_TABLES = ["transactions", "budgets", "savings_goals", "investments"]


def init_db(db_path=None) -> None:
    """Create all tables if they do not exist. Safe to call on every start."""
    with get_connection(db_path) as conn:
        if conn.postgres:
            ddl = SCHEMA.replace("{ID}", "INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY")
            ddl = ddl.replace("{REAL}", "DOUBLE PRECISION")
        else:
            ddl = SCHEMA.replace("{ID}", "INTEGER PRIMARY KEY AUTOINCREMENT").replace("{REAL}", "REAL")
        for statement in ddl.split(";"):
            if statement.strip():
                conn.execute(statement)


def _insert(conn, sql: str, params) -> int:
    """Run an INSERT ... RETURNING id (supported by SQLite 3.35+ and PostgreSQL)."""
    return int(conn.fetchone(sql + " RETURNING id", params)["id"])


# --------------------------------------------------------------------------- #
# Transactions
# --------------------------------------------------------------------------- #
def add_transaction(
    txn_date, description, category, txn_type, amount, payment_method,
    notes="", is_sample=False, db_path=None,
) -> int:
    data = validate_transaction(txn_date, description, category, txn_type, amount, payment_method, notes)
    now = _now()
    with get_connection(db_path) as conn:
        return _insert(
            conn,
            """INSERT INTO transactions
               (date, description, category, type, amount, payment_method, notes,
                is_sample, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["date"], data["description"], data["category"], data["type"],
             data["amount"], data["payment_method"], data["notes"], int(is_sample), now, now),
        )


def update_transaction(
    txn_id, txn_date, description, category, txn_type, amount, payment_method,
    notes="", db_path=None,
) -> bool:
    """Update in place. Editing marks the record as user data (is_sample = 0)."""
    data = validate_transaction(txn_date, description, category, txn_type, amount, payment_method, notes)
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """UPDATE transactions
               SET date = ?, description = ?, category = ?, type = ?, amount = ?,
                   payment_method = ?, notes = ?, is_sample = 0, updated_at = ?
               WHERE id = ?""",
            (data["date"], data["description"], data["category"], data["type"],
             data["amount"], data["payment_method"], data["notes"], _now(), int(txn_id)),
        )
        return cursor.rowcount == 1


def delete_transaction(txn_id, db_path=None) -> bool:
    with get_connection(db_path) as conn:
        return conn.execute("DELETE FROM transactions WHERE id = ?", (int(txn_id),)).rowcount == 1


def get_transaction(txn_id, db_path=None) -> dict | None:
    with get_connection(db_path) as conn:
        return conn.fetchone("SELECT * FROM transactions WHERE id = ?", (int(txn_id),))


def get_transactions(db_path=None) -> pd.DataFrame:
    """All transactions, newest first, with 'date' parsed as datetime."""
    with get_connection(db_path) as conn:
        df = conn.dataframe("SELECT * FROM transactions ORDER BY date DESC, id DESC")
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d")
    df["amount"] = df["amount"].astype(float)
    return df


# --------------------------------------------------------------------------- #
# Budgets
# --------------------------------------------------------------------------- #
def add_budget(month, category, amount, is_sample=False, db_path=None) -> int:
    data = validate_budget(month, category, amount)
    with get_connection(db_path) as conn:
        existing = conn.fetchone(
            "SELECT id FROM budgets WHERE month = ? AND category = ?", (data["month"], data["category"])
        )
        if existing is None:
            try:
                return _insert(
                    conn,
                    "INSERT INTO budgets (month, category, amount, is_sample, created_at) VALUES (?, ?, ?, ?, ?)",
                    (data["month"], data["category"], data["amount"], int(is_sample), _now()),
                )
            except _INTEGRITY_ERRORS:
                pass  # created concurrently; report it as a duplicate below
    raise DuplicateBudgetError(
        f"A {data['category']} budget already exists for {data['month']}. Edit the existing budget instead."
    )


def update_budget(budget_id, amount, db_path=None) -> bool:
    limit = validate_amount(amount, "Budget limit")
    with get_connection(db_path) as conn:
        cursor = conn.execute("UPDATE budgets SET amount = ?, is_sample = 0 WHERE id = ?", (limit, int(budget_id)))
        return cursor.rowcount == 1


def delete_budget(budget_id, db_path=None) -> bool:
    with get_connection(db_path) as conn:
        return conn.execute("DELETE FROM budgets WHERE id = ?", (int(budget_id),)).rowcount == 1


def get_budgets(month=None, db_path=None) -> pd.DataFrame:
    with get_connection(db_path) as conn:
        if month is None:
            df = conn.dataframe("SELECT * FROM budgets ORDER BY month DESC, category")
        else:
            df = conn.dataframe("SELECT * FROM budgets WHERE month = ? ORDER BY category", (validate_month(month),))
    df["amount"] = df["amount"].astype(float)
    return df


def copy_budgets(from_month, to_month, db_path=None) -> int:
    """Copy budgets between months, skipping categories that already exist."""
    source, target = validate_month(from_month), validate_month(to_month)
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO budgets (month, category, amount, is_sample, created_at)
               SELECT ?, category, amount, 0, ? FROM budgets WHERE month = ?
               ON CONFLICT (month, category) DO NOTHING""",
            (target, _now(), source),
        )
        return max(cursor.rowcount, 0)


# --------------------------------------------------------------------------- #
# Savings goals
# --------------------------------------------------------------------------- #
def add_goal(
    name, target_amount, target_date=None, description="", initial_saved=0.0,
    is_sample=False, db_path=None,
) -> int:
    data = validate_goal(name, target_amount, target_date, description)
    initial = validate_amount(initial_saved, "Amount already saved", allow_zero=True)
    now = _now()
    with get_connection(db_path) as conn:
        goal_id = _insert(
            conn,
            """INSERT INTO savings_goals (name, target_amount, target_date, description, is_sample, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["name"], data["target_amount"], data["target_date"], data["description"], int(is_sample), now),
        )
        if initial > 0:
            conn.execute(
                """INSERT INTO goal_contributions (goal_id, date, amount, kind, note, created_at)
                   VALUES (?, ?, ?, 'contribution', 'Opening balance', ?)""",
                (goal_id, date.today().isoformat(), initial, now),
            )
        return goal_id


def update_goal(goal_id, name, target_amount, target_date=None, description="", db_path=None) -> bool:
    data = validate_goal(name, target_amount, target_date, description)
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """UPDATE savings_goals SET name = ?, target_amount = ?, target_date = ?, description = ?, is_sample = 0
               WHERE id = ?""",
            (data["name"], data["target_amount"], data["target_date"], data["description"], int(goal_id)),
        )
        return cursor.rowcount == 1


def delete_goal(goal_id, db_path=None) -> bool:
    """Delete a goal; its contributions are removed by ON DELETE CASCADE."""
    with get_connection(db_path) as conn:
        return conn.execute("DELETE FROM savings_goals WHERE id = ?", (int(goal_id),)).rowcount == 1


def _goal_exists(conn, goal_id) -> bool:
    return conn.fetchone("SELECT id FROM savings_goals WHERE id = ?", (int(goal_id),)) is not None


def add_contribution(goal_id, amount, contribution_date=None, note="", db_path=None) -> int:
    value = validate_amount(amount, "Contribution")
    iso_date = to_iso_date(contribution_date or date.today(), "Contribution date")
    with get_connection(db_path) as conn:
        if not _goal_exists(conn, goal_id):
            raise ValidationError("That savings goal no longer exists.")
        return _insert(
            conn,
            """INSERT INTO goal_contributions (goal_id, date, amount, kind, note, created_at)
               VALUES (?, ?, ?, 'contribution', ?, ?)""",
            (int(goal_id), iso_date, value, str(note or "").strip()[:200], _now()),
        )


def get_goal_saved_amount(goal_id, db_path=None) -> float:
    with get_connection(db_path) as conn:
        row = conn.fetchone(
            "SELECT COALESCE(SUM(amount), 0) AS saved FROM goal_contributions WHERE goal_id = ?", (int(goal_id),)
        )
    return float(row["saved"])


def set_goal_saved_amount(goal_id, new_amount, note="Manual balance update", db_path=None) -> float:
    """Set the saved amount by recording an adjustment for the difference."""
    target = validate_amount(new_amount, "Saved amount", allow_zero=True)
    with get_connection(db_path) as conn:
        if not _goal_exists(conn, goal_id):
            raise ValidationError("That savings goal no longer exists.")
        current = conn.fetchone(
            "SELECT COALESCE(SUM(amount), 0) AS saved FROM goal_contributions WHERE goal_id = ?", (int(goal_id),)
        )["saved"]
        difference = round(target - float(current), 2)
        if difference != 0:
            conn.execute(
                """INSERT INTO goal_contributions (goal_id, date, amount, kind, note, created_at)
                   VALUES (?, ?, ?, 'adjustment', ?, ?)""",
                (int(goal_id), date.today().isoformat(), difference, note, _now()),
            )
        return difference


def get_goals(db_path=None) -> pd.DataFrame:
    """Goals with their saved amount (sum of contributions)."""
    with get_connection(db_path) as conn:
        df = conn.dataframe(
            """SELECT g.id, g.name, g.target_amount, g.target_date, g.description, g.is_sample, g.created_at,
                      COALESCE(SUM(c.amount), 0) AS saved_amount
               FROM savings_goals g
               LEFT JOIN goal_contributions c ON c.goal_id = g.id
               GROUP BY g.id, g.name, g.target_amount, g.target_date, g.description, g.is_sample, g.created_at
               ORDER BY g.created_at, g.id"""
        )
    df["target_amount"] = df["target_amount"].astype(float)
    df["saved_amount"] = df["saved_amount"].astype(float)
    return df


def get_contributions(goal_id=None, db_path=None) -> pd.DataFrame:
    with get_connection(db_path) as conn:
        if goal_id is None:
            df = conn.dataframe("SELECT * FROM goal_contributions ORDER BY date DESC, id DESC")
        else:
            df = conn.dataframe(
                "SELECT * FROM goal_contributions WHERE goal_id = ? ORDER BY date DESC, id DESC", (int(goal_id),)
            )
    df["amount"] = df["amount"].astype(float)
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d")
    return df


# --------------------------------------------------------------------------- #
# Investments
# --------------------------------------------------------------------------- #
def add_investment(
    name, category, valuation_mode, purchase_date, quantity=None, purchase_price=None,
    current_price=None, invested_amount=None, current_value=None, notes="",
    is_sample=False, db_path=None,
) -> int:
    data = validate_investment(name, category, valuation_mode, purchase_date, quantity, purchase_price,
                               current_price, invested_amount, current_value, notes)
    now = _now()
    with get_connection(db_path) as conn:
        return _insert(
            conn,
            """INSERT INTO investments
               (name, category, valuation_mode, quantity, purchase_price, current_price, invested_amount,
                current_value, purchase_date, price_updated_at, notes, is_sample, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["name"], data["category"], data["valuation_mode"], data["quantity"], data["purchase_price"],
             data["current_price"], data["invested_amount"], data["current_value"], data["purchase_date"],
             now, data["notes"], int(is_sample), now),
        )


def update_investment(
    investment_id, name, category, valuation_mode, purchase_date, quantity=None,
    purchase_price=None, current_price=None, invested_amount=None, current_value=None,
    notes="", db_path=None,
) -> bool:
    data = validate_investment(name, category, valuation_mode, purchase_date, quantity, purchase_price,
                               current_price, invested_amount, current_value, notes)
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """UPDATE investments
               SET name = ?, category = ?, valuation_mode = ?, quantity = ?, purchase_price = ?, current_price = ?,
                   invested_amount = ?, current_value = ?, purchase_date = ?, price_updated_at = ?, notes = ?,
                   is_sample = 0
               WHERE id = ?""",
            (data["name"], data["category"], data["valuation_mode"], data["quantity"], data["purchase_price"],
             data["current_price"], data["invested_amount"], data["current_value"], data["purchase_date"],
             _now(), data["notes"], int(investment_id)),
        )
        return cursor.rowcount == 1


def update_investment_valuation(investment_id, new_value, db_path=None) -> bool:
    """Update only the current price (units mode) or current value (fixed mode)."""
    value = validate_amount(new_value, "Current valuation", allow_zero=True)
    with get_connection(db_path) as conn:
        row = conn.fetchone("SELECT valuation_mode FROM investments WHERE id = ?", (int(investment_id),))
        if row is None:
            return False
        if row["valuation_mode"] == "units":
            sql = "UPDATE investments SET current_price = ?, price_updated_at = ? WHERE id = ?"
        else:
            sql = "UPDATE investments SET current_value = ?, price_updated_at = ? WHERE id = ?"
        conn.execute(sql, (value, _now(), int(investment_id)))
        return True


def delete_investment(investment_id, db_path=None) -> bool:
    with get_connection(db_path) as conn:
        return conn.execute("DELETE FROM investments WHERE id = ?", (int(investment_id),)).rowcount == 1


def get_investments(db_path=None) -> pd.DataFrame:
    with get_connection(db_path) as conn:
        return conn.dataframe("SELECT * FROM investments ORDER BY category, name")


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
def get_setting(key, default=None, db_path=None):
    with get_connection(db_path) as conn:
        row = conn.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row else default


def set_setting(key, value, db_path=None) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )


def get_all_settings(db_path=None) -> dict:
    with get_connection(db_path) as conn:
        return {row["key"]: row["value"] for row in conn.fetchall("SELECT key, value FROM settings")}


# --------------------------------------------------------------------------- #
# Data management
# --------------------------------------------------------------------------- #
# Table names below come from the fixed lists above, never from user input.
def get_record_counts(db_path=None) -> dict:
    counts = {}
    with get_connection(db_path) as conn:
        for table in RECORD_TABLES:
            row = conn.fetchone(f"SELECT COALESCE(SUM(is_sample), 0) AS sample, COUNT(*) AS total FROM {table}")
            counts[table] = {"sample": int(row["sample"]), "user": int(row["total"]) - int(row["sample"])}
    return counts


def has_any_data(db_path=None) -> bool:
    return any(c["sample"] + c["user"] > 0 for c in get_record_counts(db_path).values())


def delete_sample_data(db_path=None) -> None:
    """Remove demonstration records only; user-entered records are kept."""
    with get_connection(db_path) as conn:
        for table in RECORD_TABLES:
            conn.execute(f"DELETE FROM {table} WHERE is_sample = 1")


def clear_all_data(db_path=None) -> None:
    """Delete every financial record (settings such as the user's name are kept)."""
    with get_connection(db_path) as conn:
        for table in DATA_TABLES:
            conn.execute(f"DELETE FROM {table}")
