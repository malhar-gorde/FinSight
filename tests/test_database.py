from datetime import date, timedelta

import pytest

from finsight import calculations as calc
from finsight import database as db
from finsight import sample_data
from finsight.validation import ValidationError


def _add_expense(db_path, amount=500, category="Food", when=None, description="Lunch"):
    return db.add_transaction(when or date.today(), description, category, "Expense", amount, "UPI",
                              db_path=db_path)


# ---------------------------------------------------------------- schema
def test_init_creates_all_tables(db_path):
    for table in ["transactions", "budgets", "savings_goals", "goal_contributions", "investments", "settings"]:
        with db.get_connection(db_path) as conn:
            conn.fetchone(f"SELECT COUNT(*) AS n FROM {table}")  # raises if the table is missing


def test_init_is_idempotent_and_keeps_data(db_path):
    _add_expense(db_path)
    db.init_db(db_path)
    assert len(db.get_transactions(db_path)) == 1


def test_empty_database_reads_do_not_crash(db_path):
    txns = db.get_transactions(db_path)
    assert txns.empty
    assert calc.summarize(txns)["savings_rate"] is None
    assert calc.expenses_by_category(txns).empty
    assert calc.monthly_summary(txns, "2026-10", 6)["net"].sum() == 0
    assert db.get_budgets(db_path=db_path).empty
    assert calc.goal_progress(db.get_goals(db_path)).empty
    assert calc.portfolio_summary(calc.investment_values(db.get_investments(db_path)))["invested"] == 0


# ---------------------------------------------------------------- transactions
def test_add_edit_delete_transaction(db_path):
    txn_id = _add_expense(db_path, 450)
    stored = db.get_transaction(txn_id, db_path)
    assert stored["amount"] == 450 and stored["type"] == "Expense"

    assert db.update_transaction(txn_id, date.today(), "Dinner", "Food", "Expense", 900, "Credit Card",
                                 "with friends", db_path=db_path)
    txns = db.get_transactions(db_path)
    assert len(txns) == 1, "editing must not create a duplicate"
    assert txns.iloc[0]["amount"] == 900 and txns.iloc[0]["description"] == "Dinner"

    assert db.delete_transaction(txn_id, db_path)
    assert db.get_transactions(db_path).empty
    assert not db.delete_transaction(txn_id, db_path)


def test_changing_type_moves_amount_between_income_and_expense(db_path):
    txn_id = _add_expense(db_path, 1000, category="Other")
    assert calc.summarize(db.get_transactions(db_path))["expenses"] == 1000
    db.update_transaction(txn_id, date.today(), "Refund", "Other Income", "Income", 1000, "UPI", db_path=db_path)
    summary = calc.summarize(db.get_transactions(db_path))
    assert summary["expenses"] == 0 and summary["income"] == 1000


@pytest.mark.parametrize("kwargs, message", [
    ({"amount": 0}, "greater than zero"),
    ({"amount": -50}, "greater than zero"),
    ({"amount": "abc"}, "number"),
    ({"description": "   "}, "Description is required"),
    ({"category": "Salary"}, "not a valid expense category"),
    ({"payment_method": "Cheque"}, "payment method"),
    ({"txn_date": date.today() + timedelta(days=3)}, "future"),
    ({"txn_type": "Transfer"}, "Income or Expense"),
])
def test_invalid_transactions_are_rejected(db_path, kwargs, message):
    values = {"txn_date": date.today(), "description": "Test", "category": "Food", "txn_type": "Expense",
              "amount": 100, "payment_method": "UPI"}
    values.update(kwargs)
    with pytest.raises(ValidationError, match=message):
        db.add_transaction(db_path=db_path, **values)
    assert db.get_transactions(db_path).empty


def test_sql_injection_text_is_stored_literally(db_path):
    nasty = "x'); DROP TABLE transactions; --"
    _add_expense(db_path, description=nasty)
    assert db.get_transactions(db_path).iloc[0]["description"] == nasty


def test_data_persists_across_connections(fresh_target):
    path = fresh_target
    db.init_db(path)
    _add_expense(path, 750)
    db.add_budget("2026-10", "Food", 5000, db_path=path)
    # Simulate an app restart: re-initialise and read through fresh connections.
    sample_data.initialize(path)
    assert db.get_transactions(path).iloc[0]["amount"] == 750
    assert len(db.get_budgets(db_path=path)) == 1


