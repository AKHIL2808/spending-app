import os
import sqlite3

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import create_user, get_user_by_email, init_db, seed_db

app = Flask(__name__)
# Development-only fallback; set SECRET_KEY in the environment for real use.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
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
    if not session.get("user_id"):
        return redirect(url_for("login"))

    # Hardcoded placeholder data — Step 5 replaces this with DB queries.
    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "initials": "DU",
        "member_since": "January 2026",
    }
    stats = {
        "total_spent": "₹12,450.00",
        "transaction_count": 8,
        "top_category": "Food",
    }
    transactions = [
        {"date": "2026-10-05", "description": "Groceries", "category": "Food",
         "slug": "food", "amount": "₹850.00"},
        {"date": "2026-10-04", "description": "Metro card top-up", "category": "Transport",
         "slug": "transport", "amount": "₹500.00"},
        {"date": "2026-10-03", "description": "Electricity bill", "category": "Bills",
         "slug": "bills", "amount": "₹2,300.00"},
        {"date": "2026-10-02", "description": "New shirt", "category": "Shopping",
         "slug": "shopping", "amount": "₹1,799.00"},
        {"date": "2026-10-01", "description": "Dinner out", "category": "Food",
         "slug": "food", "amount": "₹1,200.00"},
        {"date": "2026-09-29", "description": "Pharmacy", "category": "Health",
         "slug": "other", "amount": "₹650.00"},
    ]
    categories = [
        {"name": "Food", "slug": "food", "total": "₹4,350.00", "percent": 35},
        {"name": "Bills", "slug": "bills", "total": "₹3,100.00", "percent": 25},
        {"name": "Shopping", "slug": "shopping", "total": "₹2,500.00", "percent": 20},
        {"name": "Transport", "slug": "transport", "total": "₹1,500.00", "percent": 12},
        {"name": "Other", "slug": "other", "total": "₹1,000.00", "percent": 8},
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
    )


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
