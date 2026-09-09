"""Model dikumpulkan di sini supaya Base.metadata tahu semua tabel.

Tanpa impor ini, create_all cuma membuat tabel yang kebetulan sudah tersentuh
modul lain — dan tabel yang belum dipakai siapa pun diam-diam tidak terbentuk.
"""

from app.models.isochrone import Isochrone
from app.models.poi import Poi
from app.models.score import StationScore
from app.models.station import Station
from app.models.tenant_score import TenantScore

__all__ = ["Isochrone", "Poi", "StationScore", "Station", "TenantScore"]
