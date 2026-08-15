# Demat Account Lifecycle & Client Master Management System

A backend system for managing demat account creation, modification, and closure
workflows, modeled on real depository (CDSL CDAS) account-management processes.
Built with Python, FastAPI, and Oracle to demonstrate transaction-safe backend
design without relying on stored procedures.

## Features

- **Account creation** — client + demat account creation with PAN uniqueness
  enforcement and an immutable audit trail
- **Account modification** — submit → approve/reject workflow with per-field
  change history (only actually-changed fields are logged)
- **Account closure** — submit → approve workflow with account state validation
- **Bulk upload** — CSV-based bulk account creation using array-bind execution
  (`executemany`), chunked batch processing, and row-level error tracking
- **Reporting** — account history and a filterable client master report

## Architecture
Client (HTTP/JSON)
│
FastAPI Routers (request/response handling)
│
Pydantic Models (structural validation — format, required fields)
│
Service Layer (orchestration)
│
Repository Layer (python-oracledb — transactions, DB-dependent
│ validation, SELECT FOR UPDATE row locking)
│
Oracle 23c


### Key design decisions

- **No PL/SQL packages.** All business logic — including the account
  create/modify/close state machine — lives in Python. Transaction safety is
  handled explicitly via `SELECT ... FOR UPDATE` row locking and manual
  `commit()`/`rollback()`, rather than delegating to stored procedures. This
  keeps the codebase Python-native and demonstrates direct database
  transaction management rather than relying on PL/SQL.
- **Bulk upload uses array-bind execution** (`cursor.executemany()`), the
  Python-driver equivalent of Pro*C host-array batch inserts — chosen over
  row-by-row inserts for the same reason the legacy system uses host arrays:
  a single batched round trip instead of one per row.
- **Non-DB validation (format, required fields) lives in Pydantic models**;
  DB-dependent validation (uniqueness, current state) lives in the repository
  layer, executed in the same transaction as the write it depends on — this
  avoids race conditions between a separate "check" step and the write.
- **Immutable audit trail.** `account_history` is append-only; every account
  or client field change is logged with old/new values, mirroring the
  regulatory reasoning behind non-financial history in real depository
  systems.

## Tech stack

- **Language/Framework:** Python, FastAPI, Pydantic v2
- **Database:** Oracle 23c Free, accessed via `python-oracledb` (thin mode)
- **Containerization:** Docker

## Project structure

app/
├── main.py # FastAPI app entrypoint
├── config.py # environment-based settings
├── database.py # connection pooling
├── models/schemas.py # Pydantic request/response models
├── services/ # orchestration layer
├── repositories/ # DB access, transactions
└── routers/ # HTTP endpoints
sql/schema.sql # full DDL (tables + indexes)


## Setup

### 1. Database

Run `sql/schema.sql` against an Oracle 23c instance, connected as a dedicated
app user (see schema comments for the recommended user/role setup).

### 2. Environment

```bash
cp .env.example .env
# fill in DB_USER, DB_PASSWORD, DB_DSN
```

### 3. Run locally

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/docs` for interactive API docs.

### 4. Run with Docker

```bash
docker compose up --build
```

## API overview

| Endpoint | Description |
|---|---|
| `POST /accounts` | Create a client + demat account |
| `POST /accounts/{id}/modify` | Submit a modification request |
| `POST /accounts/requests/{id}/approve` | Approve a modification |
| `POST /accounts/requests/{id}/reject` | Reject a modification |
| `POST /accounts/{id}/close` | Submit a closure request |
| `POST /accounts/requests/{id}/approve-close` | Approve a closure |
| `POST /accounts/requests/{id}/reject-close` | Reject a closure |
| `POST /bulk-upload` | Bulk-create accounts from a CSV file |
| `GET /accounts/{id}/history` | Full audit trail for an account |
| `GET /accounts/reports/client-master` | Client master report (optional `?status=` filter) |

## Background

This project was built to apply backend design patterns from real depository
account-management work (CDSL CDAS, Pro*C/PL/SQL) using a modern Python stack,
while deliberately keeping application logic in Python rather than the
database layer.