"""Tests for Step 6: date filter on /profile (spec 06-date-filter-profile.md).

Seed data (demo@spendly.com / demo123), all dated 2026-09:
    02 Food 12.50 | 03 Transport 30.00 | 05 Bills 85.00 | 08 Health 22.75
    11 Entertainment 18.00 | 14 Shopping 54.30 | 17 Other 9.99 | 20 Food 45.20
Range 2026-09-05..2026-09-14 inclusive -> 4 rows, total 180.05, top = Bills.
"""
import re
from datetime import date, timedelta

import pytest
from werkzeug.datastructures import MultiDict

import database.db as db
from app import _resolve_date_filter

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"

SEED_DATES = [
    "2026-09-02", "2026-09-03", "2026-09-05", "2026-09-08",
    "2026-09-11", "2026-09-14", "2026-09-17", "2026-09-20",
]
IN_RANGE = ["2026-09-05", "2026-09-08", "2026-09-11", "2026-09-14"]
OUT_OF_RANGE = [d for d in SEED_DATES if d not in IN_RANGE]

RESOLVER_KEYS = {"start", "end", "active", "label", "error",
                 "start_value", "end_value"}


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def register(client, name, email, password="password123"):
    return client.post("/register", data={
        "name": name, "email": email,
        "password": password, "confirm_password": password,
    })


def insert_expense(user_id, amount, category, date_str, description):
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date_str, description),
        )
        conn.commit()
    finally:
        conn.close()


def count_rows(table):
    conn = db.get_db()
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def get_html(client, query=""):
    response = client.get("/profile" + query)
    assert response.status_code == 200, f"Expected 200 for /profile{query}"
    return response.get_data(as_text=True)


def txn_dates(html):
    return re.findall(r'class="txn-date">\s*([\d-]+)\s*<', html)


def resolve(args, today=date(2026, 9, 15)):
    return _resolve_date_filter(MultiDict(args), today)


def stat_value(html, label):
    match = re.search(
        rf"{label}</span>\s*<span class=\"profile-stat-value\">\s*([^<]*?)\s*</span>",
        html,
    )
    assert match, f"Stat '{label}' not found"
    return match.group(1)


def active_chips(html):
    return [
        m.strip()
        for m in re.findall(r"<a[^>]*filter-chip--active[^>]*>([^<]*)</a>", html)
    ]


@pytest.fixture
def demo_client(client):
    login(client)
    return client


# ------------------------------------------------------------------ #
# Auth guard                                                           #
# ------------------------------------------------------------------ #

class TestAuthGuard:
    @pytest.mark.parametrize("query", [
        "?preset=last-30",
        "?start=2026-09-05&end=2026-09-14",
        "?start=garbage",
    ])
    def test_logged_out_filtered_profile_redirects_to_login(self, client, query):
        response = client.get("/profile" + query)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_logged_out_response_leaks_no_expense_data(self, client):
        response = client.get("/profile?start=2026-09-05&end=2026-09-14")
        body = response.get_data(as_text=True)
        assert "Electricity bill" not in body


# ------------------------------------------------------------------ #
# Resolver unit tests (_resolve_date_filter)                           #
# ------------------------------------------------------------------ #

