# AGENTS.md — Project Context for Bank Account Application

---

## Project Identity

**Project Name:** Bank Account Management System  
**Purpose:** EPFO bank account management with establishment lookup, IFSC auto-fill, EPFO payment tracking (7A, 7Q, 14B), 8F record generation, and PDF export.  
**Current Objective:** Complete the bank.html UI to match the preview design (3-card layout + EPFO table) and ensure all functionality works.  
**Entry Point:** `app.py` (Flask application)  
**Start Command:** `python app.py` (from `C:\Users\Dell\Desktop\bank_account`)  
**Local URL:** `http://127.0.0.1:5000`  
**Key Routes:**
- `/` — Onboarding form
- `/admin` — Onboarded users list
- `/bank` — Bank details management (main feature)
- `/api/onboard` — Create account
- `/api/users` — List users
- `/api/establishments` — Search establishments
- `/api/bank-accounts` — CRUD bank accounts
- `/api/epfo-8f` — List 8F records
- `/api/ifsc/<code>` — IFSC lookup (Razorpay API)
- `/api/export-pdf` — PDF export (bank/8f tabs)

---

## Architecture

**Backend:** Python 3 + Flask 3.0  
**Frontend:** Vanilla HTML/CSS/JS (single-file templates: `onboarding.html`, `admin.html`, `bank.html`)  
**Database:** SQLite (`logs/onboarding.sqlite3`) via `sqlite3` stdlib  
**External API:** Razorpay IFSC lookup (`https://ifsc.razorpay.com/`)  
**PDF Generation:** ReportLab (landscape A4)

**Key Files:**
- `app.py` — All routes, DB init, PDF export, IFSC proxy
- `import_establishments.py` — CSV import script for establishments
- `bank.html` — Main UI (needs rewrite to match `bank-preview.html`)
- `bank-preview.html` — Reference design (3-card layout + EPFO table)
- `onboarding.html` — User registration
- `admin.html` — Admin user list
- `requirements.txt` — Flask, MetaTrader5, pytest

---

## Database

**Engine:** SQLite 3  
**Path:** `logs/onboarding.sqlite3` (6.3 MB, 48,791 establishments)  
**Connection:** `sqlite3.connect(DB_PATH)` with `row_factory = sqlite3.Row`

### Tables

| Table | Key Columns | Notes |
|-------|-------------|-------|
| `onboarded_users` | id, full_name, email, phone, date_of_birth, country, password_hash, created_at | Unique email |
| `establishments` | id, sr_no, est_id (UNIQUE), est_name, office, circle, aeo, phone | 48,791 rows imported from CSV |
| `bank_accounts` | id, establishment_id (FK), account_number, ifsc, code, bank_name, branch, address, city1, city2, district, state, phone, contact, aeo, period, amount_* (24 columns), total_amount, payment_status, payment_date, eight_f_issued, eight_f_number, eight_f_issued_date, created_at | FK → establishments(id) CASCADE |
| `epfo_8f_records` | id, bank_account_id (FK), establishment_id (FK), est_id, est_name, aeo, eight_f_number, eight_f_issued_date, account_number, ifsc, bank_name, branch, address, city1, city2, district, state, phone, period, total_amount, payment_status, amount_* (24 columns), created_at | FK → bank_accounts(id), establishments(id) CASCADE |

### Relationships
- `bank_accounts.establishment_id` → `establishments.id` (CASCADE DELETE)
- `epfo_8f_records.bank_account_id` → `bank_accounts.id` (CASCADE DELETE)
- `epfo_8f_records.establishment_id` → `establishments.id` (CASCADE DELETE)

### Existing Data
- 48,791 establishments (Odisha region)
- 0 bank accounts (empty, ready for input)
- 0 epfo_8f_records (empty)

### Migration Procedure
- `import_establishments.py` runs `init_db()` (idempotent CREATE TABLE + ALTER TABLE for missing columns)
- No formal migration tool; schema changes handled by ALTER TABLE in `init_db()`

---

## Existing Functionality

