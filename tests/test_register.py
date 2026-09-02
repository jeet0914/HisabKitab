import pytest
from werkzeug.security import check_password_hash

from app import app as flask_app
from database import db as db_module


@pytest.fixture()
def app(tmp_path, monkeypatch):
    """Point db.DB_PATH at a throwaway file and give it fresh tables."""
    test_db_path = tmp_path / "test_expense_tracker.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(test_db_path))
    flask_app.config["TESTING"] = True
    db_module.init_db()
    yield flask_app


def test_register_get_renders_empty_form_no_error(client):
    response = client.get("/register")
    assert response.status_code == 200
    assert b"auth-error" not in response.data


def test_register_post_creates_user_with_hashed_password(client):
    client.post(
        "/register",
        data={"name": "Nitish Kumar", "email": "nitish@example.com", "password": "password123"},
    )
    user = db_module.get_user_by_email("nitish@example.com")
    assert user is not None
    assert user["password_hash"] != "password123"
    assert check_password_hash(user["password_hash"], "password123")


def test_register_post_redirects_to_profile(client):
    response = client.post(
        "/register",
        data={"name": "Nitish Kumar", "email": "nitish@example.com", "password": "password123"},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")


def test_register_post_sets_session(client):
    client.post(
        "/register",
        data={"name": "Nitish Kumar", "email": "nitish@example.com", "password": "password123"},
    )
    with client.session_transaction() as sess:
        assert "user_id" in sess


def test_register_duplicate_email_shows_error_no_dupe_row(client):
    data = {"name": "Nitish Kumar", "email": "nitish@example.com", "password": "password123"}
    client.post("/register", data=data)
    response = client.post("/register", data={**data, "name": "Someone Else"})

    assert response.status_code == 200
    assert b"already exists" in response.data

    conn = db_module.get_db()
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM users WHERE email = ?", ("nitish@example.com",)
    ).fetchone()["c"]
    conn.close()
    assert count == 1


def test_register_duplicate_email_case_insensitive(client):
    client.post(
        "/register",
        data={"name": "Nitish Kumar", "email": "nitish@example.com", "password": "password123"},
    )
    response = client.post(
        "/register",
        data={"name": "Someone Else", "email": "Nitish@Example.com", "password": "password123"},
    )

    assert response.status_code == 200
    assert b"already exists" in response.data

    conn = db_module.get_db()
    count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    conn.close()
    assert count == 1


def test_register_missing_name_shows_error_no_db_hit(client):
    response = client.post(
        "/register",
        data={"name": "", "email": "nitish@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    assert b"All fields are required." in response.data
    assert db_module.get_user_by_email("nitish@example.com") is None


def test_register_missing_email_shows_error_no_db_hit(client):
    response = client.post(
        "/register",
        data={"name": "Nitish Kumar", "email": "", "password": "password123"},
    )
    assert response.status_code == 200
    assert b"All fields are required." in response.data


def test_register_missing_password_shows_error_no_db_hit(client):
    response = client.post(
        "/register",
        data={"name": "Nitish Kumar", "email": "nitish@example.com", "password": ""},
    )
    assert response.status_code == 200
    assert b"All fields are required." in response.data
    assert db_module.get_user_by_email("nitish@example.com") is None


def test_register_short_password_shows_error(client):
    response = client.post(
        "/register",
        data={"name": "Nitish Kumar", "email": "nitish@example.com", "password": "short"},
    )
    assert response.status_code == 200
    assert b"at least 8 characters" in response.data
    assert db_module.get_user_by_email("nitish@example.com") is None
