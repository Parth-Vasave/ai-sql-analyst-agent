FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN useradd --create-home appuser
USER appuser

# Listens on $PORT when the host sets one (Render, Cloud Run), otherwise on 8000.
EXPOSE 8000
# Unhealthy while any configured database is unreachable (/api/health answers 503 then).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT', '8000')}/api/health\", timeout=4)"]
# No uvicorn access log: it records client IP addresses. The app logs each request itself,
# as JSON with a request ID and without the address (app/observability.py).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --no-access-log"]
