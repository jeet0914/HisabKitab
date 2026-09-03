import re

import pytest

from app import app as flask_app
from database import db as db_module
from database import queries as queries_module


@pytest.fixture()
def app(tmp_path, monkeypatch):
    test_db_path = tmp_path / "test_expense_tracker.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(test_db_path))
    flask_app.config["TESTING"] = True
    db_module.init_db()
    yield flask_app


def _login(client, email="demo@spendly.com", password="demo123"):
    return client.post("/login", data={"email": email, "password": password})


# --------------------------------------------------------------------- #
# Unit tests: database/queries.py                                        #
# --------------------------------------------------------------------- #

def test_get_user_by_id_returns_correct_fields(app):
    user_id = db_module.create_user("Nitish Kumar", "nitish@example.com", "password123")
    result = queries_module.get_user_by_id(user_id)
    assert result["name"] == "Nitish Kumar"
    assert result["email"] == "nitish@example.com"
    assert re.match(r"^[A-Z][a-z]+ \d{4}$", result["member_since"])


def test_get_user_by_id_nonexistent_returns_none(app):
    assert queries_module.get_user_by_id(9999) is None


def test_get_summary_stats_matches_seed_data(app):
    db_module.seed_db()
    user = db_module.get_user_by_email("demo@spendly.com")
    stats = queries_module.get_summary_stats(user["id"])
    assert stats["total_spent"] == pytest.approx(203.64)
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Shopping"


def test_get_summary_stats_no_expenses_returns_zeroed_dict(app):
    user_id = db_module.create_user("New User", "new@example.com", "password123")
    stats = queries_module.get_summary_stats(user_id)
    assert stats == {"total_spent": 0, "transaction_count": 0, "top_category": "—"}


def test_get_recent_transactions_ordered_newest_first(app):
    db_module.seed_db()
    user = db_module.get_user_by_email("demo@spendly.com")
    txns = queries_module.get_recent_transactions(user["id"], limit=10)
    assert len(txns) == 8
    dates = [t["date"] for t in txns]
    assert dates == sorted(dates, reverse=True)
    assert set(txns[0].keys()) == {"date", "description", "category", "amount"}


def test_get_recent_transactions_no_expenses_returns_empty_list(app):
    user_id = db_module.create_user("New User", "new@example.com", "password123")
    assert queries_module.get_recent_transactions(user_id) == []


def test_get_category_breakdown_matches_seed_data(app):
    db_module.seed_db()
    user = db_module.get_user_by_email("demo@spendly.com")
    breakdown = queries_module.get_category_breakdown(user["id"])

    assert [c["name"] for c in breakdown] == [
        "Shopping", "Bills", "Food", "Health", "Entertainment", "Other", "Transport",
    ]
    amounts = {c["name"]: c["amount"] for c in breakdown}
    assert amounts["Shopping"] == pytest.approx(60.00)
    assert amounts["Food"] == pytest.approx(44.90)

    pcts = {c["name"]: c["pct"] for c in breakdown}
    assert pcts == {
        "Shopping": 29, "Bills": 22, "Food": 22,
        "Health": 10, "Entertainment": 8, "Other": 5, "Transport": 4,
    }
    assert sum(c["pct"] for c in breakdown) == 100


def test_get_category_breakdown_no_expenses_returns_empty_list(app):
    user_id = db_module.create_user("New User", "new@example.com", "password123")
    assert queries_module.get_category_breakdown(user_id) == []


def test_get_category_breakdown_rounding_remainder_goes_to_largest(app):
    user_id = db_module.create_user("Rounding User", "rounding@example.com", "password123")
    conn = db_module.get_db()
    for amount, category in [(3.00, "Food"), (2.00, "Transport"), (2.00, "Bills")]:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date) VALUES (?, ?, ?, ?)",
            (user_id, amount, category, "2026-09-01"),
        )
    conn.commit()
    conn.close()

    breakdown = queries_module.get_category_breakdown(user_id)
    assert sum(c["pct"] for c in breakdown) == 100
    largest = max(breakdown, key=lambda c: c["amount"])
    assert largest["name"] == "Food"


# --------------------------------------------------------------------- #
# Route tests: GET /profile                                              #
# --------------------------------------------------------------------- #

def test_profile_unauthenticated_redirects_to_login(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_profile_authenticated_shows_real_seed_data(client):
    db_module.seed_db()
    _login(client)
    response = client.get("/profile")
    assert response.status_code == 200
    assert b"Demo User" in response.data
    assert b"demo@spendly.com" in response.data
    assert "₹".encode("utf-8") in response.data
    assert b"203.64" in response.data
    assert b"Shopping" in response.data


def test_profile_new_user_shows_zero_state(client):
    client.post(
        "/register",
        data={"name": "Brand New", "email": "brandnew@example.com", "password": "password123"},
    )
    response = client.get("/profile")
    assert response.status_code == 200
    assert "₹0.00".encode("utf-8") in response.data
    assert b"Brand New" in response.data
