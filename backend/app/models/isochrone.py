from geoalchemy2 import Geometry
from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Isochrone(Base):
    __tablename__ = "isochrones"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Boleh kosong: poligon buat stasiun di luar cakupan KRL tetap disimpan
    # supaya tidak perlu tarik ulang saat MRT dan LRT ikut dinilai nanti.
    station_id: Mapped[int | None] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), index=True
    )
    # Disalin apa adanya dari layer, jadi poligon yatim masih bisa ditelusuri.
    station_osm_id: Mapped[str | None] = mapped_column(String, index=True)
    station_name: Mapped[str | None]
    # Menit jalan kaki: 5, 10, atau 15.
    minutes: Mapped[int]
    profile: Mapped[str]
    area: Mapped[str] = mapped_column(Geometry("MULTIPOLYGON", srid=4326))

    __table_args__ = (Index("ix_isochrones_station_minutes", "station_id", "minutes"),)
