# NEXUS Project Status & Phase Log

## Current Status: Phase 3 — Identity + User Context (COMPLETED)

Last Updated: 2026-09-18

---

## 1. Completed Work in Phase 3
- [x] **Authoritative Authentication Engine**:
  - Secure password hashing using real `bcrypt` with unique salt generation.
  - Signed JWT access tokens with HS256 signing, expiration TTL, issuer validation, and secret key integration from `NexusSettings`.
  - Registration endpoint (`POST /api/v1/auth/register`) with conflict checks and minimum password length enforcement.
  - Login endpoint (`POST /api/v1/auth/login`) with credential validation and deactivated account prevention.
  - Logout endpoint (`POST /api/v1/auth/logout`) with audit event emission.
- [x] **User Context & Preferences**:
  - Database schema for `users` and `user_preferences` with 1-to-1 cascade relationship.
  - Custom user timezone configuration.
  - Multi-model preference schema (default provider, fast model, reasoning model, temperature).
  - Permission preferences schema (auto-grant low risk, require HITL for high risk, session grant TTL).
  - Privacy settings schema (store audit payloads, telemetry controls, external RAG controls).
  - Preferences patch endpoint (`PATCH /api/v1/auth/preferences`) and current user profile inspection (`GET /api/v1/auth/me`).
- [x] **Database Models & Alembic Migrations**:
  - `UserModel` and `UserPreferenceModel` implemented using modern SQLAlchemy 2.0 `Mapped` and `mapped_column` declarative models.
  - Tenant foreign key `user_id` added to `sessions`, `task_dags`, `audit_logs`, and `memories`.
  - Migration `002_identity_and_user_context.py` created and verified applying both forward and rollback across SQLite and PostgreSQL.
- [x] **Security Audit Trail Integration**:
  - Immutable audit trail logs recorded for all security-sensitive operations: `user_registered`, `user_login`, `user_logout`, and `user_preferences_updated`.
- [x] **Strict Tenant Data Isolation**:
  - Verified user A's token cannot access or authenticate as user B.
  - Verified database queries filtered by `user_id` strictly isolate data across tenants.
- [x] **Dashboard Frontend Authentication**:
  - `AuthContext.tsx` providing reactive `user`, `token`, `isAuthenticated`, `login`, `register`, `logout`, and `updatePreferences`.
  - Premium cyber glassmorphic `/login` and `/register` pages with validation, loading states, and error alerts.
  - `TopCommandBar.tsx` updated with dynamic user identity chip, profile shortcut, and quick sign-out button.
  - Next.js production build (`next build`) compiled 17/17 static routes successfully.
- [x] **Automated Testing & Quality Gates**:
  - 22/22 pytest tests passing (including bcrypt 72-byte limit, invalid email regex, full_name sanitization, timezone length validation, migration portability, WebSocket disconnect, auth, token verification, and tenant isolation).
  - 100% clean typechecks across all packages with Mypy and TypeScript (`tsc --noEmit`).
  - 100% clean Python linting and formatting with Ruff.
  - Production bundles verified: Next.js (`17/17` static pages) and Ambient shell (Vite).

---

## 2. Hardening & Bug Hunt Audit
- **Bcrypt 72-byte Limit Guard**: `hash_password` and `/register` now reject passwords > 72 bytes with HTTP 400 Bad Request instead of throwing unhandled 500 `ValueError` from bcrypt 4.0+.
- **Email Regex & Whitespace**: Reject invalid, empty, or whitespace-only emails with HTTP 400; normalize valid emails with lowercase and strip.
- **Full Name Sanitization**: Whitespace-only names stored as `None`; bounded to 255 chars to match database column.
- **Timezone Validation**: Validated length <= 64 chars to prevent DB truncation errors in PostgreSQL.
- **In-Memory Model Defaults**: `UserPreferenceModel.__init__` guarantees defaults are never `None` in Python memory before DB flush.
- **WebSocket Disconnect Guard**: `finally: manager.disconnect(websocket, surface)` prevents leaked sockets on unexpected transport exceptions.
- **Worker Busy-Loop Fix**: `if self._shutdown_event.is_set(): break` avoids 100% CPU busy loop on worker shutdown.
- **Migration Portability**: `tests/test_migrations.py` updated from hardcoded `.venv/bin/alembic` to `[sys.executable, "-m", "alembic", ...]`.
- **Settings Reactivity**: Dashboard Settings page connected to `useAuth().updatePreferences()` to persist AI Gateway provider and policy auto-approve options directly to `/api/v1/auth/preferences`.
- **Dashboard Network Error Resilience**: Helpful error alerts displayed when backend is unreachable instead of raw browser `Failed to fetch`.

---

## 2. Completed Work in Prior Phases
- [x] **Phase 0 — Project Constitution**: Core architectural documents (`AGENTS.md`, `ARCHITECTURE.md`, `PRODUCT_SPEC.md`, `SECURITY_MODEL.md`, `ROADMAP.md`, `DATABASE_ENTITIES.md`, `API_BOUNDARIES.md`).
- [x] **Phase 1 — Monorepo Foundation**: Monorepo scaffolding, shared packages, FastAPI backend, background worker, Alembic migration 001, Docker Compose.
- [x] **Phase 2 — NEXUS Design System + Dashboard**: Reusable UI component suite, full 12-page operating console shell, static compilation of all routes.

---

## 3. Known Limitations & Prerequisites for Phase 4
- With user identity and tenant boundaries fully established, Phase 4 will implement the Core Policy Engine, Tool Registry, Sandboxed Runners, and Automated File Snapshot/Rollback Kernel.
- Stop after Phase 3 as required by the phase completion gate. Await user review and approval before proceeding.

