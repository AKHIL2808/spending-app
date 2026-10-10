# Spec: Backend Routes for Profile Page

## Overview
Step 4 built the `/profile` page with hardcoded placeholder data. This step replaces that data with real queries against the SQLite database, so the profile page shows the logged-in user's actual details, expense totals, recent transactions and per-category breakdown. All query logic lives in new helpers in `database/db.py`; the `/profile` route only fetches data, formats it for display, and renders the existing template.

## Depends on
- Step 1: Database setup (`users` and `expenses` tables, `get_db()`)
- Step 2: Registration
- Step 3: Login + Logout (session holds `user_id`)
- Step 4: Profile page (template, CSS and route skeleton exist)

## Routes
- `GET /profile` — now backed by DB queries instead of hardcoded data — logged-in only (redirect to `/login` if unauthenticated; if the session's user no longer exists in the DB, clear the session and redirect to `/login`)

No new routes. Stub routes (`/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`) must remain untouched.

## Database changes
No schema changes. The existing `users` and `expenses` tables are sufficient.

New helper functions in `database/db.py` (all parameterised, all scoped by `user_id`, each opens and closes its own connection via `get_db()`):
- `get_user_by_id(user_id)` — already exists; reuse it
- `get_expense_summary(user_id)` — returns total spent, transaction count, and top category (by total amount); zero/`None` values when the user has no expenses
- `get_recent_expenses(user_id, limit=10)` — rows of `date, description, category, amount`, ordered by `date DESC, id DESC`
- `get_category_breakdown(user_id)` — rows of `category, total`, ordered by total descending; percentages computed so they sum to 100 (rounded integers)

## Templates
- **Create:** none
- **Modify:** `templates/profile.html` — only if needed to handle the empty state (e.g. a "No expenses yet" message when there are no transactions/categories). Keep existing structure, classes and `url_for()` usage.

## Files to change
- `database/db.py` — add the helper functions above
- `app.py` — import helpers; rewrite `profile()` to build `user`, `stats`, `transactions`, `categories` from DB data (initials from name, `member_since` as "Month YYYY" from `created_at`, amounts formatted as `₹1,234.00`, category slug = lowercase name if it has a CSS class in `profile.css` (`food`, `transport`, `bills`, `shopping`), otherwise `other`)
- `templates/profile.html` — empty-state handling only (optional)
- `CLAUDE.md` — update the `/profile` row in the implemented-routes table to "DB-wired (Step 5)"

## Files to create
- `.claude/specs/05-backend-routes-profile.md` (this file)
- `tests/test_profile.py` (written during the test step, not during implementation of the route)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()`
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles; no new inline `<style>` tags
- DB logic belongs in `database/db.py` only — the route must not contain SQL
- Route stays single-responsibility: guard, fetch, format, render
- Every query must filter by the session's `user_id`; a user must never see another user's expenses
- Use `url_for()` for all links; use `abort()` for HTTP errors, not raw strings
- Do not implement any stub route (Steps 7–9)
- Always close DB connections (`try/finally`), consistent with existing helpers

## Definition of done
- [ ] Visiting `/profile` logged out redirects to `/login`
- [ ] Logged in as the seeded demo user (`demo@spendly.com` / `demo123`), `/profile` returns 200 and shows name "Demo User" and the email from the DB
- [ ] "Member since" reflects the user's `created_at` month and year
- [ ] Total spent equals the sum of the demo user's seeded expenses (₹277.74 with the current seed data)
- [ ] Transaction count equals 8 for the seeded demo user
- [ ] Top category is the category with the highest total (Bills, ₹85.00, for the seed data)
- [ ] The transaction table lists expenses newest first, with date, description, category badge and ₹-formatted amount
- [ ] The category breakdown lists each category with its total and a percentage; percentages sum to 100
- [ ] A newly registered user with no expenses sees ₹0.00, 0 transactions, and an empty-state message with no errors (HTTP 200)
- [ ] Adding an expense row directly in the DB for user A does not appear on user B's profile
- [ ] No hardcoded profile data remains in `app.py`
- [ ] No SQL appears in `app.py`
- [ ] No hex colour values appear in `profile.html`
