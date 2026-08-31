# Role-Based Access Control — Design Spec

**Date:** 2026-09-01
**Status:** Approved for implementation
**Target version:** v1.3.0

## Problem

The app has authentication (login, session with `user_id` / `user_email` / `user_name`)
but **no authorization**. `/bank`, `/admin`, and every `/api/*` data route is reachable
by anyone, logged in or not, and every user sees every bank-account and 8F record.

We want:

1. A regular user sees **only the bank-account / 8F data they entered**.
2. An **admin** sees **all** data, plus an "Entered By" column showing which
   user entered each row, and can filter the tables by that user.
3. All data pages and APIs require a logged-in session; the admin area requires
   the admin role; a user cannot read/edit/delete another user's row even by ID.

## Roles

Two roles, derived from the login email — **no `role` column in the database**.

- `ADMIN_EMAILS` constant in `app.py`:
  ```python
  ADMIN_EMAILS = {
      e.strip().lower()
      for e in os.getenv("ADMIN_EMAILS", "raghunatha.maharana@gmail.com").split(",")
      if e.strip()
  }
  ```
- Helpers:
  ```python
  def current_role():
      return "admin" if session.get("user_email", "").lower() in ADMIN_EMAILS else "user"

  def is_admin():
      return current_role() == "admin"
  ```
- The default value covers the current admin, so the feature works with no
  configuration. On Render, set `ADMIN_EMAILS` (comma-separated) to change admins;
  requires a restart.

## Database schema & migration

Add one column to two tables:

| Table | New column |
|---|---|
| `bank_accounts` | `owner_email TEXT` |
| `epfo_8f_records` | `owner_email TEXT` |

Changes in `app.py`:

- Add `owner_email TEXT` to the `bank_accounts` and `epfo_8f_records` definitions in
  both `SCHEMA_SQLITE` and `SCHEMA_POSTGRES`.
- Extend the idempotent migration loop in `init_db()` to include `owner_email`
  alongside `demand_type` / `rrc_number` / `rrc_date` — same pattern
  (`PRAGMA table_info` / `information_schema.columns` check, then
  `ALTER TABLE ... ADD COLUMN owner_email TEXT`).
- **Backfill**, immediately after the ALTER, once per table:
  ```sql
  UPDATE bank_accounts   SET owner_email = :admin_email WHERE owner_email IS NULL;
  UPDATE epfo_8f_records SET owner_email = :admin_email WHERE owner_email IS NULL;
  ```
  where `:admin_email` = `sorted(ADMIN_EMAILS)[0]` (falls back to
  `"raghunatha.maharana@gmail.com"` if the set is somehow empty). Idempotent —
  only touches NULLs — so existing rows on local SQLite and Neon are assigned to
  the admin on first deploy, and subsequent startups do nothing.
- Indexes:
  ```sql
  CREATE INDEX IF NOT EXISTS idx_bank_accounts_owner   ON bank_accounts(owner_email);
  CREATE INDEX IF NOT EXISTS idx_epfo_8f_records_owner  ON epfo_8f_records(owner_email);
  ```

## Authentication & route protection

Two decorators in `app.py`:

```python
def login_required(f): ...
def admin_required(f): ...   # login_required + is_admin() check
```

"Is this an API route" = `request.path.startswith("/api/")`.

- Not authenticated:
  - API route → `401 {"status": "error", "message": "Login required"}`
  - page route → `302 → /login`
- Authenticated but not admin, on an admin route:
  - API route → `403 {"status": "error", "message": "Admin access required"}`
  - page route (`/admin`) → `403` with a minimal HTML body linking to `/bank`

Route protection matrix:

| Route | Protection |
|---|---|
| `/`, `/login`, `/signup`, `/api/login`, `/api/logout`, `/api/onboard`, `/api/me` | public |
| `/bank` | `@login_required` |
| `/api/bank-accounts` GET/POST | `@login_required` |
| `/api/bank-accounts/<id>` GET/PUT/DELETE | `@login_required` + row-ownership check |
| `/api/epfo-8f` | `@login_required` |
| `/api/establishments` | `@login_required` (not owner-filtered — shared reference data) |
| `/api/ifsc/<code>` | `@login_required` |
| `/api/export-pdf` | `@login_required` |
| `/admin`, `/api/users` | `@admin_required` |
| `/api/entry-owners` (new) | `@admin_required` |

Self-registration via `/signup` stays open; new accounts are regular users.

## Ownership filtering in queries

