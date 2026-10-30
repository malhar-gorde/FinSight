from datetime import date

import pandas as pd
import pytest

from finsight import calculations as calc
from finsight.formatting import format_compact_inr, format_inr, format_pct
from tests.conftest import make_transactions


# ---------------------------------------------------------------- formatting
@pytest.mark.parametrize("value, expected", [
    (0, "₹0"),
    (999, "₹999"),
    (25000, "₹25,000"),
    (125000, "₹1,25,000"),
    (12500000, "₹1,25,00,000"),
    (-4500, "−₹4,500"),
])
def test_format_inr_uses_indian_grouping(value, expected):
    assert format_inr(value) == expected


def test_format_inr_decimals_and_sign():
    assert format_inr(1234567.891, decimals=2) == "₹12,34,567.89"
    assert format_inr(500, show_sign=True) == "+₹500"
    assert format_inr(None) == "—"


def test_format_helpers():
    assert format_pct(None) == "—"
    assert format_pct(12.345) == "12.3%"
    assert format_compact_inr(150000) == "₹1.50L"


# ---------------------------------------------------------------- summaries
def test_summarize_income_expense_net_and_rate():
    txns = make_transactions([
        ("2026-10-01", "Income", "Salary", 50000),
        ("2026-10-05", "Expense", "Food", 5000),
        ("2026-10-06", "Expense", "Housing", 15000),
    ])
    summary = calc.summarize(txns)
    assert summary["income"] == 50000
    assert summary["expenses"] == 20000
    assert summary["net"] == 30000
    assert summary["savings_rate"] == pytest.approx(60.0)


def test_savings_rate_handles_zero_income():
    assert calc.savings_rate(0, 500) is None
    txns = make_transactions([("2026-10-05", "Expense", "Food", 500)])
    summary = calc.summarize(txns)
    assert summary["savings_rate"] is None
    assert summary["net"] == -500


def test_summarize_empty_frame():
    summary = calc.summarize(make_transactions([]))
    assert summary == {"income": 0.0, "expenses": 0.0, "net": 0.0, "savings_rate": None, "count": 0}


def test_percent_change_handles_zero_previous():
    assert calc.percent_change(120, 100) == pytest.approx(20)
    assert calc.percent_change(80, 100) == pytest.approx(-20)
    assert calc.percent_change(50, 0) is None


def test_compare_months_without_previous_data():
    txns = make_transactions([("2026-10-01", "Income", "Salary", 1000)])
    comparison = calc.compare_months(txns, "2026-10")
    assert comparison["previous"] is None
    assert comparison["income_change"] is None


def test_compare_months_with_previous_data():
    txns = make_transactions([
        ("2026-09-03", "Expense", "Food", 1000),
        ("2026-10-03", "Expense", "Food", 1200),
        ("2026-10-01", "Income", "Salary", 10000),
    ])
    comparison = calc.compare_months(txns, "2026-10")
    assert comparison["expense_change"] == pytest.approx(20)
    assert comparison["income_change"] is None  # no income last month -> undefined change


# ---------------------------------------------------------------- filtering
def test_date_range_filter_is_inclusive():
    txns = make_transactions([
        ("2026-09-30", "Expense", "Food", 1),
        ("2026-10-01", "Expense", "Food", 2),
        ("2026-10-31", "Expense", "Food", 3),
        ("2026-11-01", "Expense", "Food", 4),
    ])
    result = calc.filter_by_date_range(txns, date(2026, 10, 1), date(2026, 10, 31))
    assert sorted(result["amount"]) == [2, 3]
    assert sorted(calc.filter_by_month(txns, "2026-10")["amount"]) == [2, 3]


def test_filter_transactions_combines_filters_and_search():
    txns = make_transactions([
        ("2026-10-01", "Expense", "Food", 100, "Groceries"),
        ("2026-10-02", "Expense", "Travel", 200, "Cab to office"),
        ("2026-10-03", "Income", "Salary", 300, "Salary October"),
    ])
    assert len(calc.filter_transactions(txns, search="cab")) == 1
    assert len(calc.filter_transactions(txns, txn_types=["Expense"])) == 2
    assert len(calc.filter_transactions(txns, categories=["Food", "Salary"])) == 2
    assert calc.filter_transactions(txns, search="GROCER")["description"].tolist() == ["Groceries"]


