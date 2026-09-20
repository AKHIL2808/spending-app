# Students will write this file in Step 1 — Database Setup
# This file should contain:
#   get_db()   — returns a SQLite connection with row_factory and foreign keys enabled
#   init_db()  — creates all tables using CREATE TABLE IF NOT EXISTS
#   seed_db()  — inserts sample data for development

import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).parent.parent / "expense_tracker.db"


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
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category_id INTEGER,
            amount REAL NOT NULL,
            description TEXT,
            expense_date DATE NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE SET NULL
        );
    """)
    conn.commit()
    conn.close()


def seed_db():
    conn = get_db()

    categories = ["Food", "Transport", "Housing", "Entertainment", "Utilities", "Other"]
    conn.executemany(
        "INSERT OR IGNORE INTO categories (name) VALUES (?)",
        [(name,) for name in categories],
    )

    existing = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("nitish@example.com",)
    ).fetchone()

    if existing is None:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Nitish Kumar", "nitish@example.com", generate_password_hash("password123")),
        )
        user_id = cursor.lastrowid

        food_id = conn.execute(
            "SELECT id FROM categories WHERE name = ?", ("Food",)
        ).fetchone()["id"]
        transport_id = conn.execute(
            "SELECT id FROM categories WHERE name = ?", ("Transport",)
        ).fetchone()["id"]

        conn.executemany(
            """
            INSERT INTO expenses (user_id, category_id, amount, description, expense_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (user_id, food_id, 12.50, "Lunch", "2026-09-15"),
                (user_id, transport_id, 30.00, "Metro card top-up", "2026-09-16"),
                (user_id, food_id, 45.20, "Groceries", "2026-09-18"),
            ],
        )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    seed_db()
    print(f"Database ready at {DB_PATH}")
