"""Demonstration dataset.

Generates six months of realistic records for a young salaried professional in
India, dated relative to today so the dashboard is informative whenever the app
is first opened. Every record is stored with ``is_sample = 1`` so it can be
identified and removed without touching user-entered data.

The amounts are deterministic (fixed random seed), and investment valuations are
illustrative values, not market prices.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from finsight import database as db
from finsight.calculations import month_key, shift_month
from finsight.constants import VALUATION_FIXED, VALUATION_UNITS

SAMPLE_MONTHS = 6


def _month_start(month: str) -> date:
    year, mon = month.split("-")
    return date(int(year), int(mon), 1)


def _day(month: str, day: int) -> date:
    start = _month_start(month)
    # Clamp to the month's last day (e.g. day 31 in a 30-day month).
    next_month = _month_start(shift_month(month, 1))
    return min(start + timedelta(days=day - 1), next_month - timedelta(days=1))


def _transactions_for_month(month: str, index: int, rng: random.Random) -> list[tuple]:
    """Rows of (day, description, category, type, amount, payment_method, notes)."""
    rows = [
        (1, "Monthly salary", "Salary", "Income", 58000, "Bank Transfer", "Net pay after TDS"),
        (2, "Metro card recharge", "Travel", "Expense", 1000, "UPI", ""),
        (3, "House rent", "Housing", "Expense", 15000, "Bank Transfer", "Shared 2BHK"),
        (5, "Electricity bill", "Bills and Utilities", "Expense", rng.randrange(1100, 1900, 10), "Net Banking", ""),
        (6, "Mobile & broadband", "Bills and Utilities", "Expense", 999, "UPI", ""),
        (15, "Streaming subscriptions", "Entertainment", "Expense", 649, "Credit Card", ""),
    ]
    # Weekly groceries.
    for day in (4, 11, 18, 25):
        rows.append((day, "Groceries", "Food", "Expense", rng.randrange(1600, 2600, 10), "UPI", ""))
    # Eating out and food delivery.
    for day in rng.sample(range(7, 29), 5):
        description = rng.choice(["Dinner with friends", "Food delivery", "Café", "Lunch outing"])
        rows.append((day, description, "Food", "Expense", rng.randrange(250, 1200, 10),
                     rng.choice(["UPI", "Credit Card"]), ""))
    # Cab rides.
    for day in rng.sample(range(7, 29), 4):
        rows.append((day, "Cab ride", "Travel", "Expense", rng.randrange(180, 480, 10), "UPI", ""))
    # Shopping.
    for day in rng.sample(range(8, 28), rng.choice([1, 2])):
        description = rng.choice(["Clothing", "Home essentials", "Online order", "Footwear"])
        rows.append((day, description, "Shopping", "Expense", rng.randrange(900, 3200, 10),
                     "Credit Card", ""))
    rows.append((rng.randrange(16, 27), "Movie tickets", "Entertainment", "Expense",
                 rng.randrange(500, 900, 10), "Debit Card", ""))
    if index % 2 == 0:
        rows.append((rng.randrange(9, 22), "Pharmacy", "Healthcare", "Expense",
                     rng.randrange(250, 900, 10), "Cash", ""))
    if index % 3 == 1:
        rows.append((10, "Online course", "Education", "Expense", 1499, "Credit Card", "Data analytics course"))
    if index % 3 == 2:
        rows.append((28, "Savings account interest", "Investment Income", "Income", 412, "Bank Transfer", ""))

    # Month-specific events so insights have something real to find.
    events = {
        0: [(14, "Freelance website project", "Freelance", "Income", 8500, "Bank Transfer", "")],
        2: [(20, "Doctor consultation", "Healthcare", "Expense", 1200, "UPI", "")],
        3: [(12, "Freelance logo design", "Freelance", "Income", 6000, "Bank Transfer", ""),
            (22, "Birthday gift for sister", "Other", "Expense", 2500, "UPI", "")],
        4: [(19, "Weekend trip — train tickets", "Travel", "Expense", 2400, "UPI", "")],
        5: [(9, "Flight tickets — Goa trip", "Travel", "Expense", 8400, "Credit Card", "Booked for December"),
            (21, "Festive shopping", "Shopping", "Expense", 4800, "Credit Card", ""),
            (23, "Sweets and gifts", "Food", "Expense", 2200, "UPI", "")],
    }
    rows.extend(events.get(index, []))
    return rows


def load_sample_data(db_path=None, today: date | None = None) -> None:
    """Insert the demonstration dataset in one transaction. Existing records are not modified."""
    with db.session(db_path):
        _insert_sample_data(db_path, today)


def _insert_sample_data(db_path=None, today: date | None = None) -> None:
    today = today or date.today()
    rng = random.Random(2026)
    current_month = month_key(today)
    months = [shift_month(current_month, -offset) for offset in range(SAMPLE_MONTHS - 1, -1, -1)]

    for index, month in enumerate(months):
        for day, description, category, txn_type, amount, method, notes in _transactions_for_month(month, index, rng):
            txn_date = _day(month, day)
            if txn_date > today:
                continue  # never create future-dated records
            db.add_transaction(txn_date, description, category, txn_type, amount, method,
                               notes, is_sample=True, db_path=db_path)

    # Budgets for the last three months.
    budget_plan = {
        "Food": 14000, "Travel": 5000, "Shopping": 9000, "Entertainment": 2000,
        "Bills and Utilities": 3500, "Housing": 15000,
    }
    for month in months[-3:]:
        for category, limit in budget_plan.items():
            db.add_budget(month, category, limit, is_sample=True, db_path=db_path)

    # Savings goals with contribution history.
    emergency = db.add_goal(
        "Emergency Fund", 150000, None,
        "Six months of essential expenses, kept in a liquid account.",
        is_sample=True, db_path=db_path,
    )
    db.add_contribution(emergency, 60000, _day(months[0], 1), "Opening balance", db_path=db_path)
    laptop = db.add_goal(
        "New Laptop", 85000, _day(shift_month(current_month, 5), 28),
        "Upgrade for data science coursework.", is_sample=True, db_path=db_path,
    )
    vacation = db.add_goal(
        "Goa Vacation", 25000, _day(shift_month(current_month, 1), 20),
        "December trip with college friends.", is_sample=True, db_path=db_path,
    )
    for month in months:
        contribution_date = min(_day(month, 2), today)
        db.add_contribution(emergency, 5000, contribution_date, "Monthly transfer", db_path=db_path)
        db.add_contribution(laptop, 5000, contribution_date, "Monthly transfer", db_path=db_path)
    for month in months[-5:]:
        db.add_contribution(vacation, 5000, min(_day(month, 2), today), "Monthly transfer", db_path=db_path)

    # Small investment portfolio (illustrative, manually entered valuations).
    note = "Demonstration record — prices are illustrative and manually entered."
    holdings = [
        ("Nifty 50 Index Fund", "Mutual Funds", VALUATION_UNITS, 412.35, 218.40, 241.10, None, None, 300),
        ("Flexi Cap Fund (SIP)", "Mutual Funds", VALUATION_UNITS, 186.52, 96.80, 104.25, None, None, 240),
        ("IT Services Co. (demo stock)", "Stocks", VALUATION_UNITS, 15, 1540.00, 1612.50, None, None, 200),
        ("Private Bank (demo stock)", "Stocks", VALUATION_UNITS, 20, 1610.00, 1575.20, None, None, 150),
        ("Gold ETF", "Exchange-Traded Funds", VALUATION_UNITS, 150, 62.50, 74.20, None, None, 330),
        ("Gold coin (5 g)", "Gold", VALUATION_FIXED, None, None, None, 31500, 36800, 400),
        ("Bank Fixed Deposit — 1 yr", "Fixed Deposits", VALUATION_FIXED, None, None, None, 50000, 52150, 210),
    ]
    for name, category, mode, qty, buy, current, invested, value, days_ago in holdings:
        db.add_investment(
            name, category, mode, today - timedelta(days=days_ago), quantity=qty,
            purchase_price=buy, current_price=current, invested_amount=invested,
            current_value=value, notes=note, is_sample=True, db_path=db_path,
        )


def initialize(db_path=None) -> bool:
    """Create tables and, on the very first run only, load the demonstration data.

    Returns True when sample data was loaded. A settings flag records that first-run
    setup happened, so restarting the app never re-seeds or overwrites user data,
    even if the user later removes all records.
    """
    db.init_db(db_path)
    if db.get_setting("initialized", db_path=db_path) is not None:
        return False
    with db.session(db_path):
        loaded = False
        if not db.has_any_data(db_path):
            _insert_sample_data(db_path)
            loaded = True
        db.set_setting("initialized", "1", db_path=db_path)
    return loaded


def reset_sample_data(db_path=None) -> None:
    """Replace demo records with a fresh set, atomically. User records are untouched."""
    with db.session(db_path):
        db.delete_sample_data(db_path)
        _insert_sample_data(db_path)
