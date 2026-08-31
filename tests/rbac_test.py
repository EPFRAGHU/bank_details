from conftest import make_bank_payload  # noqa: F401  (re-exported for later tasks)
import app as app_module


def test_is_admin_true_for_configured_admin_email(client, login):
    login(client, "admin@example.com")
    with app_module.app.test_request_context("/"):
        from flask import session
        session["user_email"] = "admin@example.com"
        assert app_module.is_admin() is True
        assert app_module.current_role() == "admin"


def test_is_admin_false_for_other_email(client):
    with app_module.app.test_request_context("/"):
        from flask import session
        session["user_email"] = "someone@else.com"
        assert app_module.is_admin() is False
        assert app_module.current_role() == "user"


def test_admin_backfill_email_is_a_configured_admin():
    assert app_module.admin_backfill_email() in app_module.ADMIN_EMAILS or \
        app_module.admin_backfill_email() == "raghunatha.maharana@gmail.com"


def test_db_context_manager_closes_connection(client):
    import app as app_module
    with app_module._db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1
    # After the with-block the connection must be closed.
    import pytest
    with pytest.raises(Exception):
        conn.execute("SELECT 1")   # sqlite3.ProgrammingError / psycopg2 InterfaceError


def test_owner_email_columns_exist(client):
    with app_module._db() as conn:
        cur = conn.cursor()
        for table in ("bank_accounts", "epfo_8f_records"):
            cur.execute(f"PRAGMA table_info({table})")
            cols = [r[1] for r in cur.fetchall()]
            assert "owner_email" in cols, f"{table} missing owner_email"


def test_backfill_assigns_null_owner_rows_to_admin(client, est_ids):
    # Simulate a pre-existing row with no owner, then re-run init_db().
    with app_module._db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO bank_accounts (establishment_id, account_number, ifsc, bank_name) "
            "VALUES (?, ?, ?, ?)", (est_ids[0], "999999999999", "SBIN0009999", "Test Bank"))
        conn.commit()
    app_module.init_db()
    with app_module._db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT owner_email FROM bank_accounts WHERE account_number = '999999999999'")
        assert cur.fetchone()[0] == app_module.admin_backfill_email()


def test_init_db_is_idempotent(client):
    app_module.init_db()
    app_module.init_db()  # must not raise


PROTECTED_API = [
    ("GET", "/api/bank-accounts"),
    ("GET", "/api/bank-accounts/1"),
    ("GET", "/api/epfo-8f"),
    ("GET", "/api/establishments"),
    ("GET", "/api/export-pdf?tab=bank"),
    ("GET", "/api/ifsc/SBIN0001234"),
]


def test_protected_api_requires_login(client):
    for method, path in PROTECTED_API:
        resp = client.open(path, method=method)
        assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"


def test_bank_page_redirects_when_logged_out(client):
    resp = client.get("/bank")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_admin_routes_forbidden_for_regular_user(client, login):
    login(client, "user@example.com")
    for path in ("/api/users", "/api/entry-owners"):
        assert client.get(path).status_code == 403
    assert client.get("/admin").status_code == 403


def test_admin_routes_ok_for_admin(client, login):
    login(client, "admin@example.com")
    assert client.get("/api/users").status_code == 200
    assert client.get("/admin").status_code == 200


def test_login_page_still_public(client):
    assert client.get("/login").status_code == 200
    assert client.get("/signup").status_code == 200
