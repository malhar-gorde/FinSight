# FinSight — CV / Résumé Project Description

Every point below describes functionality that exists in this codebase. Once you have deployed it,
you can say "built and deployed" and add the live link.

## One line

**FinSight: Personal Finance & Investment Dashboard** | Next.js, TypeScript, Python (FastAPI, pandas), PostgreSQL, Vercel

## Three bullets

- Built a full-stack personal finance web app with a **Next.js/TypeScript** frontend and a
  **Python FastAPI** backend running as Vercel serverless functions, backed by **PostgreSQL**.
- Implemented financial analytics in **pandas**: savings rate, month-on-month change, budget utilisation
  with status thresholds, goal pacing and unrealised portfolio returns. Visualised the results with
  interactive **Recharts** dashboards.
- Designed a transparent **rule-based insight engine** (budget alerts, category spending spikes,
  median-based unusual-expense detection) and covered it with **100 pytest tests** that run against both
  SQLite and PostgreSQL.

## Extended

- Wrote a database layer that supports **PostgreSQL and SQLite** from the same parameterised SQL, using
  CHECK/UNIQUE constraints, a cascading foreign key and atomic bulk operations.
- Built CRUD workflows for transactions, budgets, savings goals and investments, with validation on both
  client and server, two-step confirmation for destructive actions and CSV/ZIP export.
- Added optional password protection using an HMAC-signed, HTTP-only session cookie.
- Designed a responsive, accessible UI (labelled form controls and a mobile navigation drawer) in a
  custom ivory, forest and sage design system.

## Talking points

- Why the frontend and the financial logic are separate services, and how Next.js proxies `/api/py` in
  development while Vercel routes it to a Python function in production.
- Why a goal's saved amount is derived from `SUM(contributions)` instead of being stored.
- How unusual expenses are detected per category, so rent isn't flagged against small daily spending.
- Serverless trade-offs: cold starts, connection handling, and why SQLite can't persist on Vercel.
