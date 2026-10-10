import os
import sqlite3
from datetime import datetime

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (
    create_user,
    get_category_breakdown,
    get_expense_summary,
    get_recent_expenses,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
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


def _build_profile_context(user_row):
    user_id = user_row["id"]
    summary = get_expense_summary(user_id)

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
            "date": expense["date"],
            "description": expense["description"],
            "category": expense["category"],
            "slug": _category_slug(expense["category"]),
            "amount": _format_currency(expense["amount"]),
        }
        for expense in get_recent_expenses(user_id)
    ]
    categories = [
        {
            "name": category["name"],
            "slug": _category_slug(category["name"]),
            "total": _format_currency(category["total"]),
            "percent": category["percent"],
        }
        for category in get_category_breakdown(user_id)
    ]
    return {
        "user": user,
        "stats": stats,
        "transactions": transactions,
        "categories": categories,
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
        return render_template(
            "register.html", error=error, name=name, email=email
        ), 400
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

    context = _build_profile_context(user_row)

    return render_template("profile.html", **context)


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
