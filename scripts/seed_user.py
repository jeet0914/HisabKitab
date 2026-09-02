import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash

from database.db import get_db, init_db

FIRST_NAMES = [
    "Rahul", "Priya", "Amit", "Sneha", "Vikram", "Ananya", "Rohan", "Kavita",
    "Arjun", "Divya", "Suresh", "Neha", "Karthik", "Meera", "Rajesh", "Pooja",
    "Vivek", "Shreya", "Manoj", "Aditi", "Sandeep", "Ritu", "Ganesh", "Lakshmi",
    "Harish", "Nandini", "Deepak", "Swati", "Naveen", "Anjali", "Pradeep",
    "Kiran", "Ashwin", "Bhavna", "Ravi", "Sunita",
]

LAST_NAMES = [
    "Sharma", "Verma", "Iyer", "Nair", "Reddy", "Gupta", "Patel", "Menon",
    "Rao", "Chatterjee", "Mukherjee", "Desai", "Joshi", "Kulkarni", "Pillai",
    "Bose", "Chauhan", "Malhotra", "Kapoor", "Agarwal", "Bhat", "Das",
    "Krishnan", "Naidu", "Trivedi", "Shetty", "Ghosh", "Rana", "Saxena", "Yadav",
]


def generate_user():
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    name = f"{first} {last}"
    number = random.randint(10, 999)
    email = f"{first.lower()}.{last.lower()}{number}@gmail.com"
    return name, email


def main():
    init_db()
    conn = get_db()

    name, email = generate_user()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    while existing is not None:
        name, email = generate_user()
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()

    password_hash = generate_password_hash("password123")
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, password_hash),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()

    print("User created:")
    print(f"  id: {user_id}")
    print(f"  name: {name}")
    print(f"  email: {email}")


if __name__ == "__main__":
    main()
