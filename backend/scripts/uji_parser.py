"""Uji Parser pola narasumber (lapis 2) atas kalimat yang bentuknya diketahui.

Setiap kasus di sini berasal dari kesalahan NYATA yang pernah terjadi, atau dari
bentuk kalimat nyata di data Activity. Parser ini lolos uji "tidak error" sejak
awal, dan tetap salah memberi label pada 16 dari 25 aktivitas (B23) - karena
tidak ada yang membandingkan hasilnya dengan kalimat aslinya. Berkas ini adalah
pembanding itu.

    python -m scripts.uji_parser

Dijalankan di dalam container (butuh sqlalchemy dan geoalchemy2).
"""

import sys

from app.services.activity_parse import (
    LABEL_AKHIR_PEKAN,
    LABEL_RENTANG_SKALA,
    LABEL_SKALA_TIDAK_KONSISTEN,
    LABEL_SURVEYOR,
    LABEL_TANPA_PENYEBUT,
    ambil_rating,
)

KASUS = [
    (
        "B23 #476: label diambil dari urutan daftar, bukan yang terdekat",
        "Menurut petugas keamanan yang berjaga, tingkat keramaian koridor ini berbeda-beda "
        "sepanjang hari: pada pagi pukul 07.00 sampai 09.00 ia menilai keramaiannya di tingkat 3 "
        "dari 5, siang hari turun ke tingkat 1, dan kembali ramai di tingkat 3 pada sore pukul "
        "17.00 sampai 19.00.",
        [(3, "pagi", 1, 5), (1, "siang", 1, 5), (3, "sore", 1, 5)],
    ),
    (
        "#1225: baris baru di tengah kalimat bukan akhir kalimat",
        "Menurut petugas keamanan yang berjaga: pada pagi pukul 06.00 sampai 09.00 ia menilai "
        "keramaiannya di\ntingkat 5 dari 5, siang hari turun ke tingkat 3.",
        [(5, "pagi", 1, 5), (3, "siang", 1, 5)],
    ),
    (
        "#802: baris baru berhuruf kapital adalah batas kalimat",
        "Skala rame menurut petugas adalah sebagai berikut :\nPagi (6:00 - 9:00) : skala 2 dari 5 "
        "(sepi)\nSiang : skala 2 dari 5\nSore (16-30 - 19:00) : skala 4 dari 5",
        [(2, "pagi", 1, 5), (2, "siang", 1, 5), (4, "sore", 1, 5)],
    ),
    (
        "#1003: arah yang penanda waktunya lebih dekat yang dipakai",
        "Menurut petugas keamanan di sini, keramaian peron 3-4 berada pada skala 4 di pagi hari "
        "jam 06.30 hingga 09.00. Kemudian skala 2 pada siang hari dan kemudian kembali meningkat "
        "ke skala 5 pada jam 16.00 hingga 20.00 yaitu jam pulang kerja.",
        [(4, "pagi", 1, 5), (2, "siang", 1, 5), (5, "sore", 1, 5)],
    ),
    (
        "#607: koma memisahkan rentang jam dari angkanya",
        "Menurut petugas keamanan, pada pagi hari pukul 06.00-09.00 tingkat keramaian peron berada "
        "pada tingkat 5 dari 5. Pada jam 16.00-19.00, keramaian stasiun kembali meningkat ke "
        "tingkat 5 dari 5.",
        [(5, "pagi", 1, 5), (5, "sore", 1, 5)],
    ),
    (
        "#854: satu angka untuk dua rentang yang dihubungkan 'dan'",
        "Ia menyebutkan bahwa pembeli paling ramai justru pada jam pergi kerja pagi hari dan "
        "pulang kerja sore hari yang ia nilai di tingkat 5 dari 5, sementara siang hari tergolong "
        "sepi di tingkat 1.",
        [(5, "pagi", 1, 5), (5, "sore", 1, 5), (1, "siang", 1, 5)],
    ),
    (
        "#1220: kata 'malam' di dalam rentang jam tidak mengalahkan rentangnya",
        "Menurut beberapa petugas, dan sore hari jam 16:00 hingga malam 20:00 pada skala 5 dari 5.",
        [(5, "sore", 1, 5)],
    ),
    (
        "PRD hal. 12: 09.00 sendirian adalah siang, rentang 06.00-09.00 adalah pagi",
        "Menurut petugas, pukul 09.00 keramaian di tingkat 2. Menurut petugas, pukul 06.00 "
        "sampai 09.00 keramaian di tingkat 5.",
        [(2, "siang", 1, 5), (5, "pagi", 1, 5)],
    ),
    (
        "#1099: angka sebelum atribusi adalah penilaian surveyor",
        "Saat pengamatan, terlihat keramaian berada pada skala 2. Menurut petugas, keramaian di "
        "siang hari berada pada skala 3.",
        [(2, LABEL_SURVEYOR, 0, 0), (3, "siang", 1, 5)],
    ),
    (
        "#1099: skala berupa rentang tidak dipilihkan salah satu ujungnya",
        "Menurut petugas, keramaian di pagi hari berada pada skala 4 hingga 5.",
        [(4, LABEL_RENTANG_SKALA, 0, 0)],
    ),
    (
        "#782: kalimat akhir pekan dilewati",
        "Menurut petugas, saat weekend keramaian pagi hari pada skala 4 dari 5.",
        [(4, LABEL_AKHIR_PEKAN, 0, 0)],
    ),
    (
        "#1024: bentuk 'N dari 5' tanpa kata skala",
        "Menurut petugas yang sedang berjaga, kepadatan mencapai puncak sekitar jam 06.30 sampai "
        "09.00 dan 16.30 hingga 19.00 dengan nilai kepadatan 5 dari 5.",
        [(5, "pagi", 1, 5), (5, "sore", 1, 5)],
    ),
    (
        "keterisian lapak BUKAN skala keramaian",
        "Menurut penjual, pagi ada 3 dari 5 kios terisi.",
        [],
    ),
    (
        "9.32: skala 1-10 yang dipakai konsisten diterima beserta rentangnya",
        "Menurut petugas, pagi 8 dari 10, siang 4 dari 10, sore 9 dari 10.",
        [(8, "pagi", 1, 10), (4, "siang", 1, 10), (9, "sore", 1, 10)],
    ),
    (
        "9.32: angka di atas 5 tanpa penyebut tidak ditebak rentangnya",
        "Menurut petugas, sore hari ramai di level 8.",
        [(8, LABEL_TANPA_PENYEBUT, 0, 0)],
    ),
    (
        "9.32 #791: penyebut minoritas dalam satu narasi dianggap tidak konsisten",
        "Menurut penjual, sore tingkat 5 dari 5, pagi cukup ramai tingkat 3 dari 3, siang sepi "
        "tingkat 1.",
        [(5, "sore", 1, 5), (3, LABEL_SKALA_TIDAK_KONSISTEN, 0, 0), (1, "siang", 1, 5)],
    ),
    (
        "tanpa atribusi sama sekali: tidak ada yang diambil",
        "Pagi hari keramaian di tingkat 5 dari 5.",
        [],
    ),
]


def main() -> int:
    gagal = 0
    for nama, kalimat, harapan in KASUS:
        dapat = ambil_rating(kalimat)
        if dapat == harapan:
            print(f"  lulus  {nama}")
        else:
            gagal += 1
            print(f"  GAGAL  {nama}\n         dapat   {dapat}\n         harapan {harapan}")
    print(f"\n{len(KASUS) - gagal}/{len(KASUS)} lulus")
    return 1 if gagal else 0


if __name__ == "__main__":
    sys.exit(main())
