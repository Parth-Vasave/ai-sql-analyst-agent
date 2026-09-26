# One-off image for the data pipeline (clean + seed). Run via: docker compose run --rm seed
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /work

COPY scripts/requirements.txt scripts/requirements.txt
RUN pip install --no-cache-dir -r scripts/requirements.txt

COPY scripts ./scripts
ENTRYPOINT ["python", "-m"]
CMD ["scripts.seed_database"]
