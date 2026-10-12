# Spec: Add Expense

## Overview
Turns the `/expenses/add` stub into a working feature. A logged-in user opens a form, enters an amount, category, date and optional description, and the expense is saved to their account. On success they are redirected to their profile, where the new expense shows up in the transactions list and updates the summary stats and category breakdown. Until now the only expenses in the app are the seeded ones, so this is the first step that lets users put real data in.

## Depends on
- Step 1: Database setup (`expenses` table, `get_db()`, `CATEGORIES`)
- Step 3: Login + Logout (session holds `user_id`)
- Step 5: Backend routes for profile (so the new expense is visible on `/profile`)
- Step 6: Date filter on profile (the new expense must respect it; the default redirect shows all time)

## Routes
- `GET /expenses/add` — renders the add-expense form with today's date pre-filled — logged-in only
- `POST /expenses/add` — validates the form, inserts the expense for the session user, redirects to `/profile` — logged-in only

Logged-out users are redirected to `/login` (same guard as `/profile`). A session whose `user_id` no longer matches a user is cleared and redirected to `/login`.

The stub routes `/expenses/<id>/edit` and `/expenses/<id>/delete` must remain untouched. CLAUDE.md lists `/expenses/add` as "Step 7"; Step 7 turned out to be the analytics placeholder, so this spec (Step 8) is the one that implements it, and the CLAUDE.md table must be corrected.

## Database changes
No schema changes. The existing `expenses` table (`user_id`, `amount`, `category`, `date`, `description`, `created_at`) already fits.

New helper in `database/db.py`:
- `create_expense(user_id, amount, category, date, description)` — parameterised `INSERT`, commits, closes the connection in `finally`, returns `lastrowid`. `description` is stored as `NULL` when empty.

Verified against `database/db.py`: `CATEGORIES` already exists and is the single source of truth for allowed categories; no `create_expense` helper exists yet.

## Templates
- **Create:** `templates/add_expense.html` — extends `base.html`; a form (POST, action via `url_for('add_expense')`) with fields: amount (number, `step="0.01"`, `min="0.01"`), category (select built from `CATEGORIES`), date (`type="date"`, defaults to today), description (text, optional); a submit button and a Cancel link back to `url_for('profile')`. Shows an error message block and re-fills the submitted values on validation failure.
- **Modify:** `templates/profile.html` — add an "Add expense" button/link using `url_for('add_expense')` near the transactions list heading.
- **Modify:** `templates/base.html` — optional: no change required.

## Files to change
- `app.py` — replace the `add_expense()` stub with a real GET/POST route (session guard, validate, call `create_expense`, redirect); import `create_expense` and `CATEGORIES`; add a small `_validate_expense_form(form, today)` helper above the routes
- `database/db.py` — add `create_expense()`
- `templates/profile.html` — "Add expense" link
- `static/css/profile.css` — style for the new link/button if needed (CSS variables only)
- `CLAUDE.md` — change the `GET /expenses/add` row to implemented (Step 8, `GET/POST`, login-guarded) and fix the stub step numbering

## Files to create
- `templates/add_expense.html`
- `static/css/add_expense.css` — page-specific styles, loaded via `{% block head %}`
- `.claude/specs/08-add-expense.md` (this file)
- `tests/test_add_expense.py` (written during the test step, not during implementation)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives only in `database/db.py`; the route fetches/validates, calls the helper, redirects
- No inline styles and no inline `<style>` tags; page styles go in `static/css/add_expense.css`
- Use `url_for()` for every internal link and for the form action
- `user_id` always comes from the session, never from the form
- Server-side validation (do not rely on HTML attributes alone), returning HTTP 400 with the form re-rendered and a message:
  - amount is required, must parse as a number, must be finite (reject `nan`/`inf`) and greater than 0; round to 2 decimals; reject unreasonably large values (e.g. above 10,000,000)
  - category must be one of `CATEGORIES`
  - date is required, must parse as `YYYY-MM-DD`
  - description is stripped, capped at 200 characters, optional
- Use `abort()` for HTTP errors, not bare string returns
- Follow the Post/Redirect/Get pattern: successful POST redirects to `profile`, never renders directly
- Vanilla JS only; the form must work with JS disabled
- Do not implement the edit or delete stub routes

## Definition of done
- [ ] Logged-in `GET /expenses/add` returns 200 and shows the form with today's date pre-filled and all `CATEGORIES` in the dropdown
- [ ] Logged-out `GET` and `POST` to `/expenses/add` redirect to `/login` and insert nothing
- [ ] A valid POST inserts one row for the session user and redirects to `/profile`
- [ ] The new expense appears at the top of the profile transactions list, and the total, transaction count and category breakdown update
- [ ] Submitting an empty amount, a non-numeric amount, zero, a negative amount, `nan` or `inf` returns 400 with an error message and inserts nothing
- [ ] Submitting a category not in `CATEGORIES` returns 400 and inserts nothing
- [ ] Submitting a missing or malformed date returns 400 and inserts nothing
- [ ] On a validation error the form is re-rendered with the user's entered values preserved
- [ ] An empty description is accepted and stored as `NULL`; a description over 200 characters is rejected or trimmed per the rule above
- [ ] A `user_id` field posted in the form is ignored; the expense belongs to the session user
- [ ] A session pointing at a deleted user is cleared and redirected to `/login`, not a 500
- [ ] The Cancel link returns to `/profile` without saving
- [ ] The profile page has a working "Add expense" link
- [ ] The page extends `base.html` and loads `add_expense.css` via the `head` block; no hex colours or inline styles
- [ ] The layout works at phone width with no horizontal scroll
- [ ] `/expenses/<id>/edit` and `/expenses/<id>/delete` still behave as the stubs did; existing pages (`/`, `/login`, `/register`, `/profile`, `/analytics`) behave as before
- [ ] `CLAUDE.md` routes table reflects the implemented route
