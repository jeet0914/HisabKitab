"""Tests for the "Edit Expense" feature: GET/POST /expenses/<id>/edit.

Spec: .claude/specs/08-edit-expense.md

Behaviour under test (per spec, not implementation):
- Both GET and POST /expenses/<id>/edit require an active session; unauthenticated
  requests redirect to /login.
- GET/POST for an expense id that doesn't exist, or that belongs to a different
  user, returns 404 — never the form, never another user's data.
- GET (logged in, own expense) renders a form pre-filled with the expense's
  current amount, category (a <select> with the right option selected), date,
  and description.
- POST (logged in, own expense) with valid data (positive numeric amount, a
  category from CATEGORIES, a YYYY-MM-DD date, optional description) updates
  the existing row in place and redirects (302) to /profile.
- POST with an invalid amount (blank, negative, zero, or non-numeric) does NOT
  update the row, and re-renders the form (200, not a redirect) with an error
  message.
- POST with a category not in CATEGORIES does NOT update the row, and
  re-renders the form (200) with an error message.
- After a successful edit, the updated values are visible on a later GET
  /profile, and the old values are not.
"""

import re
from datetime import date

import pytest

from app import app as flask_app
from database import db as db_module


# --------------------------------------------------------------------- #
# Fixtures                                                               #
# --------------------------------------------------------------------- #

@pytest.fixture()
def app(tmp_path, monkeypatch):
    """Point db_module.DB_PATH at a throwaway file and initialise fresh tables."""
    test_db_path = tmp_path / "test_expense_tracker.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(test_db_path))
    flask_app.config["TESTING"] = True
    db_module.init_db()
    yield flask_app


def _register(client, name="Edit Expense Tester", email="editexpense@example.com", password="password123"):
    """Register (and thereby log in, per app.py) a fresh user; return the user row."""
    client.post("/register", data={"name": name, "email": email, "password": password})
    return db_module.get_user_by_email(email)


def _insert_expense(user_id, amount, category, date_str, description):
    """Insert an expense row directly via the DB layer; return its id."""
    conn = db_module.get_db()
    cursor = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date_str, description),
    )
    conn.commit()
    expense_id = cursor.lastrowid
    conn.close()
    return expense_id


def _get_expense(expense_id):
    conn = db_module.get_db()
    row = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    conn.close()
    return row


def _extract_select_options(html, select_name):
    """Return the list of <option value="..."> values inside the <select
    name="select_name"> block, in document order.
    """
    select_match = re.search(
        r'<select[^>]*name=["\']' + re.escape(select_name) + r'["\'][^>]*>(.*?)</select>',
        html,
        re.DOTALL,
    )
    assert select_match is not None, f"Could not find <select name={select_name!r}> in the form"
    return select_match.group(1)


def _selected_option_value(select_html):
    """Return the value of the <option> marked selected= inside select_html, or None."""
    match = re.search(
        r'<option[^>]*value=["\']([^"\']*)["\'][^>]*selected', select_html
    )
    return match.group(1) if match else None


VALID_CATEGORY = db_module.CATEGORIES[0]
OTHER_CATEGORY = db_module.CATEGORIES[1]
TODAY_ISO = date.today().isoformat()


# --------------------------------------------------------------------- #
# Auth guard                                                             #
# --------------------------------------------------------------------- #

class TestAuthGuard:

    def test_get_edit_expense_unauthenticated_redirects_to_login(self, client):
        user = _register(client)
        expense_id = _insert_expense(user["id"], 20.00, VALID_CATEGORY, TODAY_ISO, "Groceries")
        client.get("/logout")

        response = client.get(f"/expenses/{expense_id}/edit")
        assert response.status_code == 302, "Unauthenticated GET must redirect, not render"
        assert response.headers["Location"].endswith("/login")

    def test_post_edit_expense_unauthenticated_redirects_to_login(self, client):
        user = _register(client)
        expense_id = _insert_expense(user["id"], 20.00, VALID_CATEGORY, TODAY_ISO, "Groceries")
        client.get("/logout")

        response = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "99.00",
                "category": VALID_CATEGORY,
                "date": TODAY_ISO,
                "description": "Should not be saved",
            },
        )
        assert response.status_code == 302, "Unauthenticated POST must redirect, not process"
        assert response.headers["Location"].endswith("/login")

        row = _get_expense(expense_id)
        assert row["amount"] == pytest.approx(20.00), "Unauthenticated POST must never update the row"