class TestResolver:
    def test_no_params_resolves_to_all(self):
        result = resolve({})
        assert set(result) >= RESOLVER_KEYS
        assert result["active"] == "all"
        assert result["start"] is None and result["end"] is None
        assert result["error"] is None
        assert "all time" in result["label"].lower()

    def test_preset_all_is_unbounded(self):
        result = resolve({"preset": "all"})
        assert result["active"] == "all"
        assert result["start"] is None and result["end"] is None
        assert result["error"] is None

    def test_this_month_bounds(self):
        result = resolve({"preset": "this-month"}, date(2026, 9, 15))
        assert result["active"] == "this-month"
        assert result["start"] == "2026-09-01"
        assert result["end"] == "2026-09-30"

    @pytest.mark.parametrize("today,start,end", [
        (date(2026, 12, 10), "2026-12-01", "2026-12-31"),
        (date(2028, 2, 10), "2028-02-01", "2028-02-29"),
        (date(2026, 2, 28), "2026-02-01", "2026-02-28"),
        (date(2026, 1, 31), "2026-01-01", "2026-01-31"),
    ])
    def test_this_month_calendar_boundaries(self, today, start, end):
        result = resolve({"preset": "this-month"}, today)
        assert (result["start"], result["end"]) == (start, end)

    def test_last_month_bounds(self):
        result = resolve({"preset": "last-month"}, date(2026, 9, 15))
        assert result["active"] == "last-month"
        assert (result["start"], result["end"]) == ("2026-08-01", "2026-08-31")

    @pytest.mark.parametrize("today,start,end", [
        (date(2026, 1, 15), "2025-12-01", "2025-12-31"),  # year boundary
        (date(2026, 3, 1), "2026-02-01", "2026-02-28"),
        (date(2028, 3, 31), "2028-02-01", "2028-02-29"),  # leap year
        (date(2026, 10, 31), "2026-09-01", "2026-09-30"),
    ])
    def test_last_month_calendar_boundaries(self, today, start, end):
        result = resolve({"preset": "last-month"}, today)
        assert (result["start"], result["end"]) == (start, end)

    def test_last_30_is_inclusive_of_today(self):
        result = resolve({"preset": "last-30"}, date(2026, 9, 30))
        assert result["end"] == "2026-09-30"
        assert result["start"] == "2026-09-01", "30 days inclusive of today"

    def test_last_90_is_inclusive_of_today(self):
        result = resolve({"preset": "last-90"}, date(2026, 9, 30))
        assert result["end"] == "2026-09-30"
        assert result["start"] == "2026-07-03", "90 days inclusive of today"

    def test_custom_range_is_inclusive_and_echoed(self):
        result = resolve({"start": "2026-09-05", "end": "2026-09-14"})
        assert result["active"] == "custom"
        assert (result["start"], result["end"]) == ("2026-09-05", "2026-09-14")
        assert (result["start_value"], result["end_value"]) == (
            "2026-09-05", "2026-09-14")
        assert result["error"] is None
        assert "2026" in result["label"]

    def test_same_start_and_end_is_valid(self):
        result = resolve({"start": "2026-09-05", "end": "2026-09-05"})
        assert result["error"] is None
        assert result["start"] == result["end"] == "2026-09-05"

    def test_only_start_is_open_ended(self):
        result = resolve({"start": "2026-09-05"})
        assert result["start"] == "2026-09-05"
        assert result["end"] is None
        assert result["error"] is None
        assert result["active"] == "custom"

    def test_only_end_is_open_ended(self):
        result = resolve({"end": "2026-09-14"})
        assert result["start"] is None
        assert result["end"] == "2026-09-14"
        assert result["error"] is None
        assert result["active"] == "custom"

    def test_custom_takes_precedence_over_preset(self):
        result = resolve({"preset": "last-30", "start": "2026-01-01",
                          "end": "2026-01-31"})
        assert result["active"] == "custom"
        assert (result["start"], result["end"]) == ("2026-01-01", "2026-01-31")

    @pytest.mark.parametrize("args", [
        {"start": "garbage"},
        {"end": "garbage"},
        {"start": "2026-13-45"},
        {"start": "2026-02-30"},
        {"start": "09/05/2026", "end": "09/14/2026"},
        {"start": "' OR 1=1 --"},
        {"end": "2026-09-05'; DROP TABLE expenses; --"},
        {"start": "2026-09-05", "end": "nope"},
        {"start": "99999-01-01"},
    ])
    def test_invalid_dates_fall_back_to_all_with_error(self, args):
        result = resolve(args)
        assert result["error"], f"Expected an error message for {args}"
        assert result["active"] == "all"
        assert result["start"] is None and result["end"] is None

    def test_start_after_end_falls_back_to_all_with_error(self):
        result = resolve({"start": "2026-09-14", "end": "2026-09-05"})
        assert result["error"]
        assert result["active"] == "all"
        assert result["start"] is None and result["end"] is None

    def test_unknown_preset_does_not_raise_and_is_unbounded(self):
        result = resolve({"preset": "last-century"})
        assert result["active"] == "all"
        assert result["start"] is None and result["end"] is None

    def test_invalid_custom_with_valid_preset_does_not_raise(self):
        result = resolve({"preset": "last-30", "start": "garbage"})
        assert result["start"] is None and result["end"] is None
        assert result["error"]


