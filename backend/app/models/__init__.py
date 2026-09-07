"""Satu pintu impor untuk seluruh model.

SQLAlchemy hanya tahu sebuah tabel ada kalau berkas modelnya pernah diimpor.
Kalau tidak, tabelnya tidak akan dibuat dan tidak akan muncul di autogenerate
Alembic — gagalnya diam-diam, tanpa pesan error.

Karena itu setiap model baru cukup didaftarkan di sini sekali, dan pemakainya
(alembic/env.py dan docker-entrypoint.sh) tinggal `import app.models` tanpa
perlu tahu ada berapa berkas.
"""

from app.models.activity import (
    ActivityExtraction,
    ActivityPoint,
    ActivityRaw,
    CrowdRating,
)
from app.models.isochrone import Isochrone
from app.models.reference import AreaProfile, PassengerVolume, Poi, PriceReference
from app.models.station import Station
from app.models.station_objects import (
    AdSpot,
    FacilityIssue,
    StationZone,
    Tenant,
    TenantCluster,
)

__all__ = [
    "ActivityExtraction",
    "ActivityPoint",
    "ActivityRaw",
    "AdSpot",
    "AreaProfile",
    "CrowdRating",
    "FacilityIssue",
    "Isochrone",
    "PassengerVolume",
    "Poi",
    "PriceReference",
    "Station",
    "StationZone",
    "Tenant",
    "TenantCluster",
]
