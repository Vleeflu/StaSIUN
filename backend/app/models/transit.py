"""Simpul transit jalan dari data Dinas Bina Marga: halte dan terminal bus.

Terpisah dari `Poi` dengan sengaja. Alasannya tercatat di migrasi
`c3f5e8a1d624`: tabel `poi` dibaca banyak kueri tanpa saringan sumber, sehingga
halte yang dimasukkan ke sana akan ikut menggelembungkan variabel U, TSI, dan
calon sponsor.
"""

from geoalchemy2 import Geometry
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TransitNode(Base):
    __tablename__ = "transit_nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    # halte_brt | halte_non_brt | terminal_bus
    jenis: Mapped[str] = mapped_column(String, index=True)
    nama: Mapped[str | None] = mapped_column(String)
    jenis_asli: Mapped[str | None] = mapped_column(String)
    sumber: Mapped[str] = mapped_column(String)
    location = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False
    )
