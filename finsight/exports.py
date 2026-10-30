"""CSV and ZIP exports."""

from __future__ import annotations

import io
import zipfile

import pandas as pd

from finsight import database as db

TRANSACTION_EXPORT_COLUMNS = [
    "id", "date", "description", "category", "type", "amount", "payment_method", "notes", "source",
]


def export_csv(frame: pd.DataFrame) -> bytes:
    """Transactions as CSV with numeric amounts and ISO dates, ready for spreadsheets."""
    export = frame.copy()
    export["date"] = export["date"].dt.strftime("%Y-%m-%d")
    export["source"] = export["is_sample"].map({1: "Demo", 0: "User"})
    return export[TRANSACTION_EXPORT_COLUMNS].to_csv(index=False).encode("utf-8-sig")


def export_zip(db_path=None) -> bytes:
    """Every table as a CSV file inside one ZIP archive."""
    with db.session(db_path):
        tables = {
            "transactions.csv": db.get_transactions(db_path).assign(
                date=lambda d: d["date"].dt.strftime("%Y-%m-%d")),
            "budgets.csv": db.get_budgets(db_path=db_path),
            "savings_goals.csv": db.get_goals(db_path),
            "goal_contributions.csv": db.get_contributions(db_path=db_path).assign(
                date=lambda d: d["date"].dt.strftime("%Y-%m-%d")),
            "investments.csv": db.get_investments(db_path),
        }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, frame in tables.items():
            archive.writestr(name, frame.to_csv(index=False))
    return buffer.getvalue()
