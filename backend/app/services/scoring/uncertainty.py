"""Penanganan ketidakpastian: confidence interval BCa dan shrinkage estimator.

PRD hal. 13: "Confidence Interval dihitung menggunakan bootstrap resampling
metode BCa yang tidak mengasumsikan distribusi normal dan tetap valid untuk
sampel kecil maupun besar."

KENAPA BUKAN INTERVAL NORMAL BIASA
-----------------------------------
Interval baku `theta +/- 1,96 * SE` mengandaikan sampling distribution
(sebaran nilai estimasi kalau pengambilan sampel diulang berkali-kali)
berbentuk normal dan simetris. Data kita melanggar keduanya: cacahan titik
minat menceng ke kanan, dan skala ordinal 1-5 dari narasumber terbatas di dua
ujungnya sehingga tidak mungkin simetris di dekat batas. Dengan n kecil per
zona, interval normal bisa memberi batas bawah negatif untuk besaran yang
mustahil negatif.

APA YANG DIKOREKSI BCa
-----------------------
Percentile bootstrap polos hanya mengambil kuantil dari sebaran replikasi.
BCa menambahkan dua koreksi:

    z0  bias-correction. Membaca berapa proporsi replikasi yang jatuh di bawah
        estimasi asli. Kalau tepat separuh, z0 = 0 dan tidak ada koreksi.
    a   acceleration. Mengoreksi skewness (kemencengan) — keadaan saat ragam
        estimasi ikut berubah mengikuti nilainya sendiri. Diperkirakan lewat
        jackknife (hitung ulang estimasi sambil membuang satu pengamatan).

Kalau z0 = 0 DAN a = 0, seluruh rumusnya runtuh kembali menjadi percentile
biasa. Jadi BCa perumuman ketat dari percentile, bukan metode saingan.

Dipakai scipy.stats.bootstrap dengan method="BCa" — implementasi yang sudah
teruji luas — dibungkus penanganan kasus tepi yang khas data kita: n sangat
kecil, dan sampel yang seluruh nilainya sama.
"""

from dataclasses import dataclass

import numpy as np
from scipy import stats

# Di bawah ini jackknife tidak bisa dihitung (butuh minimal dua pengamatan
# tersisa setelah satu dibuang), jadi BCa tidak terdefinisi.
MIN_SAMPEL_BCA = 3


@dataclass
class Interval:
    estimasi: float
    ci_low: float | None
    ci_high: float | None
    n_sample: int
    metode: str  # "BCa", "rentang", atau "tunggal"

    @property
    def lebar(self) -> float | None:
        if self.ci_low is None or self.ci_high is None:
            return None
        return self.ci_high - self.ci_low


def interval_bca(
    sampel, statistik=np.mean, keyakinan: float = 0.95, n_resample: int = 9999, seed: int = 42
) -> Interval:
    """Confidence interval BCa untuk sebuah statistik.

    `seed` dipatok supaya hasilnya dapat direproduksi. Bootstrap itu acak, dan
    angka yang berubah-ubah tiap kali dijalankan mustahil diaudit — sesuatu
    yang tidak bisa ditawar untuk angka yang akan ditampilkan ke pengguna.

    Kasus tepi dikembalikan apa adanya, bukan dipaksa menghasilkan interval:

        n = 0   tidak ada estimasi sama sekali
        n = 1   estimasi ada, interval tidak. Satu pengamatan tidak mengandung
                informasi apa pun tentang sebarannya
        n = 2   interval diisi rentang min-max, ditandai metode "rentang"
                supaya jelas itu BUKAN interval statistik
        semua nilai sama  ragamnya nol, jadi intervalnya titik itu sendiri
    """
    x = np.asarray([v for v in np.asarray(sampel, dtype=float) if not np.isnan(v)])
    n = x.size

    if n == 0:
        return Interval(float("nan"), None, None, 0, "kosong")
    if n == 1:
        return Interval(float(statistik(x)), None, None, 1, "tunggal")

    est = float(statistik(x))

    # Seluruh nilai identik: tidak ada ragam untuk di-resample. scipy akan
    # melempar peringatan degenerate; jawabannya memang titik itu sendiri.
    if np.allclose(x, x[0]):
        return Interval(est, est, est, n, "konstan")

    if n < MIN_SAMPEL_BCA:
        return Interval(est, float(x.min()), float(x.max()), n, "rentang")

    try:
        hasil = stats.bootstrap(
            (x,),
            statistik,
            confidence_level=keyakinan,
            n_resamples=n_resample,
            method="BCa",
            random_state=np.random.default_rng(seed),
        )
        lo = float(hasil.confidence_interval.low)
        hi = float(hasil.confidence_interval.high)
        # Sampel yang sangat kecil kadang membuat koreksi akselerasi meledak
        # dan menghasilkan batas tak hingga. Itu bukan interval yang sah.
        if not (np.isfinite(lo) and np.isfinite(hi)):
            return Interval(est, float(x.min()), float(x.max()), n, "rentang")
        return Interval(est, lo, hi, n, "BCa")
    except Exception:
        # Jangan pernah menjatuhkan seluruh perhitungan skor karena satu zona
        # yang sebarannya aneh. Turunkan ke rentang, dan tandai metodenya.
        return Interval(est, float(x.min()), float(x.max()), n, "rentang")


