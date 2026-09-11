"""Rantai data Activity Community Maps, dari mentah sampai hasil ekstraksi.

Empat tabel yang berurutan:

    activity_raw  ->  activity_points  ->  activity_extractions   (lapis 1)
                                       ->  crowd_ratings          (lapis 2)

Pemisahan mentah dan bersih itu disengaja. Aturan pengambilan data di
ADJUSTMENT.md bagian 7.3 melarang kurasi manual: entri tidak dipilih satu per
satu, melainkan disaring oleh aturan yang dieksekusi kode. Supaya penyaringan
itu bisa diaudit dan dihitung, entri yang gugur harus tetap tersimpan beserta
alasan gugurnya — itulah gunanya activity_raw.
"""

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.geo import SRID_RENDER
from app.models.mixins import TimestampMixin


class ActivityRaw(TimestampMixin, Base):
    """Entri Activity apa adanya, sebelum disaring dan ditata.

    Payload disimpan sebagai JSONB — tipe kolom PostgreSQL untuk menampung JSON
    tanpa struktur tetap. Ini bukan kemalasan: bentuk persis ekspor Activity
    belum diketahui, dan memaksakan struktur sekarang berarti merombak seluruh
    tabel begitu bentuk aslinya ternyata berbeda. Semua ketidakpastian bentuk
    ditampung di sini, sehingga tabel-tabel di belakangnya bisa rapi.
    """

    __tablename__ = "activity_raw"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Dari adapter mana entri ini masuk: "file", "layer", atau "bbox".
    source_kind: Mapped[str]
    # Nama berkas atau layer_id-nya, supaya bisa ditelusuri balik.
    source_ref: Mapped[str]
    # Id entri di sisi MAPID kalau ada.
    external_id: Mapped[str | None]

    payload: Mapped[dict] = mapped_column(JSONB)

    # Sidik jari isi payload. Dipakai sebagai kunci anti-duplikat: menarik
    # ulang sumber yang sama tidak menghasilkan baris ganda. Lebih dapat
    # diandalkan daripada external_id, yang belum tentu ada di semua sumber.
    payload_hash: Mapped[str]

    # Hasil penyaringan. "pending" sebelum diperiksa, "passed" kalau lolos
    # seluruh gate, "rejected" kalau gugur. Yang gugur TIDAK dihapus — jumlah
    # lolos dan gugur per gate itulah bukti bahwa penyaringnya aturan, bukan
    # pilihan tangan.
    gate_status: Mapped[str] = mapped_column(default="pending", server_default="pending")
    # Gate mana yang menolak: "spasial", "wilayah", "kualitas", atau "temporal".
    gate_reason: Mapped[str | None]

    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("payload_hash", name="uq_activity_raw_hash"),
        CheckConstraint(
            "gate_status IN ('pending', 'passed', 'rejected')",
            name="ck_activity_raw_gate_status",
        ),
    )


