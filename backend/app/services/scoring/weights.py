"""Pembobotan variabel SEPI lewat dua jalur, lalu digabung.

PRD hal. 13: "Bobot tiap variabel diperoleh melalui dua jalur, yaitu Entropy
Weighting dari variabilitas data aktual dan AHP dari penilaian ahli dengan
syarat rasio konsistensi di bawah 0,10. Keduanya digabung dengan formulasi
w = lambda*w(entropy) + (1 - lambda)*w(AHP)."

KENAPA HARUS DUA JALUR
----------------------
Keduanya punya titik buta yang berlawanan, dan itulah alasan digabung:

  Entropy  membaca "apa yang benar-benar bervariasi di data ini". Buta terhadap
           makna. Kalau seluruh stasiun DKI kebetulan punya Permeability Index
           mirip, variabel Aksesibilitas akan diberi bobot NOL — padahal
           seluruh argumen PRD berdiri di atas pentingnya isochrone.

  AHP      membaca "apa yang menurut ahli penting". Buta terhadap data. Bisa
           memberi bobot besar pada variabel yang di wilayah studi ini
           ternyata tidak membedakan apa pun.

Menggabungkan keduanya bukan basa-basi metodologis — itu menambal dua kegagalan
yang arahnya berlawanan.
"""

import numpy as np

# Indeks Random Saaty: CI rata-rata matriks perbandingan berpasangan yang diisi
# ACAK, per ukuran matriks. Dipakai sebagai pembanding, sehingga CR menjawab
# "seberapa tidak konsisten dibanding orang yang menjawab asal", bukan
# "seberapa tidak konsisten" dalam ukuran mutlak yang tak punya acuan.
RANDOM_INDEX = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}

# Ambang PRD. Di atas ini, penilaian ahli dianggap terlalu saling bertentangan
# untuk dipakai, dan matriksnya harus diperbaiki — bukan hasilnya dipaksakan.
AMBANG_CR = 0.10


class AHPTidakKonsisten(ValueError):
    """Matriks perbandingan berpasangan gagal syarat CR < 0,10."""


def bobot_entropy(matriks: np.ndarray) -> np.ndarray:
    """Bobot dari variabilitas data.

        p_ij = x_ij / sum_i x_ij           proporsi kolom j di alternatif i
        e_j  = -(1/ln m) sum_i p_ij ln p_ij      entropi kolom, 0..1
        d_j  = 1 - e_j                     derajat divergensi
        w_j  = d_j / sum_j d_j             bobot ternormalisasi

    PERHATIKAN ARAHNYA — ini kebalikan dari entropi Shannon pada keberagaman
    fungsi lahan, walau rumusnya sama persis. Di sana indeksnya berjalan atas
    KATEGORI dalam satu stasiun dan entropi tinggi berarti beragam (bagus).
    Di sini indeksnya berjalan atas STASIUN dalam satu kriteria, dan entropi
    tinggi berarti semua stasiun bernilai mirip — kriteria itu tidak membantu
    membedakan apa pun, jadi bobotnya kecil.

    Periksa kasus batasnya:
      semua stasiun sama  -> p seragam -> e = 1 -> d = 0 -> bobot NOL
      satu mendominasi    -> e -> 0    -> d = 1 -> bobot maksimum
    """
    x = np.asarray(matriks, dtype=float)
    m, n = x.shape
    if m < 2:
        raise ValueError("entropy weighting butuh minimal dua alternatif")

    d = np.zeros(n)
    for j in range(n):
        kolom = x[:, j]
        ada = kolom[~np.isnan(kolom)]
        # Kolom kosong atau berjumlah nol tidak membawa informasi apa pun.
        if ada.size < 2 or ada.sum() <= 0:
            d[j] = 0.0
            continue

        p = ada / ada.sum()
        # Konvensi lim(p->0) p ln p = 0. Tanpa penyaringan ini, ln(0) menjadi
        # -inf dan seluruh perhitungan berubah jadi NaN.
        p = p[p > 0]
        e = -np.sum(p * np.log(p)) / np.log(ada.size)

        # PENSKALAAN CAKUPAN — tanpa ini bobot entropi antar-kolom tidak
        # sebanding, dan akibatnya parah.
        #
        # Entropi di atas dinormalkan dengan ln(jumlah pengamatan KOLOM ITU),
        # bukan ln(jumlah stasiun). Kolom berisi 2 pengamatan karena itu diukur
        # pada skala yang sama sekali berbeda dari kolom berisi 45, dan hampir
        # selalu tampak lebih "membedakan".
        #
        # Terjadi sungguhan 12 Sep: variabel C baru terisi di 2 dari 45 stasiun,
        # dan bobot entropinya melonjak ke 0,776 sementara bobot T runtuh dari
        # 0,380 ke 0,148. Satu variabel yang hampir kosong mengambil alih
        # seluruh skor.
        #
        # Alasan penskalaannya lugas: kriteria yang hanya teramati di 2 dari 45
        # stasiun TIDAK BISA memisahkan 43 sisanya. Daya bedanya terhadap
        # himpunan penuh paling banter sebesar cakupannya.
        cakupan = ada.size / m
        d[j] = (1.0 - e) * cakupan

    total = d.sum()
    if total <= 0:
        # Semua kriteria seragam. Tidak ada dasar membedakan bobot, jadi rata.
        return np.full(n, 1.0 / n)
    return d / total


