"""Financial calculations.

Pure functions over pandas DataFrames: no Streamlit and no database access,
which keeps them easy to test and reuse.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from finsight.constants import (
    DEFAULT_CAUTION_THRESHOLD,
    EXCEEDED_THRESHOLD,
    STATUS_CAUTION,
    STATUS_EXCEEDED,
    STATUS_HEALTHY,
    VALUATION_UNITS,
)


# --------------------------------------------------------------------------- #
# Month helpers
# --------------------------------------------------------------------------- #
def month_key(value) -> str:
    """Return 'YYYY-MM' for a date-like value."""
    return pd.Timestamp(value).strftime("%Y-%m")


def shift_month(month: str, offset: int) -> str:
    """shift_month('2026-01', -1) -> '2025-12'."""
    period = pd.Period(month, freq="M") + offset
    return period.strftime("%Y-%m")


def month_bounds(month: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """First and last calendar day of a month."""
    period = pd.Period(month, freq="M")
    return period.start_time.normalize(), period.end_time.normalize()


def month_range(end_month: str, months: int) -> list[str]:
    """The `months` consecutive months ending at `end_month`, oldest first."""
    return [shift_month(end_month, -offset) for offset in range(months - 1, -1, -1)]


def available_months(transactions: pd.DataFrame) -> list[str]:
    """Months that contain at least one transaction, newest first."""
    if transactions.empty:
        return []
    months = transactions["date"].dt.strftime("%Y-%m").unique().tolist()
    return sorted(months, reverse=True)


# --------------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------------- #
def filter_by_date_range(transactions: pd.DataFrame, start=None, end=None) -> pd.DataFrame:
    """Rows whose date falls within [start, end], both inclusive."""
    mask = pd.Series(True, index=transactions.index)
    if start is not None:
        mask &= transactions["date"] >= pd.Timestamp(start).normalize()
    if end is not None:
        mask &= transactions["date"] <= pd.Timestamp(end).normalize()
    return transactions[mask]


def filter_by_month(transactions: pd.DataFrame, month: str) -> pd.DataFrame:
    start, end = month_bounds(month)
    return filter_by_date_range(transactions, start, end)


def filter_transactions(
    transactions: pd.DataFrame,
    search: str = "",
    start=None,
    end=None,
    categories=None,
    txn_types=None,
    payment_methods=None,
) -> pd.DataFrame:
    """Combine the Transactions page filters. Empty filters mean 'no restriction'."""
    result = filter_by_date_range(transactions, start, end)
    if categories:
        result = result[result["category"].isin(categories)]
    if txn_types:
        result = result[result["type"].isin(txn_types)]
    if payment_methods:
        result = result[result["payment_method"].isin(payment_methods)]
    term = (search or "").strip().lower()
    if term:
        haystack = (
            result["description"].fillna("") + " " + result["notes"].fillna("") + " "
            + result["category"].fillna("")
        ).str.lower()
        result = result[haystack.str.contains(term, regex=False)]
    return result


SORT_OPTIONS = {
    "Date (newest first)": (["date", "id"], [False, False]),
    "Date (oldest first)": (["date", "id"], [True, True]),
    "Amount (highest first)": (["amount", "date"], [False, False]),
    "Amount (lowest first)": (["amount", "date"], [True, False]),
}


def sort_transactions(transactions: pd.DataFrame, sort_label: str) -> pd.DataFrame:
    columns, ascending = SORT_OPTIONS.get(sort_label, SORT_OPTIONS["Date (newest first)"])
    return transactions.sort_values(columns, ascending=ascending, kind="mergesort")


# --------------------------------------------------------------------------- #
# Summaries
# --------------------------------------------------------------------------- #
def savings_rate(income: float, expenses: float) -> float | None:
    """Net savings / income x 100. None when there is no income (rate undefined)."""
    if income is None or income <= 0:
        return None
    return (income - expenses) / income * 100


def percent_change(current: float, previous: float) -> float | None:
    """Relative change in percent. None when the previous value is zero/missing."""
    if previous is None or previous == 0 or pd.isna(previous):
        return None
    return (current - previous) / abs(previous) * 100


def summarize(transactions: pd.DataFrame) -> dict:
    """Income, expenses, net savings and savings rate for a set of transactions."""
    income = float(transactions.loc[transactions["type"] == "Income", "amount"].sum())
    expenses = float(transactions.loc[transactions["type"] == "Expense", "amount"].sum())
    return {
        "income": income,
        "expenses": expenses,
        "net": income - expenses,
        "savings_rate": savings_rate(income, expenses),
        "count": int(len(transactions)),
    }


def compare_months(transactions: pd.DataFrame, month: str) -> dict:
    """Summary for `month` plus the previous month and the relative changes.

    Changes are None when the previous month has no transactions, so the UI can
    avoid showing a comparison that the data does not support.
    """
    previous_month = shift_month(month, -1)
    current = summarize(filter_by_month(transactions, month))
    previous_rows = filter_by_month(transactions, previous_month)
    previous = summarize(previous_rows)
    has_previous = not previous_rows.empty
    return {
        "month": month,
        "previous_month": previous_month,
        "current": current,
        "previous": previous if has_previous else None,
        "income_change": percent_change(current["income"], previous["income"]) if has_previous else None,
        "expense_change": percent_change(current["expenses"], previous["expenses"]) if has_previous else None,
        "net_change": (current["net"] - previous["net"]) if has_previous else None,
        "rate_change": (
            current["savings_rate"] - previous["savings_rate"]
            if has_previous and current["savings_rate"] is not None
            and previous["savings_rate"] is not None
            else None
        ),
    }


def expenses_by_category(transactions: pd.DataFrame) -> pd.DataFrame:
    """Expense total and share (%) per category, largest first."""
    expenses = transactions[transactions["type"] == "Expense"]
    if expenses.empty:
        return pd.DataFrame(columns=["category", "amount", "share", "count"])
    grouped = (
        expenses.groupby("category")["amount"]
        .agg(amount="sum", count="count")
        .reset_index()
        .sort_values("amount", ascending=False, kind="mergesort")
    )
    grouped["share"] = grouped["amount"] / grouped["amount"].sum() * 100
    return grouped.reset_index(drop=True)


def monthly_summary(transactions: pd.DataFrame, end_month: str, months: int = 6) -> pd.DataFrame:
    """One row per month for the `months` ending at `end_month`.

    Months without any transactions are kept (with zero totals) so that the time
    axis is continuous; `has_data` marks whether a month had any records.
    """
    keys = month_range(end_month, months)
    frame = pd.DataFrame({"month": keys})
    if transactions.empty:
        frame[["income", "expenses"]] = 0.0
        frame["has_data"] = False
    else:
        data = transactions.assign(month=transactions["date"].dt.strftime("%Y-%m"))
        data = data[data["month"].isin(keys)]
        pivot = data.pivot_table(
            index="month", columns="type", values="amount", aggfunc="sum", fill_value=0.0
        )
        counts = data.groupby("month").size()
        frame["income"] = frame["month"].map(pivot["Income"] if "Income" in pivot else {}).fillna(0.0)
        frame["expenses"] = frame["month"].map(pivot["Expense"] if "Expense" in pivot else {}).fillna(0.0)
        frame["has_data"] = frame["month"].map(counts).fillna(0).astype(int) > 0
    frame["income"] = frame["income"].astype(float)
    frame["expenses"] = frame["expenses"].astype(float)
    frame["net"] = frame["income"] - frame["expenses"]
    frame["savings_rate"] = [
        savings_rate(inc, exp) for inc, exp in zip(frame["income"], frame["expenses"])
    ]
    frame["cumulative_net"] = frame["net"].cumsum()
    frame["label"] = pd.to_datetime(frame["month"] + "-01").dt.strftime("%b %y")
    return frame


def daily_run_rate_projection(transactions: pd.DataFrame, month: str, today: date | None = None):
    """Project month-end spending from the average daily spend so far.

    Only meaningful for the current, partially elapsed month; returns None otherwise.
    """
    today = today or date.today()
    if month != month_key(today):
        return None
    start, end = month_bounds(month)
    days_elapsed = today.day
    days_in_month = end.day
    if days_elapsed >= days_in_month:
        return None
    spent = summarize(filter_by_month(transactions, month))["expenses"]
    if spent <= 0:
        return None
    return {
        "spent_so_far": spent,
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
        "projected": spent / days_elapsed * days_in_month,
    }


# --------------------------------------------------------------------------- #
# Budgets
# --------------------------------------------------------------------------- #
def budget_status(percent_used: float, caution_threshold: float = DEFAULT_CAUTION_THRESHOLD) -> str:
    """Healthy below the caution threshold, Caution up to 100%, Exceeded above 100%."""
    if percent_used > EXCEEDED_THRESHOLD:
        return STATUS_EXCEEDED
    if percent_used >= caution_threshold:
        return STATUS_CAUTION
    return STATUS_HEALTHY


def budget_performance(
    budgets: pd.DataFrame,
    transactions: pd.DataFrame,
    month: str,
    caution_threshold: float = DEFAULT_CAUTION_THRESHOLD,
) -> pd.DataFrame:
    """Spending against each budget for `month`, using only that month's expenses."""
    columns = ["id", "category", "budget", "spent", "remaining", "percent_used", "status"]
    month_budgets = budgets[budgets["month"] == month] if not budgets.empty else budgets
    if month_budgets.empty:
        return pd.DataFrame(columns=columns)
    month_expenses = filter_by_month(transactions, month)
    month_expenses = month_expenses[month_expenses["type"] == "Expense"]
    spent_by_category = month_expenses.groupby("category")["amount"].sum()

    result = month_budgets[["id", "category", "amount"]].rename(columns={"amount": "budget"}).copy()
    result["spent"] = result["category"].map(spent_by_category).fillna(0.0).astype(float)
    result["remaining"] = result["budget"] - result["spent"]
    result["percent_used"] = result["spent"] / result["budget"] * 100
    result["status"] = [budget_status(p, caution_threshold) for p in result["percent_used"]]
    return result.sort_values("percent_used", ascending=False, kind="mergesort").reset_index(drop=True)