def test_sorting_by_amount_and_date():
    txns = make_transactions([
        ("2026-10-01", "Expense", "Food", 300),
        ("2026-10-03", "Expense", "Food", 100),
        ("2026-10-02", "Expense", "Food", 200),
    ])
    assert calc.sort_transactions(txns, "Amount (highest first)")["amount"].tolist() == [300, 200, 100]
    assert calc.sort_transactions(txns, "Date (oldest first)")["amount"].tolist() == [300, 200, 100]
    assert calc.sort_transactions(txns, "Date (newest first)")["amount"].tolist() == [100, 200, 300]


# ---------------------------------------------------------------- monthly
def test_monthly_summary_fills_missing_months():
    txns = make_transactions([
        ("2026-07-01", "Income", "Salary", 1000),
        ("2026-07-05", "Expense", "Food", 400),
        ("2026-09-01", "Income", "Salary", 1000),
    ])
    monthly = calc.monthly_summary(txns, "2026-09", 3)
    assert monthly["month"].tolist() == ["2026-07", "2026-08", "2026-09"]
    assert monthly["has_data"].tolist() == [True, False, True]
    assert monthly["net"].tolist() == [600, 0, 1000]
    assert monthly["cumulative_net"].tolist() == [600, 600, 1600]


def test_monthly_summary_empty():
    monthly = calc.monthly_summary(make_transactions([]), "2026-10", 6)
    assert len(monthly) == 6
    assert not monthly["has_data"].any()


def test_expenses_by_category_shares_sum_to_100():
    txns = make_transactions([
        ("2026-10-01", "Expense", "Food", 300),
        ("2026-10-02", "Expense", "Travel", 100),
        ("2026-10-03", "Income", "Salary", 5000),
    ])
    breakdown = calc.expenses_by_category(txns)
    assert breakdown["category"].tolist() == ["Food", "Travel"]
    assert breakdown["share"].sum() == pytest.approx(100)
    assert breakdown.iloc[0]["share"] == pytest.approx(75)


# ---------------------------------------------------------------- budgets
def test_budget_status_thresholds():
    assert calc.budget_status(50) == "Healthy"
    assert calc.budget_status(75) == "Caution"
    assert calc.budget_status(100) == "Caution"
    assert calc.budget_status(100.01) == "Exceeded"
    assert calc.budget_status(80, caution_threshold=85) == "Healthy"


def test_budget_performance_uses_correct_month_and_category():
    budgets = pd.DataFrame([
        {"id": 1, "month": "2026-10", "category": "Food", "amount": 1000.0},
        {"id": 2, "month": "2026-10", "category": "Travel", "amount": 500.0},
        {"id": 3, "month": "2026-09", "category": "Food", "amount": 9999.0},
    ])
    txns = make_transactions([
        ("2026-10-02", "Expense", "Food", 600),
        ("2026-10-20", "Expense", "Food", 300),
        ("2026-09-28", "Expense", "Food", 5000),    # previous month: must be ignored
        ("2026-10-05", "Expense", "Shopping", 800),  # no budget: ignored
        ("2026-10-06", "Expense", "Travel", 650),
        ("2026-10-07", "Income", "Salary", 700),     # income never counts as spending
    ])
    perf = calc.budget_performance(budgets, txns, "2026-10").set_index("category")
    assert set(perf.index) == {"Food", "Travel"}
    assert perf.loc["Food", "spent"] == 900
    assert perf.loc["Food", "remaining"] == 100
    assert perf.loc["Food", "status"] == "Caution"
    assert perf.loc["Travel", "spent"] == 650
    assert perf.loc["Travel", "status"] == "Exceeded"
    totals = calc.budget_totals(perf.reset_index())
    assert totals["budget"] == 1500 and totals["spent"] == 1550 and totals["exceeded"] == 1


