"""Tests for Step 9: Edit Expense (GET/POST /expenses/<id>/edit)."""

import re

import pytest

import database.db as db

OWNER_EMAIL = "owner@example.com"
OTHER_EMAIL = "other@example.com"
PASSWORD = "pass12345"


# --------------------------------------------------------------------------
# Fixtures and helpers
# --------------------------------------------------------------------------
@pytest.fixture
def owner_id(client):
    return db.create_user("Owner User", OWNER_EMAIL, PASSWORD)


@pytest.fixture
def other_id(client):
    return db.create_user("Other User", OTHER_EMAIL, PASSWORD)


@pytest.fixture
def expense_id(owner_id):
    return db.create_expense(owner_id, 42.5, "Food", "2026-02-10", "Original lunch")


@pytest.fixture
def other_expense_id(other_id):
    return db.create_expense(other_id, 99.0, "Bills", "2026-02-11", "Other rent")


@pytest.fixture
def auth_client(client, owner_id):
    resp = client.post("/login", data={"email": OWNER_EMAIL, "password": PASSWORD})
    assert resp.status_code in (302, 303), "Login should redirect"
    return client


def _url(expense_id):
    return f"/expenses/{expense_id}/edit"


def _row(expense_id):
    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT id, user_id, amount, category, date, description, created_at "
            "FROM expenses WHERE id = ?",
            (expense_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _count_expenses():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    finally:
        conn.close()


def _valid_form(**overrides):
    data = {
        "amount": "55.25",
        "category": "Transport",
        "date": "2026-03-04",
        "description": "Edited taxi",
    }
    data.update(overrides)
    return data


# --------------------------------------------------------------------------
# GET: pre-filled form
# --------------------------------------------------------------------------
class TestGetPrefilled:
    def test_returns_200(self, auth_client, expense_id):
        assert auth_client.get(_url(expense_id)).status_code == 200

    def test_fields_prefilled(self, auth_client, expense_id):
        body = auth_client.get(_url(expense_id)).data.decode()
        assert "42.5" in body, "Amount should be pre-filled"
        assert "2026-02-10" in body, "Date should be pre-filled"
        assert "Original lunch" in body, "Description should be pre-filled"

    def test_all_categories_listed_and_current_selected(self, auth_client, expense_id):
        body = auth_client.get(_url(expense_id)).data.decode()
        for cat in db.CATEGORIES:
            assert cat in body, f"Category {cat!r} missing from dropdown"
        sel = re.search(r"<option[^>]*value=\"Food\"[^>]*>", body)
        assert sel and "selected" in sel.group(0), "Current category must be selected"
        other = re.search(r"<option[^>]*value=\"Bills\"[^>]*>", body)
        assert other and "selected" not in other.group(0)

    def test_form_fields_present(self, auth_client, expense_id):
        body = auth_client.get(_url(expense_id)).data.decode()
        for name in ("amount", "category", "date", "description"):
            assert f'name="{name}"' in body, f"Missing field {name}"

    def test_edit_wording_present(self, auth_client, expense_id):
        body = auth_client.get(_url(expense_id)).data.decode()
        assert "Edit" in body, "Edit-mode wording expected"
        assert (
            "Add expense</button>" not in body
        ), "Submit button must not use add-mode label"

    def test_form_posts_back_to_edit_url(self, auth_client, expense_id):
        body = auth_client.get(_url(expense_id)).data.decode()
        form_tag = re.search(r"<form[^>]*>", body)
        assert form_tag, "A form is expected"
        tag = form_tag.group(0)
        assert f'action="{_url(expense_id)}"' in tag
        assert "post" in tag.lower()

    def test_cancel_link_to_profile(self, auth_client, expense_id):
        body = auth_client.get(_url(expense_id)).data.decode()
        assert 'href="/profile"' in body

    def test_get_does_not_modify_row(self, auth_client, expense_id):
        before = _row(expense_id)
        auth_client.get(_url(expense_id))
        assert _row(expense_id) == before

    def test_null_description_renders_ok(self, auth_client, owner_id):
        eid = db.create_expense(owner_id, 5, "Other", "2026-01-01", None)
        resp = auth_client.get(_url(eid))
        assert resp.status_code == 200
        assert "None" not in resp.data.decode(), "NULL must not render as 'None'"


# --------------------------------------------------------------------------
# Edit links on profile
# --------------------------------------------------------------------------
class TestProfileEditLinks:
    def test_profile_has_edit_link_per_expense(self, auth_client, owner_id, expense_id):
        second = db.create_expense(owner_id, 7, "Health", "2026-02-12", "Pills")
        body = auth_client.get("/profile").data.decode()
        assert f'href="{_url(expense_id)}"' in body
        assert f'href="{_url(second)}"' in body

    def test_profile_does_not_link_other_users_expense(
        self, auth_client, expense_id, other_expense_id
    ):
        body = auth_client.get("/profile").data.decode()
        assert f'href="{_url(other_expense_id)}"' not in body

    def test_edit_link_is_followable(self, auth_client, expense_id):
        body = auth_client.get("/profile").data.decode()
        assert auth_client.get(_url(expense_id)).status_code == 200
        assert _url(expense_id) in body


# --------------------------------------------------------------------------
# Auth guard
# --------------------------------------------------------------------------
class TestAuthGuard:
    def test_logged_out_get_redirects_to_login(self, client, expense_id):
        resp = client.get(_url(expense_id))
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    def test_logged_out_post_redirects_and_changes_nothing(self, client, expense_id):
        before = _row(expense_id)
        resp = client.post(_url(expense_id), data=_valid_form())
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")
        assert _row(expense_id) == before, "Logged-out POST must not modify row"

    @pytest.mark.parametrize("method", ["get", "post"])
    def test_deleted_user_session_cleared_and_redirected(
        self, client, expense_id, method
    ):
        with client.session_transaction() as sess:
            sess["user_id"] = 999999
            sess["user_name"] = "Ghost"
        before = _row(expense_id)
        resp = getattr(client, method)(_url(expense_id))
        assert resp.status_code == 302, "Stale session must redirect, not 500"
        assert resp.headers["Location"].endswith("/login")
        with client.session_transaction() as sess:
            assert "user_id" not in sess, "Session should be cleared"
        assert _row(expense_id) == before


# --------------------------------------------------------------------------
# Happy path POST
# --------------------------------------------------------------------------
class TestHappyPath:
    def test_valid_post_redirects_to_profile(self, auth_client, expense_id):
        resp = auth_client.post(_url(expense_id), data=_valid_form())
        assert resp.status_code in (302, 303)
        assert resp.headers["Location"].endswith("/profile")

    def test_valid_post_updates_all_fields(self, auth_client, expense_id):
        auth_client.post(_url(expense_id), data=_valid_form())
        row = _row(expense_id)
        assert float(row["amount"]) == pytest.approx(55.25)
        assert row["category"] == "Transport"
        assert row["date"] == "2026-03-04"
        assert row["description"] == "Edited taxi"

    def test_user_id_and_created_at_unchanged(self, auth_client, owner_id, expense_id):
        before = _row(expense_id)
        auth_client.post(_url(expense_id), data=_valid_form())
        after = _row(expense_id)
        assert after["user_id"] == owner_id == before["user_id"]
        assert after["created_at"] == before["created_at"]

    def test_no_new_rows_created(self, auth_client, expense_id):
        before = _count_expenses()
        auth_client.post(_url(expense_id), data=_valid_form())
        assert _count_expenses() == before

    def test_other_rows_untouched(self, auth_client, expense_id, other_expense_id):
        before = _row(other_expense_id)
        auth_client.post(_url(expense_id), data=_valid_form())
        assert _row(other_expense_id) == before

    def test_follow_redirect_lands_on_profile_with_new_values(
        self, auth_client, expense_id
    ):
        resp = auth_client.post(
            _url(expense_id), data=_valid_form(), follow_redirects=True
        )
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "Edited taxi" in body
        assert "Original lunch" not in body

    def test_profile_stats_and_breakdown_reflect_change(self, auth_client, expense_id):
        before = auth_client.get("/profile").data.decode()
        assert "₹42.50" in before
        auth_client.post(
            _url(expense_id),
            data=_valid_form(amount="100", category="Shopping", description="Gadget"),
        )
        body = auth_client.get("/profile").data.decode()
        assert "₹100.00" in body, "Total should reflect new amount"
        assert "₹42.50" not in body, "Old amount should be gone"
        assert "Shopping" in body, "Top category / breakdown should show new category"
        assert "Gadget" in body
        assert "Original lunch" not in body

    def test_transaction_count_unchanged_after_edit(self, auth_client, expense_id):
        before = _count_expenses()
        auth_client.post(_url(expense_id), data=_valid_form())
        assert _count_expenses() == before

    def test_amount_rounded_to_two_decimals(self, auth_client, expense_id):
        auth_client.post(_url(expense_id), data=_valid_form(amount="1.239"))
        assert float(_row(expense_id)["amount"]) == pytest.approx(1.24)

    def test_description_is_stripped(self, auth_client, expense_id):
        auth_client.post(_url(expense_id), data=_valid_form(description="  padded  "))
        assert _row(expense_id)["description"] == "padded"

    @pytest.mark.parametrize("cat", db.CATEGORIES)
    def test_every_category_accepted(self, auth_client, expense_id, cat):
        resp = auth_client.post(_url(expense_id), data=_valid_form(category=cat))
        assert resp.status_code in (302, 303)
        assert _row(expense_id)["category"] == cat

    def test_max_amount_boundary_accepted(self, auth_client, expense_id):
        resp = auth_client.post(_url(expense_id), data=_valid_form(amount="10000000"))
        assert resp.status_code in (302, 303)
        assert float(_row(expense_id)["amount"]) == pytest.approx(10000000)

    def test_description_exactly_200_chars_accepted(self, auth_client, expense_id):
        resp = auth_client.post(
            _url(expense_id), data=_valid_form(description="a" * 200)
        )
        assert resp.status_code in (302, 303)
        assert _row(expense_id)["description"] == "a" * 200

    def test_sql_injection_in_description_stored_literally(
        self, auth_client, expense_id
    ):
        payload = "'); DROP TABLE expenses;--"
        resp = auth_client.post(_url(expense_id), data=_valid_form(description=payload))
        assert resp.status_code in (302, 303)
        assert _row(expense_id)["description"] == payload

    def test_posted_user_id_ignored(self, auth_client, owner_id, other_id, expense_id):
        resp = auth_client.post(
            _url(expense_id), data=_valid_form(user_id=str(other_id))
        )
        assert resp.status_code in (302, 303)
        row = _row(expense_id)
        assert row["user_id"] == owner_id, "Posted user_id must be ignored"
        assert row["description"] == "Edited taxi"


class TestDescriptionHandling:
    @pytest.mark.parametrize("desc", ["", "   "])
    def test_empty_description_stored_as_null(self, auth_client, expense_id, desc):
        resp = auth_client.post(_url(expense_id), data=_valid_form(description=desc))
        assert resp.status_code in (302, 303)
        assert _row(expense_id)["description"] is None

    def test_missing_description_field_accepted_as_null(self, auth_client, expense_id):
        data = _valid_form()
        del data["description"]
        resp = auth_client.post(_url(expense_id), data=data)
        assert resp.status_code in (302, 303)
        assert _row(expense_id)["description"] is None

    def test_description_over_200_chars_rejected(self, auth_client, expense_id):
        before = _row(expense_id)
        resp = auth_client.post(
            _url(expense_id), data=_valid_form(description="a" * 201)
        )
        assert resp.status_code == 400
        assert _row(expense_id) == before


# --------------------------------------------------------------------------
# 404 handling
# --------------------------------------------------------------------------
class TestNotFound:
    def test_get_nonexistent_id_404(self, auth_client):
        assert auth_client.get(_url(987654)).status_code == 404

    def test_post_nonexistent_id_404(self, auth_client):
        before = _count_expenses()
        resp = auth_client.post(_url(987654), data=_valid_form())
        assert resp.status_code == 404
        assert _count_expenses() == before, "POST to missing id must not insert"

    def test_get_other_users_expense_404(self, auth_client, other_expense_id):
        resp = auth_client.get(_url(other_expense_id))
        assert resp.status_code == 404
        assert "Other rent" not in resp.data.decode(), "Must not leak other data"

    def test_post_other_users_expense_404_and_unchanged(
        self, auth_client, other_expense_id
    ):
        before = _row(other_expense_id)
        resp = auth_client.post(_url(other_expense_id), data=_valid_form())
        assert resp.status_code == 404
        assert _row(other_expense_id) == before

    def test_foreign_and_missing_give_same_status(self, auth_client, other_expense_id):
        foreign = auth_client.get(_url(other_expense_id)).status_code
        missing = auth_client.get(_url(987654)).status_code
        assert foreign == missing == 404

    def test_post_foreign_with_posted_user_id_does_not_steal(
        self, auth_client, owner_id, other_id, other_expense_id
    ):
        before = _row(other_expense_id)
        resp = auth_client.post(
            _url(other_expense_id), data=_valid_form(user_id=str(owner_id))
        )
        assert resp.status_code == 404
        assert _row(other_expense_id) == before

    def test_non_integer_id_404(self, auth_client):
        assert auth_client.get("/expenses/abc/edit").status_code == 404


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
class TestValidation:
    @pytest.mark.parametrize(
        "amount",
        [
            "",
            "   ",
            "abc",
            "12abc",
            "0",
            "0.00",
            "-5",
            "-0.01",
            "nan",
            "NaN",
            "inf",
            "-inf",
            "Infinity",
            "10000000.01",
            "99999999999",
        ],
    )
    def test_bad_amount_returns_400_row_unchanged(
        self, auth_client, expense_id, amount
    ):
        before = _row(expense_id)
        resp = auth_client.post(_url(expense_id), data=_valid_form(amount=amount))
        assert resp.status_code == 400, f"amount={amount!r} should be rejected"
        assert _row(expense_id) == before

    def test_missing_amount_field_returns_400(self, auth_client, expense_id):
        data = _valid_form()
        del data["amount"]
        before = _row(expense_id)
        assert auth_client.post(_url(expense_id), data=data).status_code == 400
        assert _row(expense_id) == before

    @pytest.mark.parametrize(
        "category", ["", "Nonsense", "food", "Food; DROP TABLE expenses;--"]
    )
    def test_invalid_category_returns_400_row_unchanged(
        self, auth_client, expense_id, category
    ):
        before = _row(expense_id)
        resp = auth_client.post(_url(expense_id), data=_valid_form(category=category))
        assert resp.status_code == 400
        assert _row(expense_id) == before

    def test_missing_category_field_returns_400(self, auth_client, expense_id):
        data = _valid_form()
        del data["category"]
        before = _row(expense_id)
        assert auth_client.post(_url(expense_id), data=data).status_code == 400
        assert _row(expense_id) == before

    @pytest.mark.parametrize(
        "bad_date",
        [
            "",
            "   ",
            "not-a-date",
            "15/01/2026",
            "2026-13-01",
            "2026-02-30",
            "2026-1-5",
            "20260115",
        ],
    )
    def test_bad_date_returns_400_row_unchanged(
        self, auth_client, expense_id, bad_date
    ):
        before = _row(expense_id)
        resp = auth_client.post(_url(expense_id), data=_valid_form(date=bad_date))
        assert resp.status_code == 400, f"date={bad_date!r} should be rejected"
        assert _row(expense_id) == before

    def test_missing_date_field_returns_400(self, auth_client, expense_id):
        data = _valid_form()
        del data["date"]
        before = _row(expense_id)
        assert auth_client.post(_url(expense_id), data=data).status_code == 400
        assert _row(expense_id) == before

    def test_error_response_rerenders_form_with_message(self, auth_client, expense_id):
        resp = auth_client.post(_url(expense_id), data=_valid_form(amount="abc"))
        assert resp.status_code == 400
        body = resp.data.decode().lower()
        assert "<form" in body, "Form should be re-rendered"
        assert "error" in body or "amount" in body

    def test_entered_values_preserved_on_error(self, auth_client, expense_id):
        resp = auth_client.post(
            _url(expense_id),
            data={
                "amount": "-5",
                "category": "Health",
                "date": "2026-07-08",
                "description": "Preserved text zz",
            },
        )
        assert resp.status_code == 400
        body = resp.data.decode()
        assert "-5" in body
        assert "2026-07-08" in body
        assert "Preserved text zz" in body
        sel = re.search(r"<option[^>]*value=\"Health\"[^>]*>", body)
        assert sel and "selected" in sel.group(
            0
        ), "Submitted category should remain selected"
        assert "Original lunch" not in body, "Entered values win over stored ones"

    def test_error_page_still_in_edit_mode(self, auth_client, expense_id):
        resp = auth_client.post(_url(expense_id), data=_valid_form(amount="abc"))
        body = resp.data.decode()
        assert f'action="{_url(expense_id)}"' in body
        assert "Add expense</button>" not in body


# --------------------------------------------------------------------------
# Unaffected routes
# --------------------------------------------------------------------------
class TestAddRouteUnaffected:
    def test_add_form_still_add_mode(self, auth_client):
        body = auth_client.get("/expenses/add").data.decode()
        assert "Add expense" in body
        form_tag = re.search(r"<form[^>]*>", body).group(0)
        assert 'action="/expenses/add"' in form_tag

    def test_add_still_inserts_and_redirects(self, auth_client, owner_id):
        before = _count_expenses()
        resp = auth_client.post(
            "/expenses/add",
            data={
                "amount": "9.99",
                "category": "Food",
                "date": "2026-05-05",
                "description": "Snack",
            },
        )
        assert resp.status_code in (302, 303)
        assert resp.headers["Location"].endswith("/profile")
        assert _count_expenses() == before + 1

    def test_add_validation_still_400(self, auth_client):
        before = _count_expenses()
        resp = auth_client.post(
            "/expenses/add",
            data={"amount": "abc", "category": "Food", "date": "2026-05-05"},
        )
        assert resp.status_code == 400
        assert _count_expenses() == before


class TestOtherRoutesUnchanged:
    def test_delete_route_still_responds_as_stub(self, client):
        resp = client.get("/expenses/1/delete")
        assert resp.status_code == 200

    @pytest.mark.parametrize("path", ["/", "/login", "/register"])
    def test_public_pages_still_200(self, client, path):
        assert client.get(path).status_code == 200

    def test_profile_and_analytics_still_200(self, auth_client):
        assert auth_client.get("/profile").status_code == 200
        assert auth_client.get("/analytics").status_code == 200


# --------------------------------------------------------------------------
# DB helpers
# --------------------------------------------------------------------------
class TestDbHelpers:
    def test_get_expense_returns_fields_for_owner(self, owner_id, expense_id):
        exp = db.get_expense(expense_id, owner_id)
        assert exp is not None
        assert exp["id"] == expense_id
        assert float(exp["amount"]) == pytest.approx(42.5)
        assert exp["category"] == "Food"
        assert exp["date"] == "2026-02-10"
        assert exp["description"] == "Original lunch"

    def test_get_expense_scoped_by_user(self, owner_id, other_id, expense_id):
        assert db.get_expense(expense_id, other_id) is None

    def test_get_expense_missing_returns_none(self, owner_id):
        assert db.get_expense(987654, owner_id) is None

    def test_update_expense_returns_true_and_updates(self, owner_id, expense_id):
        ok = db.update_expense(
            expense_id, owner_id, 10.0, "Health", "2026-04-01", "Checkup"
        )
        assert ok is True
        row = _row(expense_id)
        assert float(row["amount"]) == pytest.approx(10.0)
        assert row["category"] == "Health"
        assert row["date"] == "2026-04-01"
        assert row["description"] == "Checkup"

    def test_update_expense_keeps_user_id_and_created_at(self, owner_id, expense_id):
        before = _row(expense_id)
        db.update_expense(expense_id, owner_id, 1.0, "Other", "2026-04-01", "x")
        after = _row(expense_id)
        assert after["user_id"] == before["user_id"]
        assert after["created_at"] == before["created_at"]

    def test_update_expense_empty_description_becomes_null(self, owner_id, expense_id):
        db.update_expense(expense_id, owner_id, 1.0, "Other", "2026-04-01", "")
        assert _row(expense_id)["description"] is None

    def test_update_expense_foreign_returns_false_and_unchanged(
        self, owner_id, other_expense_id
    ):
        before = _row(other_expense_id)
        ok = db.update_expense(
            other_expense_id, owner_id, 1.0, "Other", "2026-04-01", "hack"
        )
        assert ok is False
        assert _row(other_expense_id) == before

    def test_update_expense_missing_returns_false(self, owner_id):
        assert (
            db.update_expense(987654, owner_id, 1.0, "Other", "2026-04-01", "x")
            is False
        )

    def test_get_recent_expenses_includes_id(self, owner_id, expense_id):
        rows = db.get_recent_expenses(owner_id)
        assert rows, "Expected at least one expense"
        assert rows[0]["id"] == expense_id
