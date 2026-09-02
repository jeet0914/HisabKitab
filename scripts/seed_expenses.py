import os
import random
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import get_db

USER_ID = 2
COUNT = 5
MONTHS = 3

CATEGORY_WEIGHTS = {
    "Food": 30,
    "Transport": 20,
    "Bills": 15,
    "Shopping": 15,
    "Other": 10,
    "Entertainment": 5,
    "Health": 5,
}

CATEGORY_RANGES = {
    "Food": (50, 800),
    "Transport": (20, 500),
    "Bills": (200, 3000),
    "Health": (100, 2000),
    "Entertainment": (100, 1500),
    "Shopping": (200, 5000),
    "Other": (50, 1000),
}

DESCRIPTIONS = {
    "Food": ["Zomato order", "Swiggy delivery", "Groceries - BigBasket", "Lunch at restaurant", "Chai and snacks", "Vegetables from local market"],
    "Transport": ["Ola cab", "Uber ride", "Auto fare", "Petrol refill", "Metro card recharge", "Bus pass"],
    "Bills": ["Electricity bill", "Mobile recharge", "Internet bill", "Water bill", "Gas cylinder", "DTH recharge"],
    "Health": ["Pharmacy - Apollo", "Doctor consultation", "Gym membership", "Health checkup", "Medicines"],
    "Entertainment": ["Movie tickets - PVR", "Netflix subscription", "Concert tickets", "Amusement park", "Spotify premium"],
    "Shopping": ["Amazon order", "Myntra purchase", "New clothes", "Footwear", "Electronics - Flipkart", "Home decor"],
    "Other": ["Miscellaneous", "Gift for friend", "Donation", "Stationery", "Courier charges"],
}


def weighted_category():
    categories = list(CATEGORY_WEIGHTS.keys())
    weights = list(CATEGORY_WEIGHTS.values())
    return random.choices(categories, weights=weights, k=1)[0]


def random_date_within_months(months):
    today = date.today()
    max_days_back = months * 30
    days_back = random.randint(0, max_days_back)
    return today - timedelta(days=days_back)


def main():
    conn = get_db()

    user = conn.execute("SELECT id FROM users WHERE id = ?", (USER_ID,)).fetchone()
    if user is None:
        print(f"No user found with id {USER_ID}.")
        conn.close()
        return

    expenses = []
    for _ in range(COUNT):
        category = weighted_category()
        low, high = CATEGORY_RANGES[category]
        amount = round(random.uniform(low, high), 2)
        description = random.choice(DESCRIPTIONS[category])
        expense_date = random_date_within_months(MONTHS)
        expenses.append((USER_ID, amount, category, expense_date.isoformat(), description))

    try:
        conn.execute("BEGIN")
        for user_id, amount, category, expense_date, description in expenses:
            conn.execute(
                """
                INSERT INTO expenses (user_id, amount, category, date, description)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, amount, category, expense_date, description),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    dates = sorted(e[3] for e in expenses)
    print(f"Inserted {len(expenses)} expenses for user_id {USER_ID}.")
    print(f"Date range: {dates[0]} to {dates[-1]}")
    print("Sample records:")
    for user_id, amount, category, expense_date, description in expenses[:5]:
        print(f"  {expense_date} | {category:<13} | Rs.{amount:>8.2f} | {description}")


if __name__ == "__main__":
    main()
