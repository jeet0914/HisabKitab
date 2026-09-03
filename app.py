import os
from datetime import datetime

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import create_user, get_db, get_user_by_email, init_db, seed_db
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")


# ------------------------------------------------------------------ #
# Formatting helpers (shared — do not edit inside subagent tasks)     #
# ------------------------------------------------------------------ #

def _format_currency(amount):
    """Render a numeric amount as an Indian-Rupee string, e.g. ₹1,234.56."""
    return f"₹{amount:,.2f}"


def _format_date(date_str):
    """Convert a stored 'YYYY-MM-DD' date into display form, e.g. 'Aug 28, 2026'."""
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%b %d, %Y")


def _compute_initials(name):
    """Derive up to 2 uppercase initials from a display name, e.g. 'Demo User' -> 'DU'."""
    parts = [p for p in name.split() if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            return render_template("register.html", error="All fields are required.")

        if len(password) < 8:
            return render_template(
                "register.html", error="Password must be at least 8 characters."
            )

        if get_user_by_email(email):
            return render_template(
                "register.html", error="An account with that email already exists."
            )

        user_id = create_user(name, email, password)
        session["user_id"] = user_id
        return redirect(url_for("profile"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            return render_template("login.html", error="All fields are required.")

        user = get_user_by_email(email)

        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template(
                "login.html", error="Invalid email or password."
            )

        session["user_id"] = user["id"]
        return redirect(url_for("profile"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]

    user_row = get_user_by_id(user_id)
    user = {
        "name": user_row["name"],
        "email": user_row["email"],
        "initials": _compute_initials(user_row["name"]),
        "member_since": user_row["member_since"],
    }

    summary = get_summary_stats(user_id)
    stats = [
        {"label": "Total Spent", "value": _format_currency(summary["total_spent"]), "icon": "credit-card"},
        {"label": "Transactions", "value": str(summary["transaction_count"]), "icon": "list"},
        {"label": "Top Category", "value": summary["top_category"], "icon": "tag"},
    ]

    raw_transactions = get_recent_transactions(user_id, limit=10)
    transactions = [
        {
            "date": _format_date(t["date"]),
            "description": t["description"],
            "category": t["category"],
            "amount": _format_currency(t["amount"]),
        }
        for t in raw_transactions
    ]

    raw_breakdown = get_category_breakdown(user_id)
    category_breakdown = [
        {
            "category": c["name"],
            "amount": _format_currency(c["amount"]),
            "percent": c["pct"],
        }
        for c in raw_breakdown
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        category_breakdown=category_breakdown,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


with app.app_context():
    init_db()
    seed_db()


if __name__ == "__main__":
    app.run(debug=True, port=5001)
