# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Spendly is a Flask-based expense tracker built as a **step-by-step learning project**. Many core pieces are intentionally left as stubs for the student to implement — check a file's contents before assuming functionality exists.

- `database/db.py` is currently a stub: its docstring specifies it should eventually expose `get_db()` (SQLite connection with `row_factory` and foreign keys enabled), `init_db()` (creates tables with `CREATE TABLE IF NOT EXISTS`), and `seed_db()` (inserts sample dev data). None of these are implemented yet.
- `database/__init__.py` is empty.
- `app.py` defines real routes for `landing`, `register`, `login`, `terms`, and `privacy` (each just renders a template), plus explicit placeholder routes (`/logout`, `/profile`, `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`) that return plain placeholder strings, each commented with the step number it belongs to (e.g. "Logout — coming in Step 3"). There is no auth, session, or database logic wired up yet — registration/login forms POST to routes that don't yet process them.
- `static/js/main.js` is a stub with no logic yet.

When asked to build out a feature, check whether it maps to one of these placeholder steps and implement it in place rather than restructuring the scaffold.

## Commands

Run all commands from this directory (`expense-tracker/expense-tracker`). A `.venv` already exists.

```bash
source .venv/bin/activate       # activate the virtualenv
pip install -r requirements.txt # install dependencies
python app.py                   # run the dev server (debug=True, http://localhost:5001)
pytest                          # run tests (pytest-flask is installed; no test files exist yet)
```

There is no linter, formatter, or build step configured.

## Architecture

- **Flask app factory-less setup**: `app.py` creates a single module-level `Flask(__name__)` instance and defines routes directly on it — no blueprints yet.
- **Templates** (`templates/`): Jinja2, all extending `base.html`, which defines the shared nav/footer and yields `title`, `head`, `content`, and `scripts` blocks. Use `url_for('<route_function_name>', ...)` for all internal links (see `base.html` for examples).
- **Static assets** (`static/css/style.css`, `static/js/main.js`): one global stylesheet and one global JS file, both linked from `base.html` — no bundler, no per-page assets.
- **Database** (`database/`): intended to hold a plain `sqlite3`-based data layer (per the stub docstring in `db.py`), not an ORM. `app.py` does not yet import from `database` at all.
- **Port**: the dev server runs on port `5001`, not Flask's default `5000`.
