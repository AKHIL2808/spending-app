# Spec: Date Filter for Profile Page

## Overview
Step 5 wired `/profile` to real data, but the stats, transaction history and category breakdown always cover all of a user's expenses (history capped at the 10 most recent). This step adds a date filter to the profile page so a user can narrow all three sections to a time period: quick presets (This month, Last month, Last 30 days, Last 90 days, All time) and a custom range with start and end dates. The selection lives in the query string (`?preset=...` or `?start=...&end=...`) so filtered views are bookmarkable, and the filter UI is a plain GET form with no JavaScript required.

## Depends on
- Step 1: Database setup (`expenses.date` stored as `YYYY-MM-DD` text)
- Step 3: Login + Logout (session holds `user_id`)
- Step 4: Profile page (template and `profile.css`)
- Step 5: Backend routes for profile (`get_expense_summary`, `get_recent_expenses`, `get_category_breakdown`, `_build_profile_context`)

## Routes
- `GET /profile` — now accepts optional query params `preset` (`this-month`, `last-month`, `last-30`, `last-90`, `all`) and `start` / `end` (`YYYY-MM-DD`); results are filtered accordingly — logged-in only (unchanged auth behaviour)

No new routes. Stub routes (`/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`) must remain untouched.

Filter resolution rules:
- No params → `all` (current behaviour, unchanged)
- Valid `preset` → computed date range from today's date
- Valid `start` and/or `end` (custom) → inclusive range; either bound may be omitted (open-ended). Custom takes precedence over `preset` if both are present
- Unparseable dates, or `start` later than `end` → ignore the filter, fall back to `all`, and show an inline error message (HTTP 200, page still renders). Never raise a 500

## Database changes
No schema changes. `expenses.date` is `TEXT` in `YYYY-MM-DD` form, so string comparison with `date >= ? AND date <= ?` is correct.

Modify existing helpers in `database/db.py` to take optional `start_date=None, end_date=None` (ISO strings) and add `AND date >= ?` / `AND date <= ?` only when provided. Build the WHERE clause from fixed string fragments and pass values as `?` parameters — never interpolate user input into SQL:
- `get_expense_summary(user_id, start_date=None, end_date=None)`
- `get_recent_expenses(user_id, limit=10, start_date=None, end_date=None)`
- `get_category_breakdown(user_id, start_date=None, end_date=None)`

Existing callers and defaults must keep working unchanged.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html`
  - Add a filter section above the stats: preset links/buttons (built with `url_for('profile', preset=...)`, active one highlighted) and a `<form method="get" action="{{ url_for('profile') }}">` with two `<input type="date">` fields (`start`, `end`) and an Apply button, plus a Clear link
  - Show the active range label (e.g. "Showing 1 Sep 2026 – 30 Sep 2026" or "Showing all time")
  - Show the validation error message when present
  - Empty-state text should say "No transactions in this period." when a filter is active

## Files to change
- `database/db.py` — add optional date bounds to the three profile helpers
- `app.py` — add a `_resolve_date_filter(args, today)` helper (parse/validate params, return start, end, active key, label, error); pass bounds into `_build_profile_context`; `profile()` reads `request.args`, still guard → fetch → format → render
- `templates/profile.html` — filter UI, range label, error, empty-state wording
- `static/css/profile.css` — styles for the filter bar (reuse existing CSS variables)
- `CLAUDE.md` — update the `/profile` row to mention the date filter (Step 6)

## Files to create
- `.claude/specs/06-date-filter-profile.md` (this file)
- `tests/test_profile_date_filter.py` (written during the test step, not during implementation)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()`
- Parameterised queries only — never f-strings with user input in SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles; no new inline `<style>` tags
- Vanilla JS only, and the filter must work with JS disabled (plain GET form + links)
- DB logic belongs in `database/db.py` only — the route must not contain SQL; date parsing/validation lives in an `app.py` helper, not inline in `profile()`
- Validate dates with `datetime.strptime(value, "%Y-%m-%d")`; pass only the re-serialised ISO string to the DB
- Every query must still filter by the session's `user_id`
- Use `url_for()` for all links; never hardcode `/profile?...`
- Do not implement any stub route (Steps 7–9)
- Always close DB connections (`try/finally`)
- Compute "today" in one place (a parameter to the resolver) so it is testable

## Definition of done
- [ ] `/profile` with no query params behaves exactly as in Step 5 (all-time data)
- [ ] The filter bar shows the five presets and a custom start/end form; the active preset is visibly highlighted
- [ ] `?preset=last-30` limits stats, transaction list and category breakdown to expenses in the last 30 days (inclusive of today)
- [ ] `?preset=this-month` and `?preset=last-month` use the correct calendar month boundaries, including across a year boundary (January → December)
- [ ] `?start=2026-09-05&end=2026-09-14` against the seed data shows only expenses dated within that range, inclusive of both endpoints; total, count, top category and percentages (sum to 100) all reflect the filtered set
- [ ] Only `start` (or only `end`) gives an open-ended range
- [ ] Submitting the custom form keeps the entered dates in the inputs after reload
- [ ] An invalid date (e.g. `?start=garbage`) or `start` after `end` returns HTTP 200, shows an error message, and falls back to all-time data
- [ ] A range with no matching expenses shows ₹0.00, 0 transactions, "—" top category and the empty-state messages with no errors
- [ ] "Clear" / "All time" returns to the unfiltered view
- [ ] A SQL-injection style value in `start`/`end` (e.g. `' OR 1=1 --`) is rejected by validation and never reaches the query
- [ ] Filtering never exposes another user's expenses
- [ ] Logged-out access to `/profile?preset=last-30` still redirects to `/login`
- [ ] No SQL in `app.py`, no hex colours in `profile.html` or the new CSS
