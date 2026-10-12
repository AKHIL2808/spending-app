# Spec: Coming Soon Analytics Page

## Overview
Adds an Analytics page that tells logged-in users charts and spending insights are on the way. It is a placeholder: no data is queried and no charts are drawn. It gives the roadmap a real destination (a nav link and a page) now, and a template the real analytics can replace later. The page should look finished: a heading, a short explanation, and a preview list of planned features.

## Depends on
- Step 3: Login + Logout (session holds `user_id`, `user_name`)
- Step 4: Profile page (shared layout conventions and `profile.css` style language)

## Routes
- `GET /analytics` — renders the "coming soon" analytics page — logged-in only (logged-out users redirect to `/login`, same guard as `/profile`)

No other routes. The stub routes (`/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`) must remain untouched. CLAUDE.md lists `/expenses/add` as "Step 7"; this spec's step number refers to the analytics page and does not implement that stub.

## Database changes
No database changes. Verified against `database/db.py`: the page needs no data, so no new helpers are added.

## Templates
- **Create:** `templates/analytics.html` — extends `base.html`; contains a heading, a "Coming soon" badge, a one-paragraph explanation, a short list of planned features (e.g. monthly spending trends, category charts, budget tracking) and a link back to the profile page via `url_for('profile')`
- **Modify:** `templates/base.html` — add an "Analytics" link (using `url_for('analytics')`) in the logged-in branch of the nav, between "Profile" and "Sign out"

## Files to change
- `app.py` — add the `analytics()` route (session guard, then render the template); place it with the other implemented routes, above the placeholder section
- `templates/base.html` — nav link
- `CLAUDE.md` — add a `GET /analytics` row to the implemented routes table (marked as a "coming soon" placeholder)

## Files to create
- `templates/analytics.html`
- `static/css/analytics.css` — page-specific styles, loaded through `{% block head %}` in `analytics.html`
- `.claude/specs/07-coming-soon-analytics-page.md` (this file)
- `tests/test_analytics.py` (written during the test step, not during implementation)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (no queries are expected in this step)
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables from `style.css` — never hardcode hex values
- All templates extend `base.html`
- No inline styles and no inline `<style>` tags; page styles go in `static/css/analytics.css`
- Use `url_for()` for every internal link — never hardcode `/analytics` or `/profile`
- The route does one thing: guard, then render. No SQL and no data fetching in it
- Redirect logged-out users to `login`; if the session `user_id` no longer matches a user, clear the session and redirect like `profile()` does (reuse `get_user_by_id`)
- Vanilla JS only; the page must work with JS disabled
- Do not implement any stub route (`/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`)
- Match the existing visual style (cards, `--font-display` headings, `--radius-*` variables) and stay usable at phone width

## Definition of done
- [ ] Logged-in `GET /analytics` returns HTTP 200 and shows the "Coming soon" heading/badge, the explanation and the planned-features list
- [ ] Logged-out `GET /analytics` redirects to `/login`
- [ ] A session pointing at a deleted user is cleared and redirected to `/login`, not a 500
- [ ] The nav shows an "Analytics" link only when logged in, and it navigates to the page
- [ ] The page has a link back to the profile page that works
- [ ] The page extends `base.html` (nav and footer present) and loads `analytics.css` via the `head` block
- [ ] No hex colours in `analytics.html` or `analytics.css`; no inline styles
- [ ] No SQL or data fetching in the `analytics()` route
- [ ] The layout looks right at a narrow (phone) width with no horizontal scroll
- [ ] Existing pages (`/`, `/login`, `/register`, `/profile`) and the stub routes behave as before
- [ ] `CLAUDE.md` routes table lists `GET /analytics`