# ------------------------------------------------------------------ #
# DB helpers                                                           #
# ------------------------------------------------------------------ #

class TestDbHelpers:
    @pytest.fixture
    def uid(self, client):
        return db.get_user_by_email(DEMO_EMAIL)["id"]

    def test_defaults_unchanged_return_all_rows(self, uid):
        summary = db.get_expense_summary(uid)
        assert summary["transaction_count"] == 8
        assert summary["total_spent"] == pytest.approx(277.74)
        assert len(db.get_recent_expenses(uid)) == 8
        assert sum(c["total"] for c in db.get_category_breakdown(uid)) == \
            pytest.approx(277.74)

    def test_summary_with_range(self, uid):
        summary = db.get_expense_summary(uid, "2026-09-05", "2026-09-14")
        assert summary["transaction_count"] == 4
        assert summary["total_spent"] == pytest.approx(180.05)
        assert summary["top_category"] == "Bills"

    def test_summary_bounds_are_inclusive(self, uid):
        summary = db.get_expense_summary(uid, "2026-09-05", "2026-09-05")
        assert summary["transaction_count"] == 1
        assert summary["total_spent"] == pytest.approx(85.00)

    def test_summary_keyword_args_open_ended(self, uid):
        only_start = db.get_expense_summary(uid, start_date="2026-09-17")
        only_end = db.get_expense_summary(uid, end_date="2026-09-03")
        assert only_start["transaction_count"] == 2
        assert only_end["transaction_count"] == 2

    def test_summary_empty_range(self, uid):
        summary = db.get_expense_summary(uid, "2030-01-01", "2030-12-31")
        assert summary["transaction_count"] == 0
        assert summary["total_spent"] == 0
        assert not summary["top_category"]

    def test_recent_expenses_with_range_newest_first(self, uid):
        rows = db.get_recent_expenses(
            uid, start_date="2026-09-05", end_date="2026-09-14")
        assert [r["date"] for r in rows] == sorted(IN_RANGE, reverse=True)

    def test_recent_expenses_limit_still_applies_with_filter(self, uid):
        rows = db.get_recent_expenses(
            uid, limit=2, start_date="2026-09-05", end_date="2026-09-14")
        assert [r["date"] for r in rows] == ["2026-09-14", "2026-09-11"]

    def test_recent_expenses_empty_range(self, uid):
        assert list(db.get_recent_expenses(
            uid, start_date="2030-01-01", end_date="2030-12-31")) == []

    def test_category_breakdown_range_percents_sum_to_100(self, uid):
        cats = db.get_category_breakdown(uid, "2026-09-05", "2026-09-14")
        assert {c["name"] for c in cats} == {
            "Bills", "Health", "Entertainment", "Shopping"}
        assert sum(c["percent"] for c in cats) == 100

    def test_category_breakdown_empty_range(self, uid):
        assert list(db.get_category_breakdown(
            uid, "2030-01-01", "2030-12-31")) == []

    def test_injection_string_as_bound_is_inert(self, uid):
        # Even if it reached the helper, a bound is a bound parameter only.
        before = count_rows("expenses")
        summary = db.get_expense_summary(uid, "' OR 1=1 --", None)
        assert summary["transaction_count"] <= 8
        assert count_rows("expenses") == before

    def test_helpers_never_return_other_users_rows(self, client, uid):
        register(client, "Other Person", "other@example.com")
        other = db.get_user_by_email("other@example.com")["id"]
        insert_expense(other, 500.00, "Food", "2026-09-10", "OTHERUSERROW")
        summary = db.get_expense_summary(uid, "2026-09-05", "2026-09-14")
        assert summary["transaction_count"] == 4
        rows = db.get_recent_expenses(
            uid, start_date="2026-09-05", end_date="2026-09-14")
        assert all(r["description"] != "OTHERUSERROW" for r in rows)


