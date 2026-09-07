"""Kolom-kolom yang berulang di banyak tabel.

Mixin adalah kelas yang tidak pernah menjadi tabel sendiri. Isinya hanya kumpulan
kolom yang ditempelkan ke tabel lain lewat pewarisan, supaya definisi yang sama
tidak ditulis ulang di belasan tempat — dan supaya tidak ada satu tabel pun yang
kelupaan memakainya.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, func, text
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Kapan baris dibuat dan terakhir diubah.

    Dipakai untuk menelusuri data lama: PRD mensyaratkan keluhan lawas
    divalidasi ulang ke pengamatan terkini, dan itu mustahil kalau tidak ada
    catatan waktu sama sekali.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SourceMixin:
    """Asal data eksternal beserta tanggal aksesnya.

    PRD hal. 8 dan 9 mensyaratkan setiap data pendukung di luar ekosistem MAPID
    mencantumkan sumber dan tanggal akses. Karena itu keduanya WAJIB diisi —
    kalau boleh kosong, cepat atau lambat akan ada baris tanpa sumber dan
    klaimnya jadi tidak bisa dipertanggungjawabkan.
    """

    # Nama sumbernya, misal "BPS DKI Jakarta" atau "Situs resmi tenant".
    source: Mapped[str]
    source_url: Mapped[str | None]
    accessed_at: Mapped[date] = mapped_column(Date)


class ScoreMetadataMixin:
    """Lima kolom keyakinan yang wajib menempel di setiap tabel skor.

    Ini acceptance criteria tersendiri di PRD (Tabel 8, "Metadata Transparansi"),
    bukan tambahan opsional: setiap skor harus tampil bersama jumlah sampel,
    interval keyakinan, dan penanda tingkat keyakinannya, supaya zona berdata
    terbatas tetap bisa ditampilkan tanpa menyesatkan pengguna.

    Dijadikan mixin karena akan dipakai empat tabel skor sekaligus. Kalau
    ditulis manual berkali-kali, cukup sekali lupa dan kriteria itu bocor tanpa
    ketahuan siapa pun.
    """

    # Berapa titik data yang menyusun skor ini. Nol berarti skornya sepenuhnya
    # hasil pinjaman dari kelompok pembanding lewat shrinkage.
    n_sample: Mapped[int] = mapped_column(default=0, server_default=text("0"))

    # Batas bawah dan atas interval keyakinan, hasil bootstrap BCa.
    ci_low: Mapped[float | None]
    ci_high: Mapped[float | None]

    # Tingkat keyakinan 0-1. Ditampilkan ke pengguna sebagai label
    # (rendah/sedang/tinggi); pemetaan ke labelnya dikerjakan di lapisan API,
    # bukan disimpan, supaya ambangnya bisa diubah tanpa migrasi.
    confidence: Mapped[float | None]

    # Porsi nilai yang berasal dari estimasi, bukan dari pengamatan langsung.
    # Nilai 0 berarti seluruhnya terukur, 1 berarti seluruhnya diestimasi.
    estimated_share: Mapped[float | None]
