#!/bin/sh
# Prepare the database, then hand off to uvicorn.
set -e

# 1. Wait until Postgres accepts connections. The db service has a healthcheck,
#    but retrying here keeps the backend robust to slow first-time initdb runs.
python - <<'PY'
import sys
import time

from sqlalchemy import create_engine, text

from app.core.config import settings

if not settings.DATABASE_URL:
    print("DATABASE_URL is not set", file=sys.stderr)
    sys.exit(1)

engine = create_engine(settings.DATABASE_URL)
for attempt in range(1, 31):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Database is ready.")
        break
    except Exception as exc:  # noqa: BLE001 — any connection error means "not ready yet"
        print(f"Waiting for database ({attempt}/30): {exc}")
        time.sleep(2)
else:
    print("Database never became reachable.", file=sys.stderr)
    sys.exit(1)
PY

# 1b. Ensure the PostGIS extension exists before migrations create geometry
#     columns. The postgis/postgis image auto-enables it, but managed Postgres
#     (Supabase, Neon, Railway, …) starts as plain Postgres and needs this.
#     Non-fatal: on hosts where the role can't create extensions (e.g. Supabase
#     when it isn't enabled from the dashboard) this logs a hint instead of
#     crashing the container, and the migration step below surfaces the real
#     error if PostGIS is genuinely missing.
python - <<'PY'
from sqlalchemy import create_engine, text

from app.core.config import settings

try:
    engine = create_engine(settings.DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    print("PostGIS extension ensured.")
except Exception as exc:  # noqa: BLE001
    print(f"Could not create PostGIS extension automatically: {exc}")
    print("If migrations fail next, enable the 'postgis' extension in your "
          "database dashboard (Supabase: Database -> Extensions -> postgis).")
PY

# 2. Bawa skema ke bentuk terbaru. Menggantikan Base.metadata.create_all, yang
#    hanya bisa MEMBUAT tabel baru dan diam saja kalau ada kolom baru di tabel
#    yang sudah ada. Alembic menerapkan perubahannya juga, dan riwayatnya
#    tercatat di tabel alembic_version.
alembic upgrade head

# 3. Seed stations. Defaults to the bundled GeoJSON so the stack works without
#    MAPID credentials. Set SEED_ON_START=0 to skip, or SEED_SOURCE=mapid to
#    pull live data from Geoserver MAPID (requires MAPID_API_KEY/MAPID_PROJECT_ID).
if [ "${SEED_ON_START:-1}" = "1" ]; then
    if [ "${SEED_SOURCE:-local}" = "mapid" ]; then
        echo "Seeding stations from MAPID Geoserver..."
        python -m scripts.ingest_layers || echo "MAPID ingest failed; leaving existing data untouched."
    else
        echo "Seeding stations from bundled GeoJSON..."
        python -m scripts.seed_stations || echo "Local seed failed; leaving existing data untouched."
    fi
fi

# 4. Run the API. Binds $PORT when the platform sets one (Render, Railway, …),
#    else 8000 for local Docker Compose. Extra args are forwarded to uvicorn.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" "$@"
