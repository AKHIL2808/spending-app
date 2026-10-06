# Spec: Login and Logout

## Overview
Make the existing `/login` page functional and implement `/logout`. Today `GET /login` only renders a form and `/logout` is a stub returning a raw string. This step adds `POST /login` so a registered user can authenticate with email and password, stores the user's id in the Flask session, and redirects to `/profile`. `/logout` clears the session and redirects to the landing page. The navbar in `base.html` becomes session-aware (Sign in / Get started for visitors, Profile / Sign out for logged-in users). This is the first use of sessions in Spendly and is the prerequisite for every logged-in feature (Steps 4-9).

## Depends on
- Step 01 — Database Setup (`users` table, `get_db()`)
- Step 02 — Registration (users exist, `get_user_by_email()` helper, redirect to `/login` after sign-up)

## Routes
- `GET /login` — render the sign-in form (already exists, keep). If the user is already logged in, redirect to `/profile` — public
- `POST /login` — validate credentials; on success store `user_id` in the session and redirect (302) to `/profile`; on failure re-render `login.html` with a generic error and HTTP 400 — public
- `GET /logout` — clear the session and redirect (302) to `/` — public (safe to call when not logged in)

`/login` is a single view with `methods=["GET", "POST"]` on the existing `login` route in `app.py`. `/profile` remains a stub (Step 4); the redirect target only needs to exist. Do not implement it.

## Database changes
No database changes. The existing `users` table already supports login.

No new db helpers are required: `get_user_by_email(email)` (added in Step 02) returns the row including `password_hash`. Optionally add `get_user_by_id(user_id)` to `database/db.py` (parameterised query, closes the connection) so the navbar or later steps can load the current user's name.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html`
    - Replace hardcoded `action="/login"` with `action="{{ url_for('login') }}"`.
    - Re-populate the email input (`value="{{ email or '' }}"`) after a failed submit. Never re-populate the password.
    - Keep the existing `{% if error %}` block.
  - `templates/base.html`
    - In `.nav-links`, branch on `session.get('user_id')`: logged-out shows "Sign in" and "Get started"; logged-in shows "Profile" (`url_for('profile')`) and "Sign out" (`url_for('logout')`).

## Files to change
- `app.py` — set `app.secret_key`; import `session`, `check_password_hash`; extend `login` to handle `POST`; implement `logout`
- `database/db.py` — optionally add `get_user_by_id()`
- `templates/login.html` — changes listed above
- `templates/base.html` — session-aware navbar
- `CLAUDE.md` — mark `/logout` as implemented in the routes table (optional housekeeping)

## Files to create
- `tests/test_login_logout.py` — pytest tests for the login/logout flow (use a temporary DB path so tests never touch `expense_tracker.db`; reuse the fixture approach from `tests/test_registration.py` if it exists)

## New dependencies
No new dependencies. `flask.session` and `werkzeug.security.check_password_hash` are already available.

## Validation rules
Applied server-side in the route:
- `email`: trimmed and lower-cased before lookup (matches how registration stores it)
- `password`: taken as-is (not trimmed)
- Empty email or empty password → "Email and password are required."
- Unknown email OR wrong password → the same message, "Invalid email or password.", so the response does not reveal which emails are registered
- Every failure re-renders `login.html` with a single `error` string and status 400

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only. No f-strings in SQL.
- Passwords hashed with werkzeug; verify with `check_password_hash`. Never log or echo the plain-text password.
- Use CSS variables — never hardcode hex values (no new CSS is expected; reuse existing nav and auth classes)
- All templates extend `base.html`
- DB logic lives in `database/db.py` only. Routes call helpers and do not run SQL.
- Use `url_for()` for every internal link and redirect. Never hardcode URLs.
- Store only `user_id` in the session — never the password hash.
- `app.secret_key` must be read from an environment variable (e.g. `SECRET_KEY`) with a clearly-marked development fallback, never a value that is meant to ship to production.
- Call `session.clear()` on logout, and also before setting `user_id` on login to avoid session fixation.
- Do not use `flash()` — errors are passed to the template via `error`, as in registration.
- Do not implement `/profile` or any other stub route. Do not protect routes with a login-required decorator in this step (that arrives with the features that need it).
- Route functions stay small: read the form, validate, call the db helper, redirect or render.
- Do not change the port (5001).

## Definition of done
- [ ] `GET /login` returns 200 and the form action is generated with `url_for`
- [ ] Logging in as `demo@spendly.com` / `demo123` returns 302 to `/profile` and sets `user_id` in the session
- [ ] Email matching is case-insensitive and ignores surrounding whitespace (`  Demo@Spendly.com ` works)
- [ ] A wrong password re-renders the form with "Invalid email or password." and status 400, and no session is set
- [ ] An unknown email shows the exact same "Invalid email or password." message and status 400
- [ ] Empty email or empty password shows "Email and password are required." and no session is set
- [ ] After a failed login the email field keeps what was typed and the password field is empty
- [ ] A user registered via `/register` can immediately log in with the same credentials
- [ ] `GET /logout` clears the session and redirects (302) to `/`; calling it while logged out also redirects without error
- [ ] After logout, the session no longer contains `user_id`
- [ ] The navbar shows "Sign in" / "Get started" when logged out and "Profile" / "Sign out" when logged in
- [ ] Visiting `/login` while already logged in redirects to `/profile`
- [ ] No SQL is executed directly in `app.py`
- [ ] `pytest tests/test_login_logout.py` passes
- [ ] The app starts with `python app.py` on port 5001 without errors
