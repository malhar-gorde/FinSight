from datetime import date

import pytest
from fastapi.testclient import TestClient

import api.index as api_module


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("FINSIGHT_DB_PATH", str(tmp_path / "api.db"))
    for name in ("DATABASE_URL", "POSTGRES_URL", "APP_PASSWORD", "AUTH_SECRET", "VERCEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(api_module, "_ready", False)
    return TestClient(api_module.app)


def test_meta_and_first_run_demo_data(client):
    meta = client.get("/api/py/meta").json()
    assert meta["has_sample_data"] is True
    assert meta["storage_mode"] == "local"
    assert "Food" in meta["categories"]["Expense"]


def test_overview_is_json_safe(client):
    data = client.get("/api/py/overview").json()
    assert data["has_transactions"] is True
    current = data["comparison"]["current"]
    assert current["net"] == pytest.approx(current["income"] - current["expenses"])
    assert len(data["monthly"]) == 6 and len(data["recent"]) == 8


def test_transaction_crud_updates_totals(client):
    month = date.today().strftime("%Y-%m")
    before = client.get(f"/api/py/overview?month={month}").json()["comparison"]["current"]["expenses"]
    body = {"date": date.today().isoformat(), "description": "API test", "category": "Food", "type": "Expense",
            "amount": 250, "payment_method": "UPI", "notes": ""}
    txn_id = client.post("/api/py/transactions", json=body).json()["id"]
    after = client.get(f"/api/py/overview?month={month}").json()["comparison"]["current"]["expenses"]
    assert after == pytest.approx(before + 250)

    assert client.put(f"/api/py/transactions/{txn_id}", json={**body, "amount": 300}).status_code == 200
    found = client.get("/api/py/transactions?search=API%20test").json()
    assert len(found["items"]) == 1 and found["items"][0]["amount"] == 300

    assert client.delete(f"/api/py/transactions/{txn_id}").status_code == 200
    assert client.delete(f"/api/py/transactions/{txn_id}").status_code == 404


def test_invalid_input_returns_400_with_message(client):
    body = {"date": date.today().isoformat(), "description": "Bad", "category": "Food", "type": "Expense",
            "amount": -5, "payment_method": "UPI"}
    response = client.post("/api/py/transactions", json=body)
    assert response.status_code == 400
    assert "greater than zero" in response.json()["detail"]


def test_duplicate_budget_rejected(client):
    month = date.today().strftime("%Y-%m")
    response = client.post("/api/py/budgets", json={"month": month, "category": "Food", "amount": 1000})
    assert response.status_code == 400 and "already exists" in response.json()["detail"]


def test_csv_export(client):
    response = client.get("/api/py/transactions/export.csv?types=Income")
    assert response.status_code == 200
    lines = response.content.decode("utf-8-sig").strip().splitlines()
    assert lines[0].startswith("id,date,description")
    assert all(",Income," in line for line in lines[1:])


def test_destructive_actions_require_confirmation(client):
    assert client.post("/api/py/data/clear", json={"confirm": "yes"}).status_code == 400
    assert client.post("/api/py/data/clear", json={"confirm": "DELETE"}).status_code == 200
    assert client.get("/api/py/overview").json()["has_transactions"] is False
    assert client.get("/api/py/insights").json()[0]["severity"] == "needs_data"


def test_password_protection(client, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "correct horse")
    assert client.get("/api/py/overview").status_code == 401
    assert client.get("/api/py/auth/status").json() == {"required": True, "authenticated": False}
    assert client.post("/api/py/auth/login", json={"password": "wrong"}).status_code == 401
    assert client.post("/api/py/auth/login", json={"password": "correct horse"}).status_code == 200
    assert client.get("/api/py/overview").status_code == 200  # cookie kept by the client
    client.post("/api/py/auth/logout")
    assert client.get("/api/py/overview").status_code == 401


def test_forged_cookie_rejected(client, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "secret")
    client.cookies.set("finsight_session", "9999999999.deadbeef")
    assert client.get("/api/py/overview").status_code == 401