### Completed Features
- ✅ Onboarding form with validation (name, email, phone, DOB, country, password)
- ✅ Admin page: list/search onboarded users
- ✅ Establishment search (48k records, dropdown with code/name filter)
- ✅ IFSC lookup via Razorpay API (auto-fills bank, branch, address, city, district, state)
- ✅ Bank account CRUD API (POST, GET, PUT, DELETE `/api/bank-accounts`)
- ✅ 8F record auto-creation when `eight_f_issued=true`
- ✅ EPFO 8F list API (UNION of explicit records + bank_accounts with 8F issued)
- ✅ PDF export for both tabs (sorted, landscape A4)
- ✅ Amount auto-calculation (section totals + grand total) in frontend JS

### Partially Completed / Broken
- ⚠️ **bank.html UI** — Has incomplete restructure attempt (3-card layout via `outerHTML` cloning breaks event listeners). Current DOM is hybrid of old `form-line` structure and new cards.
- ⚠️ **EPFO amount table** — Old horizontal rows (4 sections × 5 accounts) exist but are hidden by CSS; preview design shows compact vertical table with labeled sections.
- ⚠️ **Event listeners** — Re-binding after DOM restructure is incomplete; establishment search, IFSC lookup, 8F toggle may not work on new card elements.

### Unfinished / Missing
- ❌ Clean 3-card form matching `bank-preview.html` (Establishment | Bank | Payment)
- ❌ Compact EPFO table matching preview (vertical sections with A/c 1-22 inputs + totals)
- ❌ Period "from/to" (two month inputs) — preview shows this; current has single text input
- ❌ 8F inline fields (checkbox + number + date in one row) — preview shows this
- ❌ Status inline (select + date) — preview shows this

---

## Development Rules

1. **Continue, don't rebuild** — Preserve all working backend/API code.
2. **Preserve database** — Never delete/reset `logs/onboarding.sqlite3`.
3. **Inspect before modify** — Read existing code first.
4. **Reuse architecture** — Keep Flask + vanilla JS + SQLite.
5. **Safe migrations** — Use ALTER TABLE in `init_db()` for schema changes.
6. **Test after changes** — Run app, test affected endpoints/UI.
7. **Fix errors autonomously** — Handle ordinary coding errors without stopping.
8. **Avoid unnecessary rewrites** — Only rewrite broken UI (bank.html).
9. **Production-oriented** — Validate input, handle errors, no hardcoded secrets.
10. **Match preview design** — `bank-preview.html` is the reference for bank.html.

---

## Current Development Status

**Last Completed:** `bank.html` rewritten to match `bank-preview.html` design:
- 3 equal cards (Establishment | Bank | Payment) with uniform `.field` grid layout
- Compact EPFO table with 4 sections (7A, 7Q of 7A, 14B, 7Q of 14B) × 5 account columns + Total column
- Grand total row with gradient background
- Inline Period (from/to month inputs), 8F (checkbox + number + date), Status (select + date)
- All form fields map to existing backend API field names
- All JS event handlers wired correctly to new DOM (no `outerHTML` cloning)
- Establishment search with dropdown, IFSC lookup, auto-fill from existing records
- Edit/Delete in bank accounts table, PDF export for both tabs
- 8F Issued tab with 15 columns
- Tab switching, filters, sort dropdowns all working

**Currently Working On:** Updating documentation (AGENTS.md, CHANGELOG.md) to reflect completed work.

**Last Known Working State:** Flask app runs on port 5000; all APIs return correct data; bank.html now matches preview design structurally and functionally.

**Next Tasks:**
1. ✅ Documentation update (in progress)
2. Verify all CRUD operations via browser testing
3. Verify PDF export works for both tabs with data
4. Test establishment search and IFSC lookup end-to-end
5. Test edit/delete in table

**Unresolved Issues:** None critical.

---

## Quick Reference: API Field Names (for form mapping)

```
establishment_id, account_number, ifsc, code, bank_name, branch, address,
city1, city2, district, state, phone, contact, aeo, period,
amount_7a_ac1, amount_7a_ac2, amount_7a_ac10, amount_7a_ac21, amount_7a_ac22,
amount_7q_7a_ac1, amount_7q_7a_ac2, amount_7q_7a_ac10, amount_7q_7a_ac21, amount_7q_7a_ac22,
amount_14b_ac1, amount_14b_ac2, amount_14b_ac10, amount_14b_ac21, amount_14b_ac22,
amount_7q_14b_ac1, amount_7q_14b_ac2, amount_7q_14b_ac10, amount_7q_14b_ac21, amount_7q_14b_ac22,
total_amount, payment_status, payment_date, eight_f_issued, eight_f_number, eight_f_issued_date
```