Helper:

```python
def owner_scope_sql(column):
    """Returns (sql_fragment, params) to append to a WHERE clause.
    column is the (possibly alias-qualified) owner column, e.g. "b.owner_email".
    Admin -> ('', []).
    User  -> (f' AND LOWER({column}) = ? ', [session_email_lower])."""
```

Callers pass the alias-qualified column (`"b.owner_email"`). For PostgreSQL the
`?` is translated by the existing `_translate_sql`; the fragment is spliced into
each handler's SQL before `_translate_sql` runs, matching the pattern already
used for the optional `payment_status` filter.

Applied to:

- **`GET /api/bank-accounts`** — append owner scope to the existing WHERE
  (which already optionally filters `payment_status`). Also governs the form's
  "existing accounts for this establishment" auto-fill — a user can no longer
  pre-fill from another user's record.
- **`GET /api/bank-accounts/<id>`** — fetch, then if `not is_admin()` and
  `row["owner_email"]` != session email → `404 {"status":"error","message":"Not found"}`.
- **`PUT /api/bank-accounts/<id>`** — same ownership check before the UPDATE;
  `owner_email` is never modified by an update.
- **`DELETE /api/bank-accounts/<id>`** — same ownership check → 404 if not owned.
- **`GET /api/epfo-8f`** — add `owner_scope_sql("b.owner_email")` to **both**
  halves of the UNION (both halves join/select `bank_accounts b`, so `b.owner_email`
  is always available and is the single source of truth for 8F ownership).
- **`GET /api/export-pdf`** — every branch (`bank`, `8f`, `paid`, `pending`)
  gets the owner scope. For admin, an optional `owner` query param further
  restricts to one email; for a non-admin the `owner` param is ignored and the
  scope is always their own email.
- **`POST /api/bank-accounts`** — insert `owner_email = session["user_email"]`
  into `bank_accounts`, and the identical value into the `epfo_8f_records`
  insert done by the 8F-sync path.
- **`PUT /api/bank-accounts/<id>`** — the 8F-sync insert (fires when 8F is newly
  ticked during an edit) also stamps `owner_email` from the row's existing owner.

## Role signal & "entered by" list

- **`GET /api/me`** — add `"role": current_role()` to the JSON.
- **`GET /api/entry-owners`** (new, `@admin_required`):
  ```sql
  SELECT DISTINCT owner_email FROM bank_accounts
  WHERE owner_email IS NOT NULL ORDER BY owner_email;
  ```
  Returns `["a@x.com", "b@y.com", ...]`. Populates the admin's "Entered by"
  dropdowns so they list only users who actually have entries.

## Frontend (`bank.html`)

**Role bootstrap.** The init IIFE already calls `/api/me` inside `if (meRes.ok)`
(runs for any logged-in user). Set a script-scope `let IS_ADMIN = false;` and,
in that block, `IS_ADMIN = meData.role === 'admin';`. If `/api/me` fails,
`IS_ADMIN` stays `false` (safe default). When `IS_ADMIN`, add class `is-admin`
to `<body>`.

**"Entered By" column — all 4 tables.** Add as the **last** column:

- `<th class="col-owner">Entered By</th>` at the end of each of the 4 `<thead>` rows
  (Entered Bank Accounts, 8F Issued, Paid, Pending).
- `<td class="col-owner">${escapeHtml(r.owner_email || '—')}</td>` as the last cell
  in each row template (`renderRows`, `renderEightFRows`, `renderPaidRows`,
  `renderPendingRows`).
- CSS: `.col-owner { display: none; }` and `body.is-admin .col-owner { display: table-cell; }`.
  The column is present in the DOM for everyone but only visible to admin; owner
  emails are still sent to non-admins' browsers only if the backend returns them —
  which it does not, because non-admin queries still `SELECT ... owner_email` but
  every returned row is the user's own. (Acceptable: a user seeing their own email.)

**"Entered by" dropdown — admin only.** In each of the 4 tab toolbars add
`<select class="owner-filter" id="ownerFilter_<tab>">`, styled
`display: none;` with `body.is-admin .owner-filter { display: inline-block; }`.
On admin load, one `fetch('/api/entry-owners')` populates all 4 with
`<option value="">All users</option>` + one `<option>` per email. Each dropdown's
`change` handler calls the corresponding render function.

