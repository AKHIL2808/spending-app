import pytest
from werkzeug.security import check_password_hash

import app as app_module
import database.db as db

VALID = {
    "name": "Asha Rao",
    "email": "asha@example.com",
    "password": "secret123",
    "confirm_password": "secret123",
}


def user_count():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()


def count_for_email(email):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM users WHERE email = ?", (email,)
        ).fetchone()[0]
    finally:
        conn.close()


def test_get_register_renders_form(client):
    response = client.get("/register")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'action="/register"' in body
    for field in ("name", "email", "password", "confirm_password"):
        assert f'name="{field}"' in body


def test_register_success_redirects(client):
    response = client.post(
        "/register",
        data={**VALID, "name": "  Asha Rao  ", "email": "  Asha@Example.com "},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    user = db.get_user_by_email("asha@example.com")
    assert user is not None
    assert user["name"] == "Asha Rao"


def test_password_is_hashed(client):
    client.post("/register", data=VALID)
    user = db.get_user_by_email(VALID["email"])
    assert user["password_hash"] != VALID["password"]
    assert check_password_hash(user["password_hash"], VALID["password"])


def test_duplicate_email_case_insensitive(client):
    client.post("/register", data=VALID)
    response = client.post(
        "/register", data={**VALID, "email": VALID["email"].upper()}
    )
    assert response.status_code == 400
    assert "already exists" in response.get_data(as_text=True)
    assert count_for_email(VALID["email"]) == 1


def test_duplicate_of_demo_email(client):
    before = user_count()
    response = client.post(
        "/register", data={**VALID, "email": "demo@spendly.com"}
    )
    assert response.status_code == 400
    assert "already exists" in response.get_data(as_text=True)
    assert user_count() == before


def test_short_password_rejected(client):
    before = user_count()
    response = client.post(
        "/register",
        data={**VALID, "password": "1234567", "confirm_password": "1234567"},
    )
    assert response.status_code == 400
    assert "at least 8 characters" in response.get_data(as_text=True)
    assert user_count() == before


def test_eight_character_password_accepted(client):
    response = client.post(
        "/register",
        data={**VALID, "password": "12345678", "confirm_password": "12345678"},
    )
    assert response.status_code == 302


@pytest.mark.parametrize("confirm", ["different123", "", "Secret123"])
def test_password_mismatch_rejected(client, confirm):
    before = user_count()
    response = client.post(
        "/register", data={**VALID, "confirm_password": confirm}
    )
    body = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "Passwords do not match." in body
    assert user_count() == before
    assert count_for_email(VALID["email"]) == 0
    assert 'value="Asha Rao"' in body
    assert 'value="asha@example.com"' in body
    assert VALID["password"] not in body
    assert confirm not in body or confirm == ""


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"name": "   "},
        {"email": ""},
        {"email": "noatsign"},
        {"email": "@x.com"},
        {"email": "a@"},
    ],
)
def test_invalid_fields_rejected(client, overrides):
    before = user_count()
    response = client.post("/register", data={**VALID, **overrides})
    assert response.status_code == 400
    assert 'class="auth-error"' in response.get_data(as_text=True)
    assert user_count() == before


def test_failed_submit_repopulates_fields(client):
    response = client.post(
        "/register",
        data={
            "name": "Asha Rao",
            "email": "asha@example.com",
            "password": "short",
            "confirm_password": "short",
        },
    )
    body = response.get_data(as_text=True)
    assert response.status_code == 400
    assert 'value="Asha Rao"' in body
    assert 'value="asha@example.com"' in body
    assert "short" not in body.replace("Password must be at least 8 characters.", "")


def test_demo_user_unaffected(client):
    client.post(
        "/register",
        data={**VALID, "password": "short", "confirm_password": "short"},
    )
    client.post("/register", data=VALID)
    assert db.get_user_by_email("demo@spendly.com") is not None
    assert count_for_email("demo@spendly.com") == 1


def test_integrity_error_race_returns_400(client, monkeypatch):
    monkeypatch.setattr(app_module, "get_user_by_email", lambda email: None)
    response = client.post(
        "/register", data={**VALID, "email": "demo@spendly.com"}
    )
    assert response.status_code == 400
    assert "already exists" in response.get_data(as_text=True)
