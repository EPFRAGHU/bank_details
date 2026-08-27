"""Import establishments_filtered_all.csv into SQLite."""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

DB_PATH = Path("logs/onboarding.sqlite3")
CSV_PATH = Path("establishments_filtered_all.csv")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
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
            """
        )
        conn.execute(
            """
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
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (establishment_id) REFERENCES establishments(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
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
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id) ON DELETE CASCADE,
                FOREIGN KEY (establishment_id) REFERENCES establishments(id) ON DELETE CASCADE
            )
            """
        )
        bank_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(bank_accounts)").fetchall()
        }
        for col, ddl in [
            ("aeo", "ALTER TABLE bank_accounts ADD COLUMN aeo TEXT"),
            ("branch", "ALTER TABLE bank_accounts ADD COLUMN branch TEXT"),
            ("address", "ALTER TABLE bank_accounts ADD COLUMN address TEXT"),
            ("city1", "ALTER TABLE bank_accounts ADD COLUMN city1 TEXT"),
            ("city2", "ALTER TABLE bank_accounts ADD COLUMN city2 TEXT"),
            ("district", "ALTER TABLE bank_accounts ADD COLUMN district TEXT"),
            ("state", "ALTER TABLE bank_accounts ADD COLUMN state TEXT"),
            ("phone", "ALTER TABLE bank_accounts ADD COLUMN phone TEXT"),
            ("contact", "ALTER TABLE bank_accounts ADD COLUMN contact TEXT"),
            ("period", "ALTER TABLE bank_accounts ADD COLUMN period TEXT"),
            ("amount_7a_ac1", "ALTER TABLE bank_accounts ADD COLUMN amount_7a_ac1 REAL DEFAULT 0"),
            ("amount_7a_ac2", "ALTER TABLE bank_accounts ADD COLUMN amount_7a_ac2 REAL DEFAULT 0"),
            ("amount_7a_ac10", "ALTER TABLE bank_accounts ADD COLUMN amount_7a_ac10 REAL DEFAULT 0"),
            ("amount_7a_ac21", "ALTER TABLE bank_accounts ADD COLUMN amount_7a_ac21 REAL DEFAULT 0"),
            ("amount_7a_ac22", "ALTER TABLE bank_accounts ADD COLUMN amount_7a_ac22 REAL DEFAULT 0"),
            ("amount_7a_total", "ALTER TABLE bank_accounts ADD COLUMN amount_7a_total REAL DEFAULT 0"),
            ("amount_7q_7a_ac1", "ALTER TABLE bank_accounts ADD COLUMN amount_7q_7a_ac1 REAL DEFAULT 0"),
            ("amount_7q_7a_ac2", "ALTER TABLE bank_accounts ADD COLUMN amount_7q_7a_ac2 REAL DEFAULT 0"),
            ("amount_7q_7a_ac10", "ALTER TABLE bank_accounts ADD COLUMN amount_7q_7a_ac10 REAL DEFAULT 0"),
            ("amount_7q_7a_ac21", "ALTER TABLE bank_accounts ADD COLUMN amount_7q_7a_ac21 REAL DEFAULT 0"),
            ("amount_7q_7a_ac22", "ALTER TABLE bank_accounts ADD COLUMN amount_7q_7a_ac22 REAL DEFAULT 0"),
            ("amount_7q_7a_total", "ALTER TABLE bank_accounts ADD COLUMN amount_7q_7a_total REAL DEFAULT 0"),
            ("amount_14b_ac1", "ALTER TABLE bank_accounts ADD COLUMN amount_14b_ac1 REAL DEFAULT 0"),
            ("amount_14b_ac2", "ALTER TABLE bank_accounts ADD COLUMN amount_14b_ac2 REAL DEFAULT 0"),
            ("amount_14b_ac10", "ALTER TABLE bank_accounts ADD COLUMN amount_14b_ac10 REAL DEFAULT 0"),
            ("amount_14b_ac21", "ALTER TABLE bank_accounts ADD COLUMN amount_14b_ac21 REAL DEFAULT 0"),
            ("amount_14b_ac22", "ALTER TABLE bank_accounts ADD COLUMN amount_14b_ac22 REAL DEFAULT 0"),
            ("amount_14b_total", "ALTER TABLE bank_accounts ADD COLUMN amount_14b_total REAL DEFAULT 0"),
            ("amount_7q_14b_ac1", "ALTER TABLE bank_accounts ADD COLUMN amount_7q_14b_ac1 REAL DEFAULT 0"),
            ("amount_7q_14b_ac2", "ALTER TABLE bank_accounts ADD COLUMN amount_7q_14b_ac2 REAL DEFAULT 0"),
            ("amount_7q_14b_ac10", "ALTER TABLE bank_accounts ADD COLUMN amount_7q_14b_ac10 REAL DEFAULT 0"),
            ("amount_7q_14b_ac21", "ALTER TABLE bank_accounts ADD COLUMN amount_7q_14b_ac21 REAL DEFAULT 0"),
            ("amount_7q_14b_ac22", "ALTER TABLE bank_accounts ADD COLUMN amount_7q_14b_ac22 REAL DEFAULT 0"),
            ("amount_7q_14b_total", "ALTER TABLE bank_accounts ADD COLUMN amount_7q_14b_total REAL DEFAULT 0"),
            ("total_amount", "ALTER TABLE bank_accounts ADD COLUMN total_amount REAL DEFAULT 0"),
            ("payment_status", "ALTER TABLE bank_accounts ADD COLUMN payment_status TEXT DEFAULT 'pending'"),
            ("payment_date", "ALTER TABLE bank_accounts ADD COLUMN payment_date TEXT"),
            ("eight_f_issued", "ALTER TABLE bank_accounts ADD COLUMN eight_f_issued INTEGER DEFAULT 0"),
            ("eight_f_number", "ALTER TABLE bank_accounts ADD COLUMN eight_f_number TEXT"),
            ("eight_f_issued_date", "ALTER TABLE bank_accounts ADD COLUMN eight_f_issued_date TEXT"),
        ]:
            if col not in bank_cols:
                conn.execute(ddl)

        # Drop UNIQUE constraint on establishment_id if it exists (allow multiple accounts).
        indexes = conn.execute("PRAGMA index_list(bank_accounts)").fetchall()
        has_unique_est = False
        for idx in indexes:
            idx_info = conn.execute(f"PRAGMA index_info({idx[1]})").fetchall()
            cols = [info[2] for info in idx_info]
            if cols == ["establishment_id"]:
                has_unique_est = True
                break
        if has_unique_est:
            conn.execute("ALTER TABLE bank_accounts RENAME TO bank_accounts_old")
            conn.execute(
                """
                CREATE TABLE bank_accounts (
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
                    FOREIGN KEY (establishment_id) REFERENCES establishments(id) ON DELETE CASCADE
                )
                """
            )
            old_cols = {row[1] for row in conn.execute("PRAGMA table_info(bank_accounts_old)").fetchall()}
            new_cols = [
                "id", "establishment_id", "account_number", "ifsc", "code", "bank_name",
                "branch", "address", "city1", "city2", "district", "state", "phone",
                "contact", "period",
                "amount_7a_ac1", "amount_7a_ac2", "amount_7a_ac10", "amount_7a_ac21", "amount_7a_ac22", "amount_7a_total",
                "amount_7q_7a_ac1", "amount_7q_7a_ac2", "amount_7q_7a_ac10", "amount_7q_7a_ac21", "amount_7q_7a_ac22", "amount_7q_7a_total",
                "amount_14b_ac1", "amount_14b_ac2", "amount_14b_ac10", "amount_14b_ac21", "amount_14b_ac22", "amount_14b_total",
                "amount_7q_14b_ac1", "amount_7q_14b_ac2", "amount_7q_14b_ac10", "amount_7q_14b_ac21", "amount_7q_14b_ac22", "amount_7q_14b_total",
                "total_amount", "payment_status", "payment_date", "eight_f_issued",
                "eight_f_number", "eight_f_issued_date", "created_at",
            ]
            select_cols = [c if c in old_cols else "NULL" for c in new_cols]
            conn.execute(
                f"INSERT INTO bank_accounts ({', '.join(new_cols)}) SELECT {', '.join(select_cols)} FROM bank_accounts_old"
            )
            conn.execute("DROP TABLE bank_accounts_old")
        conn.commit()


def import_csv() -> int:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")
    inserted = 0
    with sqlite3.connect(DB_PATH) as conn, CSV_PATH.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            est_id = (row.get("est_id") or "").strip()
            est_name = (row.get("est_name") or "").strip()
            if not est_id or not est_name:
                continue
            try:
                sr_no = int(row.get("sr_no") or 0)
            except ValueError:
                sr_no = 0
            conn.execute(
                """
                INSERT INTO establishments (sr_no, est_id, est_name, office, circle, aeo, phone)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(est_id) DO UPDATE SET
                    sr_no=excluded.sr_no,
                    est_name=excluded.est_name,
                    office=excluded.office,
                    circle=excluded.circle,
                    aeo=excluded.aeo,
                    phone=excluded.phone
                """,
                (
                    sr_no,
                    est_id,
                    est_name,
                    (row.get("office") or "").strip() or None,
                    (row.get("circle") or "").strip() or None,
                    (row.get("aeo") or "").strip() or None,
                    (row.get("phone") or "").strip() or None,
                ),
            )
            inserted += 1
        conn.commit()
    return inserted


if __name__ == "__main__":
    init_db()
    n = import_csv()
    print(f"Imported {n} establishments into {DB_PATH}")
