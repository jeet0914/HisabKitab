"""Pure DB query helpers for the /profile route (Step 5: Backend Connection).

No Flask imports here. Each function opens its own connection via get_db()
and closes it before returning. Formatting (currency symbols, display date
strings) happens in app.py, not here — these functions return raw values.
"""

from datetime import datetime

from database.db import get_db


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


def get_summary_stats(user_id):
    """Return {'total_spent', 'transaction_count', 'top_category'}."""
    conn = get_db()
    totals = conn.execute(
        """
        SELECT COUNT(*) AS transaction_count,
               COALESCE(SUM(amount), 0) AS total_spent
        FROM expenses
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()

    if totals["transaction_count"] == 0:
        conn.close()
        return {"total_spent": 0, "transaction_count": 0, "top_category": "—"}

    top = conn.execute(
        """
        SELECT category, SUM(amount) AS cat_total
        FROM expenses
        WHERE user_id = ?
        GROUP BY category
        ORDER BY cat_total DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    conn.close()

    return {
        "total_spent": totals["total_spent"],
        "transaction_count": totals["transaction_count"],
        "top_category": top["category"],
    }


def get_recent_transactions(user_id, limit=10):
    """Return list of dicts (date, description, category, amount), newest first."""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT date, description, category, amount
        FROM expenses
        WHERE user_id = ?
        ORDER BY date DESC, id DESC
        LIMIT ?
        """,
        (user_id, limit),
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


def get_category_breakdown(user_id):
    """Return list of dicts (name, amount, pct); pct ints sum to 100."""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT category, SUM(amount) AS amount
        FROM expenses
        WHERE user_id = ?
        GROUP BY category
        ORDER BY amount DESC
        """,
        (user_id,),
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
