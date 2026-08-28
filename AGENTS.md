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
- `requirements.txt` — Flask, gunicorn, reportlab

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

**Last Completed:** v1.2.7 — Add Demand type (Current/Arrear) + RRC No. and RRC Date fields

**Currently Working On:** Saving to memory

**Last Known Working State:**
- Flask app deployed to Render with Neon PostgreSQL
- Home page redirects to /login; /signup for new accounts
- 48,791 establishments in Neon (preloaded)
- Bank page: 3-card layout, EPFO table with per-account grand totals
- Login page with session management
- 8F payment_status synced from bank_accounts (source of truth)
- PDF export: right-aligned amounts, no Rs./.00, wrapped text
- Period displays as MM/YYYY (e.g. 01/2005 to 05/2010)
- AEO column properly wraps
- Running IST clock + clickable version history modal
- Version auto-bumps on every change (v1.2.7 current)
- Demand type (Current/Arrear) radio + RRC No./Date fields
- Tables show Demand, RRC No, RRC Date columns
- Database auto-migrates new columns backward-compatibly

**Next Tasks:**
1. ✅ v1.2.7 — Demand/RRC fields (completed)
2. ✅ Memory save (in progress)
3. User acceptance testing
4. Future feature additions

**Unresolved Issues:** None critical.

**Git Repository:** `https://github.com/EPFRAGHU/bank_details.git` (branch: main)

**Neon Database:**
- URL: `postgresql://neondb_owner:npg_CPb6w7SsaMVF@ep-curly-base-b3kmxai6-pooler.c-4.ap-southeast-1.aws.neon.tech/neondb`
- Region: AWS Asia Pacific (Mumbai)
- 48,791 establishments + bank accounts + 8F records

**Render Web Service:**
- URL: `https://bank-account-app.onrender.com`
- Plan: Free tier
- Auto-deploys from GitHub main branch
- Env vars: DATABASE_URL, SECRET_KEY, PASSWORD_SALT, PYTHON_VERSION

**Version History (in bank.html):**
- v1.0.0 — Initial release (bank.html rewrite)
- v1.0.1 — Backend bug fixes
- v1.0.2 — Turso support
- v1.0.3 — PostgreSQL/Neon support
- v1.0.4 — Login page
- v1.1.0 — Payment column in 8F tab
- v1.1.1 — UI improvements
- v1.1.2 — AEO/period fixes
- v1.2.0 — Period MM/YYYY format
- v1.2.1 — 8F payment_status sync
- v1.2.2 — Removed "Back to users"
- v1.2.3 — PDF widen columns
- v1.2.4 — PDF column widths
- v1.2.5 — PDF right-align amounts
- v1.2.6 — Optimize bank page load
- v1.2.7 — Demand type + RRC fields (current)

**Database Schema (current):**
- `onboarded_users`: id, full_name, email, phone, date_of_birth, country, password_hash, created_at
- `establishments`: id, sr_no, est_id, est_name, office, circle, aeo, phone
- `bank_accounts`: id, establishment_id, account_number, ifsc, code, bank_name, branch, address, city1, city2, district, state, phone, contact, aeo, period, amount_7a_ac1-22, amount_7a_total, amount_7q_7a_ac1-22, amount_7q_7a_total, amount_14b_ac1-22, amount_14b_total, amount_7q_14b_ac1-22, amount_7q_14b_total, total_amount, payment_status, payment_date, eight_f_issued, eight_f_number, eight_f_issued_date, created_at, demand_type, rrc_number, rrc_date
- `epfo_8f_records`: same structure + bank_account_id, establishment_id, est_id, est_name, eight_f_number, etc.

**Migration Procedure:**
- `init_db()` is idempotent — runs CREATE TABLE IF NOT EXISTS
- Backward-compatible ALTER TABLE for new columns (demand_type, rrc_number, rrc_date)
- Runs on every app startup

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