FROM python:3.13-slim

WORKDIR /app
COPY backend/pyproject.toml backend/poetry.lock ./
RUN pip install poetry \
    && poetry config virtualenvs.create false \
    && poetry install --only main

COPY backend/app/ ./app/
COPY backend/alembic/ ./alembic/
COPY backend/alembic.ini ./
RUN mkdir -p ./scripts
COPY backend/scripts/seed_configuration.py ./scripts/seed_configuration.py

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
