# DoubtDesk

DoubtDesk is a university peer learning, assessment, and concept-level learning analytics platform built for Indian higher education institutions.

## Architecture Overview

- **Frontend:** React 19, TypeScript, Vite, React Router, TanStack Query, Tailwind CSS 4.
- **Backend:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, psycopg 3 / asyncpg.
- **Database:** PostgreSQL 16+ with `pgvector` vector extension.
- **Runtime:** Docker Compose with isolated services (`db`, `api`, `worker`, `frontend`).
- **Asynchronous Processing:** PostgreSQL-backed durable background worker with lease-based job queues, crash recovery, and chunk provenance.

## Core Educational Loops & Modules

1. **Identity & RBAC:** Multi-tenant university partitioning with 4 roles (Super Admin, Institution Admin, Teacher, Student), Argon2id password hashing, SHA-256 session token cookies, and mandatory RFC 6238 TOTP MFA for Super Admin.
2. **Institutional Academics:** Hierarchical academic master data (Academic Units &rarr; Programmes &rarr; Branches &rarr; Curricula &rarr; Canonical Subjects &rarr; Subject Entries &rarr; Course Offerings) with separate faculty assignments and student enrolments.
3. **Source Documents & Job Pipeline:** Transactional ingestion for PDF, DOCX, and PPTX with PyMuPDF, python-docx, and python-pptx extraction, chunk provenance, and recoverable worker leases.
4. **Knowledge Model & Concepts:** Immutable syllabus versions, stable concept identifiers, prerequisite relations, and cycle-detected curriculum graphs.
5. **Question Bank & Multi-Concept Attribution:** Source questions preserved as independent identities, multi-concept mark attribution with sum constraint validation, and faculty review workflows.
6. **Learning Nodes & Deterministic Scoring:** 6 objective scoring engines (MCQ, Fill-in-Blank, Matching Pairs, Ordering, Classification, Key Points Check) and server-authoritative payload sanitization (answer keys stripped before student delivery).
7. **Assessments & CBT Engine:** Teacher authoring, assessment publishing, auto-save drafts, server-authoritative timer expiry, and deterministic CBT grading.
8. **Concept Analytics & Gap Detection:** Distinct question counting, first valid attempt diagnostic evidence selection, 4-state diagnostic classification (`insufficient_evidence`, `candidate_weakness`, `confirmed_weakness`, `not_currently_flagged_as_weak`), separate Cohort Mean and Pooled Accuracy, and misconception event tracking.
9. **Targeted Interventions:** 3-phase teacher-approved remediation loop (Phase A Diagnostic Baseline &rarr; Phase B Primer & Practice &rarr; Phase C Disjoint Post-Assessment Reassessment) with strictly disjoint question sets ($Q_{\text{Phase A}} \cap Q_{\text{Phase C}} = \emptyset$), configurable Phase B completion rules, and matched pre/post outcome reports with non-causal disclaimers.
10. **Academic Doubts & Discussions:** Campus discussion threads with peer-anonymous posting, author self-view preservation, teacher answer verification/endorsement, community moderation flagging, and audited identity unmasking with immutable `AuditEvent` and `DoubtIdentityDisclosureEvent` logging.
11. **In-App Notifications:** Targeted notification ledger with privacy safeguards (anonymous author identity never leaked in notification messages) and unread count badges.
12. **Role Workspaces & Audit Ledger:** Route resolution via `GET /api/v1/auth/me`, teacher-assigned offerings, student-enrolled offerings, and tenant-scoped security audit logs.

## Local Development & Setup

### Environment Variables
`v1/.env` is the single configuration source for Compose, the API, worker, and seed command. The backend ignores any `backend/.env` file so credentials cannot silently diverge. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Change the example `SECRET_KEY` and local database credentials before using this setup beyond a disposable development machine. The example file contains no production credentials. Production mode rejects the development secret and insecure session-cookie setting.

### Docker Compose
Start all local services:
```bash
docker compose up -d
```

Compose waits for PostgreSQL health, applies Alembic migrations, then starts the API and job worker. Database credentials are assembled with SQLAlchemy URL handling so reserved characters in passwords are escaped correctly.

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Health Check: http://localhost:8000/health
- API Readiness Check: http://localhost:8000/ready
- Database: localhost:5432 (`doubtdesk`/`doubtdesk`)

### Running Database Migrations
```bash
cd backend
alembic upgrade head
```

### Running Automated Test Suite
The comprehensive test suite covers all 13 phases (88 tests):
```bash
cd backend
pytest -v
```

For first-time local Super Admin provisioning, set `SUPERADMIN_EMAIL`, `SUPERADMIN_PASSWORD`, and `SUPERADMIN_TOTP_SECRET` in `v1/.env`, then run `python -m app.seed` from `backend` after the database is ready.

### Frontend Build
```bash
cd frontend
npm run build
```
