"""Tests for the date-range filter on GET /profile.

Spec: .claude/specs/06-date-filter-profile-page.md

Behaviour under test (per spec, not implementation):
- `range` query-string values `this_month`, `last_month`, `last_3_months`,
  `all_time` scope the stats, recent-transactions table, and category
  breakdown to that window.
- A missing or invalid `range` silently falls back to `all_time` (no error).
- `/profile` (with or without `range`) still requires authentication.
- A range with zero matching expenses renders the existing zero/empty state
  (₹0.00, 0 transactions, "—" top category, empty breakdown) with no errors.
- The active filter pill in the UI reflects whichever range is in effect.
- `get_recent_transactions` remains capped at 10 rows, newest-first, even
  when scoped to a range.
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


def _register(client, name="Filter Tester", email="filtertester@example.com", password="password123"):
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


def _first_of_month(d, months_delta=0):
    """First-of-month date `months_delta` calendar months from `d` (may be negative)."""
    total = d.year * 12 + (d.month - 1) + months_delta
    year, month = divmod(total, 12)
    return date(year, month + 1, 1)


def _active_filter_pill(html, label):
    """True if the filter-pill anchor whose visible text is `label` carries
    the 'filter-pill-active' class. Tolerant of whitespace/newlines between
    the href and class attributes in the template markup.
    """
    match = re.search(
        r'<a[^>]*class="filter-pill([^"]*)"[^>]*>' + re.escape(label) + r"</a>",
        html,
    )
    assert match is not None, f"Could not find a filter pill for label {label!r}"
    return "filter-pill-active" in match.group(1)


TODAY = date.today()
THIS_MONTH_START = _first_of_month(TODAY, 0)
LAST_MONTH_START = _first_of_month(TODAY, -1)
TWO_MONTHS_AGO_START = _first_of_month(TODAY, -2)
FOUR_MONTHS_AGO_START = _first_of_month(TODAY, -4)
FAR_PAST_DATE = "2001-05-10"


@pytest.fixture()
def spread_user(client):
    """A logged-in user with one expense in each of five distinct windows:
    this month, last month, two months ago (inside 'last 3 months'), four
    months ago (outside 'last 3 months'), and a far-past date (only visible
    under 'all_time').
    """
    user = _register(client)
    user_id = user["id"]

    _insert_expense(user_id, 100.00, "Food", THIS_MONTH_START.isoformat(), "This month expense")
    _insert_expense(user_id, 50.00, "Transport", LAST_MONTH_START.isoformat(), "Last month expense")
    _insert_expense(user_id, 25.00, "Bills", TWO_MONTHS_AGO_START.isoformat(), "Two months ago expense")
    _insert_expense(user_id, 15.00, "Health", FOUR_MONTHS_AGO_START.isoformat(), "Four months ago expense")
    _insert_expense(user_id, 5.00, "Other", FAR_PAST_DATE, "Ancient expense")

    return user_id


@pytest.fixture()
def new_user(client):
    """A logged-in user with zero expenses."""
    user = _register(client, name="Blank Slate", email="blankslate@example.com")
    return user["id"]


@pytest.fixture()
def old_only_user(client):
    """A logged-in user whose only expense sits far outside any recent window."""
    user = _register(client, name="Old Timer", email="oldtimer@example.com")
    _insert_expense(user["id"], 42.00, "Food", FAR_PAST_DATE, "Old expense")
    return user["id"]


# --------------------------------------------------------------------- #
# Auth guard                                                             #
# --------------------------------------------------------------------- #

class TestAuthGuard:

    @pytest.mark.parametrize(
        "range_value",
        ["this_month", "last_month", "last_3_months", "all_time", "garbage", None],
    )
    def test_profile_unauthenticated_redirects_to_login_regardless_of_range(self, client, range_value):
        if range_value is None:
            response = client.get("/profile")
        else:
            response = client.get("/profile", query_string={"range": range_value})

        assert response.status_code == 302, "Unauthenticated /profile must redirect, not render"
        assert response.headers["Location"].endswith("/login"), (
            "Unauthenticated /profile must redirect to /login"
        )


# --------------------------------------------------------------------- #
# Happy paths — one per accepted range value                             #
# --------------------------------------------------------------------- #

class TestRangeHappyPaths:

    def test_this_month_scopes_stats_transactions_and_breakdown(self, client, spread_user):
        response = client.get("/profile", query_string={"range": "this_month"})
        assert response.status_code == 200
        data = response.data

        assert b"This month expense" in data
        assert b"Last month expense" not in data
        assert b"Two months ago expense" not in data
        assert b"Four months ago expense" not in data
        assert b"Ancient expense" not in data

        assert "₹100.00".encode("utf-8") in data, "Expected total spent of ₹100.00 for this_month"
        assert b'<div class="stat-value">1</div>' in data, "Expected transaction_count of 1"
        assert b'<div class="stat-value">Food</div>' in data, "Expected top_category of Food"
        assert b'<div class="progress-label">Food</div>' in data

        html = data.decode("utf-8")
        assert _active_filter_pill(html, "This Month") is True
        assert _active_filter_pill(html, "Last Month") is False
        assert _active_filter_pill(html, "Last 3 Months") is False
        assert _active_filter_pill(html, "All Time") is False

    def test_last_month_scopes_stats_transactions_and_breakdown(self, client, spread_user):
        response = client.get("/profile", query_string={"range": "last_month"})
        assert response.status_code == 200
        data = response.data

        assert b"Last month expense" in data
        assert b"This month expense" not in data
        assert b"Two months ago expense" not in data
        assert b"Four months ago expense" not in data
        assert b"Ancient expense" not in data

        assert "₹50.00".encode("utf-8") in data, "Expected total spent of ₹50.00 for last_month"
        assert b'<div class="stat-value">1</div>' in data
        assert b'<div class="stat-value">Transport</div>' in data
        assert b'<div class="progress-label">Transport</div>' in data

        html = data.decode("utf-8")
        assert _active_filter_pill(html, "Last Month") is True
        assert _active_filter_pill(html, "This Month") is False
        assert _active_filter_pill(html, "Last 3 Months") is False
        assert _active_filter_pill(html, "All Time") is False

    def test_last_3_months_scopes_stats_transactions_and_breakdown(self, client, spread_user):
        response = client.get("/profile", query_string={"range": "last_3_months"})
        assert response.status_code == 200
        data = response.data

        assert b"This month expense" in data
        assert b"Last month expense" in data
        assert b"Two months ago expense" in data
        assert b"Four months ago expense" not in data, "4-months-ago expense is outside the last-3-months window"
        assert b"Ancient expense" not in data

        assert "₹175.00".encode("utf-8") in data, "175.00 == 100 + 50 + 25 for the 3 in-window expenses"
        assert b'<div class="stat-value">3</div>' in data
        assert b'<div class="stat-value">Food</div>' in data, "Food (100) is the largest category in-window"

        html = data.decode("utf-8")
        assert _active_filter_pill(html, "Last 3 Months") is True
        assert _active_filter_pill(html, "This Month") is False
        assert _active_filter_pill(html, "Last Month") is False
        assert _active_filter_pill(html, "All Time") is False

    def test_all_time_includes_every_expense(self, client, spread_user):
        response = client.get("/profile", query_string={"range": "all_time"})
        assert response.status_code == 200
        data = response.data

        for description in [
            "This month expense",
            "Last month expense",
            "Two months ago expense",
            "Four months ago expense",
            "Ancient expense",
        ]:
            assert description.encode("utf-8") in data, f"all_time must include {description!r}"

        assert "₹195.00".encode("utf-8") in data, "195.00 == 100 + 50 + 25 + 15 + 5"
        assert b'<div class="stat-value">5</div>' in data

        html = data.decode("utf-8")
        assert _active_filter_pill(html, "All Time") is True
        assert _active_filter_pill(html, "This Month") is False
        assert _active_filter_pill(html, "Last Month") is False
        assert _active_filter_pill(html, "Last 3 Months") is False

    def test_last_3_months_transactions_are_newest_first(self, client, spread_user):
        response = client.get("/profile", query_string={"range": "last_3_months"})
        html = response.data.decode("utf-8")

        idx_this_month = html.index("This month expense")
        idx_last_month = html.index("Last month expense")
        idx_two_months_ago = html.index("Two months ago expense")

        assert idx_this_month < idx_last_month < idx_two_months_ago, (
            "Filtered transactions must stay ordered newest-first"
        )

    def test_recent_transactions_still_capped_at_ten_within_a_range(self, client):
        user = _register(client, name="Busy Spender", email="busy@example.com")
        user_id = user["id"]
        for i in range(12):
            _insert_expense(user_id, 10.00 + i, "Food", THIS_MONTH_START.isoformat(), f"Txn {i}")

        response = client.get("/profile", query_string={"range": "this_month"})
        assert response.status_code == 200

        row_count = response.data.count(b'<td class="profile-table-amount">')
        assert row_count == 10, f"Expected at most 10 transaction rows, found {row_count}"


# --------------------------------------------------------------------- #
# Invalid / missing range fallback                                       #
# --------------------------------------------------------------------- #

class TestRangeFallback:

    def test_missing_range_query_string_matches_explicit_all_time(self, client, spread_user):
        default_response = client.get("/profile")
        explicit_response = client.get("/profile", query_string={"range": "all_time"})

        assert default_response.status_code == 200
        assert default_response.data == explicit_response.data, (
            "No query string must render identically to range=all_time"
        )

    @pytest.mark.parametrize(
        "bad_range",
        [
            "garbage",
            "",
            "THIS_MONTH",
            "this month",
            "1",
            "none",
            "all-time",
            "'; DROP TABLE expenses;--",
        ],
    )
    def test_invalid_range_falls_back_to_all_time_without_error(self, client, spread_user, bad_range):
        response = client.get("/profile", query_string={"range": bad_range})
        baseline = client.get("/profile", query_string={"range": "all_time"})

        assert response.status_code == 200, f"range={bad_range!r} must not error"
        assert response.data == baseline.data, (
            f"range={bad_range!r} must render identically to all_time"
        )

        html = response.data.decode("utf-8")
        assert _active_filter_pill(html, "All Time") is True, (
            "Fallback must mark 'All Time' as the active filter pill"
        )

    def test_sql_injection_attempt_in_range_does_not_break_subsequent_queries(self, client, spread_user):
        injection_response = client.get(
            "/profile", query_string={"range": "'; DROP TABLE expenses;--"}
        )
        assert injection_response.status_code == 200

        # If the injection had succeeded, the expenses table would be gone
        # and this follow-up request would 500 or return empty/zeroed data.
        followup = client.get("/profile", query_string={"range": "this_month"})
        assert followup.status_code == 200
        assert "₹100.00".encode("utf-8") in followup.data
        assert b"This month expense" in followup.data


# --------------------------------------------------------------------- #
# Empty-range-result behaviour                                           #
# --------------------------------------------------------------------- #

class TestEmptyRangeResult:

    @pytest.mark.parametrize("range_value", ["this_month", "last_month", "last_3_months"])
    def test_range_with_no_matching_expenses_shows_zeroed_state(self, client, old_only_user, range_value):
        response = client.get("/profile", query_string={"range": range_value})
        assert response.status_code == 200
        data = response.data

        assert "₹0.00".encode("utf-8") in data, f"Expected ₹0.00 total for empty {range_value}"
        assert b'<div class="stat-value">0</div>' in data, f"Expected 0 transactions for empty {range_value}"
        assert "—".encode("utf-8") in data, "Expected em-dash placeholder for top category"
        assert b"Old expense" not in data, "Out-of-range expense must not appear in the transaction table"

    @pytest.mark.parametrize(
        "range_value", ["this_month", "last_month", "last_3_months", "all_time"]
    )
    def test_brand_new_user_shows_zeroed_state_for_every_range(self, client, new_user, range_value):
        response = client.get("/profile", query_string={"range": range_value})
        assert response.status_code == 200
        data = response.data

        assert "₹0.00".encode("utf-8") in data
        assert b'<div class="stat-value">0</div>' in data
        assert "—".encode("utf-8") in data


# --------------------------------------------------------------------- #
# Default behaviour is unaffected by this feature                        #
# --------------------------------------------------------------------- #

class TestDefaultBehaviourUnaffected:

    def test_no_query_string_shows_all_time_data_same_as_before(self, client, spread_user):
        response = client.get("/profile")
        assert response.status_code == 200
        data = response.data

        for description in [
            "This month expense",
            "Last month expense",
            "Two months ago expense",
            "Four months ago expense",
            "Ancient expense",
        ]:
            assert description.encode("utf-8") in data

        assert "₹195.00".encode("utf-8") in data
        assert b'<div class="stat-value">5</div>' in data

        html = data.decode("utf-8")
        assert _active_filter_pill(html, "All Time") is True

    def test_no_query_string_still_shows_user_identity_and_seeded_style_data(self, client, spread_user):
        response = client.get("/profile")
        assert response.status_code == 200
        assert b"Filter Tester" in response.data
        assert b"filtertester@example.com" in response.data
