FROM python:3.11-slim AS base

RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

RUN mkdir -p /data/tmp /data/failed_crm && chown -R app:app /data

USER app

# API entrypoint
FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Worker entrypoint
FROM base AS worker
CMD ["arq", "app.worker.WorkerSettings"]
