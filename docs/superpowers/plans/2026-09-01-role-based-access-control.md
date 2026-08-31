# Role-Based Access Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restrict every user to only the bank-account / 8F data they entered, while an admin sees all data plus an "Entered By" column and can filter by user; require a logged-in session on all data routes and admin role on the admin area.

**Architecture:** Two roles derived from the login email against an `ADMIN_EMAILS` env set (no DB role column). A new `owner_email TEXT` column on `bank_accounts` and `epfo_8f_records` records who created each row, stamped from the session on insert and back-filled to the admin for pre-existing rows. Two decorators (`login_required`, `admin_required`) gate the routes; a helper (`owner_scope_sql`) appends an ownership `WHERE` fragment to every read query unless the caller is admin. The frontend reads its role from `/api/me` and conditionally renders the owner column, a per-tab "Entered by" dropdown (fed by a new `/api/entry-owners` endpoint), and the admin link.

**Tech Stack:** Python 3 + Flask 3.0, vanilla `sqlite3` / `psycopg2` (SQLite local, PostgreSQL on Render), ReportLab, single-file vanilla-JS HTML templates. Tests: `pytest` + Flask `test_client()` with the session set directly via `session_transaction()`.

**Spec:** `docs/superpowers/specs/2026-09-01-role-based-access-control-design.md`

## Global Constraints

- **Two roles only:** `user` and `admin`. No `role` column, no role-management UI, no promote/demote.
- **Admin source:** `ADMIN_EMAILS = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "raghunatha.maharana@gmail.com").split(",") if e.strip()}`. Default must contain `raghunatha.maharana@gmail.com`.
- **Ownership key:** `owner_email` (TEXT, case-insensitive compares via `LOWER()`), never reassigned after row creation.
- **Existing rows:** back-filled once, on startup, to `sorted(ADMIN_EMAILS)[0]` (fallback `"raghunatha.maharana@gmail.com"`), only where `owner_email IS NULL`.
- **Dual DB:** every SQL change must be made in BOTH the SQLite and PostgreSQL branches / schema dicts. Placeholders use the existing `"%s" if USE_POSTGRES else "?"` convention; string SQL is passed through `_translate_sql()` where the codebase already does so.
- **Enumeration safety:** a non-admin touching another user's row by id returns `404` (never `403`).
- **API vs page auth failure:** `request.path.startswith("/api/")` → JSON `401`/`403`; otherwise redirect to `/login` (401) or a `403` HTML page.
- **`/api/establishments` is NOT owner-filtered** — shared 48k reference list, `@login_required` only.
- **No new sort option** for owner. `_sort_records` / `sortRecords` untouched.
- **Frontend safe default:** if `/api/me` fails, `IS_ADMIN = false` — no column, no dropdown, no admin link.
- **Version on completion:** bump to **v1.3.0** in `bank.html` (label + `VERSION_HISTORY`), `AGENTS.md`, `CHANGELOG.md`, as a separate commit.
- Commit after every task. Conventional-commit style messages (`feat:`, `test:`, `chore:`).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `app.py` | All backend: config helpers, schema+migration, decorators, query scoping, new endpoints, PDF | Modify |
| `bank.html` | Role bootstrap, owner column, "Entered by" dropdowns + filter, admin link, PDF param | Modify |
| `tests/conftest.py` | pytest fixtures: isolated SQLite DB, seeded establishments, `client`, session helpers | Create |
| `tests/rbac_test.py` | All backend RBAC tests (auth, ownership, scoping, endpoints) | Create |
| `AGENTS.md` | Status + version list + schema notes | Modify (final task) |
| `CHANGELOG.md` | v1.3.0 entry | Modify (final task) |

Test files are named `*_test.py` (not `test_*.py`) so they do NOT match the existing `.gitignore` `test_*.py` rule and ARE committed. `pytest` discovers both patterns by default.

---

## Task 1: Test harness + config helpers

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/rbac_test.py`
- Modify: `app.py` (add config block after `DATABASE_URL` / `USE_POSTGRES` lines, ~line 24)

**Interfaces:**
- Produces:
  - `app.ADMIN_EMAILS: set[str]`
  - `app.current_role() -> str` (`"admin"` | `"user"`)
  - `app.is_admin() -> bool`
  - `app.admin_backfill_email() -> str` (— `sorted(ADMIN_EMAILS)[0]` or the literal default)
  - pytest fixtures: `client` (Flask test client on an isolated SQLite DB with 2 establishments seeded), `login(client, email, user_id=...)` helper
- Consumes: nothing

- [ ] **Step 1: Write `tests/conftest.py`**

```python
import os
import tempfile
import pytest

# Point the app at an isolated SQLite DB BEFORE importing it, and make sure
# no Postgres/Turso env vars are picked up during the test run.
_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".sqlite3")
os.close(_DB_FD)
os.environ["ONBOARDING_DB"] = _DB_PATH
os.environ.pop("DATABASE_URL", None)
os.environ.pop("TURSO_URL", None)
os.environ.pop("TURSO_TOKEN", None)
os.environ.setdefault("ADMIN_EMAILS", "admin@example.com")
os.environ["SECRET_KEY"] = "test-secret"

import app as app_module  # noqa: E402


@pytest.fixture()
def client():
    # Fresh schema + seed data for every test.
    if os.path.exists(_DB_PATH):
        os.remove(_DB_PATH)
    app_module.init_db()
    with app_module._connect() as conn:
        cur = conn.cursor()
        for est_id, name in [("ORBBS0000000001", "Alpha Establishment"),
                             ("ORBBS0000000002", "Beta Establishment")]:
            cur.execute("INSERT INTO establishments (est_id, est_name) VALUES (?, ?)",
                        (est_id, name))
        conn.commit()
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
    with app_module._connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM establishments ORDER BY id")
        return [r[0] for r in cur.fetchall()]


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
```

- [ ] **Step 2: Write the failing test in `tests/rbac_test.py`**

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/rbac_test.py -v`
Expected: FAIL — `AttributeError: module 'app' has no attribute 'is_admin'`

