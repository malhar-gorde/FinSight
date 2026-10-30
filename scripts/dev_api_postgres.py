"""Run the API locally against a throwaway PostgreSQL server (development only).

Starts a local PostgreSQL with the `pgserver` package (pip install -r requirements-dev.txt),
points DATABASE_URL at it and serves the API on http://127.0.0.1:8000 — the same database
engine the app uses on Vercel. Data lives in .pgdata/ (git-ignored).

Usage:  python scripts/dev_api_postgres.py
"""

import os
import sys
from pathlib import Path

import pgserver
import uvicorn

PROJECT = Path(__file__).resolve().parent.parent

server = pgserver.get_server(PROJECT / ".pgdata", cleanup_mode="stop")
os.environ["DATABASE_URL"] = server.get_uri()
print("Using local PostgreSQL at", server.get_uri().split("@")[-1], flush=True)

sys.path.insert(0, str(PROJECT))
os.chdir(PROJECT)
uvicorn.run("api.index:app", host="127.0.0.1", port=8000)
