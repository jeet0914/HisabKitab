import pytest

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


def _register(client, email="nitish@example.com", password="password123"):
    client.post(
        "/register",
        data={"name": "Nitish Kumar", "email": email, "password": password},
    )


def test_login_get_renders_empty_form_no_error(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"auth-error" not in response.data


def test_login_post_correct_credentials_redirects_to_profile(client):
    _register(client)
    response = client.post(
        "/login", data={"email": "nitish@example.com", "password": "password123"}
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")


def test_login_post_correct_credentials_sets_session(client):
    _register(client)
    client.post(
        "/login", data={"email": "nitish@example.com", "password": "password123"}
    )
    with client.session_transaction() as sess:
        assert "user_id" in sess


def test_login_post_wrong_password_shows_generic_error_no_session(client):
    db_module.create_user("Nitish Kumar", "nitish@example.com", "password123")
    response = client.post(
        "/login", data={"email": "nitish@example.com", "password": "wrongpass"}
    )
    assert response.status_code == 200
    assert b"Invalid email or password." in response.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_login_post_nonexistent_email_shows_same_generic_error(client):
    response = client.post(
        "/login", data={"email": "nobody@example.com", "password": "password123"}
    )
    assert response.status_code == 200
    assert b"Invalid email or password." in response.data


def test_login_post_missing_email_shows_error_no_db_hit(client):
    response = client.post("/login", data={"email": "", "password": "password123"})
    assert response.status_code == 200
    assert b"All fields are required." in response.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_login_post_missing_password_shows_error_no_db_hit(client):
    db_module.create_user("Nitish Kumar", "nitish@example.com", "password123")
    response = client.post("/login", data={"email": "nitish@example.com", "password": ""})
    assert response.status_code == 200
    assert b"All fields are required." in response.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_logout_clears_session_and_redirects_to_landing(client):
    _register(client)
    client.post(
        "/login", data={"email": "nitish@example.com", "password": "password123"}
    )
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    with client.session_transaction() as sess:
        assert "user_id" not in sess
