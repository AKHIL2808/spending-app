# Spec: Registration

## Overview
Make the existing `/register` page functional. Today `GET /register` only renders a form; this step adds `POST /register` so a visitor can create a Spendly account. The submitted name, email and password are validated, the password is hashed with werkzeug, and a new row is inserted into the `users` table. On success the user is redirected to the login page. This is the first write path into the `users` table and is the prerequisite for login (Step 3) and every logged-in feature after it.

## Depends on
- Step 01 — Database Setup (`users` table, `get_db()`, `init_db()`)

## Routes
- `GET /register` — render the registration form (already exists, keep) — public
- `POST /register` — validate the form, create the user, redirect to `/login` on success; re-render `register.html` with an error message and HTTP 400 on validation failure or duplicate email — public

Implemented as a single view with `methods=["GET", "POST"]` on the existing `register` route in `app.py`. No session or login-state handling in this step.

## Database changes
No database changes. The existing `users` table (`id`, `name`, `email` UNIQUE, `password_hash`, `created_at`) already supports registration.

New helper functions in `database/db.py` (no schema change):
- `get_user_by_email(email)` — returns the matching `sqlite3.Row` or `None`
- `create_user(name, email, password)` — hashes the password with `generate_password_hash`, inserts the row with a parameterised query, returns the new user id. Raises `sqlite3.IntegrityError` on duplicate email so the route can handle the race between check and insert.

Note: `CLAUDE.md` still says `database/db.py` is empty. That is out of date, since Step 01 implemented `get_db()`, `init_db()` and `seed_db()`. Updating that line is optional and not part of this spec.

## Templates
- **Create:** none
- **Modify:**
  - `templates/register.html`
    - Replace hardcoded `action="/register"` with `action="{{ url_for('register') }}"`, since CLAUDE.md forbids hardcoded URLs.
    - Re-populate `name` and `email` inputs (`value="{{ name or '' }}"`, `value="{{ email or '' }}"`) after a failed submit. Never re-populate the password.
    - Keep the existing `{% if error %}` block for error display.
    - Add `minlength="8"` to the password input to match the placeholder.
    - Add a "Confirm password" input (`id`/`name` = `confirm_password`, type password, `required`, `minlength="8"`) after the password field. Never re-populate it.

## Files to change
- `app.py` — extend the `register` route to handle `POST`; import `request`, `redirect`, `url_for`, `abort` (if used) and the new db helpers
- `database/db.py` — add `get_user_by_email()` and `create_user()`
- `templates/register.html` — changes listed above

## Files to create
- `tests/test_registration.py` — pytest tests for the registration flow (there is no `tests/` directory yet; use a temporary DB path so tests never touch `expense_tracker.db`)

## New dependencies
No new dependencies. `werkzeug.security` is already in `requirements.txt`.

## Validation rules
Applied server-side in the route (the HTML `required` and `minlength` attributes are only a convenience):
- `name`: required, trimmed, non-empty
- `email`: required, trimmed, lower-cased, must contain `@` with non-empty parts on both sides (simple check, no regex library)
- `password`: required, at least 8 characters
- `confirm_password`: must exactly equal `password`; otherwise the message is "Passwords do not match." Checked after the length check and before the duplicate-email check.
- `email` must not already exist in `users`; the message is "An account with that email already exists."
- Each failure re-renders `register.html` with a single human-readable `error` string and status 400.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only. No f-strings in SQL.
- Passwords hashed with werkzeug (`generate_password_hash`). Never store or log the plain-text password.
- Use CSS variables — never hardcode hex values (no new CSS is expected; reuse `.auth-error`, `.form-input`, etc.)
- All templates extend `base.html`
- DB logic lives in `database/db.py` only. The route calls helpers and does not run SQL.
- Use `url_for()` for every internal link and redirect. Never hardcode URLs.
- Route function stays small: read the form, validate, call the db helper, redirect or render.
- Close every DB connection (`conn.close()`), including on the error path.
- Do not implement login, logout, sessions or `/profile`. Those are Steps 3 and 4. Do not set `app.secret_key` or use `flash()` in this step.
- Do not change the port (5001).

## Definition of done
- [ ] `GET /register` returns 200 and shows the form, and the form action is generated with `url_for`
- [ ] Submitting a valid name, a new email and an 8+ character password creates a row in `users` and redirects (302) to `/login`
- [ ] The stored `password_hash` is a werkzeug hash, not the plain-text password (verify with `check_password_hash`)
- [ ] Registering the same email again, in any letter case, re-renders the form with an "already exists" error and does not create a second row
- [ ] A password shorter than 8 characters re-renders the form with an error and creates no row
- [ ] A `confirm_password` that differs from `password` (including empty) re-renders the form with "Passwords do not match." and creates no row
- [ ] Empty name, empty email, or an email without `@` re-renders the form with an error and creates no row
- [ ] After a failed submit the name and email fields keep what was typed, and the password field is empty
- [ ] The demo user (`demo@spendly.com`) still exists and is unaffected
- [ ] No SQL is executed directly in `app.py`
- [ ] `pytest tests/test_registration.py` passes
- [ ] The app starts with `python app.py` on port 5001 without errors
