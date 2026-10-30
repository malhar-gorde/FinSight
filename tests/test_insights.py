from datetime import date

import pandas as pd

from finsight import database as db
from finsight import sample_data
from finsight.insights import NEEDS_DATA, InsightContext, generate_insights
from finsight.exports import export_csv
from tests.conftest import make_transactions

EMPTY_BUDGETS = pd.DataFrame(columns=["id", "month", "category", "amount"])
EMPTY_GOALS = pd.DataFrame(columns=["id", "name", "target_amount", "saved_amount", "target_date", "description"])
EMPTY_INVESTMENTS = pd.DataFrame(columns=["id", "name", "category", "valuation_mode", "quantity", "purchase_price",
                                          "current_price", "invested_amount", "current_value"])


def _context(txns, month="2026-10", budgets=EMPTY_BUDGETS, today=date(2026, 10, 29)):
    return InsightContext(transactions=txns, month=month, budgets=budgets, goals=EMPTY_GOALS,
                          investments=EMPTY_INVESTMENTS, today=today)


def test_empty_data_gives_getting_started_message():
    insights = generate_insights(_context(make_transactions([])))
    assert len(insights) == 1 and insights[0].severity == NEEDS_DATA


def test_no_previous_month_says_more_data_needed():
    txns = make_transactions([
        ("2026-10-01", "Income", "Salary", 50000),
        ("2026-10-02", "Expense", "Food", 4000),
        ("2026-10-03", "Expense", "Travel", 1000),
    ])
    insights = {i.category: i for i in generate_insights(_context(txns))}
    assert insights["Month-on-month"].severity == NEEDS_DATA
    assert insights["Category trends"].severity == NEEDS_DATA
    assert "90%" in insights["Savings"].title  # (50000 - 5000) / 50000
    assert "Food accounts for 80%" in insights["Spending pattern"].message


def test_month_on_month_and_budget_alert():
    txns = make_transactions([
        ("2026-09-01", "Income", "Salary", 50000),
        ("2026-09-05", "Expense", "Food", 5000),
        ("2026-10-01", "Income", "Salary", 50000),
        ("2026-10-05", "Expense", "Food", 6000),
        ("2026-10-06", "Expense", "Travel", 3400),
    ])
    budgets = pd.DataFrame([{"id": 1, "month": "2026-10", "category": "Travel", "amount": 4000.0},
                            {"id": 2, "month": "2026-10", "category": "Food", "amount": 5000.0}])
    insights = generate_insights(_context(txns, budgets=budgets))
    by_title = {i.title: i for i in insights}
    assert "Expenses up 88%" in by_title          # 9400 vs 5000
    assert "Travel budget at 85%" in by_title      # 3400 / 4000
    assert "Food budget exceeded" in by_title      # 6000 / 5000
    assert insights[0].severity == "alert"         # alerts sorted first


def test_generated_insights_from_sample_data_are_grounded(fresh_target):
    path = fresh_target
    sample_data.initialize(path)
    ctx = InsightContext(
        transactions=db.get_transactions(path), month=pd.Timestamp.today().strftime("%Y-%m"),
        budgets=db.get_budgets(db_path=path), goals=db.get_goals(path), investments=db.get_investments(path),
    )
    insights = generate_insights(ctx)
    assert insights, "sample data should produce insights"
    assert all(i.rule for i in insights), "every insight must document its rule"


def test_csv_export_contains_numeric_amounts(db_path):
    db.add_transaction(date.today(), "Groceries, weekly", "Food", "Expense", 1234.5, "UPI", db_path=db_path)
    csv_text = export_csv(db.get_transactions(db_path)).decode("utf-8-sig")
    header, row = csv_text.strip().splitlines()
    assert header == "id,date,description,category,type,amount,payment_method,notes,source"
    assert '"Groceries, weekly"' in row and ",1234.5," in row and row.endswith(",User")
