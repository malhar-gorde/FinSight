"""Shared constants: categories, payment methods and the design-system palette."""

APP_NAME = "FinSight"
TAGLINE = "Understand Your Money. Master Your Future."

TRANSACTION_TYPES = ["Income", "Expense"]

EXPENSE_CATEGORIES = [
    "Food",
    "Travel",
    "Education",
    "Shopping",
    "Entertainment",
    "Housing",
    "Healthcare",
    "Bills and Utilities",
    "Other",
]

INCOME_CATEGORIES = [
    "Salary",
    "Freelance",
    "Stipend / Scholarship",
    "Allowance",
    "Investment Income",
    "Gifts",
    "Other Income",
]

CATEGORIES_BY_TYPE = {"Income": INCOME_CATEGORIES, "Expense": EXPENSE_CATEGORIES}

PAYMENT_METHODS = [
    "UPI",
    "Debit Card",
    "Credit Card",
    "Cash",
    "Net Banking",
    "Bank Transfer",
    "Wallet",
]

INVESTMENT_CATEGORIES = [
    "Stocks",
    "Mutual Funds",
    "Exchange-Traded Funds",
    "Fixed Deposits",
    "Gold",
    "Other Assets",
]

# Valuation modes for investments.
#   units: invested = quantity x purchase price, current = quantity x current price
#   fixed: invested and current value are entered directly (e.g. fixed deposits)
VALUATION_UNITS = "units"
VALUATION_FIXED = "fixed"

# Budget status thresholds (percent of budget used).
DEFAULT_CAUTION_THRESHOLD = 75
EXCEEDED_THRESHOLD = 100  # spending strictly above 100% of the limit is "Exceeded"

STATUS_HEALTHY = "Healthy"
STATUS_CAUTION = "Caution"
STATUS_EXCEEDED = "Exceeded"

# Limits used for input validation.
MAX_AMOUNT = 1_000_000_000  # ₹100 crore - generous sanity ceiling
MAX_DESCRIPTION_LENGTH = 120
MAX_NOTES_LENGTH = 500

# Design system palette.
COLORS = {
    "ivory": "#F7F5EF",
    "white": "#FFFFFF",
    "forest": "#244A3A",
    "sage": "#A3B8A0",
    "gold": "#C5A46D",
    "charcoal": "#252923",
    "stone": "#777970",
    "border": "#E6E3DA",
    # Supporting tones derived from the core palette, used for multi-series charts
    # and status indicators.
    "forest_soft": "#E4ECE6",
    "sage_soft": "#EEF2EC",
    "gold_soft": "#F6EFE2",
    "clay": "#A4553F",
    "clay_soft": "#F5E6E1",
}

# Ordered categorical palette for charts with many categories (balanced across
# forest, sage and gold so charts never become "all green").
CHART_SEQUENCE = [
    "#244A3A",  # forest
    "#C5A46D",  # gold
    "#A3B8A0",  # sage
    "#5E7F6B",  # mid green
    "#8C6D3F",  # deep gold
    "#D9CBA8",  # pale gold
    "#3D6553",  # pine
    "#C9D4C5",  # pale sage
    "#B8B3A6",  # warm grey
]