def budget_totals(performance: pd.DataFrame) -> dict:
    if performance.empty:
        return {"budget": 0.0, "spent": 0.0, "remaining": 0.0, "utilization": None,
                "exceeded": 0, "caution": 0}
    total_budget = float(performance["budget"].sum())
    total_spent = float(performance["spent"].sum())
    return {
        "budget": total_budget,
        "spent": total_spent,
        "remaining": total_budget - total_spent,
        "utilization": total_spent / total_budget * 100 if total_budget > 0 else None,
        "exceeded": int((performance["status"] == STATUS_EXCEEDED).sum()),
        "caution": int((performance["status"] == STATUS_CAUTION).sum()),
    }


# --------------------------------------------------------------------------- #
# Savings goals
# --------------------------------------------------------------------------- #
def goal_progress(goals: pd.DataFrame, today: date | None = None) -> pd.DataFrame:
    """Add remaining amount, percent complete, completion flag and pacing info."""
    today = today or date.today()
    if goals.empty:
        return goals.assign(remaining=[], percent=[], completed=[], days_left=[], monthly_needed=[])
    result = goals.copy()
    result["remaining"] = (result["target_amount"] - result["saved_amount"]).clip(lower=0)
    result["percent"] = result["saved_amount"] / result["target_amount"] * 100
    result["completed"] = result["saved_amount"] >= result["target_amount"]

    days_left, monthly_needed = [], []
    for target_date, remaining, completed in zip(
        result["target_date"], result["remaining"], result["completed"]
    ):
        if not target_date or pd.isna(target_date):
            days_left.append(None)
            monthly_needed.append(None)
            continue
        days = (date.fromisoformat(str(target_date)[:10]) - today).days
        days_left.append(days)
        if completed or days <= 0:
            monthly_needed.append(None)
        else:
            # Average month length 30.44 days; at least one month to avoid inflating the figure.
            months_left = max(days / 30.44, 1)
            monthly_needed.append(remaining / months_left)
    result["days_left"] = days_left
    result["monthly_needed"] = monthly_needed
    return result


