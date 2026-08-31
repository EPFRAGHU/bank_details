# Changelog

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

## [2026-09-01] — v1.2.8

### Fixed
- **App would not start** — restored `render_template` import + `template_folder="."` (login/signup/admin returned 500); fixed an `IndentationError` in `export_pdf()` that stopped the module importing
- **Bank page JavaScript was completely inert** — re-added the lost opening `<script>` tag (page JS rendered as text); fixed a temporal-dead-zone `ReferenceError` on `paidSearchEl` / `pendingSearchEl`
- **PDF export "Sort: Amount" returned 500** — numeric/blank comparison error, fixed via new `_sort_records()` helper
- **Editing a bank account silently dropped `demand_type` / `rrc_number` / `rrc_date`** — `PUT /api/bank-accounts/<id>` now persists them (and includes them in the 8F-sync insert)
- **Sorting dropdown did nothing on the Entered Bank Accounts and 8F Issued tabs** — no change listener and no sort logic; now sorts via a shared `sortRecords()` helper on all four list tabs (also fixes `Sort: Bank` looking up the wrong field)
- **Entered Bank Accounts filter ignored the AEO field** — now matched alongside est code / name / IFSC / bank / account / branch

### Added
- **Entered Bank Accounts** and **8F Issued** tabs: `Sort: Payment` option in the sort dropdown

### Removed
- Debug logging left in `app.py` (module-load prints, per-request logger, custom 500 handler, HTML-comment injection in `/bank`)

## [2026-08-28] — v1.2.7 (Auto-bumped)

### Added
- **Payment card**: Demand type radio button (Current | Arrear)
- **Payment card**: RRC No. and RRC Date fields (shown when demand is selected)
- **Entered Bank Accounts table**: Demand, RRC No, RRC Date columns
- **8F Issued table**: Demand, RRC No, RRC Date columns
- **Database migration**: demand_type, rrc_number, rrc_date columns added to bank_accounts and epfo_8f_records (backward-compatible ALTER TABLE)

### Updated
- `AGENTS.md` — Updated CURRENT STATUS with v1.2.7 details, full schema, migration procedure
- `CHANGELOG.md` — Added v1.2.7 entry

## [2026-08-28] — Memory Save (v1.2.6)

### Changed
- Optimized bank page load: lazy-load 48k establishments (only on search focus)
- Parallel API calls (loadBankAccounts + loadEightFRecords) via Promise.all
- HTTP caching for /api/establishments (max-age=300)
- Redirect home page to /login; add /signup route for new account creation
- Convert all timestamps to India/IST timezone (UTC+5:30)
- Add running date/time clock above version number
- Add version history modal (click version to see all releases)
- Period displayed as MM/YYYY on one line in both tables
- Fix 8F payment_status to always read from bank_accounts (source of truth)
- PDF: right-aligned amounts, widened columns, simplified money format
- AEO column wraps properly, period stacked vertically on form

## [2026-08-27] — Initial Project State (Inherited)

### Added
- `.gitignore` — excludes database, logs, test files, IDE configs
- Git repository initialized and pushed to `https://github.com/EPFRAGHU/bank_details.git`

### Changed
- `AGENTS.md` — Updated CURRENT STATUS section with git push milestone and last known working state
- `CHANGELOG.md` — Added git push entry

### Notes
- Database (`logs/onboarding.sqlite3`) excluded from git via .gitignore to preserve local data
- 13 files committed (52,443 insertions)
- Branch: `main`

## [2026-08-27] — UI Refinements (Round 2)

### Changed
- `bank.html` — Period fields changed from `type="month"` to `type="date"` (full calendar picker)
- `bank.html` — Bank name in table shows only `bank_name` (removed " — Branch" suffix, removed `bank_branch` field)
- `bank.html` — AEO column added to "Entered Bank Accounts" table after Establishment name
- `bank.html` — GRAND TOTAL row now shows per-account sums (A/c 1, 2, 10, 21, 22) + overall total
- `bank.html` — Period persistence on edit fixed (handles "15 May 2005 to 10 May 2008" format)
- `bank.html` — Address field moved from Establishment card to Bank card (where it belongs)
- `bank.html` — Address column removed from "Entered Bank Accounts" table

## [Unreleased]

