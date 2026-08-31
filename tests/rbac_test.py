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
