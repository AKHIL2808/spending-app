import math
import os
import sqlite3
from datetime import date, datetime, timedelta

from flask import Flask, abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (
    CATEGORIES,
    create_expense,
    create_user,
    get_category_breakdown,
    get_expense,
    get_expense_summary,
    get_recent_expenses,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
    update_expense,
)

app = Flask(__name__)
# Development-only fallback; set SECRET_KEY in the environment for real use.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

# Must match the badge--/breakdown-meter-- classes in static/css/profile.css.
CATEGORY_SLUGS = {"food", "transport", "bills", "shopping"}

DATE_PRESETS = [
    ("this-month", "This month"),
    ("last-month", "Last month"),
    ("last-30", "Last 30 days"),
    ("last-90", "Last 90 days"),
    ("all", "All time"),
]
PRESET_KEYS = {key for key, _ in DATE_PRESETS}

MAX_EXPENSE_AMOUNT = 10_000_000
MAX_DESCRIPTION_LENGTH = 200


def _format_currency(value):
    return f"₹{value:,.2f}"


def _format_member_since(created_at):
    # Blank rather than crash the page if created_at is missing or malformed.
    try:
        parsed = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
        return parsed.strftime("%B %Y")
    except (TypeError, ValueError):
        return ""


def _initials(name):
    letters = [word[0] for word in name.split()[:2]]
    return "".join(letters).upper() or "?"


def _category_slug(name):
    slug = name.lower()
    return slug if slug in CATEGORY_SLUGS else "other"


def _format_date_label(value):
    return f"{value.day} {value:%b %Y}"


def _all_time_filter(error=None):
    return {
        "start": None,
        "end": None,
        "active": "all",
        "label": "Showing all time",
        "error": error,
        "start_value": "",
        "end_value": "",
    }


def _preset_range(key, today):
    if key == "this-month":
        first = today.replace(day=1)
        next_first = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
        return first, next_first - timedelta(days=1)
    if key == "last-month":
        last_day = today.replace(day=1) - timedelta(days=1)
        return last_day.replace(day=1), last_day
    if key == "last-30":
        return today - timedelta(days=29), today
    if key == "last-90":
        return today - timedelta(days=89), today
    return None, None


def _parse_iso_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def _expense_form_values(form, default_date=""):
    """Raw, stripped form input used to validate and to refill the form."""
    return {
        "amount": form.get("amount", "").strip(),
        "category": form.get("category", "").strip(),
        "date": form.get("date", default_date).strip(),
        "description": form.get("description", "").strip(),
    }


def _validate_expense_form(values):
    """Return (cleaned, None) on success or (None, error message)."""
    if not values["amount"]:
        return None, "Amount is required."
    try:
        amount = float(values["amount"])
    except (ValueError, OverflowError):
        return None, "Amount must be a number."
    if not math.isfinite(amount):
        return None, "Amount must be a number."
    amount = round(amount, 2)
    if amount <= 0:
        return None, "Amount must be greater than 0."
    if amount > MAX_EXPENSE_AMOUNT:
        return None, f"Amount must be at most {MAX_EXPENSE_AMOUNT:,}."

    if values["category"] not in CATEGORIES:
        return None, "Choose a valid category."

    try:
        # strptime accepts unpadded values like 2026-1-5; require exact YYYY-MM-DD.
        if len(values["date"]) != 10:
            raise ValueError("date must be zero-padded YYYY-MM-DD")
        parsed_date = _parse_iso_date(values["date"])
    except (ValueError, OverflowError):
        return None, "Enter the date as YYYY-MM-DD."

    if len(values["description"]) > MAX_DESCRIPTION_LENGTH:
        return None, (
            f"Description must be {MAX_DESCRIPTION_LENGTH} characters or fewer."
        )

    return {
        "amount": amount,
        "category": values["category"],
        "date": parsed_date.isoformat(),
        "description": values["description"],
    }, None


def _range_label(start, end):
    if start and end:
        return f"Showing {_format_date_label(start)} – {_format_date_label(end)}"
    if start:
        return f"Showing from {_format_date_label(start)}"
    if end:
        return f"Showing up to {_format_date_label(end)}"
    return "Showing all time"


def _resolve_date_filter(args, today):
    """Turn query args into a validated date range; never raises on bad input."""
    start_raw = args.get("start", "").strip()
    end_raw = args.get("end", "").strip()
    preset = args.get("preset", "").strip()

    if start_raw or end_raw:
        try:
            start = _parse_iso_date(start_raw) if start_raw else None
            end = _parse_iso_date(end_raw) if end_raw else None
        except (ValueError, OverflowError):
            return _all_time_filter("Enter dates as YYYY-MM-DD.")
        if start and end and start > end:
            return _all_time_filter("Start date must be on or before end date.")
        active = "custom"
    elif preset:
        if preset not in PRESET_KEYS:
            return _all_time_filter("Unknown date preset.")
        start, end = _preset_range(preset, today)
        active = preset
    else:
        return _all_time_filter()

    return {
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "active": active,
        "label": _range_label(start, end),
        "error": None,
        "start_value": start.isoformat() if start else "",
        "end_value": end.isoformat() if end else "",
    }


