# AI LinkedIn Content Automation Agent

## Phase 2–4 development setup

This project provides a FastAPI backend with PostgreSQL-backed post persistence, recurring content configuration, a safe scheduler trigger, and a research-only discovery pipeline.

### Prerequisites

- Python 3.10+
- Docker Compose for local PostgreSQL

### Environment setup

Create a local `.env` file from the safe example and adjust values as needed:

```bash
cp .env.example .env
```

Required environment variable:

```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/ai_linkedin_agent
RESEARCH_PROVIDER=arxiv
RESEARCH_TIMEOUT_SECONDS=10
RESEARCH_WINDOW_DAYS=30
```

Do not commit `.env` or real credentials.

### Start PostgreSQL

```bash
docker compose up -d postgres
```

### Install dependencies

```bash
python -m pip install -r requirements.txt
```

### Run migrations

```bash
alembic upgrade head
```

To verify downgrade/upgrade locally:

```bash
alembic downgrade -1
alembic upgrade head
```

### Start FastAPI

```bash
python -m uvicorn app.main:app --reload
```

Swagger UI is available at:

```text
http://127.0.0.1:8000/docs
```

## Schedule configuration (Phase 3)

Use `POST /schedules` to store a recurring content configuration. A schedule requires a non-empty name, one or more distinct lowercase weekday names (`monday` through `sunday`), an exact 24-hour `HH:MM` time, a valid IANA timezone, and one or more distinct non-empty topics. `active` defaults to `true`.

Active schedules are loaded on application startup and registered with APScheduler using their configured weekday, time, and timezone. Creating, updating, deactivating, or deleting a schedule updates its in-process job. The job currently only records/logs an internal workflow execution event; it does not research, generate, or publish content.

`ScheduleScheduler.run_schedule_now(schedule_id)` is the internal development/test mechanism for proving the registration → trigger → workflow-event path. It is deliberately not exposed as a public API endpoint.

## Research pipeline (Phase 4)

`POST /research` accepts topics and returns normalized, persisted research items. The initial provider is arXiv's public Atom API, isolated behind the `ResearchSource` interface so it can be replaced later. The provider uses `RESEARCH_TIMEOUT_SECONDS`; `RESEARCH_WINDOW_DAYS` controls the default freshness filter (30 days by default). No credentials are required for arXiv, and no API keys are stored in this repository.

The research service filters malformed entries, duplicate URLs/titles, and stale/unpublished items when a freshness window is active, then applies a simple deterministic keyword score. It is research only: it does not call an LLM, generate posts or hashtags, publish to LinkedIn, or create approval workflows. Tests use fake providers rather than live network calls.

### Run tests

The automated test suite uses an isolated SQLite database override so tests do not modify the development PostgreSQL database.

```bash
python -m pytest -q
```
