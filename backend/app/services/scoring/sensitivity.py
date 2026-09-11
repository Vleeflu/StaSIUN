"""Analisis sensitivitas peringkat SEPI terhadap pilihan pembobotan (B22).

MASALAH YANG DIJAWAB
--------------------
PRD mengunci RUMUS pembobotan (entropy dipadu AHP, hal. 13), tetapi tidak
mengunci beberapa pilihan di dalamnya: berapa lambda, dan dari nilai mana
entropi dihitung. Pada 12 Sep terbukti bahwa mengganti SATU pilihan itu -
entropi dari hasil ukur atau dari nilai hasil shrinkage - menjungkirbalikkan
10 besar (ADJUSTMENT 9.28).

Menyajikan satu peringkat seolah satu-satunya jawaban dalam keadaan itu tidak
jujur. Memilih skema yang "terlihat benar" lalu menyajikannya adalah tuning ke
hasil. Yang jujur adalah menunjukkan SEBERAPA KOKOH tiap peringkat terhadap
pilihan-pilihan yang sama-sama sah.

DASAR METODE
------------
OECD & JRC (2008), *Handbook on Constructing Composite Indicators: Methodology
and User Guide*, langkah 7 "Uncertainty and sensitivity analysis": indeks
komposit wajib diuji terhadap pilihan pembobotan, dan hasilnya dilaporkan
sebagai rentang peringkat, bukan peringkat tunggal. Riset literatur N9 tim
sendiri merekomendasikan hal yang sama (rekomendasi 4).

DUA LAPIS UJI
-------------
1. Skema deterministik - pilihan diskret yang masing-masing bisa dibela:

     resmi            lambda dari ahp_sepi.yml, entropi dari nilai shrinkage
     ahp_murni        lambda = 0, sepenuhnya penilaian ahli
     entropi_murni    lambda = 1, sepenuhnya sebaran data
     entropi_terukur  lambda resmi, entropi dari hasil ukur (versi sebelum 9.28)
     bobot_rata       0,2 untuk tiap variabel - pembanding "tanpa asumsi"

2. Monte Carlo - pilihan kontinu:
     lambda ~ Uniform(0, 1)            PRD tidak menetapkan lambda
     bobot AHP x Uniform(0,75; 1,25)   ketidakpastian penilaian ahli +-25%,
                                       lalu dinormalisasi ulang

   Rentang +-25% adalah PILIHAN KAMI, bukan angka dari PRD atau literatur.
   Ia dicatat supaya bisa digugat, dan bisa diganti lewat parameter.

YANG TIDAK DIUBAH
-----------------
Matriks, shrinkage, penalti sentimen, dan batas 15% modifier teks tetap sama
di semua skema. Yang diuji HANYA pembobotan - satu sumber ketidakpastian
dalam satu waktu, supaya penyebab lompatan peringkat bisa ditunjuk.

Modul ini tidak menyentuh database, sama seperti modul skor lainnya.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.services.scoring.sepi import hitung_sepi
from app.services.scoring.weights import bobot_entropy, gabung_bobot

N_BESAR = 10
JUMLAH_UNDIAN = 1000
RENTANG_AHP = 0.25
BENIH = 42


@dataclass
class Skema:
    nama: str
    keterangan: str
    bobot: np.ndarray


@dataclass
class HasilSensitivitas:
    skema: list[Skema]
    # station_id -> ringkasan, siap disimpan sebagai JSONB
    per_stasiun: dict[int, dict] = field(default_factory=dict)
    # stasiun yang masuk N besar di SEMUA skema deterministik, urut peringkat resmi
    kokoh: list[int] = field(default_factory=list)


def _entropi_aman(x: np.ndarray) -> np.ndarray:
    """Bobot entropi; kolom yang seluruhnya NaN mendapat 0 (lihat compute_sepi)."""
    ada = ~np.all(np.isnan(x), axis=0)
    w = np.zeros(x.shape[1])
    if ada.any():
        w[ada] = bobot_entropy(x[:, ada])
    return w


def _peringkat(nilai: list[float]) -> np.ndarray:
    """Peringkat 1 = tertinggi. Seri dipecah stabil menurut urutan masukan."""
    urut = np.argsort(-np.asarray(nilai), kind="stable")
    r = np.empty(len(nilai), dtype=int)
    r[urut] = np.arange(1, len(nilai) + 1)
    return r


def susun_skema(
    x_susut: np.ndarray, x_ukur: np.ndarray, w_ahp: np.ndarray, lam: float
) -> list[Skema]:
    k = x_susut.shape[1]
    w_ent_susut = _entropi_aman(x_susut)
    w_ent_ukur = _entropi_aman(x_ukur)
    return [
        Skema("resmi", f"lambda {lam}, entropi dari nilai hasil shrinkage",
              gabung_bobot(w_ent_susut, w_ahp, lam)),
        Skema("ahp_murni", "lambda 0, sepenuhnya penilaian ahli (AHP)",
              gabung_bobot(w_ent_susut, w_ahp, 0.0)),
        Skema("entropi_murni", "lambda 1, sepenuhnya sebaran data",
              gabung_bobot(w_ent_susut, w_ahp, 1.0)),
        Skema("entropi_terukur", f"lambda {lam}, entropi dari hasil ukur",
              gabung_bobot(w_ent_ukur, w_ahp, lam)),
        Skema("bobot_rata", "bobot sama rata untuk kelima variabel",
              np.full(k, 1.0 / k)),
    ]


def analisis(
    station_ids: list[int],
    station_names: list[str],
    x_susut: np.ndarray,
    x_ukur: np.ndarray,
    terukur: np.ndarray,
    penalti: list[float],
    w_ahp: np.ndarray,
    lam: float,
    batas_modifier: float,
    n_besar: int = N_BESAR,
    jumlah_undian: int = JUMLAH_UNDIAN,
    rentang_ahp: float = RENTANG_AHP,
    benih: int = BENIH,
) -> HasilSensitivitas:
    def skor(bobot: np.ndarray):
        return hitung_sepi(
            station_ids, station_names, x_susut, bobot,
            terukur=terukur, penalti=penalti, batas_modifier=batas_modifier,
        )

    skema = susun_skema(x_susut, x_ukur, w_ahp, lam)
    n = len(station_ids)

    peringkat_skema: dict[str, np.ndarray] = {}
    kelas_skema: dict[str, list[str]] = {}
    nilai_skema: dict[str, list[float]] = {}
    for s in skema:
        hasil = skor(s.bobot)
        nilai = [h.nilai for h in hasil]
        peringkat_skema[s.nama] = _peringkat(nilai)
        kelas_skema[s.nama] = [h.kelas for h in hasil]
        nilai_skema[s.nama] = nilai

    rng = np.random.default_rng(benih)
    w_ent_susut = _entropi_aman(x_susut)
    mc = np.empty((jumlah_undian, n), dtype=int)
    for u in range(jumlah_undian):
        lam_u = rng.uniform(0.0, 1.0)
        ahp_u = w_ahp * rng.uniform(1 - rentang_ahp, 1 + rentang_ahp, size=w_ahp.size)
        ahp_u = ahp_u / ahp_u.sum()
        mc[u] = _peringkat([h.nilai for h in skor(gabung_bobot(w_ent_susut, ahp_u, lam_u))])

    hasil = HasilSensitivitas(skema=skema)
    deterministik = np.vstack([peringkat_skema[s.nama] for s in skema])
    for i, sid in enumerate(station_ids):
        kolom = deterministik[:, i]
        resmi_kelas = kelas_skema["resmi"][i]
        hasil.per_stasiun[sid] = {
            "peringkat_resmi": int(peringkat_skema["resmi"][i]),
            "peringkat_per_skema": {s.nama: int(peringkat_skema[s.nama][i]) for s in skema},
            "sepi_per_skema": {s.nama: round(float(nilai_skema[s.nama][i]), 1) for s in skema},
            "kelas_per_skema": {s.nama: kelas_skema[s.nama][i] for s in skema},
            "peringkat_min": int(kolom.min()),
            "peringkat_maks": int(kolom.max()),
            "kelas_sama_di": int(sum(k[i] == resmi_kelas for k in kelas_skema.values())),
            "jumlah_skema": len(skema),
            "mc_p05": int(np.percentile(mc[:, i], 5)),
            "mc_median": int(np.median(mc[:, i])),
            "mc_p95": int(np.percentile(mc[:, i], 95)),
            "peluang_n_besar": round(float(np.mean(mc[:, i] <= n_besar)), 3),
            "n_besar": n_besar,
            "kokoh_n_besar": bool(kolom.max() <= n_besar),
            "jumlah_undian": jumlah_undian,
        }

    hasil.kokoh = sorted(
        (sid for sid in station_ids if hasil.per_stasiun[sid]["kokoh_n_besar"]),
        key=lambda sid: hasil.per_stasiun[sid]["peringkat_resmi"],
    )
    return hasil
