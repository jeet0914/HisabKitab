import os

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import create_user, get_db, get_user_by_email, init_db, seed_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")


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

    user = {
        "name": "Jane Doe",
        "email": "jane.doe@example.com",
        "initials": "JD",
        "member_since": "March 2025",
    }

    stats = [
        {"label": "Total Spent", "value": "$1,284.50", "icon": "credit-card"},
        {"label": "Transactions", "value": "27", "icon": "list"},
        {"label": "Top Category", "value": "Food", "icon": "tag"},
    ]

    transactions = [
        {"date": "Aug 28, 2026", "description": "Whole Foods grocery run", "category": "Food", "amount": "$64.20"},
        {"date": "Aug 26, 2026", "description": "Metro monthly pass", "category": "Transport", "amount": "$95.00"},
        {"date": "Aug 24, 2026", "description": "Electric bill", "category": "Bills", "amount": "$110.75"},
        {"date": "Aug 21, 2026", "description": "Movie night", "category": "Entertainment", "amount": "$32.00"},
        {"date": "Aug 19, 2026", "description": "Pharmacy pickup", "category": "Health", "amount": "$18.40"},
    ]

    category_breakdown = [
        {"category": "Food", "amount": "$412.30", "percent": 32},
        {"category": "Bills", "amount": "$310.75", "percent": 24},
        {"category": "Transport", "amount": "$255.00", "percent": 20},
        {"category": "Entertainment", "amount": "$180.00", "percent": 14},
        {"category": "Health", "amount": "$126.45", "percent": 10},
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
