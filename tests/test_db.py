import sqlite3

import pytest

from database import db as db_module


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Point db.DB_PATH at a throwaway file for the duration of the test."""
    test_db_path = tmp_path / "test_expense_tracker.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(test_db_path))
    yield test_db_path


def test_get_db_returns_row_factory_connection(temp_db):
    conn = db_module.get_db()
    assert isinstance(conn, sqlite3.Connection)
    assert conn.row_factory is sqlite3.Row
    conn.close()


def test_get_db_enables_foreign_keys(temp_db):
    conn = db_module.get_db()
    fk_status = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk_status == 1
    conn.close()


def test_init_db_creates_tables(temp_db):
    db_module.init_db()
    conn = db_module.get_db()
    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()
    assert {"users", "expenses"}.issubset(tables)


def test_init_db_is_safe_to_call_twice(temp_db):
    db_module.init_db()
    db_module.init_db()  # must not raise


def test_seed_db_creates_demo_user_and_expenses(temp_db):
    db_module.init_db()
    db_module.seed_db()
    conn = db_module.get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", ("demo@spendly.com",)
    ).fetchone()
    assert user is not None
    assert user["password_hash"] != "demo123"  # must be hashed

    expenses = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ?", (user["id"],)
    ).fetchall()
    conn.close()

    assert len(expenses) == 8
    categories = {row["category"] for row in expenses}
    assert categories == set(db_module.CATEGORIES)


def test_seed_db_does_not_duplicate_on_repeat_calls(temp_db):
    db_module.init_db()
    db_module.seed_db()
    db_module.seed_db()
    conn = db_module.get_db()
    user_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    expense_count = conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
    conn.close()
    assert user_count == 1
    assert expense_count == 8


def test_unique_email_constraint(temp_db):
    db_module.init_db()
    conn = db_module.get_db()
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("A", "dup@example.com", "hash1"),
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("B", "dup@example.com", "hash2"),
        )
        conn.commit()
    conn.close()


def test_foreign_key_constraint_rejects_invalid_user(temp_db):
    db_module.init_db()
    conn = db_module.get_db()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date) "
            "VALUES (?, ?, ?, ?)",
            (9999, 10.0, "Food", "2026-09-02"),
        )
        conn.commit()
    conn.close()