# --------------------------------------------------------------------- #
# Ownership / 404                                                        #
# --------------------------------------------------------------------- #

class TestOwnershipAnd404:

    def test_get_nonexistent_expense_returns_404(self, client):
        _register(client)
        response = client.get("/expenses/999999/edit")
        assert response.status_code == 404

    def test_post_nonexistent_expense_returns_404(self, client):
        _register(client)
        response = client.post(
            "/expenses/999999/edit",
            data={
                "amount": "10.00",
                "category": VALID_CATEGORY,
                "date": TODAY_ISO,
                "description": "n/a",
            },
        )
        assert response.status_code == 404

    def test_get_another_users_expense_returns_404(self, client):
        first_user = _register(client, name="First User", email="first@example.com")
        expense_id = _insert_expense(first_user["id"], 15.00, VALID_CATEGORY, TODAY_ISO, "First's lunch")
        client.get("/logout")

        _register(client, name="Second User", email="second@example.com")
        response = client.get(f"/expenses/{expense_id}/edit")
        assert response.status_code == 404, "Must not render another user's expense"

    def test_post_another_users_expense_returns_404_and_does_not_modify_it(self, client):
        first_user = _register(client, name="First User", email="first@example.com")
        expense_id = _insert_expense(first_user["id"], 15.00, VALID_CATEGORY, TODAY_ISO, "First's lunch")
        client.get("/logout")

        _register(client, name="Second User", email="second@example.com")
        response = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "999.00",
                "category": OTHER_CATEGORY,
                "date": TODAY_ISO,
                "description": "Hijacked",
            },
        )
        assert response.status_code == 404

        row = _get_expense(expense_id)
        assert row["amount"] == pytest.approx(15.00), "Another user's expense must be untouched"
        assert row["category"] == VALID_CATEGORY
        assert row["description"] == "First's lunch"


# --------------------------------------------------------------------- #
# GET (logged in, own expense) — form rendering                         #
# --------------------------------------------------------------------- #

class TestGetEditExpenseForm:

    def test_get_renders_form_prefilled_with_current_values(self, client):
        user = _register(client)
        expense_id = _insert_expense(user["id"], 42.50, VALID_CATEGORY, "2026-02-10", "Distinctive Desc")

        response = client.get(f"/expenses/{expense_id}/edit")
        assert response.status_code == 200
        html = response.data.decode("utf-8")

        amount_input_match = re.search(r'<input[^>]*name=["\']amount["\'][^>]*>', html)
        assert amount_input_match is not None
        assert 'value="42.5"' in amount_input_match.group(0), (
            f"Expected amount field prefilled with 42.5, got: {amount_input_match.group(0)}"
        )

        date_input_match = re.search(r'<input[^>]*name=["\']date["\'][^>]*>', html)
        assert date_input_match is not None
        assert 'value="2026-02-10"' in date_input_match.group(0)

        assert "Distinctive Desc" in html

        select_html = _extract_select_options(html, "category")
        assert _selected_option_value(select_html) == VALID_CATEGORY

    def test_category_select_options_match_categories_list_exactly(self, client):
        user = _register(client)
        expense_id = _insert_expense(user["id"], 10.00, VALID_CATEGORY, TODAY_ISO, "x")

        response = client.get(f"/expenses/{expense_id}/edit")
        html = response.data.decode("utf-8")
        select_html = _extract_select_options(html, "category")
        options = re.findall(r'<option[^>]*value=["\']([^"\']*)["\']', select_html)
        assert options == db_module.CATEGORIES


# --------------------------------------------------------------------- #
# POST — happy path                                                     #
# --------------------------------------------------------------------- #

