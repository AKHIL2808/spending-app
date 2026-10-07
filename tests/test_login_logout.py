import pytest

DEMO = {"email": "demo@spendly.com", "password": "demo123"}


def login(client, **overrides):
    return client.post("/login", data={**DEMO, **overrides})


def session_user_id(client):
    with client.session_transaction() as sess:
        return sess.get("user_id")


def test_get_login_renders_form_with_login_action(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b'action="/login"' in resp.data


def test_login_success_redirects_and_sets_session(client):
    resp = login(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")
    assert session_user_id(client) is not None


def test_login_email_ignores_case_and_whitespace(client):
    resp = login(client, email="  Demo@Spendly.com ")
    assert resp.status_code == 302
    assert session_user_id(client) is not None


def test_wrong_password_returns_generic_error(client):
    resp = login(client, password="wrong-password")
    assert resp.status_code == 400
    assert b"Invalid email or password." in resp.data
    assert session_user_id(client) is None


def test_unknown_email_matches_wrong_password_response(client):
    wrong_pw = login(client, password="wrong-password")
    unknown = login(client, email="nobody@example.com")
    assert unknown.status_code == 400
    assert b"Invalid email or password." in unknown.data
    assert session_user_id(client) is None
    assert b"nobody@example.com" not in wrong_pw.data


@pytest.mark.parametrize("field", ["email", "password"])
def test_empty_field_requires_both(client, field):
    resp = login(client, **{field: ""})
    assert resp.status_code == 400
    assert b"Email and password are required." in resp.data
    assert session_user_id(client) is None


def test_failed_login_keeps_email_not_password(client):
    resp = login(client, email="Demo@Spendly.com", password="secret-wrong-pw")
    assert b'value="demo@spendly.com"' in resp.data
    assert b"secret-wrong-pw" not in resp.data


def test_registered_user_can_log_in(client):
    reg = client.post("/register", data={
        "name": "New User",
        "email": "new@example.com",
        "password": "password123",
        "confirm_password": "password123",
    })
    assert reg.status_code == 302
    resp = login(client, email="new@example.com", password="password123")
    assert resp.status_code == 302
    assert session_user_id(client) is not None


def test_logout_clears_session_and_redirects_to_landing(client):
    login(client)
    resp = client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")
    assert session_user_id(client) is None


def test_logout_when_logged_out_redirects(client):
    resp = client.get("/logout")
    assert resp.status_code == 302


def test_navbar_logged_out(client):
    html = client.get("/").get_data(as_text=True)
    assert "Sign in" in html
    assert "Get started" in html
    assert "Sign out" not in html


def test_navbar_logged_in(client):
    login(client)
    html = client.get("/profile").get_data(as_text=True)
    assert "Profile" in html
    assert "Sign out" in html
    assert "Get started" not in html


def test_landing_redirects_to_profile_when_logged_in(client):
    login(client)
    resp = client.get("/")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")


def test_landing_renders_when_logged_out(client):
    assert client.get("/").status_code == 200


def test_login_page_redirects_when_logged_in(client):
    login(client)
    resp = client.get("/login")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")


def test_login_clears_previous_session_data(client):
    with client.session_transaction() as sess:
        sess["junk"] = "x"
    login(client)
    with client.session_transaction() as sess:
        assert "junk" not in sess
        assert "user_id" in sess
