import sqlite3
from datetime import datetime, timezone
from flask import current_app


VALID_STATUSES = {"PENDING", "VERIFIED", "FAILED"}


def get_db():
    connection = sqlite3.connect(current_app.config["DATABASE_PATH"])
    connection.row_factory = sqlite3.Row
    return connection


def _row_to_dict(row):
    return dict(row) if row else None


def init_db():
    with get_db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                verification_token TEXT,
                status TEXT DEFAULT 'PENDING'
            );
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS verification_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT DEFAULT '',
                open_captured INTEGER DEFAULT 0,
                closed_captured INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """
        )
        db.commit()


def create_or_update_user(email, token):
    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE users SET verification_token = ?, status = 'PENDING' WHERE email = ?",
                (token, email),
            )
            db.commit()
            return "updated"

        db.execute(
            "INSERT INTO users (email, verification_token, status) VALUES (?, ?, 'PENDING')",
            (email, token),
        )
        db.commit()
        return "created"


def get_user_by_email(email):
    with get_db() as db:
        row = db.execute(
            "SELECT id, email, verification_token, status FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    return _row_to_dict(row)


def get_user_by_token(token):
    with get_db() as db:
        row = db.execute(
            "SELECT id, email, verification_token, status FROM users WHERE verification_token = ?",
            (token,),
        ).fetchone()
    return _row_to_dict(row)


def get_user_by_email_and_token(email, token):
    with get_db() as db:
        row = db.execute(
            """
            SELECT id, email, verification_token, status
            FROM users
            WHERE email = ? AND verification_token = ?
            """,
            (email, token),
        ).fetchone()
    return _row_to_dict(row)


def update_user_status(email, status):
    normalized_status = status.upper()
    if normalized_status not in VALID_STATUSES:
        raise ValueError(f"Invalid user status: {status}")

    with get_db() as db:
        db.execute(
            "UPDATE users SET status = ? WHERE email = ?",
            (normalized_status, email),
        )
        db.commit()


def log_verification_event(email, status, reason="", open_captured=False, closed_captured=False):
    normalized_status = status.upper()
    if normalized_status not in VALID_STATUSES:
        raise ValueError(f"Invalid user status for event log: {status}")

    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute(
            """
            INSERT INTO verification_events (
                email, status, reason, open_captured, closed_captured, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                email,
                normalized_status,
                reason,
                int(bool(open_captured)),
                int(bool(closed_captured)),
                created_at,
            ),
        )
        db.commit()


def get_recent_verification_events(limit=100):
    safe_limit = max(1, min(int(limit), 500))
    with get_db() as db:
        rows = db.execute(
            """
            SELECT id, email, status, reason, open_captured, closed_captured, created_at
            FROM verification_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    return [dict(row) for row in rows]
