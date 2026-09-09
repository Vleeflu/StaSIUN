from geoalchemy2 import Geometry
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Id OpenStreetMap, dibawa turun dari sumbernya. Jadi kunci sambungan ke
    # poligon isochrone: nama tidak bisa dipakai karena Halim dan Cawang
    # masing-masing dipakai dua stasiun dari moda yang berbeda.
    osm_id: Mapped[str | None] = mapped_column(String, unique=True, index=True)
    name: Mapped[str]
    # Kode resmi KAI, misal MRI buat Manggarai. Ada di sebagian besar stasiun.
    code: Mapped[str | None]
    types: Mapped[list[str]] = mapped_column(ARRAY(String))
    lines: Mapped[list[str]] = mapped_column(ARRAY(String))
    # False buat stasiun yang cuma dilewati KRL tanpa berhenti, contohnya Gambir.
    served: Mapped[bool] = mapped_column(default=True)
    address: Mapped[str | None]
    kecamatan: Mapped[str | None]
    kabkot: Mapped[str | None]
    location: Mapped[str] = mapped_column(Geometry("POINT", srid=4326))
