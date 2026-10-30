# FinSight

**Understand Your Money. Master Your Future.**

FinSight is a personal finance and investment dashboard for students and young professionals. It covers
income and expense tracking, monthly budgets, savings goals, a simple investment portfolio and
rule-based financial insights. Every figure is calculated from your own stored records.

- **Frontend:** Next.js 16 (React 19, TypeScript), Recharts, Lucide icons
- **Backend:** Python FastAPI running as a Vercel serverless function, using pandas for the financial calculations
- **Database:** PostgreSQL in production (e.g. Neon through the Vercel Marketplace), SQLite for local development
- **Tests:** pytest, with 100 tests run against both SQLite and a real PostgreSQL server

> Screenshots: add images to `docs/screenshots/` and embed them here.

---

## Features

| Area | What it does |
|---|---|
| **Overview** | Month selector; income, expense, net-savings and savings-rate cards with month-on-month changes; spending-by-category donut; income vs expenses (3/6/12 months); cumulative savings trend; financial health summary; recent transactions. |
| **Transactions** | Add, edit in place and delete (with confirmation); search; filter by date range, type, category and payment method; sort by date or amount; export filtered or all records to CSV. |
| **Budgets** | Monthly limit per expense category; spent, remaining, % used, progress bar and Healthy / Caution / Exceeded status; duplicate prevention; copy last month's budgets. |
| **Savings Goals** | Target, optional date and description; contributions and balance adjustments; % complete, remaining, days left and required monthly saving; full history. |
| **Investments** | Stocks, mutual funds, ETFs, FDs, gold and other assets; units × price or fixed-value valuation; invested, current, unrealised P&L, return %; allocation and per-holding charts. |
| **Financial Insights** | Rule-based insights (budget alerts, savings rate, month-on-month change, largest category, unusual transactions, category spikes, month-end projection, goal pacing, portfolio concentration), each showing its calculation rule. Includes a **monthly report** and 12-month **trends**. |
| **Settings** | Name, caution threshold, record counts (yours vs demo), remove/reset demo data, clear all data (type DELETE to confirm), ZIP export of every table. |
| **Security** | Optional single-password sign-in (`APP_PASSWORD`) with a signed, HTTP-only session cookie. |

## Architecture

```
FinSight-Vercel/
├── app/                      # Next.js pages (App Router)
│   ├── page.tsx              #   Overview
│   ├── transactions/ budgets/ goals/ investments/ insights/ settings/ login/
│   ├── layout.tsx            #   Fonts, providers, sidebar shell
│   └── globals.css           #   Design system (ivory / forest / sage / gold)
├── components/               # Shell, charts, forms, UI primitives
├── lib/                      # API client, formatting (₹ Indian grouping), types
├── api/index.py              # FastAPI app → Vercel Python function at /api/py/*
├── finsight/                 # Python core (no web framework code)
│   ├── database.py           #   PostgreSQL + SQLite, parameterised SQL
│   ├── calculations.py       #   Pure pandas financial calculations
│   ├── insights.py           #   Rule-based insight engine
│   ├── validation.py  sample_data.py  exports.py  formatting.py  constants.py
├── tests/                    # pytest: calculations, database (SQLite + Postgres), API
├── scripts/dev_api_postgres.py   # Run the API locally on a throwaway PostgreSQL
├── next.config.mjs           # Proxies /api/py/* to the local API in development
├── vercel.json               # Python function settings (bundles finsight/)
└── requirements.txt          # Python runtime deps installed by Vercel
```

The browser only talks to `/api/py/*`. On Vercel that path is served by `api/index.py`. During local
development, Next.js forwards it to uvicorn on port 8000.

### Database tables

| Table | Key columns |
|---|---|
| `transactions` | `id`, `date`, `description`, `category`, `type` (Income/Expense, CHECK), `amount` (> 0, CHECK), `payment_method`, `notes`, `is_sample` |
| `budgets` | `id`, `month` (YYYY-MM), `category`, `amount` (> 0), **UNIQUE (month, category)** |
| `savings_goals` | `id`, `name`, `target_amount` (> 0), `target_date`, `description` |
| `goal_contributions` | `id`, `goal_id` → goals **ON DELETE CASCADE**, `date`, `amount`, `kind` (contribution/adjustment) |
| `investments` | `id`, `name`, `category`, `valuation_mode` (units/fixed), quantity & prices or invested & current value, `price_updated_at` |
| `settings` | `key`, `value` |

