import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "drift.db")


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS drift_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drift_type TEXT NOT NULL,
            confidence REAL,
            severity TEXT,
            resource TEXT,
            changes_count INTEGER,
            features_json TEXT,
            plan_json TEXT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS drift_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            message TEXT,
            is_repeat INTEGER DEFAULT 0,
            repeat_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES drift_events(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS training_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            features_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print(f"[DB] Initialized: {DB_PATH}")


def save_drift_event(drift_type, confidence, severity, resource, changes_count, features_dict, plan_dict):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO drift_events (drift_type, confidence, severity, resource, changes_count, features_json, plan_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        drift_type, confidence, severity, resource, changes_count,
        json.dumps(features_dict), json.dumps(plan_dict, default=str)
    ))

    event_id = cur.lastrowid

    # Check if this resource already had the same drift type
    cur.execute("""
        SELECT COUNT(*), MAX(detected_at) FROM drift_events
        WHERE resource = ? AND drift_type = ? AND id != ?
    """, (resource, drift_type, event_id))

    count, last_detected = cur.fetchone()

    if count > 0:
        message = f"Repeat incident! Resource '{resource}' drifted as '{drift_type}' - {count} previous time(s). Last: {last_detected}"
        is_repeat = 1
        cur.execute("""
            INSERT INTO drift_alerts (event_id, message, is_repeat, repeat_count)
            VALUES (?, ?, ?, ?)
        """, (event_id, message, is_repeat, count))
        print(f"[DB] ALERT: {message}")
    else:
        message = f"New drift detected: {drift_type} on {resource}"
        cur.execute("""
            INSERT INTO drift_alerts (event_id, message, is_repeat, repeat_count)
            VALUES (?, ?, ?, ?)
        """, (event_id, message, 0, 0))
        print(f"[DB] {message}")

    conn.commit()
    conn.close()
    return event_id


def save_training_sample(label, features_dict):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO training_data (label, features_json)
        VALUES (?, ?)
    """, (label, json.dumps(features_dict)))
    conn.commit()
    conn.close()


def get_recent_events(limit=20):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, drift_type, confidence, severity, resource, changes_count, detected_at
        FROM drift_events ORDER BY detected_at DESC LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_alerts(limit=10):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, a.message, a.is_repeat, a.repeat_count, a.created_at, e.drift_type, e.resource
        FROM drift_alerts a
        JOIN drift_events e ON a.event_id = e.id
        ORDER BY a.created_at DESC LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_training_data():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT label, features_json FROM training_data")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_summary():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT drift_type, COUNT(*) as count, ROUND(AVG(confidence), 2) as avg_conf
        FROM drift_events GROUP BY drift_type ORDER BY count DESC
    """)
    summary = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM drift_alerts WHERE is_repeat = 1")
    repeats = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM drift_events")
    total = cur.fetchone()[0]

    conn.close()
    return {"total_events": total, "repeat_alerts": repeats, "by_type": summary}


if __name__ == "__main__":
    init_db()
    print("DB initialized successfully.")
