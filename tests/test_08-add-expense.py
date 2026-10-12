"""Tests for Step 8: Add Expense (GET/POST /expenses/add)."""
import re
from datetime import date
from pathlib import Path

import pytest

import database.db as db

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "add_expense.html"
CSS = ROOT / "static" / "css" / "add_expense.css"
HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
URL = "/expenses/add"


@pytest.fixture
def auth_client(client):
    resp = client.post(
        "/login", data={"email": "demo@spendly.com", "password": "demo123"}
    )
    assert resp.status_code in (302, 303), "Demo login should redirect"
    return client


def _demo_user_id():
    user = db.get_user_by_email("demo@spendly.com")
    return user["id"]


def _count_expenses(user_id=None):
    conn = db.get_db()
    try:
        if user_id is None:
            return conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        return conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def _valid_form(**overrides):
    data = {
        "amount": "12.50",
        "category": "Food",
        "date": "2026-01-15",
        "description": "Lunch",
    }
    data.update(overrides)
    return data


class TestGetForm:
    def test_returns_200(self, auth_client):
        assert auth_client.get(URL).status_code == 200

    def test_todays_date_prefilled(self, auth_client):
        body = auth_client.get(URL).data.decode()
        assert date.today().isoformat() in body, "Today's date should be pre-filled"

    def test_all_categories_in_dropdown(self, auth_client):
        body = auth_client.get(URL).data.decode()
        assert "<select" in body
        for cat in db.CATEGORIES:
            assert cat in body, f"Category {cat!r} missing from dropdown"

    def test_form_fields_present(self, auth_client):
        body = auth_client.get(URL).data.decode()
        for name in ("amount", "category", "date", "description"):
            assert f'name="{name}"' in body, f"Missing field {name}"
        assert 'method="POST"' in body.replace("post", "POST")

    def test_cancel_link_to_profile(self, auth_client):
        body = auth_client.get(URL).data.decode()
        assert 'href="/profile"' in body, "Cancel link to /profile expected"

    def test_extends_base_and_loads_css_in_head(self, auth_client):
        body = auth_client.get(URL).data.decode()
        assert "<nav" in body and "<footer" in body
        assert "css/add_expense.css" in body.split("</head>")[0]


class TestAuthGuard:
    def test_logged_out_get_redirects_to_login(self, client):
        resp = client.get(URL)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    def test_logged_out_post_redirects_and_inserts_nothing(self, client):
        before = _count_expenses()
        resp = client.post(URL, data=_valid_form())
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")
        assert _count_expenses() == before, "Logged-out POST must not insert"

    @pytest.mark.parametrize("method", ["get", "post"])
    def test_deleted_user_session_cleared_and_redirected(self, client, method):
        with client.session_transaction() as sess:
            sess["user_id"] = 999999
            sess["user_name"] = "Ghost"
        before = _count_expenses()
        resp = getattr(client, method)(URL)
        assert resp.status_code == 302, "Stale session must redirect, not 500"
        assert resp.headers["Location"].endswith("/login")
        with client.session_transaction() as sess:
            assert "user_id" not in sess, "Session should be cleared"
        assert _count_expenses() == before


