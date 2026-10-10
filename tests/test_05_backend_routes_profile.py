"""Tests for Step 5: DB-backed /profile route and its database helpers."""
import re
from datetime import datetime
from pathlib import Path

import pytest

import database.db as db

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def register(client, name, email, password="password123"):
    return client.post(
        "/register",
        data={
            "name": name,
            "email": email,
            "password": password,
            "confirm_password": password,
        },
    )


def get_profile_html(client):
    response = client.get("/profile")
    assert response.status_code == 200, "Expected /profile to return 200"
    return response.get_data(as_text=True)


def user_id_for(email):
    return db.get_user_by_email(email)["id"]


def insert_expense(user_id, amount, category, date, description):
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def demo_client(client):
    login(client)
    return client


@pytest.fixture
def new_user_client(client):
    register(client, "Fresh Person", "fresh@example.com")
    login(client, "fresh@example.com", "password123")
    return client


# ------------------------------------------------------------------ #
# Auth guard                                                           #
# ------------------------------------------------------------------ #

class TestProfileAuth:
    def test_profile_logged_out_redirects_to_login(self, client):
        response = client.get("/profile")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_profile_stale_session_user_redirects_to_login(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = 99999
        response = client.get("/profile")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_profile_stale_session_is_cleared(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = 99999
        client.get("/profile")
        with client.session_transaction() as sess:
            assert "user_id" not in sess, "Stale session should be cleared"


# ------------------------------------------------------------------ #
# Demo user profile                                                    #
# ------------------------------------------------------------------ #

class TestDemoProfile:
    def test_demo_profile_returns_200(self, demo_client):
        assert demo_client.get("/profile").status_code == 200

    def test_demo_profile_shows_name_and_email(self, demo_client):
        html = get_profile_html(demo_client)
        assert "Demo User" in html
        assert DEMO_EMAIL in html

    def test_member_since_matches_created_at_month_year(self, demo_client):
        user = db.get_user_by_email(DEMO_EMAIL)
        expected = datetime.strptime(
            user["created_at"], "%Y-%m-%d %H:%M:%S"
        ).strftime("%B %Y")
        html = get_profile_html(demo_client)
        assert expected in html, f"Expected member-since '{expected}'"

    def test_total_spent_is_sum_of_seed(self, demo_client):
        html = get_profile_html(demo_client)
        assert "₹277.74" in html

    def test_transaction_count_is_8(self, demo_client):
        html = get_profile_html(demo_client)
        # Count table rows for the 8 seeded descriptions
        descriptions = [
            "Lunch", "Metro card top-up", "Electricity bill", "Pharmacy",
            "Movie tickets", "New shirt", "Miscellaneous", "Groceries",
        ]
        for d in descriptions:
            assert d in html, f"Missing transaction '{d}'"
        assert re.search(r"(?<![\d.])8(?![\d.])", html), "Expected count 8"

    def test_top_category_is_bills_with_total(self, demo_client):
        html = get_profile_html(demo_client)
        assert "Bills" in html
        assert "₹85.00" in html

    def test_transactions_listed_newest_first(self, demo_client):
        html = get_profile_html(demo_client)
        ordered_dates = [
            "2026-09-20", "2026-09-17", "2026-09-14", "2026-09-11",
            "2026-09-08", "2026-09-05", "2026-09-03", "2026-09-02",
        ]
        positions = [html.find(d) for d in ordered_dates]
        assert all(p >= 0 for p in positions), f"Dates missing: {positions}"
        assert positions == sorted(positions), "Transactions not newest first"

    @pytest.mark.parametrize(
        "amount", ["₹12.50", "₹30.00", "₹85.00", "₹22.75",
                   "₹18.00", "₹54.30", "₹9.99", "₹45.20"],
    )
    def test_transaction_amounts_are_rupee_formatted(self, demo_client, amount):
        assert amount in get_profile_html(demo_client)

    @pytest.mark.parametrize(
        "category",
        ["Food", "Transport", "Bills", "Health",
         "Entertainment", "Shopping", "Other"],
    )
    def test_category_names_displayed(self, demo_client, category):
        assert category in get_profile_html(demo_client)

    def test_category_breakdown_totals_displayed(self, demo_client):
        html = get_profile_html(demo_client)
        assert "₹57.70" in html, "Food total (12.50 + 45.20) expected"

    def test_category_breakdown_percentages_sum_to_100(self, demo_client):
        user_id = user_id_for(DEMO_EMAIL)
        breakdown = db.get_category_breakdown(user_id)
        assert sum(c["percent"] for c in breakdown) == 100


# ------------------------------------------------------------------ #
# New user / empty state                                               #
# ------------------------------------------------------------------ #

class TestEmptyProfile:
    def test_new_user_profile_returns_200(self, new_user_client):
        assert new_user_client.get("/profile").status_code == 200

    def test_new_user_shows_zero_total(self, new_user_client):
        assert "₹0.00" in get_profile_html(new_user_client)

    def test_new_user_shows_zero_transactions(self, new_user_client):
        html = get_profile_html(new_user_client)
        assert re.search(r"(?<![\d.])0(?![\d.])", html), "Expected 0 count"

    def test_new_user_shows_empty_state_message(self, new_user_client):
        html = get_profile_html(new_user_client).lower()
        assert "no expenses" in html or "no transactions" in html, (
            "Expected an empty-state message"
        )

    def test_new_user_does_not_see_demo_data(self, new_user_client):
        html = get_profile_html(new_user_client)
        assert "Electricity bill" not in html
        assert "₹277.74" not in html

    def test_new_user_shows_own_name_and_email(self, new_user_client):
        html = get_profile_html(new_user_client)
        assert "Fresh Person" in html
        assert "fresh@example.com" in html


# ------------------------------------------------------------------ #
# Data isolation                                                       #
# ------------------------------------------------------------------ #

class TestDataIsolation:
    def test_expense_for_user_a_not_visible_to_user_b(self, client):
        register(client, "User Bee", "bee@example.com")
        demo_id = user_id_for(DEMO_EMAIL)
        insert_expense(demo_id, 999.00, "Food", "2026-09-25", "SecretDemoOnlyItem")

        login(client, "bee@example.com", "password123")
        html = get_profile_html(client)
        assert "SecretDemoOnlyItem" not in html
        assert "₹999.00" not in html
        assert "₹0.00" in html

    def test_expense_for_user_b_not_visible_to_demo(self, client):
        register(client, "User Bee", "bee@example.com")
        bee_id = user_id_for("bee@example.com")
        insert_expense(bee_id, 123.45, "Food", "2026-09-25", "BeeOnlyItem")

        login(client)
        html = get_profile_html(client)
        assert "BeeOnlyItem" not in html
        assert "₹277.74" in html

    def test_new_expense_for_demo_appears_for_demo(self, client):
        demo_id = user_id_for(DEMO_EMAIL)
        insert_expense(demo_id, 10.00, "Food", "2026-09-28", "VisibleToOwner")
        login(client)
        assert "VisibleToOwner" in get_profile_html(client)


# ------------------------------------------------------------------ #
# DB helpers                                                           #
# ------------------------------------------------------------------ #

class TestGetExpenseSummary:
    def test_demo_summary(self, client):
        summary = db.get_expense_summary(user_id_for(DEMO_EMAIL))
        assert summary["total_spent"] == pytest.approx(277.74)
        assert summary["transaction_count"] == 8
        assert summary["top_category"] == "Bills"

    def test_empty_user_summary(self, client):
        register(client, "Empty", "empty@example.com")
        summary = db.get_expense_summary(user_id_for("empty@example.com"))
        assert not summary["total_spent"]
        assert summary["transaction_count"] == 0
        assert summary["top_category"] is None

    def test_summary_scoped_to_user(self, client):
        register(client, "Other", "other@example.com")
        other_id = user_id_for("other@example.com")
        insert_expense(other_id, 5.00, "Food", "2026-09-01", "x")
        summary = db.get_expense_summary(other_id)
        assert summary["total_spent"] == pytest.approx(5.00)
        assert summary["transaction_count"] == 1


class TestGetRecentExpenses:
    def test_returns_newest_first(self, client):
        rows = db.get_recent_expenses(user_id_for(DEMO_EMAIL))
        dates = [r["date"] for r in rows]
        assert dates == sorted(dates, reverse=True)
        assert len(rows) == 8

    def test_rows_have_expected_fields(self, client):
        rows = db.get_recent_expenses(user_id_for(DEMO_EMAIL))
        for field in ("date", "description", "category", "amount"):
            assert field in rows[0].keys()

    def test_limit_respected(self, client):
        rows = db.get_recent_expenses(user_id_for(DEMO_EMAIL), limit=3)
        assert len(rows) == 3
        assert rows[0]["description"] == "Groceries"

    def test_default_limit_is_10(self, client):
        uid = user_id_for(DEMO_EMAIL)
        for i in range(5):
            insert_expense(uid, 1.0, "Food", f"2026-10-0{i + 1}", f"extra{i}")
        assert len(db.get_recent_expenses(uid)) == 10

    def test_same_date_ordered_by_id_desc(self, client):
        uid = user_id_for(DEMO_EMAIL)
        insert_expense(uid, 1.0, "Food", "2026-12-01", "first")
        insert_expense(uid, 2.0, "Food", "2026-12-01", "second")
        rows = db.get_recent_expenses(uid, limit=2)
        assert [r["description"] for r in rows] == ["second", "first"]

    def test_empty_user_returns_empty(self, client):
        register(client, "Empty", "empty@example.com")
        assert list(db.get_recent_expenses(user_id_for("empty@example.com"))) == []


class TestGetCategoryBreakdown:
    def test_demo_percentages_sum_to_100(self, client):
        breakdown = db.get_category_breakdown(user_id_for(DEMO_EMAIL))
        assert sum(c["percent"] for c in breakdown) == 100

    def test_ordered_by_total_descending(self, client):
        breakdown = db.get_category_breakdown(user_id_for(DEMO_EMAIL))
        totals = [c["total"] for c in breakdown]
        assert totals == sorted(totals, reverse=True)
        assert breakdown[0]["name"] == "Bills"

    def test_three_equal_categories_sum_to_100(self, client):
        register(client, "Equal", "equal@example.com")
        uid = user_id_for("equal@example.com")
        for cat in ("Food", "Transport", "Bills"):
            insert_expense(uid, 10.00, cat, "2026-09-01", cat)
        breakdown = db.get_category_breakdown(uid)
        assert len(breakdown) == 3
        assert sum(c["percent"] for c in breakdown) == 100
        assert all(isinstance(c["percent"], int) for c in breakdown)

    def test_empty_user_returns_empty(self, client):
        register(client, "Empty", "empty@example.com")
        assert list(db.get_category_breakdown(user_id_for("empty@example.com"))) == []

    def test_breakdown_scoped_to_user(self, client):
        register(client, "Other", "other@example.com")
        uid = user_id_for("other@example.com")
        insert_expense(uid, 20.00, "Health", "2026-09-01", "x")
        breakdown = db.get_category_breakdown(uid)
        assert [c["name"] for c in breakdown] == ["Health"]
        assert breakdown[0]["percent"] == 100


# ------------------------------------------------------------------ #
# Static source checks                                                 #
# ------------------------------------------------------------------ #

class TestSourceRules:
    def test_profile_template_has_no_hex_colours(self):
        text = (PROJECT_ROOT / "templates" / "profile.html").read_text(encoding="utf-8")
        matches = re.findall(r"#[0-9a-fA-F]{3,8}\b", text)
        assert not matches, f"Hex colours found in profile.html: {matches}"

    def test_app_py_contains_no_sql(self):
        text = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
        pattern = re.compile(
            r"\b(SELECT\s.+\sFROM|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM)\b",
            re.IGNORECASE | re.DOTALL,
        )
        assert not pattern.search(text), "SQL found in app.py"