# ------------------------------------------------------------------ #
# Route: baseline and custom range                                     #
# ------------------------------------------------------------------ #

class TestNoFilter:
    def test_no_params_shows_all_seed_data(self, demo_client):
        html = get_html(demo_client)
        assert sorted(txn_dates(html)) == sorted(SEED_DATES)
        assert "₹277.74" in html
        assert stat_value(html, "Transactions") == "8"

    def test_no_params_shows_all_time_label_and_no_error(self, demo_client):
        html = get_html(demo_client)
        assert "Showing all time" in html
        assert 'role="alert"' not in html
        assert "filter-error" not in html

    def test_preset_all_equals_unfiltered(self, demo_client):
        assert sorted(txn_dates(get_html(demo_client, "?preset=all"))) == \
            sorted(SEED_DATES)


class TestCustomRange:
    QUERY = "?start=2026-09-05&end=2026-09-14"

    def test_only_in_range_rows_shown(self, demo_client):
        html = get_html(demo_client, self.QUERY)
        shown = txn_dates(html)
        assert sorted(shown) == IN_RANGE
        for d in OUT_OF_RANGE:
            assert d not in shown

    def test_endpoints_inclusive(self, demo_client):
        shown = txn_dates(get_html(demo_client, self.QUERY))
        assert "2026-09-05" in shown and "2026-09-14" in shown

    def test_stats_reflect_filtered_set(self, demo_client):
        html = get_html(demo_client, self.QUERY)
        assert stat_value(html, "Total spent") == "₹180.05"
        assert stat_value(html, "Transactions") == "4"
        assert stat_value(html, "Top category") == "Bills"
        assert "₹277.74" not in html

    def test_category_breakdown_reflects_filtered_set(self, demo_client):
        html = get_html(demo_client, self.QUERY)
        names = re.findall(r'class="breakdown-name">\s*([^<]+?)\s*<', html)
        assert sorted(names) == ["Bills", "Entertainment", "Health", "Shopping"]
        percents = [float(p) for p in re.findall(
            r'class="breakdown-percent">\s*([\d.]+)%', html)]
        assert sum(percents) == pytest.approx(100)

    def test_filtered_descriptions_excluded(self, demo_client):
        html = get_html(demo_client, self.QUERY)
        assert "Electricity bill" in html
        assert "Lunch" not in html and "Groceries" not in html

    def test_label_mentions_range(self, demo_client):
        html = get_html(demo_client, self.QUERY)
        assert "Showing" in html
        assert "2026" in html
        assert "Showing all time" not in html

    def test_inputs_keep_entered_dates(self, demo_client):
        html = get_html(demo_client, self.QUERY)
        assert re.search(
            r'<input[^>]*name="start"[^>]*value="2026-09-05"', html)
        assert re.search(
            r'<input[^>]*name="end"[^>]*value="2026-09-14"', html)

    def test_only_start_open_ended(self, demo_client):
        shown = txn_dates(get_html(demo_client, "?start=2026-09-17"))
        assert sorted(shown) == ["2026-09-17", "2026-09-20"]

    def test_only_end_open_ended(self, demo_client):
        shown = txn_dates(get_html(demo_client, "?end=2026-09-03"))
        assert sorted(shown) == ["2026-09-02", "2026-09-03"]

    def test_single_day_range(self, demo_client):
        html = get_html(demo_client, "?start=2026-09-08&end=2026-09-08")
        assert txn_dates(html) == ["2026-09-08"]
        assert stat_value(html, "Transactions") == "1"

    def test_custom_overrides_preset_in_route(self, demo_client):
        html = get_html(
            demo_client, "?preset=last-30&start=2026-09-05&end=2026-09-14")
        assert sorted(txn_dates(html)) == IN_RANGE

    def test_empty_whitespace_params_treated_as_unfiltered(self, demo_client):
        html = get_html(demo_client, "?start=&end=")
        assert sorted(txn_dates(html)) == sorted(SEED_DATES)
        assert "filter-error" not in html