**Filter integration.** In each render function's filtering step, after the
existing text-filter logic:
```js
const ownerVal = document.getElementById('ownerFilter_<tab>')?.value || '';
if (ownerVal) rows = rows.filter(r => (r.owner_email || '') === ownerVal);
```
Also add `(r.owner_email || '').toLowerCase().includes(q)` to each existing
free-text filter's match list (harmless for users — field is their own email).

**`/admin` link.** Show the "Onboarded Users" / admin link in `bank.html` only
when `IS_ADMIN` (hide it from regular users).

**Sorting.** `owner_email` is **not** added as a sort option. `sortRecords` is
unchanged.

## PDF export

- `bank.html` `exportPdf(tab, sortBy)` gains an optional `owner` argument. When
  `IS_ADMIN` and the tab's "Entered by" dropdown has a value, append
  `&owner=<email>` to the export URL.
- `app.py` `export_pdf()`:
  - Owner scope added to every query branch (see above).
  - If `is_admin()`: append an **"Entered By"** column (last column) to `headers`
    and to every `rows` entry, and add one extra width value to **each** of the
    two `widths` arrays (`8f/paid/pending` branch and `bank` branch). If not
    admin: column omitted entirely and widths unchanged.

## Error handling

| Situation | Response |
|---|---|
| Logged out, `/api/*` | `401 {"status":"error","message":"Login required"}` |
| Logged out, `/bank` | `302 → /login` |
| Non-admin → `/admin` | `403` HTML with link to `/bank` |
| Non-admin → `/api/users`, `/api/entry-owners` | `403 {"status":"error","message":"Admin access required"}` |
| Non-admin → `GET/PUT/DELETE /api/bank-accounts/<id>` not owned | `404 {"status":"error","message":"Not found"}` (not 403 — IDs not enumerable) |
| `/api/me` fails on frontend | `IS_ADMIN=false`; no column, no dropdown, no admin link |
| `owner_email` NULL on a row post-backfill | shows `—`; admin sees it; never matches a user's `WHERE owner_email = ?` |
| Session email no longer in `onboarded_users` | session still valid; queries return that email's (likely empty) scope |

## Testing

**Backend — script / test-client driven (against local SQLite):**

1. Migration: fresh DB gets `owner_email` on both tables + both indexes; existing
   rows backfill to admin email; second `init_db()` run is a no-op.
2. Auth: every protected route returns 401 (API) / 302 (page) when logged out;
   `/admin`, `/api/users`, `/api/entry-owners` return 403 for a non-admin session.
3. Ownership: create users `u1`, `u2`; use admin.
   - `u1` `POST /api/bank-accounts` → row's `owner_email` == u1; 8F-sync row too.
   - `u2` `GET /api/bank-accounts` → does not include u1's row.
   - admin `GET /api/bank-accounts` → includes it, with `owner_email`.
   - `u2` `GET/PUT/DELETE /api/bank-accounts/<u1 id>` → 404.
   - `u1` `PUT` own row → 200, `owner_email` unchanged.
4. `GET /api/epfo-8f`: u1 sees only own; admin sees all.
5. `GET /api/export-pdf` (`bank`, `8f`, `paid`, `pending`): u1 → only own;
   admin → all; admin `&owner=<u1>` → only u1's; `u2` `&owner=<u1>` → ignored,
   still only u2's; admin PDFs contain the "Entered By" column, user PDFs don't.
6. `GET /api/entry-owners`: admin → sorted distinct emails; user → 403.

**Frontend — browser driven:**

- Regular user: no "Entered By" column, no dropdown, no `/admin` link; all 4
  tabs show only own rows; PDF has no owner column.
- Admin: column visible last on all 4 tabs; "Entered by" dropdown populated from
  `/api/entry-owners`; selecting a user filters that tab; free-text filter also
  matches email; PDF includes the column.

**Credential constraint:** the assistant does not enter passwords, so browser
UI verification for the two roles requires either the user logging in, or
temporarily stubbing the two `/api/me` responses. Backend role behaviour is
verified via API/test-client with manually set session state. This will be
flagged during implementation.

## Out of scope

- No `role` column, no role-management UI, no promote/demote buttons.
- No "change email" feature (so `owner_email` as the ownership key cannot drift).
- No sort-by-owner option.
- No change to `/signup` openness.
- No re-assignment of a row's owner after creation.

## Version bump

On completion: **v1.3.0** (new feature — RBAC). Update `bank.html` label +
`VERSION_HISTORY`, `AGENTS.md`, `CHANGELOG.md`, as a separate "Bump version"
commit per project convention.