# ---------------------------------------------------------------- budgets
def test_duplicate_budget_is_rejected(db_path):
    db.add_budget("2026-10", "Food", 8000, db_path=db_path)
    with pytest.raises(db.DuplicateBudgetError):
        db.add_budget("2026-10", "Food", 9000, db_path=db_path)
    db.add_budget("2026-11", "Food", 9000, db_path=db_path)  # different month is fine
    assert len(db.get_budgets(db_path=db_path)) == 2


def test_budget_validation_and_update(db_path):
    with pytest.raises(ValidationError):
        db.add_budget("2026-10", "Salary", 1000, db_path=db_path)
    with pytest.raises(ValidationError):
        db.add_budget("2026-13", "Food", 1000, db_path=db_path)
    with pytest.raises(ValidationError):
        db.add_budget("2026-10", "Food", 0, db_path=db_path)
    budget_id = db.add_budget("2026-10", "Food", 1000, db_path=db_path)
    db.update_budget(budget_id, 2500, db_path=db_path)
    assert db.get_budgets("2026-10", db_path=db_path).iloc[0]["amount"] == 2500
    db.delete_budget(budget_id, db_path=db_path)
    assert db.get_budgets(db_path=db_path).empty


def test_copy_budgets_skips_existing(db_path):
    db.add_budget("2026-09", "Food", 8000, db_path=db_path)
    db.add_budget("2026-09", "Travel", 3000, db_path=db_path)
    db.add_budget("2026-10", "Food", 9500, db_path=db_path)
    assert db.copy_budgets("2026-09", "2026-10", db_path=db_path) == 1
    october = db.get_budgets("2026-10", db_path=db_path).set_index("category")
    assert october.loc["Food", "amount"] == 9500  # existing budget not overwritten
    assert october.loc["Travel", "amount"] == 3000


# ---------------------------------------------------------------- goals
def test_goal_contributions_and_balance_adjustment(db_path):
    goal_id = db.add_goal("Laptop", 80000, date.today() + timedelta(days=200), initial_saved=10000,
                          db_path=db_path)
    db.add_contribution(goal_id, 5000, db_path=db_path)
    assert db.get_goal_saved_amount(goal_id, db_path) == 15000

    with pytest.raises(ValidationError):
        db.add_contribution(goal_id, -100, db_path=db_path)
    with pytest.raises(ValidationError):
        db.set_goal_saved_amount(goal_id, -1, db_path=db_path)

    assert db.set_goal_saved_amount(goal_id, 12000, db_path=db_path) == -3000
    goals = db.get_goals(db_path)
    assert goals.iloc[0]["saved_amount"] == 12000
    history = db.get_contributions(goal_id, db_path)
    assert history["amount"].sum() == 12000, "history must add up to the displayed balance"


def test_goal_completion_and_cascade_delete(db_path):
    goal_id = db.add_goal("Trip", 10000, db_path=db_path)
    db.add_contribution(goal_id, 10000, db_path=db_path)
    progress = calc.goal_progress(db.get_goals(db_path))
    assert bool(progress.iloc[0]["completed"]) and progress.iloc[0]["percent"] == 100

    db.delete_goal(goal_id, db_path)
    assert db.get_goals(db_path).empty
    assert db.get_contributions(db_path=db_path).empty
    with pytest.raises(ValidationError):
        db.add_contribution(goal_id, 100, db_path=db_path)


def test_goal_requires_positive_target(db_path):
    with pytest.raises(ValidationError):
        db.add_goal("Bad", 0, db_path=db_path)
    with pytest.raises(ValidationError):
        db.add_goal("", 1000, db_path=db_path)