# ------------------------------------------------------------------ #
# Route: empty results                                                 #
# ------------------------------------------------------------------ #

class TestEmptyRange:
    QUERY = "?start=2030-01-01&end=2030-12-31"

    def test_empty_range_zero_stats(self, demo_client):
        html = get_html(demo_client, self.QUERY)
        assert stat_value(html, "Total spent") == "₹0.00"
        assert stat_value(html, "Transactions") == "0"
        assert stat_value(html, "Top category") == "—"

    def test_empty_range_shows_empty_state_messages(self, demo_client):
        html = get_html(demo_client, self.QUERY)
        assert "No transactions in this period." in html
        assert txn_dates(html) == []
        assert "filter-error" not in html

    def test_unfiltered_new_user_empty_state_is_not_period_wording(self, client):
        register(client, "Fresh Person", "fresh@example.com")
        login(client, "fresh@example.com", "password123")
        html = get_html(client)
        assert "No transactions in this period." not in html


# ------------------------------------------------------------------ #
# Route: validation errors                                             #
# ------------------------------------------------------------------ #

class TestValidationErrors:
    @pytest.mark.parametrize("query", [
        "?start=garbage",
        "?end=garbage",
        "?start=2026-02-30",
        "?start=2026-13-01&end=2026-14-01",
        "?start=2026-09-14&end=2026-09-05",
        "?start=%27%20OR%201%3D1%20--",
        "?end=2026-09-05%27%3B%20DROP%20TABLE%20expenses%3B%20--",
        "?start=" + "9" * 5000,
        "?start=%00",
        "?start=%E2%82%B9%F0%9F%92%A5",
    ])
    def test_invalid_input_returns_200_with_error_and_all_time_data(
            self, demo_client, query):
        response = demo_client.get("/profile" + query)
        assert response.status_code == 200, "Must never 500 on bad input"
        html = response.get_data(as_text=True)
        assert 'role="alert"' in html or "filter-error" in html, \
            "Expected inline error message"
        assert sorted(txn_dates(html)) == sorted(SEED_DATES), \
            "Should fall back to all-time data"
        assert "₹277.74" in html

    def test_unknown_preset_returns_200_all_time(self, demo_client):
        response = demo_client.get("/profile?preset=bogus")
        assert response.status_code == 200
        assert sorted(txn_dates(response.get_data(as_text=True))) == \
            sorted(SEED_DATES)

    def test_error_message_escaped_no_reflected_markup(self, demo_client):
        html = get_html(demo_client, "?start=%3Cscript%3Ealert(1)%3C/script%3E")
        assert "<script>alert(1)</script>" not in html

    def test_injection_does_not_alter_db(self, demo_client):
        expenses_before = count_rows("expenses")
        users_before = count_rows("users")
        for value in ["' OR 1=1 --", "'; DROP TABLE expenses; --"]:
            demo_client.get("/profile", query_string={"start": value})
            demo_client.get("/profile", query_string={"end": value})
        assert count_rows("expenses") == expenses_before
        assert count_rows("users") == users_before

    def test_injection_does_not_leak_other_users_rows(self, client):
        register(client, "Other Person", "other@example.com")
        other = db.get_user_by_email("other@example.com")["id"]
        insert_expense(other, 777.77, "Food", "2026-09-10", "SECRETXYZ")
        login(client)
        html = get_html(client, "?start=%27%20OR%201%3D1%20--")
        assert "SECRETXYZ" not in html


