from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
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

    # SEPI = 100 x jumlah berbobot variabel yang TERSEDIA, bobotnya
    # dinormalisasi ulang atas variabel itu saja (lihat scoring/sepi.py).
    # Sifatnya POINTWISE: nilai satu stasiun tidak bergantung pada stasiun mana
    # pun yang lain, jadi menambah stasiun ke lingkup tidak mengubahnya. Karena
    # itu hanya angka INI yang boleh diklasifikasikan ke tiga rentang PRD.
    sepi: Mapped[float] = mapped_column(Float)
    kelas: Mapped[str] = mapped_column(String)
    keputusan: Mapped[str] = mapped_column(String)

    # Peringkat menurut `sepi`, bukan menurut TOPSIS - supaya urutan yang
    # ditampilkan konsisten dengan angka yang ditampilkan.
    rank: Mapped[int] = mapped_column(Integer)

    # Kedekatan TOPSIS 0-100. Disimpan TERPISAH dan sengaja tidak dipakai
    # untuk klasifikasi: nilainya ditentukan oleh himpunan alternatif yang
    # kebetulan ikut dinilai, sehingga menambah satu stasiun bisa menukar
    # urutan dua stasiun lain yang datanya tidak berubah (rank reversal, lihat
    # scoring/topsis.py). Berguna sebagai pembanding relatif, bukan sebagai
    # skor yang berdiri sendiri.
    topsis: Mapped[float] = mapped_column(Float)

    # Berapa dari lima variabel yang benar-benar terukur, dan keyakinan yang
    # mengikutinya. Skor dari tiga variabel TIDAK sebanding dengan skor lima
    # variabel, dan itu harus terbaca di panel, bukan disembunyikan.
    variabel_terpakai: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float)

    raw_t: Mapped[float] = mapped_column(Float)
    # NULL, bukan NaN. "Belum diukur" bukan sebuah angka, dan NaN bukan JSON
    # yang sah sehingga akan mematahkan API saat disajikan. Terisi begitu
    # survey Activity masuk (blocker N1).
    raw_e: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_a: Mapped[float] = mapped_column(Float)
    raw_u: Mapped[float] = mapped_column(Float)
    # NULL, bukan NaN. "Belum diukur" bukan sebuah angka, dan NaN bukan JSON
    # yang sah sehingga akan mematahkan API saat disajikan. Terisi begitu
    # survey Activity masuk (blocker N1).
    raw_c: Mapped[float | None] = mapped_column(Float, nullable=True)

    line_count: Mapped[int] = mapped_column(Integer)
    halte_count: Mapped[int] = mapped_column(Integer)
    other_mode_count: Mapped[int] = mapped_column(Integer)
    area_km2: Mapped[float] = mapped_column(Float)

    # Ringkasan analisis sensitivitas (scoring/sensitivity.py): peringkat
    # stasiun ini di tiap skema pembobotan, rentang peringkat, dan peluang
    # masuk N besar saat bobot diacak. Peringkat yang melompat antar-skema
    # ditandai rapuh - lihat ADJUSTMENT 9.30.
    sensitivity: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_station_scores_minutes_rank", "minutes", "rank"),
    )
