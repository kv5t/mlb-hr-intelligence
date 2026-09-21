# MLB HR Intelligence

MLB HR Intelligence is a read-only baseball analytics application focused on home-run production, frequency, recurrence, evidence coverage, and auditable source semantics. The application treats unavailable or incomplete evidence as explicit states rather than numeric zero.

## Current status

B01 through B13 of the 0.1 implementation backlog are technically complete. The current gate is **post-B13 visual and UX owner acceptance**. B14 has not started; after owner acceptance, the next planned item is **B14 — Player and Leaderboard API Family**.

The current user-facing slice includes:

- Today schedule and recent observed HR leaders
- Games discovery with server-side filters, ordering, and pagination
- Game Detail with coverage, positively evidenced participants, and canonical HR events
- URL-driven state, responsive navigation, accessible semantic states, and dataset freshness
- Deterministic synthetic development data for offline testing

## Architecture

```text
Browser / React SPA
        │ same-origin /api/v1/
        ▼
Django REST Framework
        │
Analytics services ── canonical domain models ── SQLite
        │
Coverage, provenance, and DatasetRevision metadata
```

KPI formulas live in the backend analytics layer. React validates API payloads with Zod and presents server results without recalculating canonical metrics.

### Backend stack

- Python 3.12
- Django 5.2
- Django REST Framework
- django-filter
- SQLite with WAL and foreign-key enforcement
- Django test runner and Ruff

### Frontend stack

- Node.js 24 and npm
- React 19, TypeScript, and Vite
- React Router
- Tailwind CSS and shadcn/ui foundation
- TanStack Query and TanStack Table
- Zod
- Apache ECharts, available for later analytical screens
- Vitest and React Testing Library

## Repository structure

```text
backend/              Django project, domain, analytics, API, and tests
frontend/             React SPA, typed API boundary, screens, and tests
docs/product/         Product and architecture specifications
.github/workflows/    Deterministic backend and frontend CI
```

## Prerequisites

- Python 3.12
- Node.js 24 and npm
- A Python virtual environment at `.venv/` in the repository root, or equivalent commands adjusted for your environment

Install backend dependencies from the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
```

Install frontend dependencies:

```bash
cd frontend
npm ci
```

## Quick start

In terminal 1:

```bash
cd backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py prepare_synthetic_demo
../.venv/bin/python manage.py runserver 0.0.0.0:8000
```

In terminal 2:

```bash
cd frontend
VITE_API_PROXY_TARGET=http://127.0.0.1:8000 npm run dev -- --host 0.0.0.0
```

Open [http://127.0.0.1:5173/today?season=2099&date=2099-04-03&window=7G](http://127.0.0.1:5173/today?season=2099&date=2099-04-03&window=7G).

## Synthetic demo

`prepare_synthetic_demo` is an explicit development command. It loads deterministic **fake 2099 data**, verifies its synthetic identity, establishes synthetic calendar bounds, and publishes a `DatasetRevision`. It performs no provider HTTP and creates no provider-access approval.

The data is **not real MLB data** and does not establish provider completeness. The command never runs automatically at application startup. Repeated use preserves canonical fixture identities and rows while recording a new explicit publication revision.

## Local development

The Vite development server sends relative `/api` requests to Django through its configured proxy. Application source does not hard-code localhost. Django's `runserver` and Vite's development server are development tools only.

The principal development URLs are:

- `http://127.0.0.1:5173/today?season=2099&date=2099-04-03&window=7G`
- `http://127.0.0.1:5173/games?season=2099`
- `http://127.0.0.1:8000/api/v1/`

## LAN and mobile visual testing

Bind Django and Vite to `0.0.0.0` as shown in Quick start. Determine the active interface on macOS with:

```bash
route -n get default | grep interface
ipconfig getifaddr <active-interface>
```

On a phone connected to the same network, open:

```text
http://<LAN-IP>:5173/today?season=2099&date=2099-04-03&window=7G
```

