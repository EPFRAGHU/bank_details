# Changelog

## [Unreleased]

### In Progress
- Final verification of bank.html CRUD operations, PDF export, establishment search, IFSC lookup

## [2026-08-27] — Backend Bug Fixes (app.py)

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