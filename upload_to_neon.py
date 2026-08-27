"""Upload local SQLite data to Neon PostgreSQL.
Usage: python upload_to_neon.py
Reads DATABASE_URL from environment.
"""
import os
import sys
import psycopg2
import psycopg2.extras
import sqlite3


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    sys.exit(1)

LOCAL_DB = "logs/onboarding.sqlite3"


def get_sqlite_columns(local, table):
    return [r[1] for r in local.execute(f"PRAGMA table_info({table})").fetchall()]


def upload_table(pg_conn, local, table_name):
    """Upload one table from SQLite to PostgreSQL using COPY/executemany."""
    print(f"\n--- Uploading {table_name} ---", flush=True)
    cols = get_sqlite_columns(local, table_name)
    if not cols:
        print(f"  Table not found locally, skipping", flush=True)
        return 0

    rows = local.execute(f"SELECT * FROM {table_name}").fetchall()
    if not rows:
        print(f"  0 rows, skipping", flush=True)
        return 0

    print(f"  Found {len(rows)} rows, {len(cols)} columns", flush=True)

    # Clear existing data
    cur = pg_conn.cursor()
    cur.execute(f"DELETE FROM {table_name}")
    print("  Cleared existing data", flush=True)

    # Insert using execute_batch for speed
    col_list = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(cols))
    insert_sql = f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})"

    # Convert rows to tuples - SQLite rows support both index and key access
    # Use column names to get values via __getitem__
    data = []
    for row in rows:
        values = []
        for c in cols:
            try:
                values.append(row[c])
            except (IndexError, KeyError):
                values.append(None)
        data.append(tuple(values))

    # Use execute_batch for efficient bulk insert
    psycopg2.extras.execute_batch(cur, insert_sql, data, page_size=1000)
    pg_conn.commit()
    print(f"  Inserted {len(data)} rows", flush=True)
    return len(data)


def main():
    print(f"Connecting to Neon PostgreSQL...", flush=True)
    pg = psycopg2.connect(DATABASE_URL)
    print("Connected!", flush=True)

    # Create tables using the same schema as app.py
    print("\nCreating tables...", flush=True)
    schema_sql = [
        """CREATE TABLE IF NOT EXISTS onboarded_users (
            id SERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT,
            date_of_birth TEXT,
            country TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)::text
        )""",
        """CREATE TABLE IF NOT EXISTS establishments (
            id SERIAL PRIMARY KEY,
            sr_no INTEGER,
            est_id TEXT UNIQUE,
            est_name TEXT NOT NULL,
            office TEXT,
            circle TEXT,
            aeo TEXT,
            phone TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS bank_accounts (
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
            created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)::text,
            aeo TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS epfo_8f_records (
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
            created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)::text
        )""",
    ]
    cur = pg.cursor()
    for stmt in schema_sql:
        cur.execute(stmt)
    pg.commit()
    print("Tables created", flush=True)

    # Open local SQLite
    local = sqlite3.connect(LOCAL_DB)
    local.row_factory = sqlite3.Row

    # Upload data
    upload_table(pg, local, "establishments")
    upload_table(pg, local, "onboarded_users")
    upload_table(pg, local, "bank_accounts")
    upload_table(pg, local, "epfo_8f_records")

    local.close()
    pg.close()
    print("\nUpload complete!", flush=True)


if __name__ == "__main__":
    main()