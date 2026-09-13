"""Composite Exposure Index - ukuran paparan untuk Ad-Space dan Naming Rights.

KENAPA BUKAN SEPI
-----------------
SEPI mengukur POTENSI EKONOMI kawasan, dan bobotnya mencerminkan itu:
aksesibilitas 0,255 dan urban 0,253 menguasai separuh, sementara transportasi
hanya 0,181. Untuk menilai kelayakan usaha, susunan itu benar.

Untuk menilai PAPARAN IKLAN, ia keliru - dan kekeliruannya terlihat jelas di
data. Tanah Abang punya nilai transportasi tertinggi (0,68) tetapi hanya
peringkat 23 SEPI, sementara Pondok Jati bernilai transportasi terendah (0,23)
justru peringkat 3. Untuk ruang iklan, hasil itu terbalik dari yang masuk akal:
yang dibeli pengiklan adalah orang yang lewat, bukan keberagaman toko di
sekitarnya.

PRD sudah menyiapkan jawabannya di hal. 13:

    CEI = 0,5 x T + 0,3 x E + 0,2 x U

disebut "rekomposisi SEPI yang menekankan dimensi eksposur". Transportasi -
yang memuat volume penumpang, jumlah moda, status interchange, dan skala
keramaian narasumber - diberi bobot setengah.

Dengan rumus itu urutannya jadi masuk akal: Manggarai 73,3 dan Tanah Abang 67,7
di dua teratas, sedangkan Pondok Jati turun ke peringkat 10.

C DAN A SENGAJA TIDAK IKUT
--------------------------
Rumusnya hanya memakai T, E, dan U - itu ketetapan PRD, bukan kelalaian.
Aksesibilitas (A) mengukur seberapa luas kawasan yang terjangkau jalan kaki,
yang menentukan basis pelanggan sebuah toko, bukan berapa banyak mata yang
melihat sebuah layar di dalam stasiun. Komersial (C) mengukur inventaris iklan
yang SUDAH terpasang - memasukkannya akan membuat stasiun yang sudah penuh
iklan terlihat paling layak diiklani, yang memutar logikanya.
"""

from __future__ import annotations

BOBOT_CEI = {"T": 0.5, "E": 0.3, "U": 0.2}


def hitung_cei(raw_t: float | None, raw_e: float | None, raw_u: float | None) -> float | None:
    """CEI 0-100 dari nilai variabel yang sudah ternormalisasi 0-1.

    Mengembalikan None kalau ada variabel yang belum tersedia sama sekali -
    lebih baik diam daripada mengarang paparan dari data yang tidak ada.
    """
    if raw_t is None or raw_e is None or raw_u is None:
        return None
    nilai = (
        BOBOT_CEI["T"] * float(raw_t)
        + BOBOT_CEI["E"] * float(raw_e)
        + BOBOT_CEI["U"] * float(raw_u)
    ) * 100.0
    return round(min(max(nilai, 0.0), 100.0), 2)


def kelas_paparan(cei: float | None) -> str | None:
    """Label paparan yang enak dibaca. Ambangnya sama dengan kelas SEPI."""
    if cei is None:
        return None
    if cei >= 70:
        return "Paparan tinggi"
    if cei >= 40:
        return "Paparan sedang"
    return "Paparan terbatas"
