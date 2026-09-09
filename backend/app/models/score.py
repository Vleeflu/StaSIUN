from sqlalchemy import Float, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StationScore(Base):
    """Skor SEPI satu stasiun pada satu pita waktu isochrone.

    Angka mentah tiap variabel ikut disimpan, bukan cuma skor akhirnya. Tanpa
    itu skornya tidak bisa dijelaskan ke siapa pun — dan seluruh gunanya SEPI
    justru ada di penjelasan kenapa satu stasiun menang.
    """

    __tablename__ = "station_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), index=True
    )
    minutes: Mapped[int] = mapped_column(Integer)

    sepi: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)

    raw_t: Mapped[float] = mapped_column(Float)
    raw_e: Mapped[float] = mapped_column(Float)
    raw_a: Mapped[float] = mapped_column(Float)
    raw_u: Mapped[float] = mapped_column(Float)
    raw_c: Mapped[float] = mapped_column(Float)

    line_count: Mapped[int] = mapped_column(Integer)
    halte_count: Mapped[int] = mapped_column(Integer)
    other_mode_count: Mapped[int] = mapped_column(Integer)
    area_km2: Mapped[float] = mapped_column(Float)

    __table_args__ = (
        Index("ix_station_scores_minutes_rank", "minutes", "rank"),
    )
