"""Penyusunan skor SEPI dan klasifikasinya.

    SEPI = 100 x (w1*T + w2*E + w3*A + w4*U + w5*C)

MENANGANI VARIABEL YANG DATANYA BELUM ADA
------------------------------------------
Per 7 Sep hanya U yang lengkap dan T yang separuh; E, A, dan C menunggu data.
Ada tiga cara memperlakukan variabel kosong, dan dua di antaranya salah:

  isi nol         -> SALAH. Nol berarti "terburuk di antara yang ada". Stasiun
                     yang datanya belum ditarik jadi terlihat seperti stasiun
                     yang memang buruk.
  isi rata-rata   -> SALAH. PRD melarang mengisi angka asumsi, dan ini membuat
                     seluruh stasiun tertarik ke tengah sehingga perbedaan
                     nyata di antara mereka menyusut.
  bobot dinormalisasi ulang atas variabel yang ADA  -> yang dipakai di sini.

Cara ketiga menjawab pertanyaan yang jujur: "berdasarkan yang kita tahu
sekarang, seberapa besar potensinya" — bukan berpura-pura tahu yang belum
diketahui. Konsekuensinya harus ikut dilaporkan: skor yang disusun dari dua
variabel tidak sebanding dengan skor lima variabel, dan itulah yang dicatat
kolom `variabel_terpakai` serta `confidence`.
"""

from dataclasses import dataclass

import numpy as np

# Urutan baku variabel SEPI. Dipakai di seluruh mesin skor supaya indeks kolom
# tidak pernah ditebak-tebak.
VARIABEL = ("T", "E", "A", "U", "C")

NAMA_VARIABEL = {
    "T": "Transportasi",
    "E": "Ekonomi",
    "A": "Aksesibilitas",
    "U": "Urban",
    "C": "Komersial",
}

# PRD hal. 13, lengkap dengan kalimat keputusan bisnisnya. Ambang batas ini
# ditetapkan PRD, bukan pilihan tim.
#
# Batas atas ditulis sebagai batas EKSKLUSIF (40 dan 70, bukan 39 dan 69).
# PRD menulis rentangnya sebagai 0-39 / 40-69 / 70-100, yang benar untuk
# bilangan bulat tetapi meninggalkan dua celah pada skor kontinu: 39 < x < 40
# dan 69 < x < 70 tidak masuk kelas mana pun. Skor SEPI adalah jumlah berbobot,
# jadi 39,59 memang mungkin - dan pernah benar-benar terjadi. Interval setengah
# terbuka [0,40) [40,70) [70,100] menutup seluruh garis bilangan tanpa
# menggeser maksud PRD: 39 tetap Low, 40 tetap Moderate.
KELAS = (
    (
        0,
        40,
        "Low Potential",
        "Hindari investasi tenant menetap. Cocok untuk vending machine atau "
        "iklan luar ruang informatif berbiaya rendah.",
    ),
    (
        40,
        70,
        "Moderate Potential",
        "Layak untuk ekspansi UMKM tipe grab-and-go dengan harga sewa standar pasar.",
    ),
    (
        70,
        100,
        "Premium Transit Hub",
        "Target Naming Rights, penempatan brand korporat besar, dan justifikasi "
        "sewa kelas premium.",
    ),
)


@dataclass
class SkorSepi:
    station_id: int
    station_name: str
    nilai: float  # 0-100
    kelas: str
    keputusan: str
    komponen: dict[str, float | None]  # nilai tiap variabel, None kalau kosong
    bobot_terpakai: dict[str, float]  # bobot setelah dinormalisasi ulang
    variabel_terpakai: int
    confidence: float  # 0-1
    # SEPI sebelum modifier teks, dan besar penalti yang diterapkan. Disimpan
    # supaya pengurangannya bisa ditunjukkan, bukan cuma hasil akhirnya.
    nilai_dasar: float = 0.0
    penalti_teks: float = 0.0


def klasifikasi(nilai: float) -> tuple[str, str]:
    """Petakan skor 0-100 ke label dan kalimat keputusan bisnisnya.

    Batas bawah inklusif, batas atas eksklusif - kecuali kelas terakhir, yang
    atasnya inklusif supaya skor 100 tepat masih punya kelas.
    """
    for bawah, atas, label, keputusan in KELAS:
        terakhir = atas == 100
        if bawah <= nilai <= atas if terakhir else bawah <= nilai < atas:
            return label, keputusan
    # Hanya tercapai kalau nilainya di luar 0-100, yang berarti ada bug di hulu.
    raise ValueError(f"skor SEPI di luar rentang 0-100: {nilai}")