Vite continues to proxy `/api` to Django on the development machine. Host firewall policy must allow the two development ports.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `DJANGO_DEBUG` | Enables Django debug behavior. Use `0` in production. |
| `DJANGO_SECRET_KEY` | Django cryptographic secret. Required when debug is disabled; keep outside Git. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated Django host allowlist. Production must be explicit and must not use `*`. |
| `DJANGO_DB_PATH` | SQLite database path. Defaults to `backend/db.sqlite3`. Production storage must be persistent. |
| `VITE_API_PROXY_TARGET` | Non-secret development proxy target, normally `http://127.0.0.1:8000`. |

Do not commit real `.env` files or secrets. Variables prefixed with `VITE_` are exposed to frontend build tooling and must never contain secrets.

## Tests and quality checks

Backend:

```bash
cd backend
../.venv/bin/ruff check .
../.venv/bin/ruff format --check .
../.venv/bin/python manage.py check
../.venv/bin/python manage.py makemigrations --check --dry-run
../.venv/bin/python manage.py test
```

Frontend:

```bash
cd frontend
npm run typecheck
npm run lint
npm run test
npm run build
```

## Continuous integration

GitHub Actions runs deterministic Backend CI and Frontend CI on pushes and pull requests. CI requires no secrets, external services, or live provider HTTP. Backend CI checks formatting, lint, Django configuration, migrations, and tests. Frontend CI uses `npm ci`, then typecheck, lint, tests, and a production build.

## Data and MetricValue semantics

Analytical values use explicit semantic states:

| State | Meaning |
| --- | --- |
| `VALUE` | A supported numeric value, including a legitimate zero. |
| `NOT_APPLICABLE` | The metric does not apply to this scope. |
| `UNKNOWN` | Evidence is insufficient or unavailable. |
| `INCOMPLETE` | Evidence is known to be partial or conflicting. |
| `ORDER_UNVERIFIED` | Ordering needed by the metric is not proven. |
| `INSUFFICIENT_HISTORY` | The scope lacks enough history for the metric. |

`UNKNOWN` is not zero, and `INCOMPLETE` is not zero. The frontend does not infer missing values or calculate canonical KPIs.

## DatasetRevision

Every public API response carries a current `dataset_revision` and `data_as_of`. The revision is a monotonic publication-consistency token. It lets composed views detect mixed publications; it is not a historical database snapshot and cannot be supplied as a public historical-read parameter.

## Deployment guidance

### Current development and staging runbook

1. Configure environment variables outside Git.
2. Place the SQLite database on persistent storage.
3. Run `python manage.py migrate` before serving a new release.
4. Build the SPA with `cd frontend && npm ci && npm run build`.
5. Serve the generated static files from `frontend/dist/`.
6. Route `/api/` to Django and route other unknown SPA paths to `index.html`.
7. Keep `/api/v1/` same-origin where possible.

The intended production topology is:

```text
Browser
  ↓ HTTPS
same-origin web host / reverse proxy
  ├── frontend SPA and static assets
  └── /api/ → Django application server
```

Production must use `DJANGO_DEBUG=0`, a strong `DJANGO_SECRET_KEY`, an explicit `DJANGO_ALLOWED_HOSTS`, HTTPS, persistent database storage, and a tested database backup and restore process. Secrets and environment configuration must remain outside Git.

### Production requirements still to implement

The repository does not yet contain a production application server setup such as Gunicorn or Uvicorn, a Dockerfile, Docker Compose, reverse-proxy configuration, Coolify configuration, production static-file serving, a healthcheck endpoint, or backup automation. These are **not yet implemented**.

`python manage.py runserver` and `npm run dev` are not production deployment methods. A production release must add and validate the missing operational infrastructure before public use.

## Security and operational limitations

- No live provider automation is enabled; provider access remains deny-by-default.
- No credentials or provider payloads belong in source control or public API responses.
- SQLite suits the current single-node implementation but requires persistent storage, backups, and operational review before production.
- Authentication, production hardening, rate limiting, monitoring, health checks, and deployment automation are not yet implemented.
- The current frontend awaits owner visual and UX acceptance across desktop and mobile.

## Roadmap

Technical implementation through B13 is complete. The project is paused at the mandatory post-B13 visual acceptance checkpoint. After explicit owner acceptance, the next planned work item is **B14 — Player and Leaderboard API Family**.
