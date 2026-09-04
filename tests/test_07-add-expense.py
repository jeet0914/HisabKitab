"""Tests for the "Add Expense" feature: GET/POST /expenses/add.

Spec: .claude/specs/07-add-expense.md

Behaviour under test (per spec, not implementation):
- Both GET and POST /expenses/add require an active session; unauthenticated
  requests redirect to /login.
- GET (logged in) renders a form with fields named amount, category (a
  <select>), date, and description. The <select> options must match
  CATEGORIES from database/db.py exactly (same values, same order).
- POST (logged in) with valid data (positive numeric amount, a category from
  CATEGORIES, a YYYY-MM-DD date, optional description) inserts a new row into
  `expenses` for the logged-in user and redirects (302) to /profile.
- POST with an invalid amount (blank, negative, zero, or non-numeric) does
  NOT insert a row, and re-renders the form (200, not a redirect) with an
  error message.
- POST with a category not in CATEGORIES does NOT insert a row, and
  re-renders the form (200) with an error message.
- After a successful add, the new expense is visible on a later GET
  /profile (it appears in the transaction list).
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


def _register(client, name="Add Expense Tester", email="addexpense@example.com", password="password123"):
    """Register (and thereby log in, per app.py) a fresh user; return the user row."""
    client.post("/register", data={"name": name, "email": email, "password": password})
    return db_module.get_user_by_email(email)


def _insert_expense(user_id, amount, category, date_str, description):
    conn = db_module.get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date_str, description),
    )
    conn.commit()
    conn.close()


def _expense_count(user_id=None):
    conn = db_module.get_db()
    if user_id is None:
        row = conn.execute("SELECT COUNT(*) AS count FROM expenses").fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()
    conn.close()
    return row["count"]


def _all_expenses(user_id):
    conn = db_module.get_db()
    rows = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY id", (user_id,)
    ).fetchall()
    conn.close()
    return rows


def _extract_select_options(html, select_name):
    """Return the list of <option value="..."> values inside the <select
    name="select_name"> block, in document order. Tolerant of attribute
    ordering/whitespace around the name attribute.
    """
    select_match = re.search(
        r'<select[^>]*name=["\']' + re.escape(select_name) + r'["\'][^>]*>(.*?)</select>',
        html,
        re.DOTALL,
    )
    assert select_match is not None, f"Could not find <select name={select_name!r}> in the form"
    options_html = select_match.group(1)
    return re.findall(r'<option[^>]*value=["\']([^"\']*)["\']', options_html)


VALID_CATEGORY = db_module.CATEGORIES[0]
TODAY_ISO = date.today().isoformat()


# --------------------------------------------------------------------- #
# Auth guard                                                             #
# --------------------------------------------------------------------- #

class TestAuthGuard:

    def test_get_add_expense_unauthenticated_redirects_to_login(self, client):
        response = client.get("/expenses/add")
        assert response.status_code == 302, "Unauthenticated GET must redirect, not render"
        assert response.headers["Location"].endswith("/login"), (
            "Unauthenticated GET /expenses/add must redirect to /login"
        )

    def test_post_add_expense_unauthenticated_redirects_to_login(self, client):
        response = client.post(
            "/expenses/add",
            data={
                "amount": "25.00",
                "category": VALID_CATEGORY,
                "date": TODAY_ISO,
                "description": "Should not be saved",
            },
        )
        assert response.status_code == 302, "Unauthenticated POST must redirect, not process"
        assert response.headers["Location"].endswith("/login"), (
            "Unauthenticated POST /expenses/add must redirect to /login"
        )
        assert _expense_count() == 0, "Unauthenticated POST must never insert a row"


# --------------------------------------------------------------------- #
# GET (logged in) — form rendering                                      #
# --------------------------------------------------------------------- #

class TestGetAddExpenseForm:

    def test_get_logged_in_renders_form_with_expected_fields(self, client):
        _register(client)
        response = client.get("/expenses/add")
        assert response.status_code == 200
        html = response.data.decode("utf-8")

        assert re.search(r'name=["\']amount["\']', html), "Expected an amount field"
        assert re.search(r'<select[^>]*name=["\']category["\']', html), (
            "Expected a category <select> field"
        )
        assert re.search(r'name=["\']date["\']', html), "Expected a date field"
        assert re.search(r'name=["\']description["\']', html), "Expected a description field"

    def test_category_select_options_match_categories_list_exactly(self, client):
        _register(client)
        response = client.get("/expenses/add")
        html = response.data.decode("utf-8")

        options = _extract_select_options(html, "category")
        assert options == db_module.CATEGORIES, (
            f"Expected category options {db_module.CATEGORIES!r}, got {options!r}"
        )

    def test_date_field_defaults_to_today(self, client):
        _register(client)
        response = client.get("/expenses/add")
        html = response.data.decode("utf-8")

        date_input_match = re.search(
            r'<input[^>]*name=["\']date["\'][^>]*>', html
        )
        assert date_input_match is not None, "Expected a date <input> element"
        value_match = re.search(r'value=["\']([^"\']*)["\']', date_input_match.group(0))
        assert value_match is not None, "Expected the date input to have a default value"
        assert value_match.group(1) == TODAY_ISO, (
            f"Expected date field to default to today ({TODAY_ISO}), got {value_match.group(1)!r}"
        )


# --------------------------------------------------------------------- #
# POST — happy path                                                     #
# --------------------------------------------------------------------- #

class TestPostAddExpenseValid:

    def test_valid_submission_inserts_row_and_redirects_to_profile(self, client):
        user = _register(client)

        response = client.post(
            "/expenses/add",
            data={
                "amount": "45.50",
                "category": VALID_CATEGORY,
                "date": "2026-01-15",
                "description": "Lunch with team",
            },
        )

        assert response.status_code == 302, "Valid submission must redirect, not re-render"
        assert response.headers["Location"].endswith("/profile"), (
            "Valid submission must redirect to /profile"
        )

        assert _expense_count(user["id"]) == 1, "Expected exactly one expense row to be inserted"
        rows = _all_expenses(user["id"])
        row = rows[0]
        assert row["amount"] == pytest.approx(45.50)
        assert row["category"] == VALID_CATEGORY
        assert row["date"] == "2026-01-15"
        assert row["description"] == "Lunch with team"
        assert row["user_id"] == user["id"]

    def test_valid_submission_with_empty_description_still_inserts(self, client):
        user = _register(client)

        response = client.post(
            "/expenses/add",
            data={
                "amount": "10.00",
                "category": VALID_CATEGORY,
                "date": TODAY_ISO,
                "description": "",
            },
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")
        assert _expense_count(user["id"]) == 1, "Optional description must not block insertion"

    @pytest.mark.parametrize("category", db_module.CATEGORIES)
    def test_valid_submission_accepts_every_category(self, client, category):
        user = _register(client, email=f"cat-{category.lower()}@example.com")

        response = client.post(
            "/expenses/add",
            data={
                "amount": "12.34",
                "category": category,
                "date": TODAY_ISO,
                "description": f"{category} expense",
            },
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")
        rows = _all_expenses(user["id"])
        assert len(rows) == 1
        assert rows[0]["category"] == category

    def test_new_expense_appears_on_profile_page_after_redirect(self, client):
        _register(client)

        client.post(
            "/expenses/add",
            data={
                "amount": "99.99",
                "category": VALID_CATEGORY,
                "date": TODAY_ISO,
                "description": "Distinctive Description XYZ",
            },
        )

        profile_response = client.get("/profile")
        assert profile_response.status_code == 200
        assert b"Distinctive Description XYZ" in profile_response.data, (
            "Newly added expense must appear in the profile page's transaction list"
        )

    def test_new_expense_appears_when_following_redirect_directly(self, client):
        _register(client)

        response = client.post(
            "/expenses/add",
            data={
                "amount": "15.00",
                "category": VALID_CATEGORY,
                "date": TODAY_ISO,
                "description": "Follow Redirect Description",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert b"Follow Redirect Description" in response.data


# --------------------------------------------------------------------- #
# POST — invalid amount                                                 #
# --------------------------------------------------------------------- #

class TestPostAddExpenseInvalidAmount:

    @pytest.mark.parametrize(
        "bad_amount",
        ["", "-25.50", "-0.01", "0", "abc", "twelve"],
        ids=["blank", "negative", "small-negative", "zero", "non-numeric", "words"],
    )
    def test_invalid_amount_does_not_insert_and_rerenders_form(self, client, bad_amount):
        user = _register(client)

        response = client.post(
            "/expenses/add",
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
        assert _expense_count(user["id"]) == 0, (
            f"Invalid amount {bad_amount!r} must not insert a row"
        )
        assert b"error" in response.data.lower(), (
            f"Expected an error message in the response for invalid amount {bad_amount!r}"
        )
        # The form should still be present so the user can correct their input.
        assert re.search(rb'name=["\']amount["\']', response.data), (
            "Expected the add-expense form to be re-rendered"
        )


# --------------------------------------------------------------------- #
# POST — invalid category                                               #
# --------------------------------------------------------------------- #

class TestPostAddExpenseInvalidCategory:

    @pytest.mark.parametrize(
        "bad_category",
        ["NotACategory", "", "food", "FOOD", "'; DROP TABLE expenses;--"],
        ids=["unknown", "blank", "lowercase", "uppercase", "sql-injection"],
    )
    def test_invalid_category_does_not_insert_and_rerenders_form(self, client, bad_category):
        user = _register(client)

        response = client.post(
            "/expenses/add",
            data={
                "amount": "20.00",
                "category": bad_category,
                "date": TODAY_ISO,
                "description": "Should not be saved",
            },
        )

        assert response.status_code == 200, (
            f"Invalid category {bad_category!r} must re-render the form, not redirect"
        )
        assert _expense_count(user["id"]) == 0, (
            f"Invalid category {bad_category!r} must not insert a row"
        )
        assert b"error" in response.data.lower(), (
            f"Expected an error message in the response for invalid category {bad_category!r}"
        )

    def test_sql_injection_attempt_in_category_does_not_break_subsequent_requests(self, client):
        user = _register(client)

        injection_response = client.post(
            "/expenses/add",
            data={
                "amount": "20.00",
                "category": "'; DROP TABLE expenses;--",
                "date": TODAY_ISO,
                "description": "Injection attempt",
            },
        )
        assert injection_response.status_code == 200
        assert _expense_count(user["id"]) == 0

        # If the injection had succeeded, the expenses table would be gone
        # and this follow-up request would fail instead of behaving normally.
        followup = client.post(
            "/expenses/add",
            data={
                "amount": "20.00",
                "category": VALID_CATEGORY,
                "date": TODAY_ISO,
                "description": "Post-injection sanity check",
            },
        )
        assert followup.status_code == 302
        assert followup.headers["Location"].endswith("/profile")
        assert _expense_count(user["id"]) == 1


# --------------------------------------------------------------------- #
# POST — combined / miscellaneous invalid input                         #
# --------------------------------------------------------------------- #

class TestPostAddExpenseMiscValidation:

    def test_missing_amount_field_entirely_does_not_insert(self, client):
        user = _register(client)

        response = client.post(
            "/expenses/add",
            data={
                "category": VALID_CATEGORY,
                "date": TODAY_ISO,
                "description": "No amount field at all",
            },
        )

        assert response.status_code in (200, 400), (
            "Missing amount field must not redirect as if successful"
        )
        assert _expense_count(user["id"]) == 0

    def test_missing_category_field_entirely_does_not_insert(self, client):
        user = _register(client)

        response = client.post(
            "/expenses/add",
            data={
                "amount": "20.00",
                "date": TODAY_ISO,
                "description": "No category field at all",
            },
        )

        assert response.status_code in (200, 400), (
            "Missing category field must not redirect as if successful"
        )
        assert _expense_count(user["id"]) == 0

    def test_other_users_expenses_are_unaffected_by_this_users_submission(self, client):
        first_user = _register(client, name="First User", email="first@example.com")
        client.get("/logout")
        second_user = _register(client, name="Second User", email="second@example.com")

        client.post(
            "/expenses/add",
            data={
                "amount": "30.00",
                "category": VALID_CATEGORY,
                "date": TODAY_ISO,
                "description": "Second user's expense",
            },
        )

        assert _expense_count(second_user["id"]) == 1
        assert _expense_count(first_user["id"]) == 0, (
            "Adding an expense must only affect the logged-in user's own records"
        )
