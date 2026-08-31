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
