# DoubtDesk Backend

FastAPI backend and PostgreSQL-backed worker for DoubtDesk v1. Runtime configuration is loaded from the canonical `v1/.env` file or process environment variables.

From `v1/backend`, install `requirements-dev.txt`, run database migrations with `alembic upgrade head`, run the API with `uvicorn app.main:app`, run the worker with `python -m app.worker`, and run backend checks with `pytest`.
