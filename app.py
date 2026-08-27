"""Simple Flask backend for onboarding form submissions.
Supports SQLite (local), Turso (libSQL), and PostgreSQL (Neon).
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

DB_PATH = os.getenv("ONBOARDING_DB", "logs/onboarding.sqlite3")
TURSO_URL = os.getenv("TURSO_URL", "").strip()
TURSO_TOKEN = os.getenv("TURSO_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USE_TURSO = bool(TURSO_URL and TURSO_TOKEN)
USE_POSTGRES = bool(DATABASE_URL and DATABASE_URL.startswith(("postgres://", "postgresql://")))

app = Flask(__name__, template_folder=".")


def _translate_sql(sql):
    """Translate SQLite ? placeholders to PostgreSQL %s if needed."""
    if USE_POSTGRES:
        return sql.replace("?", "%s")
    return sql


def _connect(db_path: str = DB_PATH):
    """Open a database connection."""
    if USE_POSTGRES:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn
    if USE_TURSO:
        import libsql
        return libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _to_float(v):
    try:
        return float(v) if v not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def _row_dict(row):
    """Convert a database row to a dict."""
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if hasattr(row, "keys"):
        try:
            return {k: row[k] for k in row.keys()}
        except Exception:
            return dict(row)
    return row


# ============================================================
# SCHEMA DEFINITIONS
# ============================================================

SCHEMA_SQLITE = {
    "onboarded_users": """
        CREATE TABLE IF NOT EXISTS onboarded_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT,
            date_of_birth TEXT,
            country TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
        )
    """,
    "establishments": """
        CREATE TABLE IF NOT EXISTS establishments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sr_no INTEGER,
            est_id TEXT UNIQUE,
            est_name TEXT NOT NULL,
            office TEXT,
            circle TEXT,
            aeo TEXT,
            phone TEXT
        )
    """,
    "bank_accounts": """
        CREATE TABLE IF NOT EXISTS bank_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            establishment_id INTEGER NOT NULL,
            account_number TEXT NOT NULL,
            ifsc TEXT NOT NULL,
            code TEXT,
            bank_name TEXT NOT NULL,
            branch TEXT,
            address TEXT,
            city1 TEXT,
            city2 TEXT,
            district TEXT,
            state TEXT,
            phone TEXT,
            contact TEXT,
            period TEXT,
            amount_7a_ac1 REAL DEFAULT 0,
            amount_7a_ac2 REAL DEFAULT 0,
            amount_7a_ac10 REAL DEFAULT 0,
            amount_7a_ac21 REAL DEFAULT 0,
            amount_7a_ac22 REAL DEFAULT 0,
            amount_7a_total REAL DEFAULT 0,
            amount_7q_7a_ac1 REAL DEFAULT 0,
            amount_7q_7a_ac2 REAL DEFAULT 0,
            amount_7q_7a_ac10 REAL DEFAULT 0,
            amount_7q_7a_ac21 REAL DEFAULT 0,
            amount_7q_7a_ac22 REAL DEFAULT 0,
            amount_7q_7a_total REAL DEFAULT 0,
            amount_14b_ac1 REAL DEFAULT 0,
            amount_14b_ac2 REAL DEFAULT 0,
            amount_14b_ac10 REAL DEFAULT 0,
            amount_14b_ac21 REAL DEFAULT 0,
            amount_14b_ac22 REAL DEFAULT 0,
            amount_14b_total REAL DEFAULT 0,
            amount_7q_14b_ac1 REAL DEFAULT 0,
            amount_7q_14b_ac2 REAL DEFAULT 0,
            amount_7q_14b_ac10 REAL DEFAULT 0,
            amount_7q_14b_ac21 REAL DEFAULT 0,
            amount_7q_14b_ac22 REAL DEFAULT 0,
            amount_7q_14b_total REAL DEFAULT 0,
            total_amount REAL DEFAULT 0,
            payment_status TEXT DEFAULT 'pending',
            payment_date TEXT,
            eight_f_issued INTEGER DEFAULT 0,
            eight_f_number TEXT,
            eight_f_issued_date TEXT,
            created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
            aeo TEXT,
            FOREIGN KEY (establishment_id) REFERENCES establishments(id) ON DELETE CASCADE
        )
    """,
    "epfo_8f_records": """
        CREATE TABLE IF NOT EXISTS epfo_8f_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_account_id INTEGER NOT NULL,
            establishment_id INTEGER NOT NULL,
            est_id TEXT NOT NULL,
            est_name TEXT NOT NULL,
            aeo TEXT,
            eight_f_number TEXT,
            eight_f_issued_date TEXT,
            account_number TEXT,
            ifsc TEXT,
            bank_name TEXT,
            branch TEXT,
            address TEXT,
            city1 TEXT,
            city2 TEXT,
            district TEXT,
            state TEXT,
            phone TEXT,
            period TEXT,
            total_amount REAL,
            payment_status TEXT,
            amount_7a_ac1 REAL DEFAULT 0,
            amount_7a_ac2 REAL DEFAULT 0,
            amount_7a_ac10 REAL DEFAULT 0,
            amount_7a_ac21 REAL DEFAULT 0,
            amount_7a_ac22 REAL DEFAULT 0,
            amount_7a_total REAL DEFAULT 0,
            amount_7q_7a_ac1 REAL DEFAULT 0,
            amount_7q_7a_ac2 REAL DEFAULT 0,
            amount_7q_7a_ac10 REAL DEFAULT 0,
            amount_7q_7a_ac21 REAL DEFAULT 0,
            amount_7q_7a_ac22 REAL DEFAULT 0,
            amount_7q_7a_total REAL DEFAULT 0,
            amount_14b_ac1 REAL DEFAULT 0,
            amount_14b_ac2 REAL DEFAULT 0,
            amount_14b_ac10 REAL DEFAULT 0,
            amount_14b_ac21 REAL DEFAULT 0,
            amount_14b_ac22 REAL DEFAULT 0,
            amount_14b_total REAL DEFAULT 0,
            amount_7q_14b_ac1 REAL DEFAULT 0,
            amount_7q_14b_ac2 REAL DEFAULT 0,
            amount_7q_14b_ac10 REAL DEFAULT 0,
            amount_7q_14b_ac21 REAL DEFAULT 0,
            amount_7q_14b_ac22 REAL DEFAULT 0,
            amount_7q_14b_total REAL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
            FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id) ON DELETE CASCADE,
            FOREIGN KEY (establishment_id) REFERENCES establishments(id) ON DELETE CASCADE
        )
    """,
}

SCHEMA_POSTGRES = {
    "onboarded_users": """
        CREATE TABLE IF NOT EXISTS onboarded_users (
            id SERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT,
            date_of_birth TEXT,
            country TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
        )
    """,
    "establishments": """
        CREATE TABLE IF NOT EXISTS establishments (
            id SERIAL PRIMARY KEY,
            sr_no INTEGER,
            est_id TEXT UNIQUE,
            est_name TEXT NOT NULL,
            office TEXT,
            circle TEXT,
            aeo TEXT,
            phone TEXT
        )
    """,
    "bank_accounts": """
        CREATE TABLE IF NOT EXISTS bank_accounts (
            id SERIAL PRIMARY KEY,
            establishment_id INTEGER NOT NULL REFERENCES establishments(id) ON DELETE CASCADE,
            account_number TEXT NOT NULL,
            ifsc TEXT NOT NULL,
            code TEXT,
            bank_name TEXT NOT NULL,
            branch TEXT,
            address TEXT,
            city1 TEXT,
            city2 TEXT,
            district TEXT,
            state TEXT,
            phone TEXT,
            contact TEXT,
            period TEXT,
            amount_7a_ac1 DOUBLE PRECISION DEFAULT 0,
            amount_7a_ac2 DOUBLE PRECISION DEFAULT 0,
            amount_7a_ac10 DOUBLE PRECISION DEFAULT 0,
            amount_7a_ac21 DOUBLE PRECISION DEFAULT 0,
            amount_7a_ac22 DOUBLE PRECISION DEFAULT 0,
            amount_7a_total DOUBLE PRECISION DEFAULT 0,
            amount_7q_7a_ac1 DOUBLE PRECISION DEFAULT 0,
            amount_7q_7a_ac2 DOUBLE PRECISION DEFAULT 0,
            amount_7q_7a_ac10 DOUBLE PRECISION DEFAULT 0,
            amount_7q_7a_ac21 DOUBLE PRECISION DEFAULT 0,
            amount_7q_7a_ac22 DOUBLE PRECISION DEFAULT 0,
            amount_7q_7a_total DOUBLE PRECISION DEFAULT 0,
            amount_14b_ac1 DOUBLE PRECISION DEFAULT 0,
            amount_14b_ac2 DOUBLE PRECISION DEFAULT 0,
            amount_14b_ac10 DOUBLE PRECISION DEFAULT 0,
            amount_14b_ac21 DOUBLE PRECISION DEFAULT 0,
            amount_14b_ac22 DOUBLE PRECISION DEFAULT 0,
            amount_14b_total DOUBLE PRECISION DEFAULT 0,
            amount_7q_14b_ac1 DOUBLE PRECISION DEFAULT 0,
            amount_7q_14b_ac2 DOUBLE PRECISION DEFAULT 0,
            amount_7q_14b_ac10 DOUBLE PRECISION DEFAULT 0,
            amount_7q_14b_ac21 DOUBLE PRECISION DEFAULT 0,
            amount_7q_14b_ac22 DOUBLE PRECISION DEFAULT 0,
            amount_7q_14b_total DOUBLE PRECISION DEFAULT 0,
            total_amount DOUBLE PRECISION DEFAULT 0,
            payment_status TEXT DEFAULT 'pending',
            payment_date TEXT,
            eight_f_issued INTEGER DEFAULT 0,
            eight_f_number TEXT,
            eight_f_issued_date TEXT,
            created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
            aeo TEXT
        )
    """,
    "epfo_8f_records": """
        CREATE TABLE IF NOT EXISTS epfo_8f_records (
            id SERIAL PRIMARY KEY,
            bank_account_id INTEGER NOT NULL REFERENCES bank_accounts(id) ON DELETE CASCADE,
            establishment_id INTEGER NOT NULL REFERENCES establishments(id) ON DELETE CASCADE,
            est_id TEXT NOT NULL,
            est_name TEXT NOT NULL,
            aeo TEXT,
            eight_f_number TEXT,
            eight_f_issued_date TEXT,
            account_number TEXT,
            ifsc TEXT,
            bank_name TEXT,
            branch TEXT,
            address TEXT,
            city1 TEXT,
            city2 TEXT,
            district TEXT,
            state TEXT,
            phone TEXT,
            period TEXT,
            total_amount DOUBLE PRECISION,
            payment_status TEXT,
            amount_7a_ac1 DOUBLE PRECISION DEFAULT 0,
            amount_7a_ac2 DOUBLE PRECISION DEFAULT 0,
            amount_7a_ac10 DOUBLE PRECISION DEFAULT 0,
            amount_7a_ac21 DOUBLE PRECISION DEFAULT 0,
            amount_7a_ac22 DOUBLE PRECISION DEFAULT 0,
            amount_7a_total DOUBLE PRECISION DEFAULT 0,
            amount_7q_7a_ac1 DOUBLE PRECISION DEFAULT 0,
            amount_7q_7a_ac2 DOUBLE PRECISION DEFAULT 0,
            amount_7q_7a_ac10 DOUBLE PRECISION DEFAULT 0,
            amount_7q_7a_ac21 DOUBLE PRECISION DEFAULT 0,
            amount_7q_7a_ac22 DOUBLE PRECISION DEFAULT 0,
            amount_7q_7a_total DOUBLE PRECISION DEFAULT 0,
            amount_14b_ac1 DOUBLE PRECISION DEFAULT 0,
            amount_14b_ac2 DOUBLE PRECISION DEFAULT 0,
            amount_14b_ac10 DOUBLE PRECISION DEFAULT 0,
            amount_14b_ac21 DOUBLE PRECISION DEFAULT 0,
            amount_14b_ac22 DOUBLE PRECISION DEFAULT 0,
            amount_14b_total DOUBLE PRECISION DEFAULT 0,
            amount_7q_14b_ac1 DOUBLE PRECISION DEFAULT 0,
            amount_7q_14b_ac2 DOUBLE PRECISION DEFAULT 0,
            amount_7q_14b_ac10 DOUBLE PRECISION DEFAULT 0,
            amount_7q_14b_ac21 DOUBLE PRECISION DEFAULT 0,
            amount_7q_14b_ac22 DOUBLE PRECISION DEFAULT 0,
            amount_7q_14b_total DOUBLE PRECISION DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
        )
    """,
}


def init_db(db_path: str = DB_PATH) -> None:
    """Initialize database schema."""
    schema = SCHEMA_POSTGRES if USE_POSTGRES else SCHEMA_SQLITE
    if not USE_POSTGRES and not USE_TURSO:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        cur = conn.cursor()
        for table_name, ddl in schema.items():
            cur.execute(_translate_sql(ddl))
        conn.commit()


def _hash_password(password: str) -> str:
    import hashlib
    salt = os.getenv("PASSWORD_SALT", "onboarding-static-salt-change-me")
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def _validate(payload: dict) -> str | None:
    required = ("full_name", "email", "country", "password")
    for field in required:
        value = (payload.get(field) or "").strip()
        if not value:
            return f"Missing required field: {field}"
    email = payload["email"].strip()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return "Invalid email address"
    if len(payload["password"]) < 8:
        return "Password must be at least 8 characters"
    return None


# ============================================================
# ROUTES
# ============================================================

@app.route("/", methods=["GET"])
def index():
    return render_template("onboarding.html")


@app.route("/api/onboard", methods=["POST"])
def onboard():
    payload = request.get_json(silent=True) or request.form.to_dict()
    error = _validate(payload)
    if error:
        return jsonify({"status": "error", "message": error}), 400

    try:
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(
                _translate_sql(
                    "INSERT INTO onboarded_users (full_name, email, phone, date_of_birth, country, password_hash) VALUES (%s, %s, %s, %s, %s, %s)" if USE_POSTGRES
                    else "INSERT INTO onboarded_users (full_name, email, phone, date_of_birth, country, password_hash) VALUES (?, ?, ?, ?, ?, ?)"
                ),
                (
                    payload["full_name"].strip(),
                    payload["email"].strip().lower(),
                    (payload.get("phone") or "").strip() or None,
                    (payload.get("date_of_birth") or "").strip() or None,
                    payload["country"].strip(),
                    _hash_password(payload["password"]),
                ),
            )
            conn.commit()
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower() or "integrity" in type(e).__name__.lower():
            return jsonify({"status": "error", "message": "Email already registered"}), 409
        raise

    return jsonify({"status": "ok", "message": "Account created"}), 201


@app.route("/api/users", methods=["GET"])
def list_users():
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(_translate_sql("SELECT id, full_name, email, phone, date_of_birth, country, created_at FROM onboarded_users ORDER BY id DESC"))
        rows = [_row_dict(r) for r in cur.fetchall()]
    return jsonify(rows)


@app.route("/admin", methods=["GET"])
def admin():
    html = render_template("admin.html")
    return Response(html, headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})


@app.route("/bank", methods=["GET"])
def bank_page():
    html = render_template("bank.html")
    return Response(html, headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})


@app.route("/api/establishments", methods=["GET"])
def list_establishments():
    search = (request.args.get("q") or "").strip()
    limit_param = (request.args.get("limit") or "500").lower()
    limit = None if limit_param == "all" else min(max(int(limit_param), 1), 5000)
    with _connect() as conn:
        cur = conn.cursor()
        if search:
            like = f"%{search}%"
            if USE_POSTGRES:
                cur.execute(
                    "SELECT id, est_id, est_name, office, circle, aeo, phone FROM establishments WHERE est_name ILIKE %s OR est_id ILIKE %s OR office ILIKE %s OR circle ILIKE %s ORDER BY est_name",
                    (like, like, like, like),
                )
            else:
                cur.execute(
                    "SELECT id, est_id, est_name, office, circle, aeo, phone FROM establishments WHERE est_name LIKE ? OR est_id LIKE ? OR office LIKE ? OR circle LIKE ? ORDER BY est_name",
                    (like, like, like, like),
                )
        else:
            cur.execute("SELECT id, est_id, est_name, office, circle, aeo, phone FROM establishments ORDER BY sr_no")
        if limit is not None:
            rows = cur.fetchmany(limit)
        else:
            rows = cur.fetchall()
        data = [_row_dict(r) for r in rows]
    return jsonify(data)


@app.route("/api/bank-accounts", methods=["GET", "POST"])
def bank_accounts():
    if request.method == "GET":
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(_translate_sql("""
                SELECT b.id, b.establishment_id, b.account_number, b.ifsc,
                       b.code, b.bank_name, b.branch, b.address, b.city1, b.city2,
                       b.district, b.state, b.phone, b.contact, b.aeo, b.created_at,
                       b.period,
                       b.amount_7a_ac1, b.amount_7a_ac2, b.amount_7a_ac10, b.amount_7a_ac21, b.amount_7a_ac22, b.amount_7a_total,
                       b.amount_7q_7a_ac1, b.amount_7q_7a_ac2, b.amount_7q_7a_ac10, b.amount_7q_7a_ac21, b.amount_7q_7a_ac22, b.amount_7q_7a_total,
                       b.amount_14b_ac1, b.amount_14b_ac2, b.amount_14b_ac10, b.amount_14b_ac21, b.amount_14b_ac22, b.amount_14b_total,
                       b.amount_7q_14b_ac1, b.amount_7q_14b_ac2, b.amount_7q_14b_ac10, b.amount_7q_14b_ac21, b.amount_7q_14b_ac22, b.amount_7q_14b_total,
                       b.total_amount,
                       b.payment_status, b.payment_date, b.eight_f_issued,
                       b.eight_f_number, b.eight_f_issued_date,
                       e.est_id, e.est_name
                FROM bank_accounts b
                JOIN establishments e ON e.id = b.establishment_id
                ORDER BY b.id DESC
            """))
            data = [_row_dict(r) for r in cur.fetchall()]
        return jsonify(data)

    # POST
    payload = request.get_json(silent=True) or request.form.to_dict()
    payload = {k: ("" if v is None else str(v)) for k, v in payload.items()}
    required = ("establishment_id", "account_number", "ifsc", "bank_name")
    for field in required:
        if not payload.get(field, "").strip():
            return jsonify({"status": "error", "message": f"Missing {field}"}), 400
    ifsc = payload["ifsc"].strip().upper()
    if len(ifsc) != 11:
        return jsonify({"status": "error", "message": "IFSC must be 11 characters"}), 400
    account = payload["account_number"].strip()
    if not (6 <= len(account) <= 18) or not account.isdigit():
        return jsonify({"status": "error", "message": "Invalid account number"}), 400
    try:
        est_id = int(payload["establishment_id"])
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid establishment_id"}), 400

    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(_translate_sql("SELECT id FROM establishments WHERE id = %s" if USE_POSTGRES else "SELECT id FROM establishments WHERE id = ?"), (est_id,))
        if cur.fetchone() is None:
            return jsonify({"status": "error", "message": "Unknown establishment"}), 404

    sections = ["7a", "7q_7a", "14b", "7q_14b"]
    section_totals = {}
    section_amounts = {}
    for sec in sections:
        ac_vals = [_to_float(payload.get(f"amount_{sec}_ac1")),
                   _to_float(payload.get(f"amount_{sec}_ac2")),
                   _to_float(payload.get(f"amount_{sec}_ac10")),
                   _to_float(payload.get(f"amount_{sec}_ac21")),
                   _to_float(payload.get(f"amount_{sec}_ac22"))]
        section_amounts[sec] = ac_vals
        section_totals[sec] = sum(ac_vals)
    total_amount = _to_float(payload.get("total_amount")) or sum(section_totals.values())
    payment_status = (payload.get("payment_status") or "pending").strip().lower()
    if payment_status not in {"paid", "pending"}:
        payment_status = "pending"
    eight_f_issued = 1 if str(payload.get("eight_f_issued")).lower() in {"1", "true", "on", "yes"} else 0
    eight_f_number = (payload.get("eight_f_number") or "").strip() or None
    eight_f_issued_date = (payload.get("eight_f_issued_date") or "").strip() or None

    try:
        with _connect() as conn:
            cur = conn.cursor()
            insert_cols = "establishment_id, account_number, ifsc, code, bank_name, branch, address, city1, city2, district, state, phone, contact, aeo, period, amount_7a_ac1, amount_7a_ac2, amount_7a_ac10, amount_7a_ac21, amount_7a_ac22, amount_7a_total, amount_7q_7a_ac1, amount_7q_7a_ac2, amount_7q_7a_ac10, amount_7q_7a_ac21, amount_7q_7a_ac22, amount_7q_7a_total, amount_14b_ac1, amount_14b_ac2, amount_14b_ac10, amount_14b_ac21, amount_14b_ac22, amount_14b_total, amount_7q_14b_ac1, amount_7q_14b_ac2, amount_7q_14b_ac10, amount_7q_14b_ac21, amount_7q_14b_ac22, amount_7q_14b_total, total_amount, payment_status, payment_date, eight_f_issued, eight_f_number, eight_f_issued_date"
            placeholders = ", ".join(["%s" if USE_POSTGRES else "?"] * 45)
            insert_sql = f"INSERT INTO bank_accounts ({insert_cols}) VALUES ({placeholders})"
            if USE_POSTGRES:
                insert_sql += " RETURNING id"
            values = (
                est_id, account, ifsc,
                (payload.get("code") or "").strip() or None,
                payload["bank_name"].strip(),
                (payload.get("branch") or "").strip() or None,
                (payload.get("address") or "").strip() or None,
                (payload.get("city1") or "").strip() or None,
                (payload.get("city2") or "").strip() or None,
                (payload.get("district") or "").strip() or None,
                (payload.get("state") or "").strip() or None,
                (payload.get("phone") or "").strip() or None,
                (payload.get("contact") or "").strip() or None,
                (payload.get("aeo") or "").strip() or None,
                (payload.get("period") or "").strip() or None,
                *section_amounts["7a"], section_totals["7a"],
                *section_amounts["7q_7a"], section_totals["7q_7a"],
                *section_amounts["14b"], section_totals["14b"],
                *section_amounts["7q_14b"], section_totals["7q_14b"],
                total_amount, payment_status,
                (payload.get("payment_date") or "").strip() or None,
                eight_f_issued, eight_f_number, eight_f_issued_date,
            )
            cur.execute(insert_sql, values)
            if USE_POSTGRES:
                row = cur.fetchone()
                bank_id = row["id"] if row else None
            else:
                bank_id = cur.lastrowid
            if eight_f_issued:
                epfo_cols = "bank_account_id, establishment_id, est_id, est_name, aeo, eight_f_number, eight_f_issued_date, account_number, ifsc, bank_name, branch, address, city1, city2, district, state, phone, period, total_amount, payment_status, amount_7a_ac1, amount_7a_ac2, amount_7a_ac10, amount_7a_ac21, amount_7a_ac22, amount_7a_total, amount_7q_7a_ac1, amount_7q_7a_ac2, amount_7q_7a_ac10, amount_7q_7a_ac21, amount_7q_7a_ac22, amount_7q_7a_total, amount_14b_ac1, amount_14b_ac2, amount_14b_ac10, amount_14b_ac21, amount_14b_ac22, amount_14b_total, amount_7q_14b_ac1, amount_7q_14b_ac2, amount_7q_14b_ac10, amount_7q_14b_ac21, amount_7q_14b_ac22, amount_7q_14b_total"
                epfo_placeholders = ", ".join(["%s" if USE_POSTGRES else "?"] * 44)
                epfo_sql = f"INSERT INTO epfo_8f_records ({epfo_cols}) VALUES ({epfo_placeholders})"
                epfo_values = (
                    bank_id, est_id,
                    (payload.get("est_id") or "").strip(),
                    (payload.get("est_name") or "").strip(),
                    (payload.get("aeo") or "").strip() or None,
                    eight_f_number, eight_f_issued_date,
                    account, ifsc,
                    payload["bank_name"].strip(),
                    (payload.get("branch") or "").strip() or None,
                    (payload.get("address") or "").strip() or None,
                    (payload.get("city1") or "").strip() or None,
                    (payload.get("city2") or "").strip() or None,
                    (payload.get("district") or "").strip() or None,
                    (payload.get("state") or "").strip() or None,
                    (payload.get("phone") or "").strip() or None,
                    (payload.get("period") or "").strip() or None,
                    total_amount, payment_status,
                    *section_amounts["7a"], section_totals["7a"],
                    *section_amounts["7q_7a"], section_totals["7q_7a"],
                    *section_amounts["14b"], section_totals["14b"],
                    *section_amounts["7q_14b"], section_totals["7q_14b"],
                )
                cur.execute(epfo_sql, epfo_values)
            conn.commit()
    except Exception as e:
        msg = str(e).lower()
        if "foreign key" in msg or "fk_" in msg or "violates" in msg:
            return jsonify({"status": "error", "message": "Unknown establishment"}), 404
        if "unique" in msg or "integrity" in type(e).__name__.lower() or "constraint" in msg:
            return jsonify({"status": "error", "message": f"Integrity error: {e}"}), 400
        raise

    return jsonify({"status": "ok", "message": "Bank details saved", "id": bank_id}), 201


@app.route("/api/bank-accounts/<int:bank_id>", methods=["GET", "PUT", "DELETE"])
def bank_account_detail(bank_id: int):
    if request.method == "GET":
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(_translate_sql("""
                SELECT b.id, b.establishment_id, b.account_number, b.ifsc,
                       b.code, b.bank_name, b.branch, b.address, b.city1, b.city2,
                       b.district, b.state, b.phone, b.contact, b.aeo, b.created_at,
                       e.est_id, e.est_name
                FROM bank_accounts b
                JOIN establishments e ON e.id = b.establishment_id
                WHERE b.id = %s
            """ if USE_POSTGRES else """
                SELECT b.id, b.establishment_id, b.account_number, b.ifsc,
                       b.code, b.bank_name, b.branch, b.address, b.city1, b.city2,
                       b.district, b.state, b.phone, b.contact, b.aeo, b.created_at,
                       e.est_id, e.est_name
                FROM bank_accounts b
                JOIN establishments e ON e.id = b.establishment_id
                WHERE b.id = ?
            """), (bank_id,))
            row = cur.fetchone()
            if row is None:
                return jsonify({"status": "error", "message": "Not found"}), 404
            return jsonify(_row_dict(row))

    if request.method == "DELETE":
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(_translate_sql("DELETE FROM bank_accounts WHERE id = %s" if USE_POSTGRES else "DELETE FROM bank_accounts WHERE id = ?"), (bank_id,))
            conn.commit()
            if cur.rowcount == 0:
                return jsonify({"status": "error", "message": "Not found"}), 404
        return jsonify({"status": "ok", "message": "Deleted"})

    # PUT
    payload = request.get_json(silent=True) or request.form.to_dict()
    payload = {k: ("" if v is None else str(v)) for k, v in payload.items()}
    required = ("account_number", "ifsc", "bank_name")
    for field in required:
        if not payload.get(field, "").strip():
            return jsonify({"status": "error", "message": f"Missing {field}"}), 400
    ifsc = payload["ifsc"].strip().upper()
    if len(ifsc) != 11:
        return jsonify({"status": "error", "message": "IFSC must be 11 characters"}), 400
    account = payload["account_number"].strip()
    if not (6 <= len(account) <= 18) or not account.isdigit():
        return jsonify({"status": "error", "message": "Invalid account number"}), 400

    sections = ["7a", "7q_7a", "14b", "7q_14b"]
    section_totals = {}
    section_amounts = {}
    for sec in sections:
        ac_vals = [_to_float(payload.get(f"amount_{sec}_ac1")),
                   _to_float(payload.get(f"amount_{sec}_ac2")),
                   _to_float(payload.get(f"amount_{sec}_ac10")),
                   _to_float(payload.get(f"amount_{sec}_ac21")),
                   _to_float(payload.get(f"amount_{sec}_ac22"))]
        section_amounts[sec] = ac_vals
        section_totals[sec] = sum(ac_vals)
    total_amount = _to_float(payload.get("total_amount")) or sum(section_totals.values())

    ph = "%s" if USE_POSTGRES else "?"
    update_sql = f"""UPDATE bank_accounts SET
        account_number = {ph}, ifsc = {ph}, bank_name = {ph}, branch = {ph}, address = {ph},
        city1 = {ph}, city2 = {ph}, district = {ph}, state = {ph}, phone = {ph}, contact = {ph},
        aeo = {ph}, period = {ph},
        amount_7a_ac1 = {ph}, amount_7a_ac2 = {ph}, amount_7a_ac10 = {ph}, amount_7a_ac21 = {ph}, amount_7a_ac22 = {ph}, amount_7a_total = {ph},
        amount_7q_7a_ac1 = {ph}, amount_7q_7a_ac2 = {ph}, amount_7q_7a_ac10 = {ph}, amount_7q_7a_ac21 = {ph}, amount_7q_7a_ac22 = {ph}, amount_7q_7a_total = {ph},
        amount_14b_ac1 = {ph}, amount_14b_ac2 = {ph}, amount_14b_ac10 = {ph}, amount_14b_ac21 = {ph}, amount_14b_ac22 = {ph}, amount_14b_total = {ph},
        amount_7q_14b_ac1 = {ph}, amount_7q_14b_ac2 = {ph}, amount_7q_14b_ac10 = {ph}, amount_7q_14b_ac21 = {ph}, amount_7q_14b_ac22 = {ph}, amount_7q_14b_total = {ph},
        total_amount = {ph}, payment_status = {ph}, payment_date = {ph}, eight_f_issued = {ph},
        eight_f_number = {ph}, eight_f_issued_date = {ph}
        WHERE id = {ph}"""

    update_values = (
        account, ifsc, payload["bank_name"].strip(),
        (payload.get("branch") or "").strip() or None,
        (payload.get("address") or "").strip() or None,
        (payload.get("city1") or "").strip() or None,
        (payload.get("city2") or "").strip() or None,
        (payload.get("district") or "").strip() or None,
        (payload.get("state") or "").strip() or None,
        (payload.get("phone") or "").strip() or None,
        (payload.get("contact") or "").strip() or None,
        (payload.get("aeo") or "").strip() or None,
        (payload.get("period") or "").strip() or None,
        *section_amounts["7a"], section_totals["7a"],
        *section_amounts["7q_7a"], section_totals["7q_7a"],
        *section_amounts["14b"], section_totals["14b"],
        *section_amounts["7q_14b"], section_totals["7q_14b"],
        total_amount,
        (payload.get("payment_status") or "pending").strip().lower(),
        (payload.get("payment_date") or "").strip() or None,
        1 if str(payload.get("eight_f_issued")).lower() in {"1", "true", "on", "yes"} else 0,
        (payload.get("eight_f_number") or "").strip() or None,
        (payload.get("eight_f_issued_date") or "").strip() or None,
        bank_id,
    )

    try:
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(update_sql, update_values)
            cur.execute(_translate_sql(f"SELECT eight_f_issued, establishment_id FROM bank_accounts WHERE id = {ph}"), (bank_id,))
            row = cur.fetchone()
            was_issued = _row_dict(row) if row else None
            if was_issued and not was_issued.get("eight_f_issued") and str(payload.get("eight_f_issued")).lower() in {"1", "true", "on", "yes"}:
                cur.execute(_translate_sql(f"SELECT est_id, est_name FROM establishments WHERE id = {ph}"), (was_issued["establishment_id"],))
                est_row = _row_dict(cur.fetchone())
                epfo_cols = "bank_account_id, establishment_id, est_id, est_name, aeo, eight_f_number, eight_f_issued_date, account_number, ifsc, bank_name, branch, address, city1, city2, district, state, phone, period, total_amount, payment_status, amount_7a_ac1, amount_7a_ac2, amount_7a_ac10, amount_7a_ac21, amount_7a_ac22, amount_7a_total, amount_7q_7a_ac1, amount_7q_7a_ac2, amount_7q_7a_ac10, amount_7q_7a_ac21, amount_7q_7a_ac22, amount_7q_7a_total, amount_14b_ac1, amount_14b_ac2, amount_14b_ac10, amount_14b_ac21, amount_14b_ac22, amount_14b_total, amount_7q_14b_ac1, amount_7q_14b_ac2, amount_7q_14b_ac10, amount_7q_14b_ac21, amount_7q_14b_ac22, amount_7q_14b_total"
                epfo_placeholders = ", ".join([ph] * 44)
                epfo_sql = f"INSERT INTO epfo_8f_records ({epfo_cols}) VALUES ({epfo_placeholders})"
                epfo_values = (
                    bank_id, was_issued["establishment_id"],
                    est_row.get("est_id", "") if est_row else "",
                    est_row.get("est_name", "") if est_row else "",
                    (payload.get("aeo") or "").strip() or None,
                    (payload.get("eight_f_number") or "").strip() or None,
                    (payload.get("eight_f_issued_date") or "").strip() or None,
                    account, ifsc, payload["bank_name"].strip(),
                    (payload.get("branch") or "").strip() or None,
                    (payload.get("address") or "").strip() or None,
                    (payload.get("city1") or "").strip() or None,
                    (payload.get("city2") or "").strip() or None,
                    (payload.get("district") or "").strip() or None,
                    (payload.get("state") or "").strip() or None,
                    (payload.get("phone") or "").strip() or None,
                    (payload.get("period") or "").strip() or None,
                    _to_float(payload.get("total_amount")),
                    (payload.get("payment_status") or "pending").strip().lower(),
                    *section_amounts["7a"], section_totals["7a"],
                    *section_amounts["7q_7a"], section_totals["7q_7a"],
                    *section_amounts["14b"], section_totals["14b"],
                    *section_amounts["7q_14b"], section_totals["7q_14b"],
                )
                cur.execute(epfo_sql, epfo_values)
            conn.commit()
            if cur.rowcount == 0:
                return jsonify({"status": "error", "message": "Not found"}), 404
    except Exception as e:
        msg = str(e).lower()
        if "foreign key" in msg or "violates" in msg:
            return jsonify({"status": "error", "message": "Unknown establishment"}), 404
        raise
    return jsonify({"status": "ok", "message": "Updated"})


@app.route("/api/epfo-8f", methods=["GET"])
def list_epfo_8f():
    with _connect() as conn:
        cur = conn.cursor()
        cols = "id, bank_account_id, establishment_id, est_id, est_name, eight_f_number, eight_f_issued_date, account_number, ifsc, bank_name, branch, address, city1, city2, district, state, phone, period, total_amount, payment_status, created_at, aeo, amount_7a_ac1, amount_7a_ac2, amount_7a_ac10, amount_7a_ac21, amount_7a_ac22, amount_7a_total, amount_7q_7a_ac1, amount_7q_7a_ac2, amount_7q_7a_ac10, amount_7q_7a_ac21, amount_7q_7a_ac22, amount_7q_7a_total, amount_14b_ac1, amount_14b_ac2, amount_14b_ac10, amount_14b_ac21, amount_14b_ac22, amount_14b_total, amount_7q_14b_ac1, amount_7q_14b_ac2, amount_7q_14b_ac10, amount_7q_14b_ac21, amount_7q_14b_ac22, amount_7q_14b_total"
        cur.execute(_translate_sql(f"SELECT {cols} FROM epfo_8f_records ORDER BY id DESC"))
        rows1 = [_row_dict(r) for r in cur.fetchall()]
        if USE_POSTGRES:
            cur.execute(_translate_sql(f"""
                SELECT b.id + 1000000 AS id, b.id AS bank_account_id, b.establishment_id,
                       e.est_id, e.est_name, b.eight_f_number, b.eight_f_issued_date,
                       b.account_number, b.ifsc, b.bank_name, b.branch, b.address,
                       b.city1, b.city2, b.district, b.state, b.phone, b.period,
                       b.total_amount, b.payment_status, b.created_at, b.aeo,
                       b.amount_7a_ac1, b.amount_7a_ac2, b.amount_7a_ac10, b.amount_7a_ac21, b.amount_7a_ac22, b.amount_7a_total,
                       b.amount_7q_7a_ac1, b.amount_7q_7a_ac2, b.amount_7q_7a_ac10, b.amount_7q_7a_ac21, b.amount_7q_7a_ac22, b.amount_7q_7a_total,
                       b.amount_14b_ac1, b.amount_14b_ac2, b.amount_14b_ac10, b.amount_14b_ac21, b.amount_14b_ac22, b.amount_14b_total,
                       b.amount_7q_14b_ac1, b.amount_7q_14b_ac2, b.amount_7q_14b_ac10, b.amount_7q_14b_ac21, b.amount_7q_14b_ac22, b.amount_7q_14b_total
                FROM bank_accounts b
                JOIN establishments e ON e.id = b.establishment_id
                WHERE b.eight_f_issued = 1
                  AND NOT EXISTS (SELECT 1 FROM epfo_8f_records r WHERE r.bank_account_id = b.id)
                ORDER BY b.id DESC
            """))
        else:
            cur.execute(_translate_sql(f"""
                SELECT b.id + 1000000 AS id, b.id AS bank_account_id, b.establishment_id,
                       e.est_id, e.est_name, b.eight_f_number, b.eight_f_issued_date,
                       b.account_number, b.ifsc, b.bank_name, b.branch, b.address,
                       b.city1, b.city2, b.district, b.state, b.phone, b.period,
                       b.total_amount, b.payment_status, b.created_at, b.aeo,
                       b.amount_7a_ac1, b.amount_7a_ac2, b.amount_7a_ac10, b.amount_7a_ac21, b.amount_7a_ac22, b.amount_7a_total,
                       b.amount_7q_7a_ac1, b.amount_7q_7a_ac2, b.amount_7q_7a_ac10, b.amount_7q_7a_ac21, b.amount_7q_7a_ac22, b.amount_7q_7a_total,
                       b.amount_14b_ac1, b.amount_14b_ac2, b.amount_14b_ac10, b.amount_14b_ac21, b.amount_14b_ac22, b.amount_14b_total,
                       b.amount_7q_14b_ac1, b.amount_7q_14b_ac2, b.amount_7q_14b_ac10, b.amount_7q_14b_ac21, b.amount_7q_14b_ac22, b.amount_7q_14b_total
                FROM bank_accounts b
                JOIN establishments e ON e.id = b.establishment_id
                WHERE b.eight_f_issued = 1
                  AND NOT EXISTS (SELECT 1 FROM epfo_8f_records r WHERE r.bank_account_id = b.id)
                ORDER BY b.id DESC
            """))
        rows2 = [_row_dict(r) for r in cur.fetchall()]
    return jsonify(rows1 + rows2)


def _fmt_money(v):
    if v is None or v == "":
        return "—"
    try:
        return f"Rs. {float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v)


def _fmt_date(v):
    if not v:
        return "—"
    s = str(v)
    if len(s) >= 10:
        return s[:10]
    return s


def _fmt_address(addr):
    """Return only the first line of the address to keep PDF compact."""
    if not addr:
        return "—"
    s = str(addr).split(",")[0].strip()
    return s if s else "—"


def _para(text, style_name="cell"):
    """Wrap text in a Paragraph so reportlab auto-wraps it."""
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph
    style = ParagraphStyle(style_name, fontSize=7, leading=8, wordWrap="CJK")
    return Paragraph(str(text or ""), style)


@app.route("/api/export-pdf", methods=["GET"])
def export_pdf():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from io import BytesIO

    tab = (request.args.get("tab") or "bank").lower()
    sort_key = (request.args.get("sort") or "est_id").strip()

    sort_map = {
        "est_id": ("est_id", False),
        "est_name": ("est_name", False),
        "ifsc": ("ifsc", False),
        "bank": ("bank_name", False),
        "branch": ("branch", False),
        "amount": ("total_amount", True),
        "aeo": ("aeo", False),
        "period": ("period", False),
    }
    col, reverse = sort_map.get(sort_key, ("est_id", False))

    with _connect() as conn:
        cur = conn.cursor()
        if tab == "8f":
            if USE_POSTGRES:
                cur.execute("""
                    SELECT b.id + 1000000 AS id, e.est_id, e.est_name, b.aeo,
                           b.eight_f_number, b.eight_f_issued_date, b.account_number, b.ifsc,
                           b.bank_name, b.branch, b.address, b.period, b.total_amount, b.payment_status,
                           b.amount_7a_total, b.amount_7q_7a_total, b.amount_14b_total, b.amount_7q_14b_total
                    FROM bank_accounts b
                    JOIN establishments e ON e.id = b.establishment_id
                    WHERE b.eight_f_issued = 1
                    ORDER BY b.id DESC
                """)
            else:
                cur.execute("""
                    SELECT b.id + 1000000 AS id, e.est_id, e.est_name, b.aeo,
                           b.eight_f_number, b.eight_f_issued_date, b.account_number, b.ifsc,
                           b.bank_name, b.branch, b.address, b.period, b.total_amount, b.payment_status,
                           b.amount_7a_total, b.amount_7q_7a_total, b.amount_14b_total, b.amount_7q_14b_total
                    FROM bank_accounts b
                    JOIN establishments e ON e.id = b.establishment_id
                    WHERE b.eight_f_issued = 1
                    ORDER BY b.id DESC
                """)
            records = [_row_dict(r) for r in cur.fetchall()]
            records.sort(key=lambda r: (r.get(col) or ""), reverse=reverse)

            headers = ["#", "Est Code", "Establishment", "AEO", "Period", "7A", "7Q(7A)", "14B", "7Q(14B)",
                       "Grand Total", "8F No", "8F Date", "Bank", "IFSC", "A/c No", "Status"]
            rows = [[str(i+1), r.get("est_id",""), Paragraph(str(r.get("est_name","") or ""), ParagraphStyle("cell", fontSize=7)),
                     r.get("aeo",""), r.get("period",""), _fmt_money(r.get("amount_7a_total")),
                     _fmt_money(r.get("amount_7q_7a_total")), _fmt_money(r.get("amount_14b_total")),
                     _fmt_money(r.get("amount_7q_14b_total")), _fmt_money(r.get("total_amount")),
                     r.get("eight_f_number",""), _fmt_date(r.get("eight_f_issued_date")),
                     r.get("bank_name",""), r.get("ifsc",""), r.get("account_number",""),
                     (r.get("payment_status","") or "").upper()] for i, r in enumerate(records)]
            title = "8F Issued Records"
        else:
            cur.execute("""
                SELECT b.id, b.account_number, b.ifsc, b.bank_name, b.branch, b.address,
                       b.period, b.total_amount, b.payment_status, b.eight_f_issued,
                       b.eight_f_number, b.eight_f_issued_date, b.aeo,
                       e.est_id, e.est_name
                FROM bank_accounts b
                JOIN establishments e ON e.id = b.establishment_id
            """)
            records = [_row_dict(r) for r in cur.fetchall()]
            records.sort(key=lambda r: (r.get(col) or ""), reverse=reverse)

            headers = ["#", "Est Code", "Establishment", "AEO", "IFSC", "Bank", "Branch",
                       "A/c No", "Address", "Period", "Total", "Payment", "8F No", "8F Date"]
            rows = [[str(i+1), r.get("est_id",""), Paragraph(str(r.get("est_name","") or ""), ParagraphStyle("cell", fontSize=7)),
                     r.get("aeo",""), r.get("ifsc",""), r.get("bank_name",""), r.get("branch",""),
                     r.get("account_number",""), Paragraph(str(r.get("address","") or ""), ParagraphStyle("cell", fontSize=7)),
                     r.get("period",""), _fmt_money(r.get("total_amount")),
                     (r.get("payment_status","") or "").upper(),
                     r.get("eight_f_number","") if r.get("eight_f_issued") else "—",
                     _fmt_date(r.get("eight_f_issued_date")) if r.get("eight_f_issued") else "—"] for i, r in enumerate(records)]
            title = "Entered Bank Accounts"

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                            leftMargin=8*mm, rightMargin=8*mm, topMargin=10*mm, bottomMargin=10*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Title"], fontSize=14, spaceAfter=4)
    sub_style = ParagraphStyle("sub", parent=styles["Normal"], fontSize=8, textColor=colors.grey, spaceAfter=8)

    elements = [Paragraph(title, title_style),
                Paragraph(f"Sorted by: {sort_key} &middot; {len(records)} record(s)", sub_style)]

    data = [headers] + rows
    col_count = len(headers)
    avail = 281 * mm
    if tab == "8f":
        widths = [8, 24, 36, 22, 18, 16, 16, 16, 16, 20, 14, 18, 22, 18, 20, 16]
    else:
        widths = [8, 24, 36, 22, 18, 22, 20, 24, 40, 18, 18, 14, 14, 16]
    total_w = sum(widths)
    if total_w > 0:
        scale = avail / total_w
        widths = [w * scale for w in widths]

    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#4c51bf")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 7),
        ("ALIGN", (0,0), (-1,0), "CENTER"),
        ("BOTTOMPADDING", (0,0), (-1,0), 5),
        ("TOPPADDING", (0,0), (-1,0), 5),
        ("BACKGROUND", (0,1), (-1,-1), colors.beige),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8f9fc")]),
        ("FONTSIZE", (0,1), (-1,-1), 7),
        ("ALIGN", (0,1), (0,-1), "CENTER"),
        ("ALIGN", (5,1), (-1,-1), "LEFT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("GRID", (0,0), (-1,-1), 0.3, colors.grey),
        ("LEFTPADDING", (0,0), (-1,-1), 3),
        ("RIGHTPADDING", (0,0), (-1,-1), 3),
    ]))
    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    filename = f"{tab}_sorted_by_{sort_key}.pdf"
    return Response(
        buffer.getvalue(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"',
                 "Cache-Control": "no-store"},
    )


@app.route("/api/ifsc/<code>", methods=["GET"])
def ifsc_lookup(code: str):
    code = (code or "").strip().upper()
    if len(code) != 11:
        return jsonify({"status": "error", "message": "IFSC must be 11 characters"}), 400
    url = f"https://ifsc.razorpay.com/{code}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "onboarding-app/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError:
        return jsonify({"status": "error", "message": "IFSC not found"}), 404
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        return jsonify({"status": "error", "message": f"Lookup failed: {error}"}), 502
    return jsonify({
        "ifsc": data.get("IFSC", code),
        "bank": data.get("BANK", ""),
        "branch": data.get("BRANCH", ""),
        "address": data.get("ADDRESS", ""),
        "city1": data.get("CITY1", ""),
        "city2": data.get("CITY2", ""),
        "district": data.get("DISTRICT", ""),
        "state": data.get("STATE", ""),
        "phone": data.get("PHONE", ""),
        "contact": data.get("CONTACT", ""),
    })


if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