Tables are created automatically on the first request. Demo data is loaded once, on the very first
run, and marked `is_sample = 1` so it can be removed without touching your own records.

### Key calculations

| Metric | Formula |
|---|---|
| Savings rate | (income − expenses) ÷ income × 100; shown as "—" when income is zero |
| Month-on-month change | (this − last) ÷ last × 100; hidden when last month has no data |
| Budget status | Healthy < caution (default 75%) ≤ Caution ≤ 100% < Exceeded |
| Goal saved amount | SUM of its contributions, so the history always adds up |
| Units-based investment | invested = units × buy price; current = units × current price |
| Return % | P&L ÷ invested × 100; undefined when invested is zero |
| Unusual expense | ≥ 3× the median of other expenses in the same category (≥ 5 on record, ≥ ₹1,000) |

---

## Deploying to Vercel

You need a free [GitHub](https://github.com) account and a free [Vercel](https://vercel.com) account
(sign up with GitHub).

### 1. Push the code to GitHub

Create an **empty** repository on GitHub called `FinSight` (no README). Then, in this folder:

```powershell
git add .
git commit -m "FinSight: Next.js + FastAPI personal finance dashboard"
git branch -M main
git remote add origin https://github.com/<your-username>/FinSight.git
git push -u origin main
```

If Git asks who you are, set it once with `git config --global user.name "Your Name"` and
`git config --global user.email "you@example.com"`.

### 2. Import the project in Vercel

1. Go to **vercel.com → Add New… → Project** and import the `FinSight` repository.
2. Vercel detects **Next.js** automatically. Leave the build settings at their defaults and click **Deploy**.

The first deployment works straight away, but **without a database the data is temporary**. The app
shows a red banner saying so. Continue with step 3.

### 3. Add a PostgreSQL database (keeps your data)

1. In your Vercel project, open **Storage → Create Database → Neon (Serverless Postgres)** and use the free plan.
2. Connect it to the project for all environments. This adds a `DATABASE_URL` environment variable automatically.

### 4. Protect your data with a password (strongly recommended)

Without a password, anyone with your link can see and edit your finances. In **Settings → Environment
Variables** add:

| Name | Value |
|---|---|
| `APP_PASSWORD` | the password you'll sign in with |
| `AUTH_SECRET` | any long random string, e.g. 40+ random letters and numbers |

### 5. Redeploy

Open **Deployments → ⋯ → Redeploy**. Your app is live at `https://<project-name>.vercel.app`. The first
visit creates the tables and loads the demo data. You can remove the demo data in Settings.

**Notes**
- The Python API is a serverless function, so the first request after a period of inactivity takes a
  few seconds while it starts (a "cold start").
- Never commit passwords or a `.env` file. Set secrets only in Vercel's Environment Variables.

---

## Running locally (Windows, VS Code)

You need Python 3.10+ and Node.js 20+.

```powershell
# 1. Python environment (in the project folder)
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# 2. JavaScript packages
npm install

# 3. Start both servers (API on :8000, website on :3000)
npm run dev
```

Open http://localhost:3000. Locally the API stores data in `data/finsight.db` (SQLite).

- If `npm run dev` can't find `python`, activate the virtual environment first (step 1), or run the two
  servers in separate terminals: `python -m uvicorn api.index:app --reload --port 8000` and `npm run next-dev`.
- If PowerShell blocks `Activate.ps1`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
- To develop against PostgreSQL like production, run `python scripts/dev_api_postgres.py` in place of uvicorn.

## Testing

```powershell
pytest            # 100 tests: calculations, insights, API, database on SQLite and PostgreSQL
npm run build     # type-checks and builds the frontend
```

The PostgreSQL tests start a temporary local server with the `pgserver` package and are skipped if it
isn't installed.

## Limitations

- Investment prices are entered manually; there is no live market-data feed.
- Single user, with one shared password. There are no separate accounts.
- No PDF reports; monthly transactions export to CSV.

## Future improvements

- Multiple user accounts (e.g. Auth.js) with per-user data
- Optional market-data integration with source attribution and last-updated time
- Recurring transactions, bill reminders and CSV import from bank statements
- PDF monthly reports

## Disclaimer

FinSight is an educational tracking tool. It does not give financial or investment advice, and past
returns shown in the app do not guarantee future performance.