# ------------------------------------------------------------------ #
# Route: presets (relative to real today)                              #
# ------------------------------------------------------------------ #

class TestPresetsViaRoute:
    @pytest.fixture
    def preset_client(self, client):
        register(client, "Preset Person", "preset@example.com")
        uid = db.get_user_by_email("preset@example.com")["id"]
        today = date.today()
        insert_expense(uid, 10.00, "Food", today.isoformat(), "TODAYROW")
        insert_expense(uid, 20.00, "Food",
                       (today - timedelta(days=29)).isoformat(), "EDGE29ROW")
        insert_expense(uid, 30.00, "Food",
                       (today - timedelta(days=30)).isoformat(), "DAY30ROW")
        insert_expense(uid, 40.00, "Food",
                       (today - timedelta(days=89)).isoformat(), "EDGE89ROW")
        insert_expense(uid, 50.00, "Food",
                       (today - timedelta(days=90)).isoformat(), "DAY90ROW")
        insert_expense(uid, 60.00, "Food", "2000-01-01", "ANCIENTROW")
        login(client, "preset@example.com", "password123")
        return client

    def test_last_30_includes_today_and_day_29_excludes_day_30(
            self, preset_client):
        html = get_html(preset_client, "?preset=last-30")
        assert "TODAYROW" in html and "EDGE29ROW" in html
        assert "DAY30ROW" not in html and "ANCIENTROW" not in html
        assert stat_value(html, "Transactions") == "2"
        assert stat_value(html, "Total spent") == "₹30.00"

    def test_last_90_includes_day_89_excludes_day_90(self, preset_client):
        html = get_html(preset_client, "?preset=last-90")
        assert "EDGE89ROW" in html and "DAY30ROW" in html
        assert "DAY90ROW" not in html and "ANCIENTROW" not in html
        assert stat_value(html, "Transactions") == "4"

    def test_all_preset_includes_everything(self, preset_client):
        html = get_html(preset_client, "?preset=all")
        assert "ANCIENTROW" in html
        assert stat_value(html, "Transactions") == "6"

    def test_this_month_includes_today_excludes_ancient(self, preset_client):
        html = get_html(preset_client, "?preset=this-month")
        assert "TODAYROW" in html
        assert "ANCIENTROW" not in html

    def test_last_month_excludes_today_and_ancient(self, preset_client):
        html = get_html(preset_client, "?preset=last-month")
        assert "TODAYROW" not in html
        assert "ANCIENTROW" not in html

    def test_seed_data_excluded_from_last_30_when_old(self, demo_client):
        # Seed is dated 2026-09; if today is >29 days after 2026-09-20 nothing matches.
        if date.today() - date(2026, 9, 20) > timedelta(days=29):
            html = get_html(demo_client, "?preset=last-30")
            assert txn_dates(html) == []
            assert "No transactions in this period." in html


# ------------------------------------------------------------------ #
# Route: filter UI                                                     #
# ------------------------------------------------------------------ #