class TestHappyPath:
    def test_valid_post_redirects_to_profile(self, auth_client):
        resp = auth_client.post(URL, data=_valid_form())
        assert resp.status_code in (302, 303)
        assert resp.headers["Location"].endswith("/profile")

    def test_valid_post_inserts_one_row_for_session_user(self, auth_client):
        uid = _demo_user_id()
        before_user = _count_expenses(uid)
        before_all = _count_expenses()
        auth_client.post(URL, data=_valid_form(description="Unique lunch xyz"))
        assert _count_expenses(uid) == before_user + 1
        assert _count_expenses() == before_all + 1
        conn = db.get_db()
        try:
            row = conn.execute(
                "SELECT user_id, amount, category, date, description "
                "FROM expenses WHERE description = ?",
                ("Unique lunch xyz",),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row[0] == uid
        assert float(row[1]) == pytest.approx(12.50)
        assert row[2] == "Food"
        assert row[3] == "2026-01-15"

    def test_new_expense_visible_on_profile(self, auth_client):
        auth_client.post(
            URL,
            data=_valid_form(
                amount="77.77", date="2099-12-31", description="Visible marker qq"
            ),
        )
        body = auth_client.get("/profile").data.decode()
        assert "Visible marker qq" in body
        assert "77.77" in body

    def test_follow_redirect_lands_on_profile(self, auth_client):
        resp = auth_client.post(URL, data=_valid_form(), follow_redirects=True)
        assert resp.status_code == 200
        assert b"Add expense" in resp.data

    def test_amount_rounded_to_two_decimals(self, auth_client):
        auth_client.post(URL, data=_valid_form(amount="1.239", description="round"))
        conn = db.get_db()
        try:
            row = conn.execute(
                "SELECT amount FROM expenses WHERE description = ?", ("round",)
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert float(row[0]) == pytest.approx(1.24)

    def test_description_is_stripped(self, auth_client):
        auth_client.post(URL, data=_valid_form(description="   padded   "))
        conn = db.get_db()
        try:
            row = conn.execute(
                "SELECT description FROM expenses WHERE description = ?",
                ("padded",),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None, "Description should be stored stripped"

    @pytest.mark.parametrize("cat", db.CATEGORIES)
    def test_every_category_accepted(self, auth_client, cat):
        before = _count_expenses()
        resp = auth_client.post(URL, data=_valid_form(category=cat))
        assert resp.status_code in (302, 303)
        assert _count_expenses() == before + 1

    def test_description_exactly_200_chars_accepted(self, auth_client):
        before = _count_expenses()
        resp = auth_client.post(URL, data=_valid_form(description="a" * 200))
        assert resp.status_code in (302, 303)
        assert _count_expenses() == before + 1


class TestDescriptionHandling:
    @pytest.mark.parametrize("desc", ["", "   "])
    def test_empty_description_stored_as_null(self, auth_client, desc):
        before = _count_expenses()
        resp = auth_client.post(
            URL, data=_valid_form(amount="3.33", description=desc)
        )
        assert resp.status_code in (302, 303)
        assert _count_expenses() == before + 1
        conn = db.get_db()
        try:
            row = conn.execute(
                "SELECT description FROM expenses WHERE amount = ? "
                "ORDER BY id DESC LIMIT 1",
                (3.33,),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row[0] is None, "Empty description must be stored as NULL"

    def test_missing_description_field_accepted(self, auth_client):
        data = _valid_form()
        del data["description"]
        before = _count_expenses()
        resp = auth_client.post(URL, data=data)
        assert resp.status_code in (302, 303)
        assert _count_expenses() == before + 1

    def test_description_over_200_chars_rejected(self, auth_client):
        before = _count_expenses()
        resp = auth_client.post(URL, data=_valid_form(description="a" * 201))
        assert resp.status_code == 400
        assert _count_expenses() == before


class TestValidation:
    @pytest.mark.parametrize(
        "amount",
        ["", "   ", "abc", "12abc", "0", "0.00", "-5", "-0.01", "nan", "NaN",
         "inf", "-inf", "Infinity", "10000000.01", "99999999999"],
    )
    def test_bad_amount_returns_400_no_insert(self, auth_client, amount):
        before = _count_expenses()
        resp = auth_client.post(URL, data=_valid_form(amount=amount))
        assert resp.status_code == 400, f"amount={amount!r} should be rejected"
        assert _count_expenses() == before

    def test_missing_amount_field_returns_400(self, auth_client):
        data = _valid_form()
        del data["amount"]
        before = _count_expenses()
        assert auth_client.post(URL, data=data).status_code == 400
        assert _count_expenses() == before

    def test_max_amount_boundary_accepted(self, auth_client):
        before = _count_expenses()
        resp = auth_client.post(URL, data=_valid_form(amount="10000000"))
        assert resp.status_code in (302, 303)
        assert _count_expenses() == before + 1

    @pytest.mark.parametrize(
        "category", ["", "Nonsense", "food", "Food; DROP TABLE expenses;--"]
    )
    def test_invalid_category_returns_400_no_insert(self, auth_client, category):
        before = _count_expenses()
        resp = auth_client.post(URL, data=_valid_form(category=category))
        assert resp.status_code == 400
        assert _count_expenses() == before

    def test_missing_category_field_returns_400(self, auth_client):
        data = _valid_form()
        del data["category"]
        before = _count_expenses()
        assert auth_client.post(URL, data=data).status_code == 400
        assert _count_expenses() == before

    @pytest.mark.parametrize(
        "bad_date",
        ["", "   ", "not-a-date", "15/01/2026", "2026-13-01", "2026-02-30",
         "2026-1-5", "20260115"],
    )
    def test_bad_date_returns_400_no_insert(self, auth_client, bad_date):
        before = _count_expenses()
        resp = auth_client.post(URL, data=_valid_form(date=bad_date))
        assert resp.status_code == 400, f"date={bad_date!r} should be rejected"
        assert _count_expenses() == before

    def test_missing_date_field_returns_400(self, auth_client):
        data = _valid_form()
        del data["date"]
        before = _count_expenses()
        assert auth_client.post(URL, data=data).status_code == 400
        assert _count_expenses() == before

    def test_error_response_shows_message(self, auth_client):
        resp = auth_client.post(URL, data=_valid_form(amount="abc"))
        assert resp.status_code == 400
        body = resp.data.decode().lower()
        assert "<form" in body, "Form should be re-rendered"
        assert "error" in body or "amount" in body, "Expected an error message"

    def test_sql_injection_in_description_stored_literally(self, auth_client):
        payload = "'); DROP TABLE expenses;--"
        before = _count_expenses()
        resp = auth_client.post(URL, data=_valid_form(description=payload))
        assert resp.status_code in (302, 303)
        assert _count_expenses() == before + 1
        conn = db.get_db()
        try:
            row = conn.execute(
                "SELECT description FROM expenses WHERE description = ?",
                (payload,),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None, "Payload should be stored verbatim"


class TestFormPreservedOnError:
    def test_values_preserved_after_error(self, auth_client):
        resp = auth_client.post(
            URL,
            data={
                "amount": "-5",
                "category": "Transport",
                "date": "2026-03-04",
                "description": "Preserved text zz",
            },
        )
        assert resp.status_code == 400
        body = resp.data.decode()
        assert "-5" in body
        assert "2026-03-04" in body
        assert "Preserved text zz" in body
        sel = re.search(
            r"<option[^>]*value=\"Transport\"[^>]*>", body
        )
        assert sel is not None and "selected" in sel.group(0), (
            "Submitted category should remain selected"
        )

    def test_invalid_amount_text_preserved_or_form_rerendered(self, auth_client):
        resp = auth_client.post(URL, data=_valid_form(amount="12abc"))
        assert resp.status_code == 400
        assert "Lunch" in resp.data.decode()


class TestUserIdIgnored:
    def test_posted_user_id_ignored(self, auth_client):
        uid = _demo_user_id()
        conn = db.get_db()
        try:
            conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                ("Other", "other@example.com", "x"),
            )
            conn.commit()
            other_id = conn.execute(
                "SELECT id FROM users WHERE email = ?", ("other@example.com",)
            ).fetchone()[0]
        finally:
            conn.close()
        before_other = _count_expenses(other_id)
        before_demo = _count_expenses(uid)
        resp = auth_client.post(URL, data=_valid_form(user_id=str(other_id)))
        assert resp.status_code in (302, 303)
        assert _count_expenses(other_id) == before_other
        assert _count_expenses(uid) == before_demo + 1


class TestProfileLink:
    def test_profile_has_add_expense_link(self, auth_client):
        body = auth_client.get("/profile").data.decode()
        assert "Add expense" in body
        assert f'href="{URL}"' in body

    def test_add_expense_link_works(self, auth_client):
        assert auth_client.get(URL).status_code == 200


class TestStaticAssetRules:
    def test_template_extends_base(self):
        text = TEMPLATE.read_text()
        assert re.search(r"{%\s*extends\s+['\"]base\.html['\"]\s*%}", text)

    def test_template_no_hex_colours(self):
        assert not HEX_RE.findall(TEMPLATE.read_text())

    def test_css_no_hex_colours(self):
        assert not HEX_RE.findall(CSS.read_text())

    def test_template_no_inline_style_attr(self):
        assert "style=" not in TEMPLATE.read_text().lower()

    def test_template_no_style_tag(self):
        assert "<style" not in TEMPLATE.read_text().lower()

    def test_template_uses_url_for(self):
        text = TEMPLATE.read_text()
        assert "url_for('add_expense')" in text or 'url_for("add_expense")' in text
        assert "url_for('profile')" in text or 'url_for("profile")' in text
        assert 'href="/profile"' not in text

    def test_css_is_served(self, auth_client):
        assert auth_client.get("/static/css/add_expense.css").status_code == 200


class TestStubsUnchanged:
    @pytest.mark.parametrize(
        "path,text",
        [("/expenses/1/edit", "Step 8"), ("/expenses/1/delete", "Step 9")],
    )
    def test_edit_delete_stubs_still_placeholders(self, client, path, text):
        resp = client.get(path)
        assert resp.status_code == 200
        assert text in resp.data.decode()

    @pytest.mark.parametrize("path", ["/", "/login", "/register"])
    def test_public_pages_still_200(self, client, path):
        assert client.get(path).status_code == 200

    def test_profile_and_analytics_still_200(self, auth_client):
        assert auth_client.get("/profile").status_code == 200
        assert auth_client.get("/analytics").status_code == 200
