"""Upload local SQLite database to Turso using HTTP API (no extra packages needed).
Usage: python upload_to_turso.py <TURSO_TOKEN>
"""
import sys
import json
import sqlite3
import urllib.request
import urllib.error


TURSO_URL = "libsql://bank-account-db-epfraghu.aws-ap-south-1.turso.io"


def execute_sql(turso_token, statements, timeout=60):
    """Execute SQL statements via Turso HTTP API.
    statements: list of {"sql": "...", "args": [{"type": "text", "value": "..."}, ...]}
    """
    url = "https://" + TURSO_URL.replace("libsql://", "") + "/v2/pipeline"
    payload = {"requests": [{"type": "execute", "stmt": s} for s in statements]}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {turso_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP Error {e.code}: {body[:500]}")
        raise


def _to_turso_arg(value):
    """Convert a Python value to Turso's typed argument format."""
    if value is None:
        return {"type": "null", "value": None}
    if isinstance(value, bool):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        # Turso expects float value as a JSON number, not a string
        return {"type": "float", "value": value}
    # Default: text
    return {"type": "text", "value": str(value)}


def upload_table(turso_token, local_db, table_name, batch_size=100):
    """Upload one table from local SQLite to Turso."""
    print(f"\n--- Uploading {table_name} ---", flush=True)
    local = sqlite3.connect(local_db)
    local.row_factory = sqlite3.Row

    cols_info = local.execute(f"PRAGMA table_info({table_name})").fetchall()
    if not cols_info:
        print(f"  Table {table_name} not found locally, skipping", flush=True)
        local.close()
        return 0

    cols = [r[1] for r in cols_info]
    rows = local.execute(f"SELECT * FROM {table_name}").fetchall()
    if not rows:
        print(f"  0 rows, skipping", flush=True)
        local.close()
        return 0

    print(f"  Found {len(rows)} rows, {len(cols)} columns", flush=True)

    # Delete existing rows
    print("  Deleting existing rows...", flush=True)
    execute_sql(turso_token, [{"sql": f"DELETE FROM {table_name}"}])

    # Insert in batches
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        statements = []
        for row in batch:
            values = [row[c] for c in cols]
            args = [_to_turso_arg(v) for v in values]
            placeholders = ", ".join(["?"] * len(cols))
            col_list = ", ".join(cols)
            statements.append({
                "sql": f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})",
                "args": args,
            })
        execute_sql(turso_token, statements)
        total += len(batch)
        if total % 1000 == 0 or total == len(rows):
            print(f"  Uploaded {total}/{len(rows)} rows...", flush=True)

    local.close()
    print(f"  Done: {total} rows uploaded", flush=True)
    return total


def main():
    if len(sys.argv) < 2:
        print("Usage: python upload_to_turso.py <TURSO_TOKEN>")
        sys.exit(1)

    turso_token = sys.argv[1]
    local_db = "logs/onboarding.sqlite3"

    # Test connection
    print(f"Testing connection to {TURSO_URL}...", flush=True)
    try:
        result = execute_sql(turso_token, [{"sql": "SELECT 1 AS test"}])
        print(f"Connection OK", flush=True)
    except Exception as e:
        print(f"Connection failed: {e}", flush=True)
        sys.exit(1)

    # Create tables (if not exist)
    print("\nCreating tables (if not exist)...", flush=True)

    create_statements = [
        """CREATE TABLE IF NOT EXISTS establishments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sr_no INTEGER,
            est_id TEXT UNIQUE,
            est_name TEXT NOT NULL,
            office TEXT,
            circle TEXT,
            aeo TEXT,
            phone TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS onboarded_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT,
            date_of_birth TEXT,
            country TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS bank_accounts (
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
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            aeo TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS epfo_8f_records (
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
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
    ]

    for stmt in create_statements:
        try:
            execute_sql(turso_token, [{"sql": stmt}])
        except Exception as e:
            print(f"  Table creation warning: {e}", flush=True)

    # Upload data
    upload_table(turso_token, local_db, "establishments")
    upload_table(turso_token, local_db, "onboarded_users")
    upload_table(turso_token, local_db, "bank_accounts")
    upload_table(turso_token, local_db, "epfo_8f_records")

    # Verify
    print("\n--- Verification ---", flush=True)
    for table in ["establishments", "onboarded_users", "bank_accounts", "epfo_8f_records"]:
        try:
            result = execute_sql(turso_token, [{"sql": f"SELECT COUNT(*) FROM {table}"}])
            rows = result["results"][0]["response"]["result"]["rows"]
            cnt = rows[0][0]["value"] if rows else "?"
            print(f"  {table}: {cnt} rows", flush=True)
        except Exception as e:
            print(f"  {table}: error - {e}", flush=True)

    print("\nUpload complete!", flush=True)


if __name__ == "__main__":
    main()