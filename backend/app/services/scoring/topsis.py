"""TOPSIS — perankingan menurut kedekatan ke solusi ideal.

    v_ij = w_j * x_ij                      matriks ternormalisasi berbobot
    A+   = (max_i v_i1, ..., max_i v_in)   sudut ideal
    A-   = (min_i v_i1, ..., min_i v_in)   sudut terburuk
    S+   = ||v_i - A+||,  S- = ||v_i - A-||
    C_i  = S- / (S+ + S-)                  0..1, makin besar makin baik

A+ hampir selalu BUKAN stasiun yang benar-benar ada — dia sudut hipotetis yang
menggabungkan nilai terbaik tiap dimensi, yang bisa saja berasal dari stasiun
yang berbeda-beda.

PERINGATAN YANG WAJIB DIBACA SEBELUM MEMAKAI HASILNYA
-----------------------------------------------------
TOPSIS bisa MEMBALIK PERINGKAT. Karena A+ dan A- ditentukan oleh himpunan
alternatif yang kebetulan ikut dinilai, menambah satu stasiun bisa menukar
urutan dua stasiun lain yang datanya tidak berubah sama sekali.

Contoh yang bisa diperiksa sendiri, bobot sama 0,5:

    X = (1,0 ; 0,2)  dan  Y = (0,6 ; 0,6)   jumlah berbobotnya sama: 0,6

    ditambah Z = (0,0):        C_X = 0,718 > C_Y = 0,680  -> X menang
    ditambah W = (1,1):        C_X = 0,333 < C_Y = 0,414  -> Y menang

Ini kelemahan terdokumentasi TOPSIS, bukan kesalahan penerapan.

AKIBATNYA UNTUK PRODUK INI:

  - Klasifikasi 0-39 / 40-69 / 70-100 memakai SEPI (jumlah berbobot), BUKAN
    peringkat TOPSIS. Jumlah berbobot bersifat pointwise: nilai satu stasiun
    tidak bergantung pada stasiun lain sama sekali, jadi stabil.
  - Peringkat TOPSIS selalu disebutkan bersama himpunan pembandingnya. Kalau
    cakupan diperluas ke Jabodetabek, peringkat lama bisa berubah walau datanya
    tidak.

Struktur PRD — SEPI untuk klasifikasi, TOPSIS untuk peringkat — karena itu
memang benar secara matematis, bukan kebetulan.
"""

import warnings
from dataclasses import dataclass

import numpy as np


@dataclass
class HasilTopsis:
    kedekatan: np.ndarray  # C_i, 0..1
    peringkat: np.ndarray  # 1 = terbaik
    ideal: np.ndarray  # A+
    terburuk: np.ndarray  # A-


def topsis(matriks: np.ndarray, bobot: np.ndarray) -> HasilTopsis:
    """Hitung kedekatan dan peringkat TOPSIS.

    Masukan sudah ternormalisasi 0-1 dan seluruh kolom sudah berorientasi
    manfaat (kolom biaya dibalik saat normalisasi), jadi A+ selalu maksimum
    dan A- selalu minimum tiap kolom.

    Nilai kosong diperlakukan sebagai "tidak menyumbang jarak", bukan nol.
    Memperlakukannya nol akan menempatkan stasiun berdata belum lengkap tepat
    di sudut terburuk — menghukumnya karena datanya belum masuk, bukan karena
    kondisinya memang buruk.
    """
    x = np.asarray(matriks, dtype=float)
    w = np.asarray(bobot, dtype=float)
    if x.shape[1] != w.size:
        raise ValueError(f"matriks punya {x.shape[1]} kolom, bobot {w.size}")

    v = x * w

    # Kolom yang seluruhnya NaN adalah variabel yang belum diukur sama sekali
    # (E dan C menunggu survey Activity). nanmax/nanmin memperingatkan "All-NaN
    # slice" untuk kolom seperti itu, padahal di sini keadaan tersebut memang
    # diharapkan dan sudah ditangani: selisihnya dinolkan beberapa baris di
    # bawah, jadi kolomnya tidak menyumbang jarak ke stasiun mana pun.
    # Peringatannya dibungkam DI SINI saja, bukan secara global, supaya All-NaN
    # yang tak terduga di tempat lain tetap terdengar.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", "All-NaN slice encountered", RuntimeWarning)
        ideal = np.nanmax(v, axis=0)
        terburuk = np.nanmin(v, axis=0)

    selisih_ideal = np.where(np.isnan(v), 0.0, v - ideal)
    selisih_terburuk = np.where(np.isnan(v), 0.0, v - terburuk)

    s_plus = np.sqrt(np.sum(selisih_ideal**2, axis=1))
    s_minus = np.sqrt(np.sum(selisih_terburuk**2, axis=1))

    penyebut = s_plus + s_minus
    # Stasiun yang tepat berimpit dengan ideal DAN terburuk sekaligus hanya
    # mungkin kalau seluruh kriterianya konstan. Diberi 0,5 (netral), bukan
    # dibiarkan jadi pembagian nol.
    kedekatan = np.where(penyebut > 0, s_minus / np.where(penyebut > 0, penyebut, 1), 0.5)

    # Peringkat 1 untuk kedekatan tertinggi.
    urutan = np.argsort(-kedekatan, kind="stable")
    peringkat = np.empty_like(urutan)
    peringkat[urutan] = np.arange(1, kedekatan.size + 1)

    return HasilTopsis(
        kedekatan=kedekatan, peringkat=peringkat, ideal=ideal, terburuk=terburuk
    )
