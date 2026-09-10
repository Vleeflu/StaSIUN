"""Satu pintu impor untuk seluruh model.

SQLAlchemy hanya tahu sebuah tabel ada kalau berkas modelnya pernah diimpor.
Kalau tidak, tabelnya tidak akan dibuat dan tidak akan muncul di autogenerate
Alembic — gagalnya diam-diam, tanpa pesan error.

Karena itu setiap model baru cukup didaftarkan di sini sekali, dan pemakainya
(alembic/env.py dan docker-entrypoint.sh) tinggal `import app.models` tanpa
perlu tahu ada berapa berkas.

Model `Poi` tinggal di `reference.py`, bukan di `poi.py` tersendiri. Branch main
sempat punya keduanya; dua kelas yang memetakan ke tabel `poi` yang sama membuat
SQLAlchemy gagal saat pemetaan, jadi yang duplikat dibuang.
"""

from app.models.activity import (
    ActivityExtraction,
    ActivityPoint,
    ActivityRaw,
    CrowdRating,
)
from app.models.isochrone import Isochrone
from app.models.reference import AreaProfile, PassengerVolume, Poi, PriceReference
from app.models.score import StationScore
from app.models.station import Station
from app.models.station_objects import (
    AdSpot,
    FacilityIssue,
    StationZone,
    Tenant,
    TenantCluster,
)
from app.models.tenant_score import TenantScore

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
    "StationScore",
    "StationZone",
    "Tenant",
    "TenantCluster",
    "TenantScore",
]
