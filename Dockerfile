FROM python:3.14-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[dev]"

COPY app ./app
COPY alembic.ini .
COPY alembic ./alembic
COPY scripts ./scripts

EXPOSE 8000
CMD ["sh", "./scripts/start.sh"]
