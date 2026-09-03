"""Pure DB query helpers for the /profile route (Step 5: Backend Connection).

No Flask imports here. Each function opens its own connection via get_db()
and closes it before returning. Formatting (currency symbols, display date
strings) happens in app.py, not here — these functions return raw values.
"""

from datetime import date, datetime, timedelta

from database.db import get_db

VALID_RANGES = {"this_month", "last_month", "last_3_months", "all_time"}


def _get_date_bounds(range_key):
    """Return (start, end) as 'YYYY-MM-DD' strings for range_key; end is exclusive."""
    today = date.today()

    if range_key == "this_month":
        start = today.replace(day=1)
        end = (date(today.year + 1, 1, 1) if today.month == 12
               else date(today.year, today.month + 1, 1))
        return start.isoformat(), end.isoformat()

    if range_key == "last_month":
        end = today.replace(day=1)
        start = (date(today.year - 1, 12, 1) if today.month == 1
                  else date(today.year, today.month - 1, 1))
        return start.isoformat(), end.isoformat()

    if range_key == "last_3_months":
        month_index = today.month - 1 - 2
        year = today.year + month_index // 12
        month = month_index % 12 + 1
        start = date(year, month, 1)
        end = today + timedelta(days=1)
        return start.isoformat(), end.isoformat()

    return "0000-01-01", "9999-12-31"  # all_time / unknown key


def get_user_by_id(user_id):
    """Return {'name', 'email', 'member_since'} for user_id, or None."""
    conn = get_db()
    row = conn.execute(
        "SELECT name, email, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    member_since = datetime.strptime(
        row["created_at"], "%Y-%m-%d %H:%M:%S"
    ).strftime("%B %Y")
    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": member_since,
    }


def get_summary_stats(user_id, range_key="all_time"):
    """Return {'total_spent', 'transaction_count', 'top_category'}."""
    conn = get_db()
    start, end = _get_date_bounds(range_key)
    totals = conn.execute(
        """
        SELECT COUNT(*) AS transaction_count,
               COALESCE(SUM(amount), 0) AS total_spent
        FROM expenses
        WHERE user_id = ? AND date >= ? AND date < ?
        """,
        (user_id, start, end),
    ).fetchone()

    if totals["transaction_count"] == 0:
        conn.close()
        return {"total_spent": 0, "transaction_count": 0, "top_category": "—"}

    top = conn.execute(
        """
        SELECT category, SUM(amount) AS cat_total
        FROM expenses
        WHERE user_id = ? AND date >= ? AND date < ?
        GROUP BY category
        ORDER BY cat_total DESC
        LIMIT 1
        """,
        (user_id, start, end),
    ).fetchone()
    conn.close()

    return {
        "total_spent": totals["total_spent"],
        "transaction_count": totals["transaction_count"],
        "top_category": top["category"],
    }


def get_recent_transactions(user_id, range_key="all_time", limit=10):
    """Return list of dicts (date, description, category, amount), newest first."""
    conn = get_db()
    start, end = _get_date_bounds(range_key)
    rows = conn.execute(
        """
        SELECT date, description, category, amount
        FROM expenses
        WHERE user_id = ? AND date >= ? AND date < ?
        ORDER BY date DESC, id DESC
        LIMIT ?
        """,
        (user_id, start, end, limit),
    ).fetchall()
    conn.close()
    return [
        {
            "date": row["date"],
            "description": row["description"],
            "category": row["category"],
            "amount": row["amount"],
        }
        for row in rows
    ]


def get_category_breakdown(user_id, range_key="all_time"):
    """Return list of dicts (name, amount, pct); pct ints sum to 100."""
    conn = get_db()
    start, end = _get_date_bounds(range_key)
    rows = conn.execute(
        """
        SELECT category, SUM(amount) AS amount
        FROM expenses
        WHERE user_id = ? AND date >= ? AND date < ?
        GROUP BY category
        ORDER BY amount DESC
        """,
        (user_id, start, end),
    ).fetchall()
    conn.close()

    if not rows:
        return []

    total = sum(row["amount"] for row in rows)
    breakdown = [
        {"name": row["category"], "amount": row["amount"], "pct": 0}
        for row in rows
    ]

    raw_pcts = [(item["amount"] / total) * 100 for item in breakdown]
    rounded_pcts = [round(p) for p in raw_pcts]
    remainder = 100 - sum(rounded_pcts)

    # `breakdown` is ordered by amount DESC (SQL ORDER BY), so index 0 is
    # always the largest category — it absorbs the rounding remainder,
    # whether positive or negative, so percentages always sum to exactly 100.
    rounded_pcts[0] += remainder

    for item, pct in zip(breakdown, rounded_pcts):
        item["pct"] = pct

    return breakdown
