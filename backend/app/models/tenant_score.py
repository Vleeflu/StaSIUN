from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TenantScore(Base):
    """Tenant Survival Index satu kategori usaha di satu stasiun.

    Seperti tabel skor SEPI, angka mentahnya ikut disimpan. Calon penyewa lapak
    tidak akan percaya angka 0-100 tanpa tahu asalnya, dan justru pembilang
    penyebutnya yang menjelaskan keputusannya: berapa calon pelanggan, berapa
    pesaing sejenis.
    """

    __tablename__ = "tenant_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), index=True
    )
    minutes: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String, index=True)

    # Skor akhir 0-100, dan peringkat stasiun ini di antara stasiun lain untuk
    # kategori yang sama. Peringkat sengaja per kategori: pertanyaan penyewa
    # adalah "di stasiun mana warung kopi saya paling aman", bukan "stasiun mana
    # yang terbaik untuk segalanya".
    tsi: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)

    # Basis pelanggan: jumlah titik ekonomi dan urban di dalam isochrone.
    demand: Mapped[int] = mapped_column(Integer)
    # Pengali arus lewat, 1,0 sampai 2,0, dari komponen T milik SEPI.
    connectivity: Mapped[float] = mapped_column(Float)
    # Pesaing sejenis yang sudah ada di dalam isochrone.
    supply: Mapped[int] = mapped_column(Integer)
    # Calon pelanggan per pesaing, sesudah pesaing ditambah satu (dirinya).
    headroom: Mapped[float] = mapped_column(Float)

    __table_args__ = (
        Index("ix_tenant_scores_lookup", "station_id", "minutes", "tsi"),
        Index("ix_tenant_scores_rank", "category", "minutes", "rank"),
    )
