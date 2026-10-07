import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEMO = {"email": "demo@spendly.com", "password": "demo123"}


def login(client):
    return client.post("/login", data=DEMO)


def test_profile_requires_login(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_profile_renders_when_logged_in(client):
    login(client)
    response = client.get("/profile")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Demo User" in body
    assert "demo@spendly.com" in body
    for label in ("Total spent", "Transactions", "Top category"):
        assert label in body


def test_profile_has_transactions_and_breakdown(client):
    login(client)
    body = client.get("/profile").get_data(as_text=True)
    tbody = body.split("<tbody>")[1].split("</tbody>")[0]
    assert tbody.count("<tr>") >= 3
    assert body.count('class="breakdown-row"') >= 3


def test_navbar_shows_username_and_sign_out(client):
    login(client)
    body = client.get("/profile").get_data(as_text=True)
    assert 'class="nav-user">Demo User' in body
    assert "Sign out" in body


def test_profile_assets_have_no_hex_or_inline_styles():
    template = (ROOT / "templates" / "profile.html").read_text()
    css = (ROOT / "static" / "css" / "profile.css").read_text()
    hex_pattern = re.compile(r"#[0-9a-fA-F]{3,8}\b")
    assert not hex_pattern.search(template)
    assert not hex_pattern.search(css)
    assert "style=" not in template
