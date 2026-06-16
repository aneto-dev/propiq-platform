FROM python:3.13-slim

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry \
    && poetry config virtualenvs.create false \
    && poetry install --only main

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
RUN mkdir -p ./scripts
COPY scripts/seed_configuration.py ./scripts/seed_configuration.py

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
