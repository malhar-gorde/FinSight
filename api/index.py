"""FinSight API — FastAPI app deployed as a Vercel Python function.

All routes live under /api/py. In development, Next.js proxies /api/py/* to
uvicorn on port 8000 (see next.config.mjs); on Vercel the same paths are served
by this function.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
from fastapi import Depends, FastAPI, HTTPException, Request, Response  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from finsight import calculations as calc  # noqa: E402
from finsight import constants as C  # noqa: E402
from finsight import database as db  # noqa: E402
from finsight import sample_data  # noqa: E402
from finsight.exports import export_csv, export_zip  # noqa: E402
from finsight.insights import InsightContext, generate_insights  # noqa: E402
from finsight.validation import ValidationError, validate_month  # noqa: E402

app = FastAPI(title="FinSight API", docs_url="/api/py/docs", openapi_url="/api/py/openapi.json")

SESSION_COOKIE = "finsight_session"
SESSION_DAYS = 30


# --------------------------------------------------------------------------- #
# Startup, errors and serialisation
# --------------------------------------------------------------------------- #
_ready = False


def ensure_ready() -> None:
    """Create tables (and demo data on the very first run) once per server instance."""
    global _ready
    if not _ready:
        sample_data.initialize()
        _ready = True


@app.exception_handler(ValidationError)
def _validation_error(_: Request, error: ValidationError):
    return JSONResponse(status_code=400, content={"detail": str(error)})


def clean(value):
    """Make pandas/numpy values JSON-safe (NaN -> None, Timestamp -> 'YYYY-MM-DD')."""
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if value is None:
        return None
    if hasattr(value, "item"):  # numpy scalar
        value = value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def records(frame: pd.DataFrame) -> list[dict]:
    return [clean(row) for row in frame.to_dict(orient="records")]


def current_month() -> str:
    return calc.month_key(date.today())


def month_param(month: Optional[str]) -> str:
    return validate_month(month) if month else current_month()


def caution_threshold() -> float:
    try:
        return float(db.get_setting("caution_threshold", C.DEFAULT_CAUTION_THRESHOLD))
    except ValueError:
        return float(C.DEFAULT_CAUTION_THRESHOLD)


# --------------------------------------------------------------------------- #
# Authentication (optional single password, set APP_PASSWORD to enable)
# --------------------------------------------------------------------------- #
def _password() -> str:
    return os.environ.get("APP_PASSWORD", "")


def _signing_key() -> bytes:
    secret = os.environ.get("AUTH_SECRET") or _password()
    return hashlib.sha256(("finsight:" + secret).encode()).digest()


def _make_token(expires: int) -> str:
    signature = hmac.new(_signing_key(), str(expires).encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{signature}"


def _token_valid(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    expires, _, signature = token.partition(".")
    if not expires.isdigit() or int(expires) < time.time():
        return False
    return hmac.compare_digest(_make_token(int(expires)), token)


def require_auth(request: Request) -> None:
    if _password() and not _token_valid(request.cookies.get(SESSION_COOKIE)):
        raise HTTPException(status_code=401, detail="Please sign in.")
    ensure_ready()


class LoginBody(BaseModel):
    password: str


@app.get("/api/py/auth/status")
def auth_status(request: Request):
    required = bool(_password())
    return {"required": required,
            "authenticated": (not required) or _token_valid(request.cookies.get(SESSION_COOKIE))}


@app.post("/api/py/auth/login")
def login(body: LoginBody, request: Request, response: Response):
    if not _password():
        return {"ok": True}
    if not hmac.compare_digest(body.password.encode(), _password().encode()):
        time.sleep(0.5)  # slow down guessing
        raise HTTPException(status_code=401, detail="Incorrect password.")
    expires = int(time.time()) + SESSION_DAYS * 86400
    response.set_cookie(
        SESSION_COOKIE, _make_token(expires), max_age=SESSION_DAYS * 86400, httponly=True,
        samesite="lax", secure=request.url.scheme == "https" or bool(os.environ.get("VERCEL")),
    )
    return {"ok": True}


@app.post("/api/py/auth/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


Protected = Depends(require_auth)


# --------------------------------------------------------------------------- #
# Meta
# --------------------------------------------------------------------------- #
@app.get("/api/py/meta", dependencies=[Protected])
def meta():
    settings = db.get_all_settings()
    counts = db.get_record_counts()
    return {
        "transaction_types": C.TRANSACTION_TYPES,
        "categories": C.CATEGORIES_BY_TYPE,
        "expense_categories": C.EXPENSE_CATEGORIES,
        "payment_methods": C.PAYMENT_METHODS,
        "investment_categories": C.INVESTMENT_CATEGORIES,
        "sort_options": list(calc.SORT_OPTIONS),
        "user_name": settings.get("user_name", ""),
        "caution_threshold": caution_threshold(),
        "has_sample_data": any(c["sample"] > 0 for c in counts.values()),
        "storage_mode": db.storage_mode(),
        "auth_required": bool(_password()),
        "today": date.today().isoformat(),
    }


@app.get("/api/py/months", dependencies=[Protected])
def months(extra: int = 0):
    """Months to offer in pickers: months with data, budget months, current (+ upcoming)."""
    options = set(calc.available_months(db.get_transactions()))
    budgets = db.get_budgets()
    if not budgets.empty:
        options.update(budgets["month"].tolist())
    now = current_month()
    options.add(now)
    for offset in range(1, min(max(extra, 0), 12) + 1):
        options.add(calc.shift_month(now, offset))
    return {"months": sorted(options, reverse=True), "current": now}


# --------------------------------------------------------------------------- #
# Overview
# --------------------------------------------------------------------------- #
def _comparison(transactions, month):
    comparison = calc.compare_months(transactions, month)
    return clean(comparison)


@app.get("/api/py/overview", dependencies=[Protected])
def overview(month: Optional[str] = None, months: int = 6):
    month = month_param(month)
    with db.session():
        transactions = db.get_transactions()
        budgets = db.get_budgets()
        goals = db.get_goals()
        investments = db.get_investments()
    month_txns = calc.filter_by_month(transactions, month)
    breakdown = calc.expenses_by_category(month_txns)
    performance = calc.budget_performance(budgets, transactions, month, caution_threshold())
    monthly = calc.monthly_summary(transactions, month, max(1, min(months, 24)))
    return {
        "month": month,
        "has_transactions": not transactions.empty,
        "comparison": _comparison(transactions, month),
        "categories": records(breakdown),
        "monthly": records(monthly),
        "health": {
            "budget": clean(calc.budget_totals(performance)),
            "goals": clean(calc.goals_totals(calc.goal_progress(goals))),
            "portfolio": clean(calc.portfolio_summary(calc.investment_values(investments))),
        },
        "recent": records(transactions.head(8)),
    }


@app.get("/api/py/monthly", dependencies=[Protected])
def monthly(month: Optional[str] = None, months: int = 12):
    return records(calc.monthly_summary(db.get_transactions(), month_param(month), max(1, min(months, 24))))


# --------------------------------------------------------------------------- #
# Transactions
# --------------------------------------------------------------------------- #
class TransactionBody(BaseModel):
    date: str
    description: str
    category: str
    type: str
    amount: float
    payment_method: str
    notes: str = ""


def _split(value: Optional[str]) -> list[str]:
    return [item for item in (value or "").split(",") if item]


def _filtered(search, start, end, types, categories, methods, sort):
    transactions = db.get_transactions()
    result = calc.filter_transactions(
        transactions, search or "", start or None, end or None, _split(categories), _split(types), _split(methods)
    )
    return transactions, calc.sort_transactions(result, sort or "Date (newest first)")


@app.get("/api/py/transactions", dependencies=[Protected])
def list_transactions(search: str = "", start: str = "", end: str = "", types: str = "", categories: str = "",
                      methods: str = "", sort: str = ""):
    transactions, result = _filtered(search, start, end, types, categories, methods, sort)
    bounds = None
    if not transactions.empty:
        bounds = {"min": transactions["date"].min().strftime("%Y-%m-%d"),
                  "max": transactions["date"].max().strftime("%Y-%m-%d")}
    return {"items": records(result), "summary": clean(calc.summarize(result)), "total": len(transactions),
            "bounds": bounds}


@app.get("/api/py/transactions/export.csv", dependencies=[Protected])
def export_transactions(search: str = "", start: str = "", end: str = "", types: str = "", categories: str = "",
                        methods: str = "", sort: str = "", month: str = ""):
    if month:
        first, last = calc.month_bounds(validate_month(month))
        start, end = first.strftime("%Y-%m-%d"), last.strftime("%Y-%m-%d")
    _, result = _filtered(search, start, end, types, categories, methods, sort)
    if month:
        name = f"finsight_{month.replace('-', '')}_transactions.csv"
    else:
        name = f"finsight_transactions_{date.today():%Y%m%d}.csv"
    return Response(export_csv(result), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.post("/api/py/transactions", dependencies=[Protected])
def create_transaction(body: TransactionBody):
    new_id = db.add_transaction(body.date, body.description, body.category, body.type, body.amount,
                                body.payment_method, body.notes)
    return {"id": new_id}


@app.put("/api/py/transactions/{txn_id}", dependencies=[Protected])
def edit_transaction(txn_id: int, body: TransactionBody):
    if not db.update_transaction(txn_id, body.date, body.description, body.category, body.type, body.amount,
                                 body.payment_method, body.notes):
        raise HTTPException(404, "That transaction no longer exists.")
    return {"id": txn_id}


@app.delete("/api/py/transactions/{txn_id}", dependencies=[Protected])
def remove_transaction(txn_id: int):
    if not db.delete_transaction(txn_id):
        raise HTTPException(404, "That transaction no longer exists.")
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Budgets
# --------------------------------------------------------------------------- #
class BudgetBody(BaseModel):
    month: str
    category: str
    amount: float


class AmountBody(BaseModel):
    amount: float


class CopyBody(BaseModel):
    from_month: str
    to_month: str


@app.get("/api/py/budgets", dependencies=[Protected])
def list_budgets(month: Optional[str] = None):
    month = month_param(month)
    caution = caution_threshold()
    with db.session():
        budgets = db.get_budgets()
        transactions = db.get_transactions()
    performance = calc.budget_performance(budgets, transactions, month, caution)
    spending = calc.expenses_by_category(calc.filter_by_month(transactions, month))
    unbudgeted = spending[~spending["category"].isin(performance["category"])] if not spending.empty else spending
    previous = calc.shift_month(month, -1)
    return {
        "month": month,
        "caution_threshold": caution,
        "items": records(performance),
        "totals": clean(calc.budget_totals(performance)),
        "unbudgeted": records(unbudgeted[["category", "amount"]]) if not unbudgeted.empty else [],
        "previous_month": previous,
        "previous_count": int((budgets["month"] == previous).sum()) if not budgets.empty else 0,
    }


@app.post("/api/py/budgets", dependencies=[Protected])
def create_budget(body: BudgetBody):
    return {"id": db.add_budget(body.month, body.category, body.amount)}


@app.put("/api/py/budgets/{budget_id}", dependencies=[Protected])
def edit_budget(budget_id: int, body: AmountBody):
    if not db.update_budget(budget_id, body.amount):
        raise HTTPException(404, "That budget no longer exists.")
    return {"id": budget_id}


@app.delete("/api/py/budgets/{budget_id}", dependencies=[Protected])
def remove_budget(budget_id: int):
    if not db.delete_budget(budget_id):
        raise HTTPException(404, "That budget no longer exists.")
    return {"ok": True}


@app.post("/api/py/budgets/copy", dependencies=[Protected])
def copy_budgets(body: CopyBody):
    return {"copied": db.copy_budgets(body.from_month, body.to_month)}


# --------------------------------------------------------------------------- #
# Savings goals
# --------------------------------------------------------------------------- #
class GoalBody(BaseModel):
    name: str
    target_amount: float
    target_date: Optional[str] = None
    description: str = ""
    initial_saved: float = 0.0


class ContributionBody(BaseModel):
    amount: float
    date: Optional[str] = None
    note: str = ""


@app.get("/api/py/goals", dependencies=[Protected])
def list_goals():
    progress = calc.goal_progress(db.get_goals())
    return {"items": records(progress), "totals": clean(calc.goals_totals(progress))}


@app.get("/api/py/goals/{goal_id}/contributions", dependencies=[Protected])
def goal_history(goal_id: int):
    return records(db.get_contributions(goal_id))


@app.post("/api/py/goals", dependencies=[Protected])
def create_goal(body: GoalBody):
    return {"id": db.add_goal(body.name, body.target_amount, body.target_date or None, body.description,
                              body.initial_saved)}


@app.put("/api/py/goals/{goal_id}", dependencies=[Protected])
def edit_goal(goal_id: int, body: GoalBody):
    if not db.update_goal(goal_id, body.name, body.target_amount, body.target_date or None, body.description):
        raise HTTPException(404, "That goal no longer exists.")
    return {"id": goal_id}


@app.delete("/api/py/goals/{goal_id}", dependencies=[Protected])
def remove_goal(goal_id: int):
    if not db.delete_goal(goal_id):
        raise HTTPException(404, "That goal no longer exists.")
    return {"ok": True}


@app.post("/api/py/goals/{goal_id}/contributions", dependencies=[Protected])
def contribute(goal_id: int, body: ContributionBody):
    return {"id": db.add_contribution(goal_id, body.amount, body.date or None, body.note)}


@app.post("/api/py/goals/{goal_id}/balance", dependencies=[Protected])
def set_balance(goal_id: int, body: AmountBody):
    return {"adjustment": db.set_goal_saved_amount(goal_id, body.amount)}


# --------------------------------------------------------------------------- #
# Investments
# --------------------------------------------------------------------------- #
class InvestmentBody(BaseModel):
    name: str
    category: str
    valuation_mode: str
    purchase_date: str
    quantity: Optional[float] = None
    purchase_price: Optional[float] = None
    current_price: Optional[float] = None
    invested_amount: Optional[float] = None
    current_value: Optional[float] = None
    notes: str = ""


@app.get("/api/py/investments", dependencies=[Protected])
def list_investments():
    values = calc.investment_values(db.get_investments())
    return {"items": records(values), "summary": clean(calc.portfolio_summary(values)),
            "allocation": records(calc.allocation_by_category(values))}


@app.post("/api/py/investments", dependencies=[Protected])
def create_investment(body: InvestmentBody):
    return {"id": db.add_investment(**body.model_dump())}


@app.put("/api/py/investments/{investment_id}", dependencies=[Protected])
def edit_investment(investment_id: int, body: InvestmentBody):
    if not db.update_investment(investment_id, **body.model_dump()):
        raise HTTPException(404, "That holding no longer exists.")
    return {"id": investment_id}


@app.post("/api/py/investments/{investment_id}/valuation", dependencies=[Protected])
def revalue(investment_id: int, body: AmountBody):
    if not db.update_investment_valuation(investment_id, body.amount):
        raise HTTPException(404, "That holding no longer exists.")
    return {"id": investment_id}


@app.delete("/api/py/investments/{investment_id}", dependencies=[Protected])
def remove_investment(investment_id: int):
    if not db.delete_investment(investment_id):
        raise HTTPException(404, "That holding no longer exists.")
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Insights and monthly report
# --------------------------------------------------------------------------- #
@app.get("/api/py/insights", dependencies=[Protected])
def insights(month: Optional[str] = None):
    month = month_param(month)
    with db.session():
        context = InsightContext(
            transactions=db.get_transactions(), month=month, budgets=db.get_budgets(), goals=db.get_goals(),
            investments=db.get_investments(), caution_threshold=caution_threshold(),
        )
    return [{"category": i.category, "severity": i.severity, "title": i.title, "message": i.message,
             "rule": i.rule} for i in generate_insights(context)]


@app.get("/api/py/report", dependencies=[Protected])
def report(month: Optional[str] = None):
    month = month_param(month)
    with db.session():
        transactions = db.get_transactions()
        budgets = db.get_budgets()
        goals = db.get_goals()
        investments = db.get_investments()
    month_txns = calc.filter_by_month(transactions, month)
    return {
        "month": month,
        "has_data": not month_txns.empty,
        "comparison": _comparison(transactions, month),
        "categories": records(calc.expenses_by_category(month_txns)),
        "budgets": records(calc.budget_performance(budgets, transactions, month, caution_threshold())),
        "goals": records(calc.goal_progress(goals)),
        "portfolio": clean(calc.portfolio_summary(calc.investment_values(investments))),
    }


# --------------------------------------------------------------------------- #
# Settings and data management
# --------------------------------------------------------------------------- #
class SettingsBody(BaseModel):
    user_name: str = ""
    caution_threshold: float = C.DEFAULT_CAUTION_THRESHOLD


class ConfirmBody(BaseModel):
    confirm: str


@app.put("/api/py/settings", dependencies=[Protected])
def save_settings(body: SettingsBody):
    name = body.user_name.strip()[:40]
    if not 50 <= body.caution_threshold <= 95:
        raise ValidationError("Caution threshold must be between 50% and 95%.")
    db.set_setting("user_name", name)
    db.set_setting("caution_threshold", int(body.caution_threshold))
    return {"ok": True}


@app.get("/api/py/data/status", dependencies=[Protected])
def data_status():
    return {"counts": db.get_record_counts(), "storage_mode": db.storage_mode()}


def _check_confirm(body: ConfirmBody) -> None:
    if body.confirm.strip() != "DELETE":
        raise ValidationError("Type DELETE to confirm.")


@app.post("/api/py/data/remove-demo", dependencies=[Protected])
def remove_demo(body: ConfirmBody):
    _check_confirm(body)
    db.delete_sample_data()
    return {"ok": True}


@app.post("/api/py/data/reset-demo", dependencies=[Protected])
def reset_demo(body: ConfirmBody):
    _check_confirm(body)
    sample_data.reset_sample_data()
    return {"ok": True}


@app.post("/api/py/data/clear", dependencies=[Protected])
def clear_data(body: ConfirmBody):
    _check_confirm(body)
    db.clear_all_data()
    return {"ok": True}


@app.get("/api/py/data/export.zip", dependencies=[Protected])
def export_all():
    return Response(export_zip(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="finsight_export_{date.today():%Y%m%d}.zip"'})