# ---------------------------------------------------------------- investments
def test_investment_crud_and_valuation(db_path):
    fund = db.add_investment("Index Fund", "Mutual Funds", "units", date.today(), quantity=10,
                             purchase_price=100, current_price=110, db_path=db_path)
    fd = db.add_investment("FD", "Fixed Deposits", "fixed", date.today(), invested_amount=50000,
                           current_value=51000, db_path=db_path)
    summary = calc.portfolio_summary(calc.investment_values(db.get_investments(db_path)))
    assert summary["invested"] == 51000 and summary["current"] == 52100

    db.update_investment_valuation(fund, 90, db_path)
    db.update_investment_valuation(fd, 52000, db_path)
    values = calc.investment_values(db.get_investments(db_path)).set_index("name")
    assert values.loc["Index Fund", "current"] == 900
    assert values.loc["Index Fund", "pnl"] == -100
    assert values.loc["FD", "current"] == 52000

    db.update_investment(fund, "Index Fund", "Mutual Funds", "units", date.today(), quantity=20,
                         purchase_price=100, current_price=90, db_path=db_path)
    assert calc.investment_values(db.get_investments(db_path)).set_index("name").loc["Index Fund", "invested"] == 2000
    db.delete_investment(fd, db_path)
    assert len(db.get_investments(db_path)) == 1


def test_investment_validation(db_path):
    with pytest.raises(ValidationError):
        db.add_investment("X", "Stocks", "units", date.today(), quantity=0, purchase_price=10,
                          current_price=10, db_path=db_path)
    with pytest.raises(ValidationError):
        db.add_investment("X", "Crypto", "units", date.today(), quantity=1, purchase_price=10,
                          current_price=10, db_path=db_path)
    with pytest.raises(ValidationError):
        db.add_investment("X", "Gold", "fixed", date.today(), invested_amount=-5, current_value=10,
                          db_path=db_path)


# ---------------------------------------------------------------- sample data
def test_first_run_loads_sample_data_once(fresh_target):
    path = fresh_target
    assert sample_data.initialize(path) is True
    counts = db.get_record_counts(path)
    assert counts["transactions"]["sample"] > 50
    assert all(c["user"] == 0 for c in counts.values())
    # No transaction may be dated in the future.
    assert db.get_transactions(path)["date"].max().date() <= date.today()

    first_count = counts["transactions"]["sample"]
    assert sample_data.initialize(path) is False  # restart: nothing re-seeded
    assert db.get_record_counts(path)["transactions"]["sample"] == first_count


def test_clearing_data_is_not_undone_by_restart(fresh_target):
    path = fresh_target
    sample_data.initialize(path)
    db.clear_all_data(path)
    sample_data.initialize(path)
    assert not db.has_any_data(path)


def test_removing_sample_data_keeps_user_records(fresh_target):
    path = fresh_target
    sample_data.initialize(path)
    _add_expense(path, 321, description="My own expense")
    db.delete_sample_data(path)
    txns = db.get_transactions(path)
    assert txns["description"].tolist() == ["My own expense"]
    assert db.get_goals(path).empty and db.get_investments(path).empty


def test_existing_user_data_prevents_seeding(fresh_target):
    path = fresh_target
    db.init_db(path)
    _add_expense(path, 100)
    assert sample_data.initialize(path) is False
    assert len(db.get_transactions(path)) == 1


def test_settings_round_trip(db_path):
    assert db.get_setting("user_name", "", db_path) == ""
    db.set_setting("user_name", "Aarav", db_path)
    db.set_setting("user_name", "Meera", db_path)
    assert db.get_all_settings(db_path)["user_name"] == "Meera"


# ---------------------------------------------------------------- environment
def test_find_database_url_handles_vercel_names():
    url = "postgresql://u:p@host/db"
    assert db.find_database_url({"DATABASE_URL": url}) == url
    assert db.find_database_url({"POSTGRES_URL": url}) == url
    # Custom prefix chosen when connecting the database in Vercel
    assert db.find_database_url({"STORAGE_DATABASE_URL": url}) == url
    assert db.find_database_url({"NEON_POSTGRES_URL": url}) == url
    # Pooled URL preferred over the unpooled variant
    assert db.find_database_url({"STORAGE_DATABASE_URL_UNPOOLED": "postgresql://direct",
                                 "STORAGE_DATABASE_URL": url}) == url
    # Non-postgres values and unrelated variables are ignored
    assert db.find_database_url({"DATABASE_URL": "", "OTHER": url}) is None
    assert db.find_database_url({}) is None
