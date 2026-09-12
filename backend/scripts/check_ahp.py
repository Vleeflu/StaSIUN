"""Baca matriks AHP dari data/ahp_sepi.yml, hitung bobotnya, periksa CR.

Dijalankan setelah data/ahp_sepi.yml diisi. Tidak menyentuh database sama
sekali — murni memeriksa apakah penilaian ahli cukup konsisten untuk dipakai.

    python -m scripts.check_ahp
"""

import sys
from pathlib import Path

import numpy as np
import yaml

from app.services.scoring.sepi import NAMA_VARIABEL, VARIABEL
from app.services.scoring.weights import AMBANG_CR, RANDOM_INDEX, bobot_ahp

BERKAS = Path(__file__).resolve().parents[1] / "data" / "ahp_sepi.yml"


def susun_matriks(perbandingan: dict) -> np.ndarray:
    """Bangun matriks 5x5 penuh dari 10 perbandingan yang diisi manusia.

    Diagonalnya 1 dan separuh bawahnya kebalikan separuh atas — keduanya
    dihitung, tidak diminta ke pengisi. Meminta manusia menulis a_ij dan a_ji
    sekaligus membuka peluang keduanya saling bertentangan, dan pertentangan
    semacam itu bukan ketidakkonsistenan yang bermakna, cuma salah ketik.
    """
    n = len(VARIABEL)
    a = np.ones((n, n))
    for i, vi in enumerate(VARIABEL):
        for j, vj in enumerate(VARIABEL):
            if i >= j:
                continue
            kunci = f"{vi}_vs_{vj}"
            if kunci not in perbandingan:
                raise KeyError(f"perbandingan {kunci} tidak ada di berkas")
            nilai = perbandingan[kunci]
            if nilai is None:
                raise ValueError(f"perbandingan {kunci} masih kosong (null)")
            nilai = float(nilai)
            if nilai <= 0:
                raise ValueError(f"perbandingan {kunci} harus positif, diberi {nilai}")
            a[i, j] = nilai
            a[j, i] = 1.0 / nilai
    return a


def gabung_geometrik(matriks: list[np.ndarray]) -> np.ndarray:
    """Gabungkan matriks beberapa penilai dengan rata-rata geometrik.

    Cara baku AHP untuk banyak penilai (Aggregation of Individual Judgements),
    dan pilihannya matematis, bukan selera: rata-rata geometrik MEMPERTAHANKAN
    sifat resiprokal matriks, rata-rata aritmetik merusaknya.

    Kalau penilai A menjawab 3 dan penilai B menjawab 1/3:
        geometrik : sqrt(3 x 1/3) = 1      -> memang seimbang
        aritmetik : (3 + 1/3)/2  = 1,67    -> condong ke A tanpa alasan

    Dan karena 1/sqrt(a*b) = sqrt(1/a x 1/b), entri kebalikannya otomatis
    tetap konsisten dengan entri aslinya.
    """
    return np.exp(np.mean(np.log(np.stack(matriks)), axis=0))


def main() -> int:
    if not BERKAS.exists():
        print(f"Berkas tidak ditemukan: {BERKAS}")
        return 1

    isi = yaml.safe_load(BERKAS.read_text(encoding="utf-8")) or {}
    daftar = isi.get("penilai") or []
    if isinstance(daftar, dict):  # bentuk lama: satu penilai, tanpa daftar
        daftar = [daftar]
    if not daftar:
        print("Belum ada satu pun penilai di berkas.")
        return 1

    matriks, terisi = [], []
    for nomor, p in enumerate(daftar, start=1):
        try:
            matriks.append(susun_matriks((p or {}).get("perbandingan") or {}))
            terisi.append(p or {})
        except (KeyError, ValueError) as exc:
            nama = (p or {}).get("nama") or f"penilai #{nomor}"
            print(f"Penilai {nama!r} dilewati: {exc}")

    if not matriks:
        print(f"\nBelum ada penilai yang lengkap. Isi dulu {BERKAS.name}.")
        return 1

    print(f"{len(matriks)} penilai terpakai:")
    for p in terisi:
        print(f"  - {p.get('nama') or '(nama belum diisi)'} | "
              f"{p.get('peran') or '(peran belum diisi)'} | {p.get('tanggal') or '-'}")

    if len(matriks) > 1:
        print("\nDigabung dengan rata-rata geometrik (cara baku AHP untuk banyak penilai).")
    a = gabung_geometrik(matriks)

    print("\nMatriks perbandingan berpasangan:")
    print("       " + "".join(f"{v:>8s}" for v in VARIABEL))
    for i, v in enumerate(VARIABEL):
        print(f"  {v:4s} " + "".join(f"{a[i, j]:8.3f}" for j in range(len(VARIABEL))))

    # paksa=True supaya CR tetap dilaporkan walau gagal — pengisi perlu tahu
    # SEBERAPA jauh melesetnya untuk bisa memperbaiki, bukan cuma tahu gagal.
    w, cr = bobot_ahp(a, paksa=True)

    print("\nBobot hasil vektor eigen utama:")
    for v, bobot in sorted(zip(VARIABEL, w), key=lambda x: -x[1]):
        bar = "#" * int(round(bobot * 50))
        print(f"  {v}  {NAMA_VARIABEL[v]:14s} {bobot:6.4f}  {bar}")
    print(f"  {'':19s} {w.sum():6.4f}  (jumlah, harus 1)")

    n = len(VARIABEL)
    ri = RANDOM_INDEX[n]
    ci = cr * ri
    print(f"\nKonsistensi:")
    print(f"  CI = {ci:.4f}   (lambda_max - n)/(n - 1)")
    print(f"  RI = {ri:.4f}   indeks acak Saaty untuk n = {n}")
    print(f"  CR = {ci:.4f} / {ri:.4f} = {cr:.4f}")

    if cr < AMBANG_CR:
        print(f"\n  LOLOS. CR = {cr:.4f} < {AMBANG_CR}. Bobot ini boleh dipakai.")
        return 0

    print(f"\n  GAGAL. CR = {cr:.4f} >= {AMBANG_CR}.")
    print("  Artinya jawaban-jawabannya saling bertentangan — misalnya T jauh lebih")
    print("  penting dari E, E jauh lebih penting dari A, tetapi A malah dinilai")
    print("  lebih penting dari T. Perbaiki jawabannya, jangan dipaksakan lewat:")
    print("  bobot dari matriks tidak konsisten tidak berarti apa-apa.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