- [ ] **Step 4: Add the config block to `app.py`**

Insert immediately after the line `USE_POSTGRES = bool(DATABASE_URL and DATABASE_URL.startswith(("postgres://", "postgresql://")))`:

```python

ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.getenv("ADMIN_EMAILS", "raghunatha.maharana@gmail.com").split(",")
    if e.strip()
}


def current_role():
    """'admin' if the logged-in email is in ADMIN_EMAILS, else 'user'."""
    from flask import session
    return "admin" if session.get("user_email", "").strip().lower() in ADMIN_EMAILS else "user"


def is_admin():
    return current_role() == "admin"


def admin_backfill_email():
    """The email pre-existing ownerless rows are assigned to."""
    return sorted(ADMIN_EMAILS)[0] if ADMIN_EMAILS else "raghunatha.maharana@gmail.com"
```

(`from flask import session` is already imported at module top; the local import inside `current_role` is harmless but you may instead rely on the module-level import — keep it consistent with the file, which imports `session` at the top, so DROP the local `from flask import session` line and use the top-level import.)

Final form:

```python
def current_role():
    """'admin' if the logged-in email is in ADMIN_EMAILS, else 'user'."""
    return "admin" if session.get("user_email", "").strip().lower() in ADMIN_EMAILS else "user"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/rbac_test.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/rbac_test.py app.py
git commit -m "test: add RBAC test harness; feat: admin-email role helpers"
```

---

## Task 2: `owner_email` schema, migration, backfill, indexes

**Files:**
- Modify: `app.py` — `SCHEMA_SQLITE["bank_accounts"]`, `SCHEMA_SQLITE["epfo_8f_records"]`, `SCHEMA_POSTGRES["bank_accounts"]`, `SCHEMA_POSTGRES["epfo_8f_records"]`, `init_db()` (~line 347-374)
- Modify: `tests/rbac_test.py`

**Interfaces:**
- Consumes: `admin_backfill_email()` (Task 1)
- Produces: `bank_accounts.owner_email`, `epfo_8f_records.owner_email` columns exist after `init_db()`; NULL values back-filled to `admin_backfill_email()`; indexes `idx_bank_accounts_owner`, `idx_epfo_8f_records_owner`

- [ ] **Step 1: Write the failing tests**

Add to `tests/rbac_test.py`:

```python
def test_owner_email_columns_exist(client):
    with app_module._connect() as conn:
        cur = conn.cursor()
        for table in ("bank_accounts", "epfo_8f_records"):
            cur.execute(f"PRAGMA table_info({table})")
            cols = [r[1] for r in cur.fetchall()]
            assert "owner_email" in cols, f"{table} missing owner_email"


def test_backfill_assigns_null_owner_rows_to_admin(client, est_ids):
    # Simulate a pre-existing row with no owner, then re-run init_db().
    with app_module._connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO bank_accounts (establishment_id, account_number, ifsc, bank_name) "
            "VALUES (?, ?, ?, ?)", (est_ids[0], "999999999999", "SBIN0009999", "Test Bank"))
        conn.commit()
    app_module.init_db()
    with app_module._connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT owner_email FROM bank_accounts WHERE account_number = '999999999999'")
        assert cur.fetchone()[0] == app_module.admin_backfill_email()


def test_init_db_is_idempotent(client):
    app_module.init_db()
    app_module.init_db()  # must not raise
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/rbac_test.py -k owner_email or backfill or idempotent -v`
Expected: FAIL — `bank_accounts missing owner_email`

- [ ] **Step 3: Add `owner_email` to all four schema definitions**

In `SCHEMA_SQLITE["bank_accounts"]` and `SCHEMA_SQLITE["epfo_8f_records"]`, add `owner_email TEXT,` just before the `FOREIGN KEY` line(s) (or as the last column where there is no trailing FK, e.g. in `epfo_8f_records` add it before the `FOREIGN KEY (bank_account_id)` line).

In `SCHEMA_POSTGRES["bank_accounts"]` and `SCHEMA_POSTGRES["epfo_8f_records"]`, add `owner_email TEXT,` as the last column line before the closing `)` (Postgres branch inlines FKs as `REFERENCES`, so append after `rrc_date TEXT`):

```
            rrc_date TEXT,
            owner_email TEXT
```

(no trailing comma on the final column).

- [ ] **Step 4: Extend the migration + add backfill and indexes in `init_db()`**

The current loop migrates `("demand_type", "TEXT"), ("rrc_number", "TEXT"), ("rrc_date", "TEXT")`. Change the column list to include `("owner_email", "TEXT")`:

```python
        for table in ("bank_accounts", "epfo_8f_records"):
            for col, col_type in [("demand_type", "TEXT"), ("rrc_number", "TEXT"),
                                  ("rrc_date", "TEXT"), ("owner_email", "TEXT")]:
                # ... existing add-column-if-missing logic unchanged ...
```

Then, AFTER that per-table loop (still inside `with _connect() as conn:` / after both tables migrated, before the final `conn.commit()`), add backfill + indexes:

```python
        backfill = admin_backfill_email()
        for table in ("bank_accounts", "epfo_8f_records"):
            cur.execute(
                _translate_sql(f"UPDATE {table} SET owner_email = ? WHERE owner_email IS NULL"),
                (backfill,),
            )
        idx_stmts = [
            "CREATE INDEX IF NOT EXISTS idx_bank_accounts_owner ON bank_accounts(owner_email)",
            "CREATE INDEX IF NOT EXISTS idx_epfo_8f_records_owner ON epfo_8f_records(owner_email)",
        ]
        for stmt in idx_stmts:
            cur.execute(stmt)
        if USE_POSTGRES:
            conn.commit()
```

