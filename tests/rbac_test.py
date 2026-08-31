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


def test_user_sees_only_own_bank_accounts(client, login, est_ids):
    login(client, "u1@example.com", user_id=1)
    r = client.post("/api/bank-accounts", json=make_bank_payload(est_ids[0]))
    assert r.status_code == 201
    row_id = r.get_json()["id"]

    login(client, "u2@example.com", user_id=2)
    listing = client.get("/api/bank-accounts").get_json()
    assert all(x["id"] != row_id for x in listing)

    login(client, "admin@example.com", user_id=3)
    listing = client.get("/api/bank-accounts").get_json()
    match = [x for x in listing if x["id"] == row_id]
    assert match and match[0]["owner_email"] == "u1@example.com"


def test_post_stamps_owner_email_on_bank_and_8f(client, login, est_ids):
    login(client, "u1@example.com", user_id=1)
    payload = make_bank_payload(est_ids[0], eight_f_issued="true",
                                eight_f_number="8F-1", eight_f_issued_date="2021-01-01",
                                est_id="ORBBS0000000001", est_name="Alpha Establishment")
    r = client.post("/api/bank-accounts", json=payload)
    assert r.status_code == 201
    with app_module._db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT owner_email FROM bank_accounts WHERE id = ?", (r.get_json()["id"],))
        assert cur.fetchone()[0] == "u1@example.com"
        cur.execute("SELECT owner_email FROM epfo_8f_records WHERE bank_account_id = ?",
                    (r.get_json()["id"],))
        assert cur.fetchone()[0] == "u1@example.com"


def test_get_by_id_404_for_non_owner(client, login, est_ids):
    login(client, "u1@example.com", user_id=1)
    row_id = client.post("/api/bank-accounts", json=make_bank_payload(est_ids[0])).get_json()["id"]

    login(client, "u2@example.com", user_id=2)
    assert client.get(f"/api/bank-accounts/{row_id}").status_code == 404

    login(client, "admin@example.com", user_id=3)
    assert client.get(f"/api/bank-accounts/{row_id}").status_code == 200


def _make_row(client, login, est_id, email, user_id):
    login(client, email, user_id=user_id)
    return client.post("/api/bank-accounts", json=make_bank_payload(est_id)).get_json()["id"]


def test_put_and_delete_404_for_non_owner(client, login, est_ids):
    row_id = _make_row(client, login, est_ids[0], "u1@example.com", 1)

    login(client, "u2@example.com", user_id=2)
    assert client.put(f"/api/bank-accounts/{row_id}",
                      json=make_bank_payload(est_ids[0])).status_code == 404
    assert client.delete(f"/api/bank-accounts/{row_id}").status_code == 404


def test_owner_can_update_and_owner_email_is_stable(client, login, est_ids):
    row_id = _make_row(client, login, est_ids[0], "u1@example.com", 1)
    login(client, "u1@example.com", user_id=1)
    r = client.put(f"/api/bank-accounts/{row_id}",
                   json=make_bank_payload(est_ids[0], bank_name="Renamed Bank"))
    assert r.status_code == 200
    with app_module._db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT owner_email, bank_name FROM bank_accounts WHERE id = ?", (row_id,))
        owner, bank = cur.fetchone()
        assert owner == "u1@example.com" and bank == "Renamed Bank"


def test_export_records_scoped_and_owner_filtered(client, login, est_ids):
    login(client, "u1@example.com", user_id=1)
    client.post("/api/bank-accounts", json=make_bank_payload(est_ids[0]))
    login(client, "u2@example.com", user_id=2)
    client.post("/api/bank-accounts", json=make_bank_payload(est_ids[1]))

    login(client, "u1@example.com", user_id=1)
    with app_module.app.test_request_context("/api/export-pdf?tab=bank"):
        from flask import session
        session["user_id"] = 1
        session["user_email"] = "u1@example.com"
        rows = app_module._export_records("bank", "est_id", None)
    assert len(rows) == 1 and rows[0]["owner_email"] == "u1@example.com"

    with app_module.app.test_request_context("/api/export-pdf?tab=bank&owner=u2@example.com"):
        from flask import session
        session["user_id"] = 3
        session["user_email"] = "admin@example.com"
        rows = app_module._export_records("bank", "est_id", "u2@example.com")
    assert len(rows) == 1 and rows[0]["owner_email"] == "u2@example.com"


def test_export_pdf_endpoint_status(client, login, est_ids):
    login(client, "u1@example.com", user_id=1)
    client.post("/api/bank-accounts", json=make_bank_payload(est_ids[0]))
    for tab in ("bank", "8f", "paid", "pending"):
        r = client.get(f"/api/export-pdf?tab={tab}")
        assert r.status_code == 200
        assert r.mimetype == "application/pdf"


def test_export_pdf_non_admin_owner_param_ignored(client, login, est_ids):
    login(client, "u1@example.com", user_id=1)
    client.post("/api/bank-accounts", json=make_bank_payload(est_ids[0]))
    login(client, "u2@example.com", user_id=2)
    with app_module.app.test_request_context("/api/export-pdf?tab=bank&owner=u1@example.com"):
        from flask import session
        session["user_id"] = 2
        session["user_email"] = "u2@example.com"
        rows = app_module._export_records("bank", "est_id", "u1@example.com")
    assert rows == []  # u2 owns nothing; the owner param must not widen scope


def test_epfo_8f_list_scoped_to_owner(client, login, est_ids):
    login(client, "u1@example.com", user_id=1)
    client.post("/api/bank-accounts", json=make_bank_payload(
        est_ids[0], eight_f_issued="true", eight_f_number="8F-1",
        eight_f_issued_date="2021-01-01",
        est_id="ORBBS0000000001", est_name="Alpha Establishment"))

    login(client, "u2@example.com", user_id=2)
    assert client.get("/api/epfo-8f").get_json() == []

    login(client, "admin@example.com", user_id=3)
    admin_view = client.get("/api/epfo-8f").get_json()
    assert len(admin_view) == 1
    assert admin_view[0]["owner_email"] == "u1@example.com"


def test_api_me_includes_role(client, login):
    login(client, "admin@example.com")
    assert client.get("/api/me").get_json()["role"] == "admin"
    login(client, "user@example.com")
    assert client.get("/api/me").get_json()["role"] == "user"


def test_entry_owners_lists_distinct_emails_for_admin(client, login, est_ids):
    login(client, "u1@example.com", user_id=1)
    client.post("/api/bank-accounts", json=make_bank_payload(est_ids[0]))
    login(client, "u2@example.com", user_id=2)
    client.post("/api/bank-accounts", json=make_bank_payload(est_ids[1]))
    client.post("/api/bank-accounts", json=make_bank_payload(est_ids[0]))

    login(client, "admin@example.com", user_id=3)
    owners = client.get("/api/entry-owners").get_json()
    assert owners == ["u1@example.com", "u2@example.com"]


def test_entry_owners_403_for_user(client, login):
    login(client, "user@example.com")
    assert client.get("/api/entry-owners").status_code == 403
