# StaSIUN backend — FastAPI + SQLAlchemy/GeoAlchemy2 on PostGIS.
FROM python:3.12-slim

# Faster, cleaner Python in containers.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /code

# Install dependencies first so the layer is cached across code changes.
# psycopg-binary ships its own libpq, so no system build deps are needed.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code, ingest/seed scripts and bundled GeoJSON data.
COPY app ./app
COPY scripts ./scripts
COPY data ./data
COPY docker-entrypoint.sh ./docker-entrypoint.sh
# Migrasi database. Dipakai entrypoint lewat `alembic upgrade head`, jadi
# berkas ini wajib ada di dalam image — tanpanya container gagal start.
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

# Entrypoint waits for the DB, creates tables, seeds, then launches uvicorn.
ENTRYPOINT ["./docker-entrypoint.sh"]