Keep the existing trailing `if not USE_POSTGRES: conn.commit()`.

- [ ] **Step 5: Run to verify pass**

Run: `pytest tests/rbac_test.py -v`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add app.py tests/rbac_test.py
git commit -m "feat: owner_email column with startup migration and admin backfill"
```

---

## Task 3: Auth decorators + route protection

**Files:**
- Modify: `app.py` — add decorators after the config block; apply to routes
- Modify: `tests/rbac_test.py`

**Interfaces:**
- Consumes: `is_admin()` (Task 1)
- Produces: `@login_required`, `@admin_required` decorators; protected routes as per the matrix

- [ ] **Step 1: Write the failing tests**

```python
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
```

(`/api/entry-owners` is built in Task 7 but must already 403 for a non-admin here — `admin_required` returns 403 before the view runs, and Flask returns 404 for the not-yet-registered route. To avoid coupling, register `/api/entry-owners` as a stub in this task returning `jsonify([])` under `@admin_required`, and flesh it out in Task 7. Add that stub now.)

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/rbac_test.py -k "protected or redirects or forbidden or admin_routes" -v`
Expected: FAIL — protected routes return 200

- [ ] **Step 3: Add decorators to `app.py`**

After the config block from Task 1:

```python
from functools import wraps


def _auth_fail(status, message):
    if request.path.startswith("/api/"):
        return jsonify({"status": "error", "message": message}), status
    if status == 401:
        return redirect("/login")
    return Response(
        f"<h1>403 — {message}</h1><p><a href='/bank'>Back to Bank</a></p>",
        status=403, mimetype="text/html",
    )


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return _auth_fail(401, "Login required")
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return _auth_fail(401, "Login required")
        if not is_admin():
            return _auth_fail(403, "Admin access required")
        return f(*args, **kwargs)
    return wrapper
```

- [ ] **Step 4: Apply decorators**

Add the decorator line directly under each `@app.route(...)` (above the `def`):

- `/api/users` → `@admin_required`
- `/admin` → `@admin_required`
- `/bank` → `@login_required`
- `/api/establishments` → `@login_required`
- `/api/bank-accounts` → `@login_required`
- `/api/bank-accounts/<int:bank_id>` → `@login_required`
- `/api/epfo-8f` → `@login_required`
- `/api/export-pdf` → `@login_required`
- `/api/ifsc/<code>` → `@login_required`

Leave public: `/`, `/signup`, `/api/onboard`, `/login`, `/api/login`, `/api/logout`, `/api/me`.

- [ ] **Step 5: Add the `/api/entry-owners` stub**

Next to `/api/users`:

```python
@app.route("/api/entry-owners", methods=["GET"])
@admin_required
def entry_owners():
    return jsonify([])
```

- [ ] **Step 6: Run to verify pass**

Run: `pytest tests/rbac_test.py -v`
Expected: PASS (all)

- [ ] **Step 7: Commit**

```bash
git add app.py tests/rbac_test.py
git commit -m "feat: login_required / admin_required decorators on all data routes"
```

---

## Task 4: Ownership on list, read, and create

**Files:**
- Modify: `app.py` — `owner_scope_sql` helper; `bank_accounts()` GET + POST; `bank_account_detail()` GET branch
- Modify: `tests/rbac_test.py`

**Interfaces:**
- Consumes: `is_admin()`, session email
- Produces:
  - `owner_scope_sql(column) -> tuple[str, list]` — `("", [])` for admin, `(" AND LOWER(<column>) = ? ", [email])` for user
  - `GET /api/bank-accounts` returns only the caller's rows (all for admin), each row dict includes `owner_email`
  - `POST /api/bank-accounts` stamps `owner_email` from session on the bank row and the 8F-sync row
  - `GET /api/bank-accounts/<id>` → 404 when a non-admin requests a row they do not own

- [ ] **Step 1: Write the failing tests**