### Fixed
- **Invalid exception class** — `except sqlite3.ForeignKeyError` (which does not exist in Python's sqlite3 module) replaced with `except sqlite3.IntegrityError` + message inspection
- **Foreign keys not enforced** — Added `_connect()` helper that sets `PRAGMA foreign_keys = ON` on every connection; replaced all `sqlite3.connect(DB_PATH)` calls in route handlers
- **Dead POST code in GET handler** — `bank_accounts()` had the POST handler as unreachable code (unconditional return at end of GET block). Restructured to use explicit `if/else` branching by method
- **INSERT value/column mismatch** — `INSERT INTO bank_accounts` had 43 `?` placeholders but 45 columns in the column list (missing 2). Fixed to 45 `?`
- **INSERT value/column mismatch** — `INSERT INTO epfo_8f_records` had 45 `?` placeholders but 44 columns. Fixed to 44 `?`
- **Type error on int payload values** — `payload.get(field).strip()` failed when JSON sends numeric values. Added payload normalization to strings before validation
- **Missing upfront establishment validation** — Added explicit `SELECT id FROM establishments WHERE id = ?` check before INSERT to return clean 404 for unknown establishment_id (rather than relying solely on FK constraint which was disabled)

### Changed
- `app.py` — Added `_connect()` helper for foreign-key-enabled connections
- `app.py` — Added explicit establishment existence check in POST `/api/bank-accounts`

### Verified
- POST with invalid establishment_id returns 404 (was: 500)
- POST with valid establishment_id creates record (201) and auto-creates 8F record
- GET list returns accounts with joined establishment data
- DELETE removes account
- PDF export works (200, application/pdf)
- IFSC lookup works
- Bank page loads (200)

### Notes
- Database unchanged; all 48,791 establishments preserved
- No data loss from any operation

## [2026-08-27] — bank.html UI Rewrite

### Changed
- **`bank.html`** — Complete rewrite to match `bank-preview.html` design:
  - Replaced old form-line layout with 3 equal cards (Establishment | Bank | Payment) using uniform `.field` grid
  - Replaced horizontal EPFO amount rows with compact vertical table (4 sections × 5 accounts + Total + Grand Total)
  - Added Period from/to (two `<input type="month">` fields) with sync to hidden `period` field
  - Added inline 8F fields (checkbox + number + date) and Status fields (select + date)
  - Removed broken `restructureForm` IIFE that used `outerHTML` cloning and lost event listeners
  - Updated table styling to match preview (`.data-table`, `.status-pill`, `.epfo-table`)

### Fixed
- **Event listeners** — All event handlers now wired directly to the correct DOM elements (no more re-binding after DOM cloning)
- **Establishment search** — Dropdown, keyboard navigation, and selection all work on the new card structure
- **IFSC lookup** — Auto-fill populates Bank Name, Address (combined), and hidden fields (branch, city1, city2, district, state, phone, contact)
- **Auto-fill from existing records** — When selecting an establishment with existing bank accounts, the form is pre-populated with the most recent record's data
- **EPFO total calculation** — Section totals and grand total auto-calculate on input; total display uses `₹X.XX` format matching preview
- **Period handling** — New `setPeriod()`/`syncPeriod()` functions handle `Apr-2026`, `Apr-2026 to Sep-2026`, and `2026-04` formats

### Notes
- All backend API field names preserved (no changes to `app.py` or database schema)
- Form submission, edit, delete, PDF export, tab switching all functional
- Database unchanged: 48,791 establishments, 0 bank accounts, 0 8F records

## [2026-08-27] — Project Audit & Documentation Setup

### Added
- `AGENTS.md` — Primary AI project memory with full architecture, database schema, features, and development rules
- `README.md` — Human documentation with project overview, setup, API endpoints, and troubleshooting
- `CHANGELOG.md` — This file

### Database
- Verified existing schema: 4 tables (`onboarded_users`, `establishments`, `bank_accounts`, `epfo_8f_records`)
- 48,791 establishments pre-loaded from CSV
- 0 bank accounts, 0 8F records (ready for input)

### Notes
- All backend APIs functional and tested
- Flask app runs on port 5000
- IFSC lookup via Razorpay API working
- PDF export functional for both tabs

## [2026-08-27] — Initial Project State (Inherited)

### Completed Features
- Onboarding form with validation (name, email, phone, DOB, country, password)
- Admin page: list/search onboarded users
- Establishment search (48k records, dropdown with code/name filter)
- IFSC lookup via Razorpay API (auto-fills bank, branch, address, city, district, state)
- Bank account CRUD API (POST, GET, PUT, DELETE `/api/bank-accounts`)
- 8F record auto-creation when `eight_f_issued=true`
- EPFO 8F list API (UNION of explicit records + bank_accounts with 8F issued)
- PDF export for both tabs (sorted, landscape A4)
- Amount auto-calculation (section totals + grand total) in frontend JS

### Partially Completed / Broken (at inheritance)
- `bank.html` UI — Incomplete restructure attempt (3-card layout via `outerHTML` cloning breaks event listeners). Current DOM was hybrid of old `form-line` structure and new cards.
- EPFO amount table — Old horizontal rows (4 sections × 5 accounts) existed but were hidden by CSS; preview design shows compact vertical table with labeled sections.
- Event listeners — Re-binding after DOM restructure was incomplete; establishment search, IFSC lookup, 8F toggle may not have worked on new card elements.

### Missing / Unfinished (at inheritance)
- Clean 3-card form matching `bank-preview.html` (Establishment | Bank | Payment) — **NOW FIXED**
- Compact EPFO table matching preview (vertical sections with A/c 1-22 inputs + totals) — **NOW FIXED**
- Period "from/to" (two month inputs) — **NOW FIXED**
- 8F inline fields (checkbox + number + date in one row) — **NOW FIXED**
- Status inline (select + date) — **NOW FIXED**

### Architecture
- Backend: Python 3 + Flask 3.0
- Frontend: Vanilla HTML/CSS/JS (single-file templates)
- Database: SQLite 3 (`logs/onboarding.sqlite3`) via `sqlite3` stdlib
- External API: Razorpay IFSC lookup
- PDF Generation: ReportLab (landscape A4)

### Key Files
- `app.py` — All routes, DB init, PDF export, IFSC proxy
- `import_establishments.py` — CSV import script with idempotent migrations
- `bank.html` — Main UI (rewritten 2026-08-27)
- `bank-preview.html` — Reference design
- `onboarding.html` — User registration
- `admin.html` — Admin user list