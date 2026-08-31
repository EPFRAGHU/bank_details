import gc
import os
import tempfile
import time

import pytest

# Point the app at an isolated SQLite DB BEFORE importing it, and make sure
# no Postgres/Turso env vars are picked up during the test run.
_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".sqlite3")
os.close(_DB_FD)
os.environ["ONBOARDING_DB"] = _DB_PATH
os.environ.pop("DATABASE_URL", None)
os.environ.pop("TURSO_URL", None)
os.environ.pop("TURSO_TOKEN", None)
os.environ["ADMIN_EMAILS"] = "admin@example.com"
os.environ["SECRET_KEY"] = "test-secret"

import app as app_module  # noqa: E402


@pytest.fixture()
def client():
    # Fresh schema + seed data for every test.
    # The app opens connections via `with _connect() as conn:` and never closes
    # them explicitly; on Windows the sqlite3 Connection/Cursor reference cycle
    # keeps the file locked until a GC pass runs, so force one before deleting.
    gc.collect()
    for _attempt in range(10):
        if not os.path.exists(_DB_PATH):
            break
        try:
            os.remove(_DB_PATH)
            break
        except PermissionError:
            gc.collect()
            time.sleep(0.05)
    else:
        if os.path.exists(_DB_PATH):
            os.remove(_DB_PATH)  # last try: let the error surface
    app_module.init_db()
    conn = app_module._connect()
    try:
        cur = conn.cursor()
        for est_id, name in [("ORBBS0000000001", "Alpha Establishment"),
                             ("ORBBS0000000002", "Beta Establishment")]:
            cur.execute("INSERT INTO establishments (est_id, est_name) VALUES (?, ?)",
                        (est_id, name))
        conn.commit()
    finally:
        conn.close()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


@pytest.fixture()
def login():
    def _login(client, email, user_id=1, name="Test User"):
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["user_email"] = email
            sess["user_name"] = name
    return _login


@pytest.fixture()
def est_ids(client):
    conn = app_module._connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM establishments ORDER BY id")
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def make_bank_payload(establishment_id, **overrides):
    payload = {
        "establishment_id": establishment_id,
        "account_number": "123456789012",
        "ifsc": "SBIN0001234",
        "bank_name": "State Bank of India",
        "period": "2020-01 to 2020-12",
        "payment_status": "pending",
    }
    payload.update(overrides)
    return payload
