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

# 2. Create tables (idempotent — SQLAlchemy skips ones that already exist).
python -c "import app.models.station; from app.core.database import engine, Base; Base.metadata.create_all(bind=engine)"

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

# 4. Run the API. Extra args passed to the container are forwarded to uvicorn.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"