def goals_totals(progress: pd.DataFrame) -> dict:
    if progress.empty:
        return {"target": 0.0, "saved": 0.0, "percent": None, "completed": 0, "count": 0}
    target = float(progress["target_amount"].sum())
    # Cap each goal at its target so over-funding one goal doesn't mask another.
    saved_capped = float(progress[["saved_amount", "target_amount"]].min(axis=1).sum())
    return {
        "target": target,
        "saved": float(progress["saved_amount"].sum()),
        "percent": saved_capped / target * 100 if target > 0 else None,
        "completed": int(progress["completed"].sum()),
        "count": int(len(progress)),
    }


# --------------------------------------------------------------------------- #
# Investments
# --------------------------------------------------------------------------- #
def investment_values(investments: pd.DataFrame) -> pd.DataFrame:
    """Invested value, current value, unrealised P&L and return % per holding."""
    if investments.empty:
        return investments.assign(invested=[], current=[], pnl=[], return_pct=[])
    result = investments.copy()
    units = result["valuation_mode"] == VALUATION_UNITS
    result["invested"] = 0.0
    result["current"] = 0.0
    result.loc[units, "invested"] = result.loc[units, "quantity"] * result.loc[units, "purchase_price"]
    result.loc[units, "current"] = result.loc[units, "quantity"] * result.loc[units, "current_price"]
    result.loc[~units, "invested"] = result.loc[~units, "invested_amount"]
    result.loc[~units, "current"] = result.loc[~units, "current_value"]
    result["invested"] = result["invested"].fillna(0.0).astype(float)
    result["current"] = result["current"].fillna(0.0).astype(float)
    result["pnl"] = result["current"] - result["invested"]
    result["return_pct"] = [
        (pnl / inv * 100) if inv > 0 else None for pnl, inv in zip(result["pnl"], result["invested"])
    ]
    return result