# ---------------------------------------------------------------- goals
def test_goal_progress(today):
    goals = pd.DataFrame([
        {"id": 1, "name": "Laptop", "target_amount": 80000.0, "saved_amount": 20000.0,
         "target_date": "2027-04-29", "description": ""},
        {"id": 2, "name": "Trip", "target_amount": 10000.0, "saved_amount": 12000.0,
         "target_date": None, "description": ""},
    ])
    progress = calc.goal_progress(goals, today).set_index("name")
    assert progress.loc["Laptop", "percent"] == pytest.approx(25)
    assert progress.loc["Laptop", "remaining"] == 60000
    assert not progress.loc["Laptop", "completed"]
    assert progress.loc["Laptop", "monthly_needed"] == pytest.approx(60000 / (182 / 30.44))
    assert progress.loc["Trip", "completed"]
    assert progress.loc["Trip", "remaining"] == 0
    totals = calc.goals_totals(progress.reset_index())
    # Over-funded goal is capped at its target: (20000 + 10000) / 90000
    assert totals["percent"] == pytest.approx(30000 / 90000 * 100)


# ---------------------------------------------------------------- investments
def test_investment_values_units_and_fixed():
    investments = pd.DataFrame([
        {"id": 1, "name": "Fund", "category": "Mutual Funds", "valuation_mode": "units",
         "quantity": 10.0, "purchase_price": 100.0, "current_price": 120.0,
         "invested_amount": None, "current_value": None},
        {"id": 2, "name": "FD", "category": "Fixed Deposits", "valuation_mode": "fixed",
         "quantity": None, "purchase_price": None, "current_price": None,
         "invested_amount": 5000.0, "current_value": 5200.0},
        {"id": 3, "name": "Gift", "category": "Other Assets", "valuation_mode": "fixed",
         "quantity": None, "purchase_price": None, "current_price": None,
         "invested_amount": 0.0, "current_value": 300.0},
    ])
    values = calc.investment_values(investments).set_index("name")
    assert values.loc["Fund", "invested"] == 1000
    assert values.loc["Fund", "current"] == 1200
    assert values.loc["Fund", "return_pct"] == pytest.approx(20)
    assert values.loc["FD", "pnl"] == 200
    assert values.loc["FD", "return_pct"] == pytest.approx(4)
    assert pd.isna(values.loc["Gift", "return_pct"])  # zero invested -> no return %

    summary = calc.portfolio_summary(values.reset_index())
    assert summary["invested"] == 6000
    assert summary["current"] == 6700
    assert summary["return_pct"] == pytest.approx(700 / 6000 * 100)

    allocation = calc.allocation_by_category(values.reset_index())
    assert allocation["share"].sum() == pytest.approx(100)


def test_portfolio_summary_empty():
    values = calc.investment_values(pd.DataFrame(columns=["valuation_mode"]))
    summary = calc.portfolio_summary(values)
    assert summary["invested"] == 0 and summary["return_pct"] is None


# ---------------------------------------------------------------- unusual
def test_unusual_expense_compared_within_category():
    rows = [(f"2026-0{m}-1{d}", "Expense", "Travel", 300) for m in (7, 8, 9) for d in (1, 2)]
    rows += [(f"2026-0{m}-03", "Expense", "Housing", 15000) for m in (7, 8, 9)]
    rows += [
        ("2026-10-03", "Expense", "Housing", 15000),        # normal rent: not unusual
        ("2026-10-09", "Expense", "Travel", 8400, "Flight"),  # 28x the usual cab ride
        ("2026-10-10", "Expense", "Travel", 600),            # 2x: below multiplier
    ]
    flagged = calc.detect_unusual_expenses(make_transactions(rows), "2026-10")
    assert flagged["description"].tolist() == ["Flight"]
    assert flagged.iloc[0]["category_median"] == 300


def test_unusual_needs_enough_history():
    rows = [("2026-09-01", "Expense", "Travel", 300), ("2026-10-09", "Expense", "Travel", 8400)]
    assert calc.detect_unusual_expenses(make_transactions(rows), "2026-10").empty


def test_daily_projection_only_for_current_month():
    txns = make_transactions([("2026-10-02", "Expense", "Food", 1000)])
    projection = calc.daily_run_rate_projection(txns, "2026-10", date(2026, 10, 10))
    assert projection["projected"] == pytest.approx(1000 / 10 * 31)
    assert calc.daily_run_rate_projection(txns, "2026-09", date(2026, 10, 10)) is None
