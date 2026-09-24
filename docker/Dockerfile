# Runtime image for both the API and the Celery worker (compose selects the command).
FROM python:3.13-slim

WORKDIR /app

# Keep Python output unbuffered so logs stream immediately in `docker compose logs`.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt ./
# --retries/--timeout make this resilient to the flaky-network IncompleteRead errors
# pip occasionally hits mid-download; harmless to keep even on a stable connection.
RUN pip install --no-cache-dir --retries 10 --timeout 100 -r requirements.txt

COPY app ./app
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations

RUN useradd --create-home appuser \
    && mkdir -p /app/uploads \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