class TestPostEditExpenseValid:

    def test_valid_submission_updates_row_in_place_and_redirects_to_profile(self, client):
        user = _register(client)
        expense_id = _insert_expense(user["id"], 20.00, VALID_CATEGORY, TODAY_ISO, "Old description")

        response = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "77.25",
                "category": OTHER_CATEGORY,
                "date": "2026-03-01",
                "description": "New description",
            },
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")

        row = _get_expense(expense_id)
        assert row["id"] == expense_id, "Editing must update the existing row, not create a new one"
        assert row["amount"] == pytest.approx(77.25)
        assert row["category"] == OTHER_CATEGORY
        assert row["date"] == "2026-03-01"
        assert row["description"] == "New description"
        assert row["user_id"] == user["id"]

        count_row_conn = db_module.get_db()
        total = count_row_conn.execute(
            "SELECT COUNT(*) AS count FROM expenses WHERE user_id = ?", (user["id"],)
        ).fetchone()["count"]
        count_row_conn.close()
        assert total == 1, "Editing must not insert an additional row"

    def test_updated_values_appear_on_profile_and_old_values_do_not(self, client):
        user = _register(client)
        expense_id = _insert_expense(
            user["id"], 20.00, VALID_CATEGORY, TODAY_ISO, "Old Distinctive Description"
        )

        client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "33.00",
                "category": VALID_CATEGORY,
                "date": TODAY_ISO,
                "description": "New Distinctive Description",
            },
        )

        profile_response = client.get("/profile")
        assert profile_response.status_code == 200
        assert b"New Distinctive Description" in profile_response.data
        assert b"Old Distinctive Description" not in profile_response.data

    def test_valid_submission_with_empty_description_still_updates(self, client):
        user = _register(client)
        expense_id = _insert_expense(user["id"], 20.00, VALID_CATEGORY, TODAY_ISO, "Has a description")

        response = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "20.00",
                "category": VALID_CATEGORY,
                "date": TODAY_ISO,
                "description": "",
            },
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")

        row = _get_expense(expense_id)
        assert row["description"] is None


# --------------------------------------------------------------------- #
# POST — invalid amount                                                 #
# --------------------------------------------------------------------- #

class TestPostEditExpenseInvalidAmount:

    @pytest.mark.parametrize(
        "bad_amount",
        ["", "-25.50", "-0.01", "0", "abc", "twelve"],
        ids=["blank", "negative", "small-negative", "zero", "non-numeric", "words"],
    )
    def test_invalid_amount_does_not_update_and_rerenders_form(self, client, bad_amount):
        user = _register(client)
        expense_id = _insert_expense(user["id"], 20.00, VALID_CATEGORY, TODAY_ISO, "Original")

        response = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": bad_amount,
                "category": VALID_CATEGORY,
                "date": TODAY_ISO,
                "description": "Should not be saved",
            },
        )

        assert response.status_code == 200, (
            f"Invalid amount {bad_amount!r} must re-render the form, not redirect"
        )
        row = _get_expense(expense_id)
        assert row["amount"] == pytest.approx(20.00), (
            f"Invalid amount {bad_amount!r} must not update the row"
        )
        assert row["description"] == "Original"
        assert b"error" in response.data.lower()
        assert re.search(rb'name=["\']amount["\']', response.data), (
            "Expected the edit-expense form to be re-rendered"
        )


# --------------------------------------------------------------------- #
# POST — invalid category                                               #
# --------------------------------------------------------------------- #

class TestPostEditExpenseInvalidCategory:

    @pytest.mark.parametrize(
        "bad_category",
        ["NotACategory", "", "food", "FOOD", "'; DROP TABLE expenses;--"],
        ids=["unknown", "blank", "lowercase", "uppercase", "sql-injection"],
    )
    def test_invalid_category_does_not_update_and_rerenders_form(self, client, bad_category):
        user = _register(client)
        expense_id = _insert_expense(user["id"], 20.00, VALID_CATEGORY, TODAY_ISO, "Original")

        response = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "50.00",
                "category": bad_category,
                "date": TODAY_ISO,
                "description": "Should not be saved",
            },
        )

        assert response.status_code == 200, (
            f"Invalid category {bad_category!r} must re-render the form, not redirect"
        )
        row = _get_expense(expense_id)
        assert row["category"] == VALID_CATEGORY, (
            f"Invalid category {bad_category!r} must not update the row"
        )
        assert row["amount"] == pytest.approx(20.00)
        assert b"error" in response.data.lower()

    def test_sql_injection_attempt_in_category_does_not_break_subsequent_requests(self, client):
        user = _register(client)
        expense_id = _insert_expense(user["id"], 20.00, VALID_CATEGORY, TODAY_ISO, "Original")

        injection_response = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "20.00",
                "category": "'; DROP TABLE expenses;--",
                "date": TODAY_ISO,
                "description": "Injection attempt",
            },
        )
        assert injection_response.status_code == 200

        followup = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "20.00",
                "category": VALID_CATEGORY,
                "date": TODAY_ISO,
                "description": "Post-injection sanity check",
            },
        )
        assert followup.status_code == 302
        assert followup.headers["Location"].endswith("/profile")

        row = _get_expense(expense_id)
        assert row["description"] == "Post-injection sanity check"
