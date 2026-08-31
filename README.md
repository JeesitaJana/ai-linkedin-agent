# AI LinkedIn Content Automation Agent

## Phase 2 development setup

This project currently provides a FastAPI backend with PostgreSQL-backed post persistence through SQLAlchemy and Alembic.

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

### Run tests

The automated test suite uses an isolated SQLite database override so tests do not modify the development PostgreSQL database.

```bash
python -m pytest -q
```
