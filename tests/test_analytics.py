"""Tests for Step 7: Coming Soon Analytics page (GET /analytics)."""
import inspect
import re
from pathlib import Path

import pytest

import app as app_module

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "analytics.html"
CSS = ROOT / "static" / "css" / "analytics.css"
CLAUDE_MD = ROOT / "CLAUDE.md"

HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")


@pytest.fixture
def auth_client(client):
    resp = client.post(
        "/login", data={"email": "demo@spendly.com", "password": "demo123"}
    )
    assert resp.status_code in (302, 303), "Demo login should redirect"
    return client


class TestAnalyticsLoggedIn:
    def test_get_returns_200(self, auth_client):
        assert auth_client.get("/analytics").status_code == 200

    def test_shows_coming_soon(self, auth_client):
        body = auth_client.get("/analytics").data
        assert b"Coming soon" in body, "Expected 'Coming soon' badge/heading"

    def test_shows_analytics_heading(self, auth_client):
        body = auth_client.get("/analytics").data
        assert b"<h1" in body and b"Analytics" in body

    @pytest.mark.parametrize(
        "phrase", ["trends", "chart", "budget"]
    )
    def test_lists_planned_features(self, auth_client, phrase):
        body = auth_client.get("/analytics").data.decode().lower()
        assert phrase in body, f"Expected planned feature mentioning {phrase!r}"

    def test_has_explanation_paragraph(self, auth_client):
        body = auth_client.get("/analytics").data
        assert b"<p" in body, "Expected an explanatory paragraph"

    def test_has_planned_features_list(self, auth_client):
        body = auth_client.get("/analytics").data
        assert b"<li" in body, "Expected a list of planned features"

    def test_links_back_to_profile(self, auth_client):
        body = auth_client.get("/analytics").data.decode()
        assert 'href="/profile"' in body
        # The link must actually work.
        assert auth_client.get("/profile").status_code == 200

    def test_includes_nav_and_footer(self, auth_client):
        body = auth_client.get("/analytics").data
        assert b"<nav" in body, "Expected nav from base.html"
        assert b"<footer" in body, "Expected footer from base.html"

    def test_references_analytics_css_in_head(self, auth_client):
        body = auth_client.get("/analytics").data.decode()
        head = body.split("</head>")[0]
        assert "css/analytics.css" in head, "analytics.css must load in <head>"

    def test_analytics_css_is_served(self, auth_client):
        assert auth_client.get("/static/css/analytics.css").status_code == 200

    def test_post_returns_405(self, auth_client):
        assert auth_client.post("/analytics").status_code == 405

    def test_post_logged_out_does_not_succeed(self, client):
        assert client.post("/analytics").status_code in (302, 401, 405)


class TestAnalyticsAuthGuard:
    def test_logged_out_redirects_to_login(self, client):
        resp = client.get("/analytics")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    def test_logged_out_does_not_leak_page(self, client):
        resp = client.get("/analytics")
        assert b"Coming soon" not in resp.data

    def test_nonexistent_user_session_cleared_and_redirected(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = 999999
            sess["user_name"] = "Ghost"
        resp = client.get("/analytics")
        assert resp.status_code == 302, "Stale session must redirect, not 500"
        assert resp.headers["Location"].endswith("/login")
        with client.session_transaction() as sess:
            assert "user_id" not in sess, "Session should be cleared"

    def test_after_logout_redirects(self, auth_client):
        auth_client.get("/logout")
        resp = auth_client.get("/analytics")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")


class TestAnalyticsNavLink:
    def test_link_present_on_profile_when_logged_in(self, auth_client):
        body = auth_client.get("/profile").data.decode()
        assert 'href="/analytics"' in body
        assert "Analytics" in body

    def test_link_navigates_to_page(self, auth_client):
        assert auth_client.get("/analytics").status_code == 200

    def test_link_between_profile_and_sign_out(self, auth_client):
        body = auth_client.get("/profile").data.decode()
        nav = body.split("<nav", 1)[1].split("</nav>", 1)[0]
        p = nav.find('href="/profile"')
        a = nav.find('href="/analytics"')
        s = nav.find('href="/logout"')
        assert -1 not in (p, a, s), "Profile, Analytics, Sign out links expected"
        assert p < a < s, "Analytics must sit between Profile and Sign out"

    @pytest.mark.parametrize("path", ["/", "/login", "/register"])
    def test_link_absent_when_logged_out(self, client, path):
        body = client.get(path).data.decode()
        assert 'href="/analytics"' not in body


class TestStaticAssetRules:
    def test_template_exists_and_extends_base(self):
        text = TEMPLATE.read_text()
        assert re.search(r"{%\s*extends\s+['\"]base\.html['\"]\s*%}", text)

    def test_template_uses_head_block_for_css(self):
        text = TEMPLATE.read_text()
        assert "block head" in text and "analytics.css" in text

    def test_template_has_no_hex_colours(self):
        assert not HEX_RE.findall(TEMPLATE.read_text())

    def test_css_has_no_hex_colours(self):
        assert not HEX_RE.findall(CSS.read_text())

    def test_template_has_no_inline_style_attr(self):
        assert "style=" not in TEMPLATE.read_text().lower()

    def test_template_has_no_style_tag(self):
        assert "<style" not in TEMPLATE.read_text().lower()

    def test_css_has_no_inline_style_attr(self):
        assert "style=" not in CSS.read_text().lower()

    def test_template_uses_url_for_for_links(self):
        text = TEMPLATE.read_text()
        assert "url_for('profile')" in text or 'url_for("profile")' in text
        assert 'href="/profile"' not in text
        assert 'href="/analytics"' not in text


class TestRouteImplementation:
    def test_route_has_no_sql_or_db_access(self):
        src = inspect.getsource(app_module.analytics)
        for token in ("execute", "get_db", "SELECT", "INSERT", "cursor"):
            assert token not in src, f"analytics() must not contain {token!r}"

    def test_route_registered_get_only(self):
        rules = [r for r in app_module.app.url_map.iter_rules()
                 if r.rule == "/analytics"]
        assert rules, "/analytics route missing"
        methods = set().union(*(r.methods for r in rules))
        assert "GET" in methods and "POST" not in methods


class TestDocs:
    def test_claude_md_lists_analytics_route(self):
        text = CLAUDE_MD.read_text()
        assert "GET /analytics" in text
        row = next(l for l in text.splitlines() if "GET /analytics" in l)
        assert "coming soon" in row.lower()


class TestExistingBehaviourUnchanged:
    @pytest.mark.parametrize("path", ["/", "/login", "/register"])
    def test_public_pages_still_200(self, client, path):
        assert client.get(path).status_code == 200

    def test_profile_still_200_logged_in(self, auth_client):
        assert auth_client.get("/profile").status_code == 200

    def test_profile_still_redirects_logged_out(self, client):
        resp = client.get("/profile")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    @pytest.mark.parametrize(
        "path,text",
        [
            ("/expenses/1/delete", "Step 9"),
        ],
    )
    def test_stub_routes_still_placeholder(self, client, path, text):
        resp = client.get(path)
        assert resp.status_code == 200
        assert text in resp.data.decode()