def portfolio_summary(values: pd.DataFrame) -> dict:
    invested = float(values["invested"].sum()) if not values.empty else 0.0
    current = float(values["current"].sum()) if not values.empty else 0.0
    pnl = current - invested
    return {
        "invested": invested,
        "current": current,
        "pnl": pnl,
        "return_pct": pnl / invested * 100 if invested > 0 else None,
        "holdings": int(len(values)),
    }


def allocation_by_category(values: pd.DataFrame) -> pd.DataFrame:
    """Current value and share of the portfolio per asset category."""
    if values.empty:
        return pd.DataFrame(columns=["category", "invested", "current", "pnl", "share"])
    grouped = (
        values.groupby("category")[["invested", "current", "pnl"]].sum().reset_index()
        .sort_values("current", ascending=False, kind="mergesort")
    )
    total = grouped["current"].sum()
    grouped["share"] = grouped["current"] / total * 100 if total > 0 else 0.0
    return grouped.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Unusual transactions
# --------------------------------------------------------------------------- #
UNUSUAL_MULTIPLIER = 3.0
UNUSUAL_MIN_HISTORY = 5
UNUSUAL_MIN_AMOUNT = 1000.0


def detect_unusual_expenses(
    transactions: pd.DataFrame,
    month: str,
    multiplier: float = UNUSUAL_MULTIPLIER,
    min_history: int = UNUSUAL_MIN_HISTORY,
    min_amount: float = UNUSUAL_MIN_AMOUNT,
) -> pd.DataFrame:
    """Flag expenses in `month` that are unusually large for their category.

    Rule: an expense is unusual when
      * its category has at least `min_history` *other* expenses on record, and
      * the amount is at least `multiplier` x the median of those other expenses, and
      * the amount is at least `min_amount` (to ignore small absolute differences).
    Comparing within a category means a monthly rent payment is compared with
    previous rent payments rather than with a cup of coffee.
    """
    columns = ["id", "date", "description", "category", "amount", "category_median", "ratio"]
    expenses = transactions[transactions["type"] == "Expense"]
    candidates = filter_by_month(expenses, month)
    rows = []
    for _, txn in candidates.iterrows():
        if txn["amount"] < min_amount:
            continue
        history = expenses[(expenses["category"] == txn["category"]) & (expenses["id"] != txn["id"])]
        if len(history) < min_history:
            continue
        median = float(history["amount"].median())
        if median > 0 and txn["amount"] >= multiplier * median:
            rows.append({
                "id": txn["id"], "date": txn["date"], "description": txn["description"],
                "category": txn["category"], "amount": float(txn["amount"]),
                "category_median": median, "ratio": float(txn["amount"]) / median,
            })
    result = pd.DataFrame(rows, columns=columns)
    return result.sort_values("ratio", ascending=False).reset_index(drop=True)


def category_change_vs_average(
    transactions: pd.DataFrame, month: str, lookback: int = 3
) -> pd.DataFrame:
    """Compare each category's spend in `month` with its average over prior months.

    The average uses only the prior months (within `lookback`) that contain any
    transactions, so gaps in record keeping don't drag the average down.
    """
    columns = ["category", "current", "average", "change_pct", "months_used"]
    prior_months = [
        m for m in month_range(shift_month(month, -1), lookback)
        if not filter_by_month(transactions, m).empty
    ]
    if not prior_months:
        return pd.DataFrame(columns=columns)
    expenses = transactions[transactions["type"] == "Expense"].assign(
        month=lambda df: df["date"].dt.strftime("%Y-%m")
    )
    current = expenses[expenses["month"] == month].groupby("category")["amount"].sum()
    prior = (
        expenses[expenses["month"].isin(prior_months)].groupby("category")["amount"].sum()
        / len(prior_months)
    )
    categories = sorted(set(current.index) | set(prior.index))
    rows = []
    for category in categories:
        cur = float(current.get(category, 0.0))
        avg = float(prior.get(category, 0.0))
        rows.append({
            "category": category, "current": cur, "average": avg,
            "change_pct": percent_change(cur, avg), "months_used": len(prior_months),
        })
    return pd.DataFrame(rows, columns=columns)
