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

import yaml

from app.core.database import SessionLocal
from app.models.score import StationScore
from app.services.scoring import (
    CRITERIA,
    AhpError,
    ahp_weights,
    build_matrix,
    combine_weights,
    entropy_weights,
    topsis,
)
from app.services.scoring.weights import MAX_CONSISTENCY_RATIO

AHP_PATH = Path(__file__).resolve().parents[1] / "data" / "ahp.yml"


def load_ahp() -> tuple[list[float], float, float]:
    config = yaml.safe_load(AHP_PATH.read_text(encoding="utf-8")) or {}
    order = config.get("order") or []

    if order != CRITERIA:
        raise AhpError(
            f"urutan di ahp.yml {order} tidak sama dengan urutan kriteria {CRITERIA}"
        )

    weights, ratio = ahp_weights(config.get("pairwise") or {}, order)
    return weights, ratio, float(config.get("lambda_entropy", 0.5))


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

    w_entropy = entropy_weights(matrix)
    w_ahp, ratio, lambda_entropy = load_ahp()

    if ratio >= MAX_CONSISTENCY_RATIO:
        print(f"! consistency ratio AHP {ratio:.3f}, harus di bawah {MAX_CONSISTENCY_RATIO}")
        print("  perbandingan berpasangan di data/ahp.yml saling bertentangan.")
        return 1

    weights = combine_weights(w_entropy, w_ahp, lambda_entropy)
    scores = topsis(matrix, weights)

    print(f"pita {args.minutes} menit, {len(details)} stasiun")
    print(f"consistency ratio AHP {ratio:.3f} (batas {MAX_CONSISTENCY_RATIO})")
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
            f"{detail['raw_t']:7.2f}{detail['raw_e']:6.0f}"
            f"{detail['raw_a']:7.2f}{detail['raw_u']:6.0f}{detail['raw_c']:6.0f}"
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
            "raw_e": detail["raw_e"],
            "raw_a": detail["raw_a"],
            "raw_u": detail["raw_u"],
            "raw_c": detail["raw_c"],
            "line_count": detail["line_count"],
            "halte_count": detail["halte_count"],
            "other_mode_count": detail["other_mode_count"],
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
    except (AhpError, ValueError) as exc:
        print(f"! {exc}")
        sys.exit(1)
