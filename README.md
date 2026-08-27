# Bank Account Management System

## Overview

EPFO bank account management system with establishment lookup, IFSC auto-fill, EPFO payment tracking (7A, 7Q, 14B), 8F record generation, and PDF export.

## Purpose

Manage bank account details for EPFO establishments, track payments across multiple sections (7A, 7Q of 7A, 14B, 7Q of 14B), generate 8F records, and export data to PDF.

## Main Features

- **Onboarding** — User registration with validation
- **Admin Dashboard** — List and search onboarded users
- **Establishment Search** — 48,791 pre-loaded establishments with dropdown autocomplete
- **IFSC Auto-fill** — Razorpay API integration auto-fills bank name, branch, address, city, district, state
- **Bank Account CRUD** — Create, read, update, delete bank account records
- **EPFO Payment Tracking** — 4 sections × 5 account types (A/c 1, 2, 10, 21, 22) with auto-calculated totals
- **8F Record Generation** — Auto-create 8F records when `eight_f_issued=true`
- **PDF Export** — Landscape A4 export for both bank accounts and 8F records tabs
- **Data Tables** — Sortable, filterable tables with inline editing

## Technology Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3, Flask 3.0 |
| Frontend | Vanilla HTML/CSS/JS (single-file templates) |
| Database | SQLite 3 (`logs/onboarding.sqlite3`) |
| External API | Razorpay IFSC lookup (`https://ifsc.razorpay.com/`) |
| PDF Generation | ReportLab (landscape A4) |

## Project Structure

```
bank_account/
├── AGENTS.md                    # AI project memory
├── README.md                    # This file
├── CHANGELOG.md                 # Development history
├── app.py                       # Flask application (all routes)
├── import_establishments.py     # CSV import script
├── bank.html                    # Main UI (needs rewrite)
├── bank-preview.html            # Reference design
├── onboarding.html              # User registration
├── admin.html                   # Admin user list
├── requirements.txt             # Python dependencies
├── logs/
│   └── onboarding.sqlite3       # SQLite database (6.3 MB)
└── establishments_filtered_all.csv  # Source CSV (48,791 rows)
```

## Installation

### Requirements
- Python 3.8+
- pip

### Setup
```bash
cd C:\Users\Dell\Desktop\bank_account
pip install -r requirements.txt
```

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `ONBOARDING_DB` | `logs/onboarding.sqlite3` | Database path |
| `PASSWORD_SALT` | `onboarding-static-salt-change-me` | Password hashing salt |

## Running the Application

```bash
python app.py
```

**Local URL:** `http://127.0.0.1:5000`

### Key Routes
- `/` — Onboarding form
- `/admin` — Onboarded users list
- `/bank` — Bank details management (main feature)

## Database

**File:** `logs/onboarding.sqlite3` (6.3 MB, pre-populated)

### Tables
- `onboarded_users` — User accounts (unique email)
- `establishments` — 48,791 EPFO establishments (Odisha region)
- `bank_accounts` — Bank account records (FK → establishments)
- `epfo_8f_records` — 8F issued records (FK → bank_accounts, establishments)

### Important Notes
- **Never delete or reset** `logs/onboarding.sqlite3`
- Schema changes use ALTER TABLE in `import_establishments.py::init_db()`
- All tables use CASCADE DELETE on foreign keys

## Important Scripts

| Script | Purpose |
|--------|---------|
| `python app.py` | Start Flask server on port 5000 |
| `python import_establishments.py` | Import/re-import establishments from CSV |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Onboarding form |
| POST | `/api/onboard` | Create account |
| GET | `/api/users` | List users |
| GET | `/admin` | Admin dashboard |
| GET | `/api/establishments` | Search establishments |
| GET/POST | `/api/bank-accounts` | List/create bank accounts |
| GET/PUT/DELETE | `/api/bank-accounts/<id>` | Read/update/delete bank account |
| GET | `/api/epfo-8f` | List 8F records |
| GET | `/api/ifsc/<code>` | IFSC lookup (Razorpay) |
| GET | `/api/export-pdf` | PDF export (tab=bank/8f, sort=...) |

## Development

### Current Focus
Rewriting `bank.html` to match `bank-preview.html` design (3-card layout + compact EPFO table).

### Testing
```bash
# Manual testing via browser at http://127.0.0.1:5000
# API testing:
curl http://127.0.0.1:5000/api/establishments?limit=5
curl http://127.0.0.1:5000/api/bank-accounts
curl "http://127.0.0.1:5000/api/ifsc/SBIN0001234"
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Port 5000 in use | Kill existing process or change port in `app.py` |
| IFSC lookup fails | Check internet connection; Razorpay API may be rate-limited |
| Database locked | Ensure no other process holds the SQLite file |
| Missing columns | Run `python import_establishments.py` to run migrations |

## Development Notes

- All templates are single-file (HTML + CSS + JS combined)
- Backend uses vanilla `sqlite3` (no ORM)
- Frontend uses vanilla JS (no frameworks)
- ReportLab generates PDFs server-side
- Establishment data is Odisha-specific (48k records)