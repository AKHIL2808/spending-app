# Students will write this file in Step 1 — Database Setup
# This file should contain:
#   get_db()   — returns a SQLite connection with row_factory and foreign keys enabled
#   init_db()  — creates all tables using CREATE TABLE IF NOT EXISTS
#   seed_db()  — inserts sample data for development

import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).parent.parent / "expense_tracker.db"

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    """)
    conn.commit()
    conn.close()


def seed_db():
    conn = get_db()

    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if user_count > 0:
        conn.close()
        return

    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
    )
    user_id = cursor.lastrowid

    expenses = [
        (user_id, 12.50, "Food", "2026-09-02", "Lunch"),
        (user_id, 30.00, "Transport", "2026-09-03", "Metro card top-up"),
        (user_id, 85.00, "Bills", "2026-09-05", "Electricity bill"),
        (user_id, 22.75, "Health", "2026-09-08", "Pharmacy"),
        (user_id, 18.00, "Entertainment", "2026-09-11", "Movie tickets"),
        (user_id, 54.30, "Shopping", "2026-09-14", "New shirt"),
        (user_id, 9.99, "Other", "2026-09-17", "Miscellaneous"),
        (user_id, 45.20, "Food", "2026-09-20", "Groceries"),
    ]
    conn.executemany(
        """
        INSERT INTO expenses (user_id, amount, category, date, description)
        VALUES (?, ?, ?, ?, ?)
        """,
        expenses,
    )

    conn.commit()
    conn.close()


def get_user_by_email(email):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()


def create_user(name, email, password):
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_expense_summary(user_id):
    conn = get_db()
    try:
        total, count = conn.execute(
            "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        # Separate query so ties on total break deterministically by name.
        top = conn.execute(
            """
            SELECT category FROM expenses WHERE user_id = ?
            GROUP BY category
            ORDER BY SUM(amount) DESC, category ASC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        return {
            "total_spent": round(total, 2),
            "transaction_count": count,
            "top_category": top["category"] if top else None,
        }
    finally:
        conn.close()


def get_recent_expenses(user_id, limit=10):
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT date, description, category, amount FROM expenses
            WHERE user_id = ?
            ORDER BY date DESC, id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _largest_remainder_percents(totals):
    """Round shares of the total to whole percents that always sum to 100."""
    grand = sum(totals)
    if grand <= 0:
        return [0] * len(totals)
    raw = [t / grand * 100 for t in totals]
    percents = [int(r) for r in raw]
    leftover = 100 - sum(percents)
    by_fraction = sorted(
        range(len(raw)), key=lambda i: raw[i] - percents[i], reverse=True
    )
    for i in by_fraction[:leftover]:
        percents[i] += 1
    return percents


def get_category_breakdown(user_id):
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT category, SUM(amount) AS total FROM expenses
            WHERE user_id = ?
            GROUP BY category
            ORDER BY total DESC, category ASC
            """,
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    percents = _largest_remainder_percents([row["total"] for row in rows])
    return [
        {"name": row["category"], "total": round(row["total"], 2), "percent": pct}
        for row, pct in zip(rows, percents)
    ]


if __name__ == "__main__":
    init_db()
    seed_db()
    print(f"Database ready at {DB_PATH}")
