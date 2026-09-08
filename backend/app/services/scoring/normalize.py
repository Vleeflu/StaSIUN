"""Normalisasi indikator ke rentang 0-1.

Langkah pertama seluruh mesin skor, dan syarat mutlak sebelum apa pun
dijumlahkan: jumlah titik minat (81 sampai 984) dan keberagaman (0,3 sampai
0,98) tidak boleh ditambahkan begitu saja, karena yang berangka besar akan
mendominasi hanya karena satuannya kebetulan besar.

PRD hal. 13: "Seluruh variabel dinormalisasi ke rentang 0 sampai 1 sebelum
masuk TOPSIS, termasuk indikator berskala ordinal dari narasumber, sehingga
skala ordinal tidak diperlakukan sebagai nilai absolut."
"""

from enum import Enum

import numpy as np


class Arah(str, Enum):
    """Apakah nilai besar itu bagus atau buruk untuk indikator ini."""

    # Makin besar makin bagus: jumlah titik minat, keberagaman, moda terhubung.
    MANFAAT = "manfaat"
    # Makin besar makin buruk: harga sewa relatif, indeks keluhan fasilitas.
    BIAYA = "biaya"


def minmax(nilai: np.ndarray, arah: Arah = Arah.MANFAAT) -> np.ndarray:
    """Petakan satu kolom indikator ke 0-1.

        manfaat:  x' = (x - min) / (max - min)
        biaya:    x' = (max - x) / (max - min)

    Nilai kosong (NaN) dipertahankan sebagai NaN, TIDAK diisi. Nol berarti
    "terburuk di antara yang ada"; kosong berarti "tidak diketahui". Menukar
    keduanya adalah cara tercepat membuat stasiun yang datanya belum masuk
    terlihat seperti stasiun yang benar-benar buruk.

    Kolom yang seluruh nilainya sama menghasilkan 0,5, bukan 0. Alasannya:
    indikator tanpa variasi tidak membedakan apa pun, jadi menempatkan semua
    di titik tengah lebih jujur daripada menyebut semuanya terburuk. Bobot
    entropinya akan nol juga, sehingga ia memang tidak ikut memengaruhi hasil.
    """
    x = np.asarray(nilai, dtype=float)
    ada = ~np.isnan(x)

    if not ada.any():
        return np.full_like(x, np.nan)

    lo = np.nanmin(x)
    hi = np.nanmax(x)
    rentang = hi - lo

    hasil = np.full_like(x, np.nan)
    if rentang == 0:
        hasil[ada] = 0.5
        return hasil

    if arah is Arah.MANFAAT:
        hasil[ada] = (x[ada] - lo) / rentang
    else:
        hasil[ada] = (hi - x[ada]) / rentang
    return hasil


def normalisasi_matriks(
    matriks: np.ndarray, arah: list[Arah] | None = None
) -> np.ndarray:
    """Normalisasi seluruh kolom sebuah matriks keputusan.

    Baris = alternatif (stasiun), kolom = indikator. Normalisasi dikerjakan
    PER KOLOM karena batas bawah dan atas tiap indikator ditentukan oleh
    seluruh stasiun, bukan oleh stasiun itu sendiri.
    """
    m = np.asarray(matriks, dtype=float)
    if m.ndim != 2:
        raise ValueError("matriks keputusan harus dua dimensi (stasiun x indikator)")

    if arah is None:
        arah = [Arah.MANFAAT] * m.shape[1]
    if len(arah) != m.shape[1]:
        raise ValueError(f"arah harus {m.shape[1]} entri, diberi {len(arah)}")

    return np.column_stack([minmax(m[:, j], arah[j]) for j in range(m.shape[1])])


def gabung_indikator(matriks_ternormalisasi: np.ndarray) -> np.ndarray:
    """Rata-ratakan beberapa indikator jadi satu nilai variabel SEPI.

    PRD Tabel 6 mendaftar beberapa indikator kunci per variabel (misalnya U
    disusun dari kepadatan titik minat, keberagaman fungsi lahan, dan jumlah
    pembangkit perjalanan) tetapi TIDAK menyebutkan cara menggabungkannya.

    Dipakai rata-rata sederhana. Ini keputusan tim, bukan ketentuan PRD, dan
    layak dibantah: rata-rata memperlakukan ketiga indikator sama penting.
    Alternatifnya memberi bobot berbeda antar-indikator, tetapi itu menambah
    satu lapis pembobotan lagi yang tidak punya dasar di PRD maupun data.

    NaN diabaikan, bukan dianggap nol: variabel yang dua dari tiga indikatornya
    ada tetap dihitung dari dua itu.
    """
    m = np.asarray(matriks_ternormalisasi, dtype=float)
    with np.errstate(invalid="ignore"):
        return np.nanmean(m, axis=1)