def bobot_ahp(perbandingan: np.ndarray, paksa: bool = False) -> tuple[np.ndarray, float]:
    """Bobot dari matriks perbandingan berpasangan ahli, plus rasio konsistensi.

    Kalau penilaiannya konsisten sempurna, ada vektor bobot w dengan
    a_ij = w_i/w_j, sehingga A = w (1/w)^T berperingkat 1 dan nilai eigennya
    (n, 0, ..., 0). Vektor eigen utamanya tepat w. Penilaian manusia tidak
    pernah sekonsisten itu, jadi A adalah perturbasi matriks peringkat-1 —
    Perron-Frobenius menjamin masih ada lambda_max real positif tunggal.

        CI = (lambda_max - n) / (n - 1)
        CR = CI / RI(n)

    Asal CI: karena diagonal A semuanya 1, tr(A) = n = jumlah seluruh nilai
    eigen. Maka rata-rata nilai eigen non-utama = (n - lambda_max)/(n - 1),
    yaitu -CI. Jadi CI adalah negatif rata-rata nilai eigen non-utama — ukuran
    seberapa banyak "massa" yang bocor keluar dari struktur peringkat-1.

    Mengembalikan (bobot, CR). Melempar AHPTidakKonsisten kalau CR >= 0,10,
    kecuali `paksa` dinyalakan — dan itu hanya untuk keperluan uji, tidak boleh
    dipakai di jalur produksi.
    """
    a = np.asarray(perbandingan, dtype=float)
    n = a.shape[0]
    if a.shape != (n, n):
        raise ValueError("matriks perbandingan harus persegi")
    if np.any(a <= 0):
        raise ValueError("seluruh entri matriks perbandingan harus positif")

    nilai_eigen, vektor_eigen = np.linalg.eig(a)
    utama = int(np.argmax(nilai_eigen.real))
    lambda_max = float(nilai_eigen[utama].real)

    w = np.abs(vektor_eigen[:, utama].real)
    w = w / w.sum()

    if n <= 2:
        # Matriks 1x1 dan 2x2 selalu konsisten; CI-nya nol menurut definisi.
        return w, 0.0

    ci = (lambda_max - n) / (n - 1)
    ri = RANDOM_INDEX.get(n)
    if ri is None or ri == 0:
        return w, 0.0

    cr = ci / ri
    if cr >= AMBANG_CR and not paksa:
        raise AHPTidakKonsisten(
            f"CR = {cr:.4f} >= {AMBANG_CR}. Penilaian ahli terlalu saling "
            f"bertentangan; perbaiki matriksnya, jangan paksakan hasilnya."
        )
    return w, cr


def gabung_bobot(
    w_entropy: np.ndarray, w_ahp: np.ndarray, lam: float = 0.5
) -> np.ndarray:
    """w = lambda*w_entropy + (1 - lambda)*w_ahp.

    lam = 1 sepenuhnya percaya data, lam = 0 sepenuhnya percaya ahli. PRD tidak
    menetapkan nilainya; 0,5 dipakai sebagai titik netral dan HARUS disebutkan
    sebagai pilihan tim, bukan disamarkan sebagai ketentuan.
    """
    if not 0.0 <= lam <= 1.0:
        raise ValueError("lambda harus di antara 0 dan 1")
    w = lam * np.asarray(w_entropy) + (1 - lam) * np.asarray(w_ahp)
    return w / w.sum()