def shrinkage(
    nilai_zona: float, nilai_grup: float, n: int, k: float
) -> tuple[float, float]:
    """Tarik estimasi bersampel kecil ke arah rata-rata kelompok pembandingnya.

        theta_topi = w * theta_zona + (1 - w) * theta_grup,   w = n / (n + k)

    Bentuk ini bukan rumus sembarangan — dia rata-rata posterior model
    normal-normal:

        x_bar | theta ~ N(theta, sigma^2 / n)      sigma^2 = ragam DALAM zona
        theta         ~ N(mu, tau^2)               tau^2   = ragam ANTAR zona

        rata-rata posterior = x_bar * n/(n + sigma^2/tau^2) + mu * ...

    Membandingkannya dengan bentuk PRD memberi arti pada k:

        k = sigma^2 / tau^2

    Jadi k BUKAN konstanta yang perlu ditebak — dia rasio ragam dalam-zona
    terhadap ragam antar-zona, dan bisa diestimasi dari data lewat
    `estimasi_k()` di bawah. Tafsirannya: pada n = k, zona dipercaya sama
    besar dengan kelompoknya.

    Mengembalikan (nilai setelah shrinkage, bobot w).
    """
    if k < 0:
        raise ValueError("k tidak boleh negatif")
    if n < 0:
        raise ValueError("n tidak boleh negatif")
    w = n / (n + k) if (n + k) > 0 else 0.0
    return w * nilai_zona + (1 - w) * nilai_grup, w


def estimasi_k(kelompok: list[np.ndarray]) -> float:
    """Estimasi k = sigma^2 / tau^2 dari data, lewat metode momen.

    sigma^2 diperkirakan dari ragam DI DALAM tiap zona, digabung (pooled).
    tau^2 diperkirakan dari ragam rata-rata ANTAR zona, dikurangi bagian yang
    memang berasal dari kesalahan pengambilan sampel.

    `kelompok` adalah daftar array, satu array per zona.

    Kalau tau^2 hasil estimasinya nol atau negatif — mungkin terjadi saat
    perbedaan antar-zona lebih kecil daripada derau samplingnya — artinya
    tidak ada bukti zona-zona itu benar-benar berbeda. Yang dikembalikan
    k tak hingga, yang membuat w = 0: seluruh estimasi jatuh ke rata-rata
    kelompok. Itu kesimpulan yang benar, bukan kegagalan.
    """
    bersih = [np.asarray(g, dtype=float) for g in kelompok]
    bersih = [g[~np.isnan(g)] for g in bersih]
    bersih = [g for g in bersih if g.size >= 2]

    if len(bersih) < 2:
        return float("inf")

    # sigma^2: ragam dalam-zona, digabung dengan bobot derajat kebebasan.
    db = sum(g.size - 1 for g in bersih)
    sigma2 = sum(np.var(g, ddof=1) * (g.size - 1) for g in bersih) / db

    rata = np.array([g.mean() for g in bersih])
    n_rata = np.mean([g.size for g in bersih])

    # Ragam rata-rata zona memuat dua hal sekaligus: perbedaan zona yang
    # sesungguhnya (tau^2) DAN derau sampling (sigma^2/n). Yang kedua dibuang.
    tau2 = np.var(rata, ddof=1) - sigma2 / n_rata

    if tau2 <= 0:
        return float("inf")
    return float(sigma2 / tau2)
