import sqlite3
import json
from datetime import datetime
from config import settings
import os

def get_db():
    os.makedirs(os.path.dirname(settings.DB_PATH) or '.', exist_ok=True)
    conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False, timeout=15.0)
    # Enable WAL mode for high concurrency
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                arn TEXT NOT NULL,
                type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                action TEXT NOT NULL,
                hcl_hash TEXT,
                exit_code INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    conn.close()

def update_session_status(session_id: str, status: str):
    conn = get_db()
    with conn:
        conn.execute(
            "INSERT INTO sessions (session_id, status) VALUES (?, ?) ON CONFLICT(session_id) DO UPDATE SET status=?, updated_at=CURRENT_TIMESTAMP",
            (session_id, status, status)
        )
    conn.close()

def get_session_status(session_id: str) -> str:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT status FROM sessions WHERE session_id=?", (session_id,))
    row = cur.fetchone()
    conn.close()
    return row['status'] if row else "unknown"

def log_audit(session_id: str, action: str, hcl_hash: str = None, exit_code: int = None):
    conn = get_db()
    with conn:
        conn.execute(
            "INSERT INTO audit_logs (session_id, action, hcl_hash, exit_code) VALUES (?, ?, ?, ?)",
            (session_id, action, hcl_hash, exit_code)
        )
    conn.close()

def save_resources(session_id: str, outputs: dict):
    # Extracts ARNs from terraform outputs and saves them
    conn = get_db()
    with conn:
        for key, value in outputs.items():
            if isinstance(value, dict) and 'value' in value:
                arn = str(value['value'])
                if arn.startswith('arn:aws:'):
                    res_type = arn.split(':')[2]
                    conn.execute(
                        "INSERT INTO resources (session_id, arn, type) VALUES (?, ?, ?)",
                        (session_id, arn, res_type)
                    )
    conn.close()

def get_all_resources() -> list:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT session_id, arn, type, created_at FROM resources ORDER BY created_at DESC")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows

init_db()
