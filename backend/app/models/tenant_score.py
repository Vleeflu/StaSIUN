from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String
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
    # Pesaing sejenis, TOTAL: yang terpetakan di luar stasiun ditambah yang
    # beroperasi di dalamnya (PRD hal. 13).
    supply: Mapped[float] = mapped_column(Float)
    # Sisi luar: titik minat terpetakan di dalam isochrone pesaing.
    supply_luar: Mapped[int] = mapped_column(Integer)
    # Sisi dalam: tenant yang beroperasi di dalam stasiun. Pecahan, karena untuk
    # stasiun yang belum disurvei nilainya ditaksir dari stasiun sejenis.
    supply_dalam: Mapped[float] = mapped_column(Float)
    # False berarti sisi dalam adalah taksiran, bukan hitungan lapangan.
    dalam_terukur: Mapped[bool] = mapped_column(Boolean)
    # 0-1. Turun ketika sisi dalam belum pernah diperiksa surveyor.
    confidence: Mapped[float] = mapped_column(Float)
    # Skor seandainya taksiran pesaing dalam stasiun meleset satu simpangan ke
    # arah yang merugikan. INI yang dipakai mengurutkan peringkat.
    tsi_bawah: Mapped[float] = mapped_column(Float)
    # Calon pelanggan per pesaing, sesudah pesaing ditambah satu (dirinya).
    headroom: Mapped[float] = mapped_column(Float)

    __table_args__ = (
        Index("ix_tenant_scores_lookup", "station_id", "minutes", "tsi"),
        Index("ix_tenant_scores_rank", "category", "minutes", "rank"),
    )