class ActivityPoint(TimestampMixin, Base):
    """Entri yang lolos seluruh gate, sudah ditata jadi kolom."""

    __tablename__ = "activity_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_id: Mapped[int] = mapped_column(
        ForeignKey("activity_raw.id", ondelete="CASCADE"), unique=True
    )

    # Stasiun dan zona isochrone tempat titik ini jatuh, hasil spatial join.
    # Keduanya boleh kosong sampai join-nya dijalankan.
    station_id: Mapped[int | None] = mapped_column(
        ForeignKey("stations.id", ondelete="SET NULL"), index=True
    )
    isochrone_id: Mapped[int | None] = mapped_column(
        ForeignKey("isochrones.id", ondelete="SET NULL"), index=True
    )

    name: Mapped[str | None]
    category: Mapped[str | None] = mapped_column(index=True)

    # Kewajiban dasar setiap entri Activity, dan satu-satunya bahan lapis 1.
    narrative: Mapped[str] = mapped_column(Text)

    # Daftar URL foto. JSONB karena jumlahnya berubah-ubah per entri.
    photo_urls: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )

    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location: Mapped[str] = mapped_column(
        Geometry("POINT", srid=SRID_RENDER, spatial_index=True)
    )

    # Asal entri, misal "survey tim" atau "tim lain".
    #
    # PERINGATAN: kolom ini HANYA untuk pelaporan dan statistik. Dilarang
    # dipakai sebagai syarat percabangan di kode pemrosesan. Klaim inti produk
    # adalah pipeline yang bekerja pada entri Activity mana pun; begitu ada
    # cabang `if provenance == "survey tim"`, klaim itu gugur.
    provenance: Mapped[str | None]

    # Apakah entri ini memuat pola penilaian narasumber. Menentukan ia masuk
    # lapis 2 atau tidak — bukan menentukan ia dipakai atau dibuang.
    has_interviewer_pattern: Mapped[bool] = mapped_column(
        default=False, server_default=text("false")
    )

    # Kapan narasi ini terakhir dibaca ekstraksi LLM (activity_extract.py).
    # Tanpa penanda, narasi yang memang tidak memuat iklan/tenant/fasilitas
    # dikirim ulang ke model setiap kali skrip dijalankan dan membakar kuota.
    llm_ec_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Pass kondisi fasilitas (positif maupun negatif, PRD Tabel 7).
    llm_fasilitas_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ActivityExtraction(TimestampMixin, Base):
    """Keluaran lapis 1: arketipe, merek, dan sentimen per titik.

    Satu baris per titik. Ketiga model berjalan pada bahan yang sama, yaitu
    teks naratif, jadi hasilnya disimpan bersama supaya mudah ditelusuri
    sebagai satu kesatuan.
    """

    __tablename__ = "activity_extractions"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_point_id: Mapped[int] = mapped_column(
        ForeignKey("activity_points.id", ondelete="CASCADE"), unique=True
    )

    # Arketipe stasiun hasil LDA. Selain menentukan profil pembobotan, ini juga
    # kelompok pembanding pada mekanisme shrinkage (PRD hal. 13).
    archetype: Mapped[str | None] = mapped_column(index=True)
    # Distribusi probabilitas seluruh topik, bukan hanya yang tertinggi.
    # Disimpan supaya keputusan arketipe bisa diperiksa ulang, bukan dipercaya
    # begitu saja.
    archetype_probs: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )

    # Daftar entitas merek hasil NER, jadi bahan kandidat sponsor.
    brands: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )

    sentiment_label: Mapped[str | None]
    sentiment_score: Mapped[float | None]

    # PRD hal. 12 mewajibkan setiap temuan berbasis teks diuji terhadap kondisi
    # spasial yang dapat diverifikasi. Selama kolom ini masih False, hasilnya
    # tidak boleh ikut menyumbang ke skor.
    spatially_validated: Mapped[bool] = mapped_column(
        default=False, server_default=text("false")
    )
    validation_note: Mapped[str | None] = mapped_column(Text)

    # Model dan versi apa yang menghasilkan baris ini. Tanpa ini, hasil dari
    # dua versi model berbeda tercampur tanpa bisa dibedakan.
    model_versions: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )


class CrowdRating(TimestampMixin, Base):
    """Keluaran lapis 2: skala keramaian 1-5 per rentang waktu.

    Opsional menurut PRD hal. 9-10. Entri tanpa pola penilaian narasumber
    dilewati begitu saja tanpa menghentikan proses, dan nilainya tetap sah
    lewat jalur lapis 1.
    """

    __tablename__ = "crowd_ratings"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_point_id: Mapped[int] = mapped_column(
        ForeignKey("activity_points.id", ondelete="CASCADE"), index=True
    )
    station_id: Mapped[int | None] = mapped_column(
        ForeignKey("stations.id", ondelete="SET NULL"), index=True
    )
    zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("station_zones.id", ondelete="SET NULL"), index=True
    )

    # Tiga rentang baku PRD hal. 10: pagi 06.00-09.00, siang 09.00-16.00,
    # sore 16.00-19.00. Dikunci lewat constraint supaya tidak ada rentang
    # keempat yang menyelinap masuk dan merusak perbandingan antar-stasiun.
    time_window: Mapped[str]

    # Skala ORDINAL. Dinormalisasi ke 0-1 sebelum masuk perhitungan,
    # (rating - scale_min) / (scale_max - scale_min), jadi jangan pernah
    # diperlakukan sebagai nilai absolut. Rentangnya ikut disimpan karena
    # Activity universal tidak selalu memakai 1-5 (ADJUSTMENT 9.32).
    rating: Mapped[int]
    scale_min: Mapped[int] = mapped_column(default=1, server_default=text("1"))
    scale_max: Mapped[int] = mapped_column(default=5, server_default=text("5"))

    # Atribusi narasumber sebagai PERAN, bukan identitas — misalnya
    # "petugas kebersihan peron 2". PRD menaruh pengolahan data pribadi di luar
    # lingkup, dan kolom inilah tempat aturan itu paling gampang bocor.
    respondent_ref: Mapped[str | None]

    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "time_window IN ('pagi', 'siang', 'sore')",
            name="ck_crowd_rating_time_window",
        ),
        CheckConstraint(
            "rating BETWEEN scale_min AND scale_max", name="ck_crowd_rating_range"
        ),
        CheckConstraint(
            "scale_min IN (0, 1) AND scale_max BETWEEN 3 AND 10",
            name="ck_crowd_rating_scale",
        ),
    )