```python
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
    with app_module._connect() as conn:
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
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/rbac_test.py -k "only_own or stamps_owner or by_id_404" -v`
Expected: FAIL (u2 sees u1's row; owner_email KeyError/None; 404 is 200)

- [ ] **Step 3: Add `owner_scope_sql` helper**

After `_row_dict` (or near the other SQL helpers):

```python
def owner_scope_sql(column):
    """WHERE-fragment restricting rows to the caller unless they are admin.

    Returns (sql_fragment, params). Fragment starts with ' AND ' so it can be
    appended to an existing WHERE; callers that have no WHERE yet must handle
    the AND->WHERE swap (see bank_accounts GET)."""
    if is_admin():
        return "", []
    return f" AND LOWER({column}) = ? ", [session.get("user_email", "").strip().lower()]
```

- [ ] **Step 4: Scope the `GET /api/bank-accounts` query**

Replace the WHERE-building block (currently: `params = []` … `sql += " ORDER BY b.id DESC"`) with a condition-list approach:

```python
            conditions = []
            params = []
            if payment_status in ("paid", "pending"):
                conditions.append("LOWER(b.payment_status) = ?")
                params.append(payment_status)
            scope_sql, scope_params = owner_scope_sql("b.owner_email")
            if scope_sql:
                conditions.append(scope_sql.replace(" AND ", "", 1).strip())
                params.extend(scope_params)
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY b.id DESC"
            cur.execute(_translate_sql(sql), params)
```

Add `b.owner_email` to the SELECT column list (after `e.est_id, e.est_name` add `, b.owner_email` — note the join means put it on the `b.` side, so add `b.owner_email,` into the `SELECT b.id, ...` block, e.g. right after `b.demand_type, b.rrc_number, b.rrc_date,`).

- [ ] **Step 5: Stamp `owner_email` on POST**

In the POST branch: change `insert_cols` to end with `, owner_email`; change `["%s" if USE_POSTGRES else "?"] * 48` to `* 49`; append to the `values` tuple (as the last element, before the closing `)`):

```python
                session.get("user_email"),
```

For the 8F-sync insert in the same POST branch: change `epfo_cols` to end with `, owner_email`; `* 47` → `* 48`; append `session.get("user_email"),` as the last `epfo_values` element.

- [ ] **Step 6: 404 non-owner on `GET /api/bank-accounts/<id>`**

In `bank_account_detail`, GET branch, after fetching `row` and the existing `if row is None: return ... 404`, add:

```python
            row = _row_dict(row)
            if not is_admin() and (row.get("owner_email") or "").strip().lower() != \
                    session.get("user_email", "").strip().lower():
                return jsonify({"status": "error", "message": "Not found"}), 404
            return jsonify(row)
```

Add `b.owner_email` to that query's SELECT list (both the Postgres and SQLite string variants).

- [ ] **Step 7: Run to verify pass**

Run: `pytest tests/rbac_test.py -v`
Expected: PASS (all)

- [ ] **Step 8: Commit**

```bash
git add app.py tests/rbac_test.py
git commit -m "feat: scope bank-account list/read to owner; stamp owner on create"
```

---

## Task 5: Ownership on update, delete, and 8F list

**Files:**
- Modify: `app.py` — `bank_account_detail()` PUT + DELETE branches; `list_epfo_8f()`
- Modify: `tests/rbac_test.py`

**Interfaces:**
- Consumes: `owner_scope_sql`, `is_admin()`, session email
- Produces:
  - `PUT` / `DELETE /api/bank-accounts/<id>` → 404 for a non-owner non-admin; `owner_email` unchanged by PUT; PUT 8F-sync insert carries the row's existing `owner_email`
  - `GET /api/epfo-8f` returns only the caller's records (all for admin), each with `owner_email`

- [ ] **Step 1: Write the failing tests**

```python
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
    with app_module._connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT owner_email, bank_name FROM bank_accounts WHERE id = ?", (row_id,))
        owner, bank = cur.fetchone()
        assert owner == "u1@example.com" and bank == "Renamed Bank"


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
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/rbac_test.py -k "non_owner or stable or epfo_8f_list_scoped" -v`
Expected: FAIL

- [ ] **Step 3: Ownership guard for PUT and DELETE**

In `bank_account_detail`, at the very start of BOTH the `if request.method == "DELETE":` block and the PUT section (after `# PUT`), add a shared pre-check. Simplest: right after `def bank_account_detail(bank_id: int):` and before the method branching, for non-GET methods:

```python
    if request.method in ("PUT", "DELETE") and not is_admin():
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(_translate_sql(
                "SELECT owner_email FROM bank_accounts WHERE id = %s" if USE_POSTGRES
                else "SELECT owner_email FROM bank_accounts WHERE id = ?"), (bank_id,))
            owned = cur.fetchone()
        owner = (_row_dict(owned) or {}).get("owner_email") if owned else None
        if owned is None or (owner or "").strip().lower() != \
                session.get("user_email", "").strip().lower():
            return jsonify({"status": "error", "message": "Not found"}), 404
```

- [ ] **Step 4: Keep `owner_email` out of the UPDATE**

Confirm the PUT `update_sql` does NOT list `owner_email` (it must not — spec says never reassigned). No change needed; just verify.

- [ ] **Step 5: Stamp `owner_email` on the PUT 8F-sync insert**

In the PUT branch's `if was_issued and not was_issued.get("eight_f_issued") ...` block: `epfo_cols` currently ends `... amount_7q_14b_total, demand_type, rrc_number, rrc_date`. Append `, owner_email`; change `[ph] * 47` to `[ph] * 48`; the SELECT that loads `was_issued` currently fetches `eight_f_issued, establishment_id` — add `owner_email` to it, and append to `epfo_values`:

```python
                    was_issued.get("owner_email"),
```

- [ ] **Step 6: Scope `GET /api/epfo-8f`**

`list_epfo_8f` runs one big UNION (Postgres and SQLite variants). For each variant:
- Add `b.owner_email` to BOTH SELECT lists in the UNION (next to `b.demand_type, b.rrc_number, b.rrc_date`).
- Add a `WHERE`/`AND` owner clause to BOTH halves. The first half currently has no WHERE; the second half has `WHERE b.eight_f_issued = 1 AND NOT EXISTS (...)`. Build the clause:

```python
        scope_sql, scope_params = owner_scope_sql("b.owner_email")
        # first half: ... JOIN bank_accounts b ON b.id = r.bank_account_id  <no WHERE>
        #   -> append:  (" WHERE " + scope_sql[5:]) if scope_sql else ""
        # second half: ... WHERE b.eight_f_issued = 1 AND NOT EXISTS (...)
        #   -> append:  scope_sql  (already starts with ' AND ')
```

Implement by turning the two f-strings into `.format()` / concatenation with two placeholders `{first_scope}` and `{second_scope}`, and pass `scope_params * 2` (params appear once per half) to `cur.execute`. Example skeleton:

```python
        first_scope = (" WHERE " + scope_sql.strip()[4:]) if scope_sql else ""
        second_scope = scope_sql  # ' AND LOWER(b.owner_email) = ? '
        sql = f"""... FROM epfo_8f_records r JOIN bank_accounts b ON b.id = r.bank_account_id{first_scope}
                  UNION
                  ... FROM bank_accounts b JOIN establishments e ON e.id = b.establishment_id
                  WHERE b.eight_f_issued = 1
                    AND NOT EXISTS (SELECT 1 FROM epfo_8f_records r2 WHERE r2.bank_account_id = b.id){second_scope}
                  ORDER BY id DESC"""
        cur.execute(_translate_sql(sql), scope_params + scope_params)
```

(When admin, `scope_sql == ""`, both inserts are empty and `scope_params == []` — unchanged behaviour.)

- [ ] **Step 7: Run to verify pass**

Run: `pytest tests/rbac_test.py -v`
Expected: PASS (all)

- [ ] **Step 8: Commit**

```bash
git add app.py tests/rbac_test.py
git commit -m "feat: scope bank-account update/delete and 8F list to owner"
```

---

## Task 6: PDF export scoping + admin "Entered By" column

**Files:**
- Modify: `app.py` — extract `_export_records(...)`; `export_pdf()` scoping, `owner` param, admin column
- Modify: `tests/rbac_test.py`

**Interfaces:**
- Consumes: `owner_scope_sql`, `is_admin()`
- Produces:
  - `_export_records(tab, sort_key, owner_filter) -> list[dict]` — the rows a PDF would contain, already owner-scoped and (for admin) `owner`-filtered
  - `GET /api/export-pdf` returns 200 `application/pdf` for any logged-in user, containing only their rows; admin can pass `?owner=<email>`; a non-admin's `owner` param is ignored

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/rbac_test.py -k export -v`
Expected: FAIL — `_export_records` not defined

- [ ] **Step 3: Extract `_export_records`**

In `export_pdf()`, the block that opens `with _connect() as conn:` and branches on `tab` to build `records` (the `if tab == "8f": ... elif tab in ("paid","pending"): ... else: ...` chain that ends by setting `records`, `headers`, `rows`, `title`). Pull the record-fetching into a module-level helper. Keep `headers`/`rows`/`title`/width logic in `export_pdf`. The helper:

```python
def _export_records(tab, sort_key, owner_filter):
    """Rows for a PDF export, owner-scoped. owner_filter (an email) is applied
    only when the caller is admin; a non-admin is always scoped to themselves."""
    sort_map = {
        "est_id": ("est_id", False), "est_name": ("est_name", False),
        "ifsc": ("ifsc", False), "bank": ("bank_name", False),
        "branch": ("branch", False), "amount": ("total_amount", True),
        "aeo": ("aeo", False), "period": ("period", False),
        "payment_status": ("payment_status", False),
    }
    col, reverse = sort_map.get(sort_key, ("est_id", False))
    scope_sql, scope_params = owner_scope_sql("b.owner_email")
    extra, extra_params = "", []
    if is_admin() and owner_filter:
        extra = " AND LOWER(b.owner_email) = ? "
        extra_params = [owner_filter.strip().lower()]

    with _connect() as conn:
        cur = conn.cursor()
        if tab == "8f":
            base = """SELECT b.id + 1000000 AS id, e.est_id, e.est_name, b.aeo,
                       b.eight_f_number, b.eight_f_issued_date, b.account_number, b.ifsc,
                       b.bank_name, b.branch, b.address, b.period, b.total_amount, b.payment_status,
                       b.amount_7a_total, b.amount_7q_7a_total, b.amount_14b_total, b.amount_7q_14b_total,
                       b.owner_email
                    FROM bank_accounts b JOIN establishments e ON e.id = b.establishment_id
                    WHERE b.eight_f_issued = 1"""
            sql = base + scope_sql + extra + " ORDER BY b.id DESC"
        elif tab in ("paid", "pending"):
            base = """SELECT b.id, e.est_id, e.est_name, b.aeo, b.period,
                       b.amount_7a_total, b.amount_7q_7a_total, b.amount_14b_total, b.amount_7q_14b_total,
                       b.total_amount, b.eight_f_number, b.eight_f_issued_date,
                       b.demand_type, b.rrc_number, b.rrc_date, b.payment_status,
                       b.bank_name, b.ifsc, b.account_number, b.owner_email
                    FROM bank_accounts b JOIN establishments e ON e.id = b.establishment_id
                    WHERE LOWER(b.payment_status) = ?"""
            sql = base + scope_sql + extra + " ORDER BY b.id DESC"
            params = [("paid" if tab == "paid" else "pending")] + scope_params + extra_params
            cur.execute(_translate_sql(sql), params)
            recs = [_row_dict(r) for r in cur.fetchall()]
            recs.sort(key=lambda r: (r.get(col) or "") if col != "total_amount"
                      else _to_float(r.get(col)), reverse=reverse)
            return recs
        else:  # bank
            base = """SELECT b.id, b.account_number, b.ifsc, b.bank_name, b.branch, b.address,
                       b.period, b.total_amount, b.payment_status, b.eight_f_issued,
                       b.eight_f_number, b.eight_f_issued_date, b.aeo,
                       e.est_id, e.est_name, b.owner_email
                    FROM bank_accounts b JOIN establishments e ON e.id = b.establishment_id
                    WHERE 1 = 1"""
            sql = base + scope_sql + extra
        params = scope_params + extra_params
        cur.execute(_translate_sql(sql), params)
        recs = [_row_dict(r) for r in cur.fetchall()]
    recs.sort(key=lambda r: (r.get(col) or "") if col != "total_amount"
              else _to_float(r.get(col)), reverse=reverse)
    return recs
```

Then in `export_pdf()` replace the inline fetch chain with:

```python
    tab = (request.args.get("tab") or "bank").lower()
    sort_key = (request.args.get("sort") or "est_id").strip()
    owner_filter = request.args.get("owner") if is_admin() else None
    records = _export_records(tab, sort_key, owner_filter)
```

Keep the existing `headers` / `rows` / `title` / `widths` building, but source it from `records` (the shape is unchanged — same column aliases). Remove the now-dead `sort_map` / `col,reverse` / `_sort_records` lines from `export_pdf` if they are no longer referenced there.

- [ ] **Step 4: Admin "Entered By" column in the PDF**

After `headers` and `rows` are built and before the `widths` block, add:

```python
    if is_admin():
        headers.append("Entered By")
        for i, rec in enumerate(records):
            rows[i].append(_para(rec.get("owner_email") or "—"))
```

In the `widths` block, when `is_admin()` append one more width to whichever array is used:

```python
    if tab in ("8f", "paid", "pending"):
        widths = [ ... existing ... ]
    else:
        widths = [ ... existing ... ]
    if is_admin():
        widths.append(20)
    total_w = sum(widths)
```

- [ ] **Step 5: Run to verify pass**

Run: `pytest tests/rbac_test.py -v`
Expected: PASS (all)

- [ ] **Step 6: Manual smoke — PDF opens**

Run:
```bash
python -c "import app; app.init_db()"
```
Start the app (`python app.py` with local SQLite), log in via browser as any user, click Export PDF on each tab, confirm a valid PDF downloads.

- [ ] **Step 7: Commit**

```bash
git add app.py tests/rbac_test.py
git commit -m "feat: owner-scope PDF export; admin Entered By column and owner filter"
```

---

## Task 7: `/api/me` role + real `/api/entry-owners`

**Files:**
- Modify: `app.py` — `api_me()`, `entry_owners()`
- Modify: `tests/rbac_test.py`

**Interfaces:**
- Consumes: `current_role()`, `admin_required`
- Produces:
  - `GET /api/me` JSON gains `"role": "admin" | "user"`
  - `GET /api/entry-owners` → sorted distinct non-null `owner_email` from `bank_accounts`; 403 for non-admin

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/rbac_test.py -k "api_me_includes_role or entry_owners" -v`
Expected: FAIL

- [ ] **Step 3: Add `role` to `/api/me`**

In `api_me()`, add to the returned `"user"` dict's sibling level:

```python
    return jsonify({
        "status": "ok",
        "role": current_role(),
        "user": {
            "id": session.get("user_id"),
            "name": session.get("user_name"),
            "email": session.get("user_email"),
        }
    })
```

- [ ] **Step 4: Implement `/api/entry-owners`**

```python
@app.route("/api/entry-owners", methods=["GET"])
@admin_required
def entry_owners():
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT owner_email FROM bank_accounts "
                    "WHERE owner_email IS NOT NULL ORDER BY owner_email")
        return jsonify([_row_dict(r)["owner_email"] if isinstance(_row_dict(r), dict)
                        else r[0] for r in cur.fetchall()])
```

(If `_row_dict` handling is awkward, simpler: `rows = cur.fetchall(); return jsonify(sorted({(_row_dict(r) or {}).get("owner_email") or r[0] for r in rows}))`. Pick whichever matches how other endpoints in this file read single-column results — check `list_establishments` style.)

- [ ] **Step 5: Run to verify pass**

Run: `pytest tests/rbac_test.py -v`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add app.py tests/rbac_test.py
git commit -m "feat: role in /api/me; /api/entry-owners for admin filter dropdown"
```

---

## Task 8: Frontend — role bootstrap, owner column, admin link

**Files:**
- Modify: `bank.html` — CSS, `<thead>` × 4, row templates × 4, init IIFE, admin link

**Interfaces:**
- Consumes: `GET /api/me` `role` field; row dicts now carry `owner_email`
- Produces: `IS_ADMIN` script-scope boolean; `<body class="is-admin">` when admin; `.col-owner` cells present in all 4 tables, visible only to admin; admin link hidden from users

- [ ] **Step 1: Add CSS**

In the `<style>` block, near the other `.col-*` rules:

```css
    .col-owner { display: none; white-space: nowrap; }
    body.is-admin .col-owner { display: table-cell; }
    .owner-filter { display: none; }
    body.is-admin .owner-filter { display: inline-block; }
```

- [ ] **Step 2: Declare `IS_ADMIN` and set it from `/api/me`**

Find the init IIFE's `/api/me` handling (inside `if (meRes.ok) { const meData = await meRes.json(); ... }`). Near the top of the `<script>` add `let IS_ADMIN = false;` in script scope (next to other `let` state such as `bankAccounts`). Inside the `if (meRes.ok)` block, after `const meData = await meRes.json();`:

```js
        IS_ADMIN = meData.role === 'admin';
        if (IS_ADMIN) document.body.classList.add('is-admin');
```

- [ ] **Step 3: Add the `Entered By` header to all 4 tables**

In each of the 4 `<thead><tr>` blocks (Entered Bank Accounts, 8F Issued, Paid, Pending), add as the LAST `<th>`:

```html
              <th class="col-owner">Entered By</th>
```

- [ ] **Step 4: Add the `Entered By` cell to all 4 row templates**

In `renderRows`, `renderEightFRows`, `renderPaidRows`, `renderPendingRows`, add as the LAST `<td>` in each row's template literal (immediately before the closing `</tr>`):

```js
          <td class="col-owner">${escapeHtml(r.owner_email || '—')}</td>
```

(In `renderRows` the loop variable is `u`, not `r` — use `${escapeHtml(u.owner_email || '—')}`.)

- [ ] **Step 5: Hide the admin link from regular users**

Locate the "Onboarded Users" / `/admin` link in `bank.html` (an `<a href="/admin">`; if none exists, this step is only the guard). Give it `id="adminLink"` and `style="display:none"`, then in the `if (IS_ADMIN)` block:

```js
          const adminLink = document.getElementById('adminLink');
          if (adminLink) adminLink.style.display = '';
```

If there is genuinely no admin link in `bank.html` today, add one in the header next to the version line:
```html
<a href="/admin" id="adminLink" style="display:none; margin-right:12px; color:#4c51bf; text-decoration:none; font-size:12px;">Users</a>
```

- [ ] **Step 6: Manual verification (browser)**

The assistant cannot type passwords. Use this setup:
1. Start the app on local SQLite (`python app.py`).
2. Create a throwaway account via `/signup` (e.g. `tester@example.com`). Log in.
3. **User view:** on `/bank`, confirm — no "Entered By" column on any of the 4 tabs, no "Users"/admin link. Create a bank account; it appears. Open `/admin` directly → 403 page with "Back to Bank".
4. Stop the app, restart with `ADMIN_EMAILS=tester@example.com` set. Hard-refresh `/bank`.
5. **Admin view:** "Entered By" column now visible as the last column on all 4 tabs, showing emails; "Users" link visible; `/admin` loads.

- [ ] **Step 7: Commit**

```bash
git add bank.html
git commit -m "feat(ui): admin-only Entered By column and role bootstrap on bank page"
```

---

## Task 9: Frontend — "Entered by" dropdowns, filter integration, PDF param

**Files:**
- Modify: `bank.html` — 4 toolbar selects, populate from `/api/entry-owners`, filter hooks in 4 render fns, `exportPdf` owner arg

**Interfaces:**
- Consumes: `IS_ADMIN`, `GET /api/entry-owners`
- Produces: per-tab `#ownerFilter_<tab>` selects (admin-only), each filtering its tab; `exportPdf` appends `&owner=` when an admin filter is set

- [ ] **Step 1: Add the four selects**

In each of the 4 tab toolbars (next to the existing sort `<select>`), add:

- Entered Bank Accounts: `<select class="owner-filter" id="ownerFilter_bank"></select>`
- 8F Issued: `<select class="owner-filter" id="ownerFilter_8f"></select>`
- Paid: `<select class="owner-filter" id="ownerFilter_paid"></select>`
- Pending: `<select class="owner-filter" id="ownerFilter_pending"></select>`

- [ ] **Step 2: Populate them on admin load**

In the init IIFE, after `IS_ADMIN` is set and `document.body.classList.add('is-admin')`:

```js
        if (IS_ADMIN) {
          try {
            const owners = await (await fetch('/api/entry-owners')).json();
            const opts = '<option value="">All users</option>' +
              owners.map(e => `<option value="${escapeHtml(e)}">${escapeHtml(e)}</option>`).join('');
            ['bank', '8f', 'paid', 'pending'].forEach(t => {
              const sel = document.getElementById('ownerFilter_' + t);
              if (sel) {
                sel.innerHTML = opts;
                sel.addEventListener('change', () => {
                  if (t === 'bank') renderRows();
                  else if (t === '8f') renderEightFRows();
                  else if (t === 'paid') renderPaidRows();
                  else renderPendingRows();
                });
              }
            });
          } catch (e) { /* leave dropdowns empty */ }
        }
```

- [ ] **Step 3: Apply the owner filter in each render function**

In `renderRows` (after the text-filter `if (q) {...}` block, before `sortRecords(...)`):

```js
      const ownerVal = document.getElementById('ownerFilter_bank')?.value || '';
      if (ownerVal) rows = rows.filter(u => (u.owner_email || '') === ownerVal);
```

Same pattern in `renderEightFRows` (`ownerFilter_8f`, var `r`), `renderPaidRows` (`ownerFilter_paid`), `renderPendingRows` (`ownerFilter_pending`). In the paid/pending functions the array is `rows` and is reassigned with `.filter`, matching the existing `rows = q ? ... : X.slice()` style.

- [ ] **Step 4: Include owner email in the free-text filters**

In each of the 4 render functions' text-filter predicate, add a clause:

```js
        (u.owner_email || '').toLowerCase().includes(q) ||
```

(use `r.` where the loop var is `r`). Harmless for non-admins (field absent).

- [ ] **Step 5: Pass `owner` to `exportPdf`**

Find `exportPdf(tab, sortBy)` and the 4 Export-PDF click handlers. Change the function:

```js
    function exportPdf(tab, sortBy) {
      let url = `/api/export-pdf?tab=${encodeURIComponent(tab)}&sort=${encodeURIComponent(sortBy)}`;
      const key = tab === 'epfo-8f' ? '8f' : tab;
      const ownerVal = document.getElementById('ownerFilter_' + key)?.value || '';
      if (IS_ADMIN && ownerVal) url += `&owner=${encodeURIComponent(ownerVal)}`;
      window.open(url, '_blank');
    }
```

(Match the existing implementation's navigation method — if it sets `window.location` or builds an `<a>`, keep that; only add the `owner` param logic. Confirm the `tab` string each caller passes: the bank tab passes `'bank'`, the 8F tab passes `'8f'` — align the `key` mapping with reality.)

- [ ] **Step 6: Manual verification (browser)**

With `ADMIN_EMAILS` including your test account and at least two users' worth of data:
1. `/bank` as admin — each tab shows an "All users" dropdown listing both emails.
2. Pick a user in the Entered Bank Accounts dropdown → table shows only that user's rows; count updates.
3. Repeat on 8F / Paid / Pending.
4. Type an email fragment in the free-text filter → matches by owner.
5. With a user selected, click Export PDF → the PDF contains only that user's rows and the "Entered By" column.
6. As a regular user (unset `ADMIN_EMAILS` / different login) → no dropdowns visible, PDF has no owner column.

- [ ] **Step 7: Commit**

```bash
git add bank.html
git commit -m "feat(ui): per-tab Entered By filter dropdown and PDF owner param"
```

---

## Task 10: Full regression pass + version bump to v1.3.0

**Files:**
- Modify: `bank.html` (version label + `VERSION_HISTORY`), `AGENTS.md`, `CHANGELOG.md`

**Interfaces:**
- Consumes: everything
- Produces: v1.3.0 released state

- [ ] **Step 1: Full backend test run**

Run: `pytest tests/ -v`
Expected: all pass. If any fail, fix before continuing (do not bump version over red tests).

- [ ] **Step 2: Migration dry-run against a copy of production shape**

Run:
```bash
python -c "import app; app.init_db(); print('init_db ok')"
```
against the local SQLite DB (which has real-ish rows). Confirm: no error, `owner_email` populated on all existing `bank_accounts` / `epfo_8f_records` rows:
```bash
python -c "import app; c=app._connect(); cur=c.cursor(); cur.execute('SELECT COUNT(*) FROM bank_accounts WHERE owner_email IS NULL'); print('null owners:', cur.fetchone()[0])"
```
Expected: `null owners: 0`.

- [ ] **Step 3: End-to-end browser pass**

Follow Task 8 Step 6 and Task 9 Step 6 checklists end to end, both roles. Confirm no console errors, all 4 tabs, sort still works, filters still work, PDF for each tab in each role.

- [ ] **Step 4: Bump version — `bank.html`**

- Change the version label (`id="versionLink"`) from `v1.0.0 → v1.2.8 (current)` to `v1.0.0 → v1.3.0 (current)`.
- Prepend to `VERSION_HISTORY`:

```js
      { v: "v1.3.0", date: "<YYYY-MM-DD HH:MM IST>", changes: ["Role-based access: each user sees only the bank-account and 8F data they entered", "Admin (set via ADMIN_EMAILS) sees all data plus an 'Entered By' column and a per-tab filter by user", "All data pages and APIs now require login; the Users/admin area requires the admin role", "A user can no longer view, edit or delete another user's record by ID (returns 404)", "PDF export is owner-scoped; admin exports include the 'Entered By' column", "Existing records assigned to the admin on upgrade"] },
```

- [ ] **Step 5: Bump version — `AGENTS.md`**

- Update `**Last Completed:**` to the v1.3.0 line.
- Add to the version list: `- v1.3.0 — Role-based access control (owner_email, admin via ADMIN_EMAILS, full route lockdown) (current)` and drop `(current)` from v1.2.8.
- Under **Last Known Working State** add: `- RBAC: users see only their own entries; admin (ADMIN_EMAILS env) sees all + "Entered By" column/filter; login required on all data routes`.
- Under **Database Schema (current)** add `owner_email` to `bank_accounts` and `epfo_8f_records`.
- Add to env vars list (Render Web Service section): `ADMIN_EMAILS` (comma-separated; default `raghunatha.maharana@gmail.com`).

- [ ] **Step 6: Bump version — `CHANGELOG.md`**

Prepend:

```markdown
## [2026-09-01] — v1.3.0

### Added
- **Role-based access control.** Two roles derived from the login email against the `ADMIN_EMAILS` env var (default `raghunatha.maharana@gmail.com`); no role column in the DB.
- `owner_email` column on `bank_accounts` and `epfo_8f_records`, stamped from the session on create; existing rows back-filled to the admin on startup.
- Admin-only **"Entered By"** column on all four list tabs and in PDF exports, plus a per-tab "Entered by" filter dropdown (`GET /api/entry-owners`).
- `role` field in `GET /api/me`.

### Changed
- `/bank` and every `/api/*` data route now require a logged-in session; `/admin`, `/api/users`, `/api/entry-owners` require the admin role.
- Bank-account and 8F list/read/update/delete/PDF queries are scoped to the caller's `owner_email` unless the caller is admin.
- Accessing another user's bank-account row by ID returns `404` (was: visible to anyone).

### Migration
- `init_db()` adds `owner_email` (backward-compatible `ALTER TABLE`), back-fills NULLs to the admin email, and creates `idx_bank_accounts_owner` / `idx_epfo_8f_records_owner`. Runs on every startup; idempotent.
```

- [ ] **Step 7: Commit**

```bash
git add bank.html AGENTS.md CHANGELOG.md
git commit -m "Bump version to v1.3.0 (role-based access control)"
```

- [ ] **Step 8: Push**

```bash
git push origin main
```

Confirm with the user before pushing if they have not pre-authorized it. After push, note that Render auto-deploys and runs the Postgres migration on boot — watch the first request for a `psycopg2` error and confirm `owner_email` back-filled on Neon.

---

## Self-Review

**Spec coverage:**

| Spec section | Task(s) |
|---|---|
| Roles / `ADMIN_EMAILS` / helpers | 1 |
| Schema + migration + backfill + indexes | 2 |
| `login_required` / `admin_required` + route matrix | 3 |
| `owner_scope_sql`; list/read/create scoping | 4 |
| update/delete/8F scoping; PUT 8F-sync stamp | 5 |
| PDF export scoping + `owner` param + admin column | 6 |
| `/api/me` role; `/api/entry-owners` | 7 (stub in 3) |
| Frontend role bootstrap + owner column + admin link | 8 |
| Frontend dropdowns + filter + PDF param | 9 |
| Error-handling table | 3 (auth), 4–5 (404), 8 (safe default) |
| Testing (backend) | 1–7 |
| Testing (frontend, manual) | 8–9 |
| Out of scope items | respected (no role column, no owner sort, signup unchanged) |
| Version bump v1.3.0 | 10 |

No gaps.

**Placeholder scan:** No "TBD"/"add error handling"/"similar to Task N". Two spots say "match the existing implementation" (PDF navigation method in Task 9 Step 5; single-column read style in Task 7 Step 4) — these are deliberate "read the current code and stay consistent" instructions with a concrete fallback given, not placeholders.

**Type consistency:**
- `owner_scope_sql(column) -> (str, list)` — used consistently in Tasks 4, 5, 6 with `"b.owner_email"`.
- `_export_records(tab, sort_key, owner_filter) -> list[dict]` — defined Task 6, used only there.
- `admin_backfill_email()` — Task 1, used Task 2.
- `IS_ADMIN` (JS) — set Task 8, read Tasks 8 & 9.
- `#ownerFilter_bank|_8f|_paid|_pending` — created Task 9 Step 1, referenced Steps 2–5 with the same ids.
- Row dict key `owner_email` — added to SELECTs in Tasks 4/5/6, read in JS Tasks 8/9 as `u.owner_email` / `r.owner_email`.
- `current_role()` / `is_admin()` — Task 1, used 3/4/5/6/7.

Consistent.
