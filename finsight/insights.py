"""Rule-based financial insights.

Each rule inspects the user's actual data and returns zero or more ``Insight``
objects. A rule produces nothing when the data does not support it, and some
rules return a "needs more data" note instead. There is no randomness and no
external AI service: every message can be traced to the calculation described
in its ``rule`` field.

To add a rule, write a function with the signature
``rule(context: InsightContext) -> list[Insight]`` and append it to ``RULES``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from finsight import calculations as calc
from finsight.constants import DEFAULT_CAUTION_THRESHOLD, STATUS_CAUTION, STATUS_EXCEEDED
from finsight.formatting import format_inr, format_pct, month_label

# Severity levels, used for ordering and colouring.
POSITIVE = "positive"
INFO = "info"
WARNING = "warning"
ALERT = "alert"
NEEDS_DATA = "needs_data"

_SEVERITY_ORDER = {ALERT: 0, WARNING: 1, POSITIVE: 2, INFO: 3, NEEDS_DATA: 4}

# Thresholds used by the rules (kept here so they are documented in one place).
MOM_CHANGE_THRESHOLD = 10.0         # % change in expenses worth mentioning
CATEGORY_SPIKE_PCT = 30.0           # % above the category's recent average
CATEGORY_SPIKE_MIN_AMOUNT = 1000.0  # ...and at least this many rupees above it
TOP_CATEGORY_MIN_SHARE = 25.0       # % of expenses for the "largest category" insight
STRONG_SAVINGS_RATE = 20.0          # % savings rate considered strong
CONCENTRATION_SHARE = 50.0          # % of portfolio in one asset category


@dataclass
class Insight:
    category: str   # e.g. "Spending pattern", "Budget alert"
    severity: str   # positive | info | warning | alert | needs_data
    title: str
    message: str
    rule: str       # plain-language explanation of how it was calculated
    metrics: dict = field(default_factory=dict)


@dataclass
class InsightContext:
    transactions: pd.DataFrame
    month: str
    budgets: pd.DataFrame
    goals: pd.DataFrame
    investments: pd.DataFrame
    caution_threshold: float = DEFAULT_CAUTION_THRESHOLD
    today: date = field(default_factory=date.today)

    @property
    def month_transactions(self) -> pd.DataFrame:
        return calc.filter_by_month(self.transactions, self.month)


# --------------------------------------------------------------------------- #
# Rules
# --------------------------------------------------------------------------- #
def spending_pattern(ctx: InsightContext) -> list[Insight]:
    breakdown = calc.expenses_by_category(ctx.month_transactions)
    if breakdown.empty:
        return []
    top = breakdown.iloc[0]
    if top["share"] < TOP_CATEGORY_MIN_SHARE or len(breakdown) < 2:
        return []
    return [Insight(
        category="Spending pattern",
        severity=INFO,
        title=f"{top['category']} is your largest expense",
        message=(
            f"{top['category']} accounts for {top['share']:.0f}% of your total expenses in "
            f"{month_label(ctx.month)} ({format_inr(top['amount'])} of "
            f"{format_inr(breakdown['amount'].sum())})."
        ),
        rule=(
            "Category total ÷ total expenses for the month × 100. Shown when the largest "
            f"category is at least {TOP_CATEGORY_MIN_SHARE:.0f}% of spending."
        ),
        metrics={"share": float(top["share"])},
    )]


def month_on_month(ctx: InsightContext) -> list[Insight]:
    comparison = calc.compare_months(ctx.transactions, ctx.month)
    previous_label = month_label(comparison["previous_month"])
    rule = (
        "(This month's expenses − last month's expenses) ÷ last month's expenses × 100. "
        f"Mentioned when the change is at least {MOM_CHANGE_THRESHOLD:.0f}%."
    )
    if comparison["previous"] is None:
        return [Insight(
            category="Month-on-month", severity=NEEDS_DATA,
            title="No previous month to compare",
            message=f"There are no transactions in {previous_label}, so a month-on-month "
                    "comparison isn't possible yet.",
            rule=rule,
        )]
    change = comparison["expense_change"]
    if change is None or abs(change) < MOM_CHANGE_THRESHOLD:
        return []
    current, previous = comparison["current"]["expenses"], comparison["previous"]["expenses"]
    partial_note = ""
    if ctx.month == calc.month_key(ctx.today):
        partial_note = " Note that this month isn't over yet."
    if change > 0:
        return [Insight(
            category="Month-on-month", severity=WARNING,
            title=f"Expenses up {change:.0f}%",
            message=f"Your expenses increased by {change:.0f}% compared with {previous_label} "
                    f"({format_inr(previous)} → {format_inr(current)}).{partial_note}",
            rule=rule, metrics={"change": change},
        )]
    return [Insight(
        category="Month-on-month", severity=POSITIVE,
        title=f"Expenses down {abs(change):.0f}%",
        message=f"Your expenses decreased by {abs(change):.0f}% compared with {previous_label} "
                f"({format_inr(previous)} → {format_inr(current)}).{partial_note}",
        rule=rule, metrics={"change": change},
    )]


def budget_alerts(ctx: InsightContext) -> list[Insight]:
    performance = calc.budget_performance(
        ctx.budgets, ctx.transactions, ctx.month, ctx.caution_threshold
    )
    insights = []
    for _, row in performance.iterrows():
        if row["status"] == STATUS_EXCEEDED:
            insights.append(Insight(
                category="Budget alert", severity=ALERT,
                title=f"{row['category']} budget exceeded",
                message=f"You have spent {format_inr(row['spent'])} against a "
                        f"{format_inr(row['budget'])} {row['category'].lower()} budget — "
                        f"{format_inr(-row['remaining'])} over ({row['percent_used']:.0f}% used).",
                rule="Spending in the category this month ÷ budget limit × 100. Exceeded above 100%.",
                metrics={"percent_used": float(row["percent_used"])},
            ))
        elif row["status"] == STATUS_CAUTION:
            insights.append(Insight(
                category="Budget alert", severity=WARNING,
                title=f"{row['category']} budget at {row['percent_used']:.0f}%",
                message=f"You have used {row['percent_used']:.0f}% of your monthly "
                        f"{row['category'].lower()} budget. {format_inr(row['remaining'])} remains.",
                rule=f"Spending ÷ budget × 100. Caution from {ctx.caution_threshold:.0f}% "
                     "(adjustable in Settings) up to 100%.",
                metrics={"percent_used": float(row["percent_used"])},
            ))
    return insights


def savings_rate_insight(ctx: InsightContext) -> list[Insight]:
    summary = calc.summarize(ctx.month_transactions)
    rule = "Savings rate = (income − expenses) ÷ income × 100 for the selected month."
    if summary["income"] <= 0:
        if summary["expenses"] > 0:
            return [Insight(
                category="Savings", severity=NEEDS_DATA,
                title="No income recorded this month",
                message="Savings rate can't be calculated because no income has been recorded for "
                        f"{month_label(ctx.month)}.",
                rule=rule,
            )]
        return []
    rate = summary["savings_rate"]

    # Compare with the average rate over up to three previous months that have income.
    history = calc.monthly_summary(ctx.transactions, calc.shift_month(ctx.month, -1), 3)
    history = history[history["income"] > 0]
    comparison = ""
    if not history.empty:
        average = float(history["savings_rate"].mean())
        comparison = (f" Your average over the previous {len(history)} month"
                      f"{'s' if len(history) > 1 else ''} with income was {average:.0f}%.")

    if rate < 0:
        severity, title = ALERT, "Spending exceeded income"
        message = (f"Your expenses were {format_inr(-summary['net'])} more than your income in "
                   f"{month_label(ctx.month)} (savings rate {format_pct(rate, 0)}).{comparison}")
    elif rate >= STRONG_SAVINGS_RATE:
        severity, title = POSITIVE, f"Savings rate of {rate:.0f}%"
        message = (f"Your savings rate in {month_label(ctx.month)} is {rate:.0f}% — you kept "
                   f"{format_inr(summary['net'])} of {format_inr(summary['income'])} earned.{comparison}")
    else:
        severity, title = INFO, f"Savings rate of {rate:.0f}%"
        message = (f"Your savings rate in {month_label(ctx.month)} is {rate:.0f}% "
                   f"({format_inr(summary['net'])} saved).{comparison}")
    return [Insight(category="Savings", severity=severity, title=title, message=message,
                    rule=rule, metrics={"savings_rate": rate})]


def unusual_transactions(ctx: InsightContext) -> list[Insight]:
    flagged = calc.detect_unusual_expenses(ctx.transactions, ctx.month)
    rule = (
        f"Flagged when an expense is at least {calc.UNUSUAL_MULTIPLIER:.0f}× the median of the "
        f"other expenses in the same category, the category has at least "
        f"{calc.UNUSUAL_MIN_HISTORY} other expenses on record, and the amount is at least "
        f"{format_inr(calc.UNUSUAL_MIN_AMOUNT)}."
    )
    insights = []
    for _, row in flagged.head(3).iterrows():
        insights.append(Insight(
            category="Unusual transaction", severity=WARNING,
            title=f"Large {row['category'].lower()} expense",
            message=f"Your {format_inr(row['amount'])} transaction “{row['description']}” on "
                    f"{row['date'].strftime('%d %b')} is {row['ratio']:.1f}× your typical "
                    f"{row['category'].lower()} expense (median {format_inr(row['category_median'])}).",
            rule=rule, metrics={"ratio": float(row["ratio"])},
        ))
    return insights


def category_spikes(ctx: InsightContext) -> list[Insight]:
    changes = calc.category_change_vs_average(ctx.transactions, ctx.month)
    if changes.empty:
        return [Insight(
            category="Category trends", severity=NEEDS_DATA,
            title="More history needed for category trends",
            message="Category trends compare this month with your previous months. Add "
                    "transactions for earlier months to unlock this insight.",
            rule="Requires at least one earlier month (within the last 3) with transactions.",
        )]
    months_used = int(changes["months_used"].iloc[0])
    spikes = changes[
        (changes["average"] > 0)
        & (changes["change_pct"] >= CATEGORY_SPIKE_PCT)
        & ((changes["current"] - changes["average"]) >= CATEGORY_SPIKE_MIN_AMOUNT)
    ].sort_values("change_pct", ascending=False)
    insights = []
    for _, row in spikes.head(2).iterrows():
        insights.append(Insight(
            category="Category trends", severity=WARNING,
            title=f"{row['category']} spending is higher than usual",
            message=f"You spent {format_inr(row['current'])} on {row['category'].lower()} in "
                    f"{month_label(ctx.month)}, {row['change_pct']:.0f}% above your "
                    f"{months_used}-month average of {format_inr(row['average'])}.",
            rule=f"Compared with the average of up to 3 previous months that have records. "
                 f"Shown when at least {CATEGORY_SPIKE_PCT:.0f}% and "
                 f"{format_inr(CATEGORY_SPIKE_MIN_AMOUNT)} above average.",
            metrics={"change_pct": float(row["change_pct"])},
        ))
    return insights


def spending_projection(ctx: InsightContext) -> list[Insight]:
    projection = calc.daily_run_rate_projection(ctx.transactions, ctx.month, ctx.today)
    if projection is None:
        return []
    return [Insight(
        category="Projection", severity=INFO,
        title="Month-end spending estimate",
        message=f"You've spent {format_inr(projection['spent_so_far'])} in the first "
                f"{projection['days_elapsed']} days of {month_label(ctx.month)}. At this pace, "
                f"spending would reach about {format_inr(projection['projected'])} by month end. "
                "Fixed costs such as rent can make early-month estimates high.",
        rule="Spending so far ÷ days elapsed × days in the month. Only shown for the current month.",
        metrics=projection,
    )]


def goal_pacing(ctx: InsightContext) -> list[Insight]:
    progress = calc.goal_progress(ctx.goals, ctx.today)
    insights = []
    for _, goal in progress.iterrows():
        if goal["completed"]:
            insights.append(Insight(
                category="Savings goals", severity=POSITIVE,
                title=f"{goal['name']} completed",
                message=f"You've reached your {format_inr(goal['target_amount'])} target for "
                        f"{goal['name']}.",
                rule="Saved amount (sum of contributions) ≥ target amount.",
            ))
        elif goal["monthly_needed"] is not None and not pd.isna(goal["monthly_needed"]):
            insights.append(Insight(
                category="Savings goals", severity=INFO,
                title=f"{goal['name']}: {goal['percent']:.0f}% funded",
                message=f"To reach {format_inr(goal['target_amount'])} by "
                        f"{date.fromisoformat(str(goal['target_date'])[:10]).strftime('%d %b %Y')}, "
                        f"you would need to save about {format_inr(goal['monthly_needed'])} per month "
                        f"({format_inr(goal['remaining'])} remaining).",
                rule="Remaining amount ÷ months until the target date (minimum one month).",
            ))
        elif goal["days_left"] is not None and not pd.isna(goal["days_left"]) and goal["days_left"] <= 0:
            insights.append(Insight(
                category="Savings goals", severity=WARNING,
                title=f"{goal['name']} target date has passed",
                message=f"The target date has passed with {format_inr(goal['remaining'])} still "
                        "to save. Consider updating the target date.",
                rule="Target date earlier than today and saved amount below target.",
            ))
    return insights


def portfolio_concentration(ctx: InsightContext) -> list[Insight]:
    values = calc.investment_values(ctx.investments)
    allocation = calc.allocation_by_category(values)
    if allocation.empty or len(values) < 2 or allocation["current"].sum() <= 0:
        return []
    top = allocation.iloc[0]
    if top["share"] < CONCENTRATION_SHARE:
        return []
    return [Insight(
        category="Portfolio", severity=INFO,
        title=f"{top['share']:.0f}% of your portfolio is in {top['category']}",
        message=f"{top['category']} makes up {top['share']:.0f}% of your tracked portfolio value "
                f"({format_inr(top['current'])}). This is an observation from your entered "
                "valuations, not investment advice.",
        rule=f"Category current value ÷ total current value × 100. Shown above {CONCENTRATION_SHARE:.0f}%.",
    )]


RULES = [
    budget_alerts,
    savings_rate_insight,
    month_on_month,
    spending_pattern,
    unusual_transactions,
    category_spikes,
    spending_projection,
    goal_pacing,
    portfolio_concentration,
]


def generate_insights(ctx: InsightContext) -> list[Insight]:
    """Run every rule and return insights ordered by severity."""
    if ctx.transactions.empty and ctx.goals.empty and ctx.investments.empty:
        return [Insight(
            category="Getting started", severity=NEEDS_DATA,
            title="No data yet",
            message="Add a few transactions to start receiving insights about your finances.",
            rule="Insights are generated only from records you have saved.",
        )]
    insights: list[Insight] = []
    for rule in RULES:
        insights.extend(rule(ctx))
    if ctx.month_transactions.empty:
        insights.append(Insight(
            category="Getting started", severity=NEEDS_DATA,
            title=f"No transactions in {month_label(ctx.month)}",
            message="Monthly insights appear once this month has income or expense records.",
            rule="Insights for a month require transactions dated in that month.",
        ))
    return sorted(insights, key=lambda item: _SEVERITY_ORDER.get(item.severity, 9))