def confidence_dari_kelengkapan(variabel_terpakai: int) -> float:
    """Tingkat keyakinan sementara, murni dari berapa variabel yang terisi.

    Ini BUKAN confidence versi PRD yang utuh. Versi utuhnya menggabungkan
    jumlah sampel dan lebar interval keyakinan hasil bootstrap BCa (F3-6),
    dan akan menggantikan fungsi ini begitu tersedia.

    Sampai saat itu, dipakai rasio sederhana variabel terisi terhadap lima.
    Nilainya sengaja dibuat kasar dan pesimistis: skor dari dua variabel
    mendapat confidence 0,4, dan angka serendah itu memang HARUS terlihat
    mencolok di panel.
    """
    return variabel_terpakai / len(VARIABEL)


def hitung_sepi(
    station_ids: list[int],
    station_names: list[str],
    matriks: np.ndarray,
    bobot: np.ndarray,
    terukur: np.ndarray | None = None,
    penalti: list[float] | None = None,
    batas_modifier: float = 0.15,
) -> list[SkorSepi]:
    """Susun skor SEPI dari matriks variabel yang sudah ternormalisasi.

    `matriks` berukuran (jumlah stasiun x 5), kolomnya mengikuti urutan
    VARIABEL. Nilai kosong ditulis NaN, bukan nol.

    `terukur` (opsional, bentuk sama dengan matriks, bool) menyatakan variabel
    mana yang benar-benar HASIL UKUR. Dipakai untuk `variabel_terpakai` dan
    `confidence`. Wajib diberikan kalau `matriks` berisi nilai hasil shrinkage:
    tanpanya setiap stasiun tampil 5 dari 5 dengan confidence 1,00, dan estimasi
    menyamar jadi pengukuran. Kalau tidak diberikan, kelengkapan dibaca dari
    NaN di `matriks` seperti sebelumnya.

    `penalti` (opsional, 0..1 per stasiun) adalah modifier dari model berbasis
    teks — saat ini polaritas sentimen keluhan fasilitas. PRD hal. 16 membatasi
    kontribusinya "maksimal 15 persen terhadap skor akhir", jadi diterapkan
    sebagai pengali:

        SEPI_akhir = SEPI_dasar x (1 - batas_modifier x penalti)

    Dengan penalti maksimal 1, pengurangan terbesar tepat 15 persen dari skor.
    Klasifikasi memakai SEPI_akhir.
    """
    x = np.asarray(matriks, dtype=float)
    w = np.asarray(bobot, dtype=float)
    if x.shape[1] != len(VARIABEL):
        raise ValueError(f"matriks harus punya {len(VARIABEL)} kolom, ada {x.shape[1]}")
    if w.size != len(VARIABEL):
        raise ValueError(f"bobot harus {len(VARIABEL)} entri, ada {w.size}")

    hasil = []
    for i, (sid, nama) in enumerate(zip(station_ids, station_names)):
        baris = x[i]
        ada = ~np.isnan(baris)

        if not ada.any():
            raise ValueError(f"stasiun {nama!r} tidak punya satu pun variabel terisi")

        # Inti penanganan data tak lengkap: bobot dinormalisasi ulang hanya
        # atas variabel yang ada, sehingga jumlahnya tetap 1 dan skornya tetap
        # berada di rentang 0-100 tanpa satu pun nilai dikarang.
        w_ada = w[ada]
        w_ternormalisasi = w_ada / w_ada.sum()

        dasar = float(np.sum(baris[ada] * w_ternormalisasi) * 100.0)
        p = 0.0
        if penalti is not None:
            p = min(max(float(penalti[i]), 0.0), 1.0)
        nilai = dasar * (1.0 - batas_modifier * p)
        # Kesalahan pembulatan floating point bisa menghasilkan 100.0000000001,
        # yang akan membuat klasifikasi() melempar error.
        nilai = min(max(nilai, 0.0), 100.0)

        label, keputusan = klasifikasi(nilai)
        terpakai = int(np.asarray(terukur[i], dtype=bool).sum()) if terukur is not None else int(ada.sum())

        hasil.append(
            SkorSepi(
                station_id=sid,
                station_name=nama,
                nilai=nilai,
                kelas=label,
                keputusan=keputusan,
                komponen={
                    v: (float(baris[j]) if ada[j] else None)
                    for j, v in enumerate(VARIABEL)
                },
                bobot_terpakai={
                    v: float(w_ternormalisasi[list(np.where(ada)[0]).index(j)])
                    for j, v in enumerate(VARIABEL)
                    if ada[j]
                },
                variabel_terpakai=terpakai,
                confidence=confidence_dari_kelengkapan(terpakai),
                nilai_dasar=min(max(dasar, 0.0), 100.0),
                penalti_teks=p,
            )
        )
    return hasil
