"""Hitung skor SEPI tiap stasiun KRL, lalu simpan peringkatnya.

Alurnya mengikuti proposal: matriks keputusan dari isi isochrone, bobot dari
entropy dipadu AHP, peringkat lewat TOPSIS.

Pakai:
    python -m scripts.compute_sepi              # pita 10 menit
    python -m scripts.compute_sepi --minutes 15
    python -m scripts.compute_sepi --dry-run    # tampilkan saja, jangan simpan
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import yaml

from app.core.database import SessionLocal
from app.models.score import StationScore
from app.services.scoring import (
    CRITERIA,
    AHPTidakKonsisten,
    bobot_ahp,
    bobot_entropy,
    build_matrix,
    gabung_bobot,
    topsis,
)
from app.services.scoring.weights import AMBANG_CR
from scripts.check_ahp import gabung_geometrik, susun_matriks

# ahp_sepi.yml, bukan ahp.yml. Yang kedua warisan branch main dan angkanya
# ditandai sendiri sebagai sementara; yang pertama diisi dari riset literatur
# N9 dan mencantumkan asal-usul tiap pasangan.
AHP_PATH = Path(__file__).resolve().parents[1] / "data" / "ahp_sepi.yml"


def load_ahp() -> tuple[np.ndarray, float, float]:
    """Bobot AHP dari ahp_sepi.yml, digabung antar penilai secara geometrik."""
    config = yaml.safe_load(AHP_PATH.read_text(encoding="utf-8")) or {}

    matriks = []
    for penilai in config.get("penilai") or []:
        perbandingan = penilai.get("perbandingan") or {}
        if any(v is None for v in perbandingan.values()):
            continue
        matriks.append(susun_matriks(perbandingan))

    if not matriks:
        raise AHPTidakKonsisten(
            "belum ada penilai yang lengkap di data/ahp_sepi.yml. "
            "Jalankan: python -m scripts.check_ahp"
        )

    bobot, cr = bobot_ahp(gabung_geometrik(matriks))
    return bobot, cr, float(config.get("lambda_entropy", 0.5))


def _atau_none(v: float) -> float | None:
    """NaN disimpan sebagai NULL, bukan NaN: NaN bukan JSON yang sah."""
    return None if v != v else v


def _angka(v: float) -> str:
    """Tampilkan '-' untuk variabel yang belum terukur, bukan 'nan'."""
    return "-" if v != v else f"{v:.2f}"


def save_scores(rows: list[dict], minutes: int) -> None:
    session = SessionLocal()
    try:
        session.query(StationScore).filter(StationScore.minutes == minutes).delete()
        for row in rows:
            session.add(StationScore(**row))
        session.commit()
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=int, default=10, choices=(5, 10, 15))
    parser.add_argument("--dry-run", action="store_true", help="jangan simpan ke database")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        details, matrix = build_matrix(session, args.minutes)
    finally:
        session.close()

    x = np.asarray(matrix, dtype=float)

    # Kolom yang seluruhnya NaN belum diukur sama sekali (E dan C menunggu
    # survey Activity, blocker N1). Entropi tidak terdefinisi di kolom kosong,
    # jadi kolomnya diberi bobot entropi 0 dan sisanya dinormalkan ulang.
    # Diberi 0 BUKAN berarti tidak penting - bobot AHP-nya tetap utuh; artinya
    # "data ini tidak menyumbang informasi sebaran", yang memang benar.
    ada_isi = ~np.all(np.isnan(x), axis=0)
    w_entropy = np.zeros(x.shape[1])
    if ada_isi.any():
        w_entropy[ada_isi] = bobot_entropy(x[:, ada_isi])

    w_ahp, ratio, lambda_entropy = load_ahp()

    if ratio >= AMBANG_CR:
        print(f"! consistency ratio AHP {ratio:.3f}, harus di bawah {AMBANG_CR}")
        print("  perbandingan berpasangan di data/ahp_sepi.yml saling bertentangan.")
        return 1

    weights = gabung_bobot(w_entropy, w_ahp, lambda_entropy)
    hasil = topsis(x, weights)
    scores = hasil.kedekatan

    print(f"pita {args.minutes} menit, {len(details)} stasiun")
    print(f"consistency ratio AHP {ratio:.3f} (batas {AMBANG_CR})")
    print(f"lambda entropy {lambda_entropy}\n")
    print(f"{'':10}" + "".join(f"{c:>10}" for c in CRITERIA))
    for label, values in (
        ("entropy", w_entropy),
        ("ahp", w_ahp),
        ("gabungan", weights),
    ):
        print(f"{label:10}" + "".join(f"{v:10.3f}" for v in values))

    ranked = sorted(zip(details, scores), key=lambda pair: -pair[1])

    print(f"\n{'#':>3}  {'STASIUN':24}{'SEPI':>7}{'T':>7}{'E':>6}{'A':>7}{'U':>6}{'C':>6}")
    for position, (detail, score) in enumerate(ranked, start=1):
        if position > 10 and position <= len(ranked) - 5:
            if position == 11:
                print("     ...")
            continue
        print(
            f"{position:3}  {detail['name'][:24]:24}{score * 100:7.1f}"
            f"{detail['raw_t']:7.2f}{_angka(detail['raw_e']):>6}"
            f"{detail['raw_a']:7.2f}{detail['raw_u']:6.2f}{_angka(detail['raw_c']):>6}"
        )

    if args.dry_run:
        print("\n(dry run, tidak disimpan)")
        return 0

    rows = [
        {
            "station_id": detail["id"],
            "minutes": args.minutes,
            "sepi": round(score * 100, 2),
            "rank": position,
            "raw_t": detail["raw_t"],
            "raw_e": _atau_none(detail["raw_e"]),
            "raw_a": detail["raw_a"],
            "raw_u": detail["raw_u"],
            "raw_c": _atau_none(detail["raw_c"]),
            "line_count": detail["line_count"],
            # moda_jalan menggantikan halte_count, moda_rel menggantikan
            # other_mode_count: keduanya kini datang dari hitung_transportasi,
            # yang memakai koreksi F3-0b (halte bus dan TransJakarta ikut
            # terhitung, bukan cuma stasiun rel lain).
            "halte_count": detail["moda_jalan"],
            "other_mode_count": detail["moda_rel"],
            "area_km2": detail["area_km2"],
        }
        for position, (detail, score) in enumerate(ranked, start=1)
    ]

    save_scores(rows, args.minutes)
    print(f"\n{len(rows)} skor tersimpan untuk pita {args.minutes} menit")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AHPTidakKonsisten, ValueError) as exc:
        print(f"! {exc}")
        sys.exit(1)