def _build_profile_context(user_row, date_filter):
    user_id = user_row["id"]
    start_date = date_filter["start"]
    end_date = date_filter["end"]
    summary = get_expense_summary(user_id, start_date, end_date)

    user = {
        "name": user_row["name"],
        "email": user_row["email"],
        "initials": _initials(user_row["name"]),
        "member_since": _format_member_since(user_row["created_at"]),
    }
    stats = {
        "total_spent": _format_currency(summary["total_spent"]),
        "transaction_count": summary["transaction_count"],
        "top_category": summary["top_category"] or "—",
    }
    transactions = [
        {
            "id": expense["id"],
            "date": expense["date"],
            "description": expense["description"],
            "category": expense["category"],
            "slug": _category_slug(expense["category"]),
            "amount": _format_currency(expense["amount"]),
        }
        for expense in get_recent_expenses(
            user_id, start_date=start_date, end_date=end_date
        )
    ]
    categories = [
        {
            "name": category["name"],
            "slug": _category_slug(category["name"]),
            "total": _format_currency(category["total"]),
            "percent": category["percent"],
        }
        for category in get_category_breakdown(user_id, start_date, end_date)
    ]
    return {
        "user": user,
        "stats": stats,
        "transactions": transactions,
        "categories": categories,
        "date_filter": date_filter,
        "presets": DATE_PRESETS,
    }


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #


@app.route("/")
def landing():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    local_part, _, domain = email.partition("@")

    error = None
    if not name:
        error = "Name is required."
    elif not email:
        error = "Email is required."
    elif not local_part or not domain:
        error = "Enter a valid email address."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."
    elif password != confirm_password:
        error = "Passwords do not match."
    elif get_user_by_email(email):
        error = "An account with that email already exists."
    else:
        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            error = "An account with that email already exists."

    if error:
        return (
            render_template("register.html", error=error, name=name, email=email),
            400,
        )
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("user_id"):
            return redirect(url_for("profile"))
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    error = None
    user = None
    if not email or not password:
        error = "Email and password are required."
    else:
        user = get_user_by_email(email)
        if user is None or not check_password_hash(user["password_hash"], password):
            error = "Invalid email or password."

    if error:
        return render_template("login.html", error=error, email=email), 400

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user_row = get_user_by_id(user_id)
    if user_row is None:
        session.clear()
        return redirect(url_for("login"))

    date_filter = _resolve_date_filter(request.args, date.today())
    context = _build_profile_context(user_row, date_filter)

    return render_template("profile.html", **context)


@app.route("/analytics")
def analytics():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    if get_user_by_id(user_id) is None:
        session.clear()
        return redirect(url_for("login"))

    return render_template("analytics.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    if get_user_by_id(user_id) is None:
        session.clear()
        return redirect(url_for("login"))

    if request.method == "GET":
        values = _expense_form_values({}, date.today().isoformat())
        return render_template(
            "add_expense.html", values=values, categories=CATEGORIES, error=None
        )

    values = _expense_form_values(request.form)
    cleaned, error = _validate_expense_form(values)
    if error:
        return (
            render_template(
                "add_expense.html", values=values, categories=CATEGORIES, error=error
            ),
            400,
        )

    create_expense(
        user_id,
        cleaned["amount"],
        cleaned["category"],
        cleaned["date"],
        cleaned["description"],
    )
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    if get_user_by_id(user_id) is None:
        session.clear()
        return redirect(url_for("login"))

    expense = get_expense(id, user_id)
    if expense is None:
        abort(404)

    if request.method == "GET":
        values = {
            "amount": f"{expense['amount']:.2f}",
            "category": expense["category"],
            "date": expense["date"],
            "description": expense["description"] or "",
        }
        return render_template(
            "add_expense.html",
            values=values,
            categories=CATEGORIES,
            error=None,
            expense_id=id,
        )

    values = _expense_form_values(request.form)
    cleaned, error = _validate_expense_form(values)
    if error:
        return (
            render_template(
                "add_expense.html",
                values=values,
                categories=CATEGORIES,
                error=error,
                expense_id=id,
            ),
            400,
        )

    if not update_expense(
        id,
        user_id,
        cleaned["amount"],
        cleaned["category"],
        cleaned["date"],
        cleaned["description"],
    ):
        abort(404)
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
