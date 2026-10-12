# Spec: Edit Expense

## Overview
Turns the `/expenses/<id>/edit` stub into a working feature. A logged-in user clicks an "Edit" link on a transaction in their profile, sees the add-expense form pre-filled with that expense's current amount, category, date and description, changes any fields and saves. On success they are redirected to `/profile`, where the transactions list, summary stats and category breakdown reflect the change. Step 8 let users create expenses; this step lets them correct mistakes. Users can only edit their own expenses.

## Depends on
- Step 1: Database setup (`expenses` table, `get_db()`, `CATEGORIES`)
- Step 3: Login + Logout (session holds `user_id`)
- Step 5: Backend routes for profile (transactions list to link from)
- Step 6: Date filter on profile
- Step 8: Add expense (reuses `_expense_form_values`, `_validate_expense_form`, and the form template/styles)

## Routes
- `GET /expenses/<int:id>/edit` — renders the expense form pre-filled with the stored values — logged-in only (owner only)
- `POST /expenses/<int:id>/edit` — validates the form, updates the expense, redirects to `/profile` — logged-in only (owner only)

Logged-out users are redirected to `/login` (same guard as `add_expense`). A session whose `user_id` no longer matches a user is cleared and redirected to `/login`. If the expense does not exist **or belongs to another user**, respond with `abort(404)` (same response for both, so ids of other users' expenses are not revealed).

The existing view function is `edit_expense(id)`; keep that endpoint name so `url_for('edit_expense', id=...)` works. The `/expenses/<id>/delete` stub must remain untouched. CLAUDE.md lists edit as "Stub — Step 8" and delete as "Step 9"; edit is implemented in this spec (Step 9), so the CLAUDE.md table must be corrected (delete stub's step number becomes Step 10).

## Database changes
No schema changes.

New helpers in `database/db.py`:
- `get_expense(expense_id, user_id)` — parameterised `SELECT id, amount, category, date, description FROM expenses WHERE id = ? AND user_id = ?`; returns a `sqlite3.Row`/dict or `None`; closes the connection in `finally`.
- `update_expense(expense_id, user_id, amount, category, date, description)` — parameterised `UPDATE ... WHERE id = ? AND user_id = ?`, commits, closes in `finally`, returns `True` if a row was changed (`cursor.rowcount == 1`), else `False`. `description` stored as `NULL` when empty. `created_at` and `user_id` are never modified.
- Modify `get_recent_expenses()` to also `SELECT id` so the profile can build edit links. Existing callers/tests that read other keys are unaffected.

Verified against `database/db.py`: `CATEGORIES` and `create_expense` exist; no `get_expense`/`update_expense` exist yet; `get_recent_expenses` currently does not return `id`.

## Templates
- **Modify:** `templates/add_expense.html` — make the form reusable for both modes: heading/submit label ("Add expense" vs "Edit expense" / "Save changes") and the form `action` come from context variables (e.g. `form_action`, `page_title`, `submit_label`) instead of being hardcoded. Cancel still links to `url_for('profile')`. Add expense behaviour must not change.
- **Modify:** `templates/profile.html` — add an "Edit" link per transaction row using `url_for('edit_expense', id=txn.id)`.
- **Create:** none (reuse `add_expense.html`; a separate template would duplicate the form).

## Files to change
- `app.py` — replace the `edit_expense(id)` stub with a real GET/POST route (session guard, load via `get_expense` or `abort(404)`, validate with existing helpers, call `update_expense`, redirect); import `get_expense`, `update_expense`; add `id` to the transaction dicts in `_build_profile_context`; pass form-mode variables from `add_expense` too
- `database/db.py` — add `get_expense()`, `update_expense()`; add `id` to `get_recent_expenses()`
- `templates/add_expense.html` — parametrise heading, action and submit label
- `templates/profile.html` — per-row Edit link
- `static/css/profile.css` — style for the Edit link (CSS variables only)
- `CLAUDE.md` — mark `GET/POST /expenses/<id>/edit` implemented (Step 9, login-guarded, owner-only) and renumber the delete stub to Step 10

## Files to create
- `.claude/specs/09-edit-expense.md` (this file)
- `tests/test_edit_expense.py` (written during the test step, not during implementation)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives only in `database/db.py`; the route fetches/validates, calls the helper, redirects
- Reuse `_expense_form_values` and `_validate_expense_form`; do not duplicate validation rules (amount finite, > 0, ≤ 10,000,000, rounded to 2 decimals; category in `CATEGORIES`; date exactly `YYYY-MM-DD`; description ≤ 200 chars)
- `user_id` always comes from the session, never from the form or URL; every read and write is scoped by `user_id` in the SQL `WHERE`
- Use `abort(404)` for missing/foreign expenses, not bare string returns
- Validation failures return HTTP 400 with the form re-rendered and entered values preserved
- Follow Post/Redirect/Get: successful POST redirects to `profile`
- No inline styles or `<style>` tags; use `url_for()` for every internal link and the form action
- Vanilla JS only; the form must work with JS disabled
- Do not implement the delete stub route

## Definition of done
- [ ] Each transaction row on `/profile` has an "Edit" link pointing to `/expenses/<id>/edit` for that expense
- [ ] Logged-in `GET /expenses/<id>/edit` for own expense returns 200 with amount, category, date and description pre-filled, and all `CATEGORIES` in the dropdown with the current one selected
- [ ] The page shows "Edit" wording (heading and submit button), and the form posts back to the edit URL
- [ ] Logged-out `GET` and `POST` to `/expenses/<id>/edit` redirect to `/login` and change nothing
- [ ] A valid POST updates amount, category, date and description of that row, leaves `user_id` and `created_at` unchanged, and redirects to `/profile`
- [ ] After editing, the profile transactions list, total, count, top category and category breakdown reflect the new values
- [ ] Editing a non-existent id returns 404
- [ ] Editing another user's expense (GET or POST) returns 404 and does not modify it
- [ ] Empty/non-numeric/zero/negative/`nan`/`inf` amount, invalid category, and missing/malformed date each return 400, keep the entered values in the form, and leave the stored row unchanged
- [ ] Clearing the description is accepted and stored as `NULL`; a description over 200 characters returns 400
- [ ] A `user_id` field posted in the form is ignored
- [ ] A session pointing at a deleted user is cleared and redirected to `/login`, not a 500
- [ ] The Cancel link returns to `/profile` without saving
- [ ] `GET/POST /expenses/add` still works exactly as before (heading, submit label, action, validation)
- [ ] `/expenses/<id>/delete` still behaves as the stub did; existing pages (`/`, `/login`, `/register`, `/profile`, `/analytics`) behave as before
- [ ] No hex colours or inline styles added; layout works at phone width with no horizontal scroll
- [ ] `CLAUDE.md` routes table reflects the implemented edit route
