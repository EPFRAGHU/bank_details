"""Upload local SQLite database to Turso.
Usage: python upload_to_turso.py <TURSO_URL> <TURSO_TOKEN>
"""
import sys
import sqlite3

def upload_to_turso(turso_url, turso_token, local_db_path="logs/onboarding.sqlite3"):
    """Upload local SQLite data to Turso by reading and inserting all rows."""
    try:
        import libsql_experimental as libsql
    except ImportError:
        import libsql

    print(f"Connecting to Turso: {turso_url}")
    conn = libsql.connect(turso_url, auth_token=turso_token)
    cur = conn.cursor()

    # Read local database
    print(f"Reading local database: {local_db_path}")
    local = sqlite3.connect(local_db_path)
    local.row_factory = sqlite3.Row

    tables = ["establishments", "onboarded_users", "bank_accounts", "epfo_8f_records"]
    for table in tables:
        # Get column names
        cols = [r[1] for r in local.execute(f"PRAGMA table_info({table})").fetchall()]
        if not cols:
            print(f"  Skipping {table} (not found)")
            continue
        # Read all rows
        rows = local.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            print(f"  {table}: 0 rows (skipping)")
            continue
        col_list = ", ".join(cols)
        placeholders = ", ".join(["?"] * len(cols))
        # Delete existing rows (to avoid duplicates)
        cur.execute(f"DELETE FROM {table}")
        # Insert all rows
        for row in rows:
            values = [row[c] for c in cols]
            cur.execute(f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})", values)
        conn.commit()
        print(f"  {table}: uploaded {len(rows)} rows")

    local.close()
    conn.close()
    print("Upload complete!")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python upload_to_turso.py <TURSO_URL> <TURSO_TOKEN>")
        sys.exit(1)
    upload_to_turso(sys.argv[1], sys.argv[2])