class TestFilterUi:
    def test_all_five_presets_present(self, demo_client):
        html = get_html(demo_client)
        for label in ["This month", "Last month", "Last 30 days",
                      "Last 90 days", "All time"]:
            assert label in html, f"Missing preset '{label}'"
        for key in ["this-month", "last-month", "last-30", "last-90"]:
            assert f"preset={key}" in html, f"Missing link for {key}"

    def test_custom_form_is_get_with_date_inputs(self, demo_client):
        html = get_html(demo_client)
        assert re.search(r'<form[^>]*method="get"[^>]*action="/profile"', html)
        assert re.search(r'<input[^>]*type="date"[^>]*name="start"', html)
        assert re.search(r'<input[^>]*type="date"[^>]*name="end"', html)
        assert "Apply" in html
        assert "Clear" in html

    def test_clear_link_points_to_plain_profile(self, demo_client):
        html = get_html(demo_client)
        assert re.search(r'<a[^>]*href="/profile"[^>]*>\s*Clear', html)

    @pytest.mark.parametrize("key,label", [
        ("this-month", "This month"),
        ("last-month", "Last month"),
        ("last-30", "Last 30 days"),
        ("last-90", "Last 90 days"),
        ("all", "All time"),
    ])
    def test_active_preset_is_highlighted_exactly_once(
            self, demo_client, key, label):
        html = get_html(demo_client, f"?preset={key}")
        assert active_chips(html) == [label]

    def test_no_params_highlights_all_time(self, demo_client):
        assert active_chips(get_html(demo_client)) == ["All time"]

    def test_custom_range_highlights_no_preset(self, demo_client):
        html = get_html(demo_client, "?start=2026-09-05&end=2026-09-14")
        assert active_chips(html) == []

    def test_invalid_input_falls_back_to_all_time_highlight(self, demo_client):
        html = get_html(demo_client, "?start=garbage")
        assert active_chips(html) == ["All time"]

    def test_clear_returns_to_unfiltered_view(self, demo_client):
        get_html(demo_client, "?start=2026-09-05&end=2026-09-14")
        html = get_html(demo_client)
        assert sorted(txn_dates(html)) == sorted(SEED_DATES)
        assert "Showing all time" in html

    def test_no_inline_style_or_hex_colours_in_rendered_filter(self, demo_client):
        html = get_html(demo_client)
        section = html.split('aria-label="Filter by date"', 1)[1].split(
            "</section>", 1)[0]
        assert "style=" not in section
        assert not re.search(r"#[0-9a-fA-F]{3,6}\b", section)


# ------------------------------------------------------------------ #
# Cross-user isolation and side effects                                #
# ------------------------------------------------------------------ #

class TestIsolationAndSideEffects:
    def test_filtered_view_never_shows_other_users_expenses(self, client):
        register(client, "Other Person", "other@example.com")
        other = db.get_user_by_email("other@example.com")["id"]
        insert_expense(other, 777.77, "Food", "2026-09-10", "SECRETXYZ")
        login(client)
        for query in ["?start=2026-09-05&end=2026-09-14",
                      "?start=2026-09-01", "?end=2026-09-30",
                      "?preset=all", ""]:
            html = get_html(client, query)
            assert "SECRETXYZ" not in html, f"Leak with {query!r}"
            assert "777.77" not in html

    def test_other_user_sees_only_own_filtered_data(self, client):
        register(client, "Other Person", "other@example.com")
        other = db.get_user_by_email("other@example.com")["id"]
        insert_expense(other, 77.00, "Food", "2026-09-10", "MINEONLY")
        login(client, "other@example.com", "password123")
        html = get_html(client, "?start=2026-09-05&end=2026-09-14")
        assert txn_dates(html) == ["2026-09-10"]
        assert "Electricity bill" not in html
        assert stat_value(html, "Total spent") == "₹77.00"

    @pytest.mark.parametrize("query", [
        "", "?preset=last-30", "?start=2026-09-05&end=2026-09-14",
        "?start=garbage", "?start=2030-01-01",
    ])
    def test_get_profile_does_not_write_to_db(self, demo_client, query):
        expenses_before = count_rows("expenses")
        users_before = count_rows("users")
        get_html(demo_client, query)
        assert count_rows("expenses") == expenses_before
        assert count_rows("users") == users_before

    def test_filter_does_not_modify_session_user(self, demo_client):
        get_html(demo_client, "?start=garbage")
        with demo_client.session_transaction() as sess:
            assert sess.get("user_id"), "Session should survive bad filter"


# ------------------------------------------------------------------ #
# Stub routes untouched                                                #
# ------------------------------------------------------------------ #

class TestStubRoutesUntouched:
    @pytest.mark.parametrize("path,text", [
        ("/expenses/1/edit", "Step 8"),
        ("/expenses/1/delete", "Step 9"),
    ])
    def test_stub_routes_still_stubs(self, client, path, text):
        response = client.get(path)
        assert response.status_code == 200
        assert text in response.get_data(as_text=True)
