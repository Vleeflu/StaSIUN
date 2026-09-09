"""Susun matriks keputusan SEPI dari isi database.

Tiap baris satu stasiun KRL, tiap kolom satu variabel. Angkanya dihitung di
dalam isochrone stasiun itu, bukan lingkaran radius — perbedaan yang penting,
karena rel dan sungai bikin jangkauan jalan kaki jauh dari bundar.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

# Urutan kolom. Dipakai juga oleh berkas AHP, jadi keduanya harus sama.
CRITERIA = ["T", "E", "A", "U", "C"]

# Jaringan yang dinilai. MRT dan LRT tidak ikut diskor — yang dijual KAI adalah
# ruang di stasiunnya sendiri; moda lain masuk hitungan sebagai penyambung.
SCORED_NETWORKS = ("KAI Commuter", "KAI")

RAW_QUERY = text(
    """
    WITH scope AS (
        SELECT s.id, s.name, s.code, s.lines, i.area
        FROM stations s
        JOIN isochrones i ON i.station_id = s.id AND i.minutes = :minutes
        WHERE s.types && CAST(:networks AS varchar[])
    )
    SELECT
        scope.id,
        scope.name,
        scope.code,
        COALESCE(array_length(scope.lines, 1), 0) AS line_count,
        -- Luas dihitung di proyeksi meter, bukan derajat, supaya angkanya
        -- benar-benar kilometer persegi dan sebanding antar wilayah.
        ST_Area(ST_Transform(scope.area, 3857)) / 1000000.0 AS area_km2,
        COUNT(p.id) FILTER (WHERE p.category = 'halte') AS halte_count,
        COUNT(p.id) FILTER (WHERE p.variable = 'E') AS poi_e,
        COUNT(p.id) FILTER (WHERE p.variable = 'U') AS poi_u,
        COUNT(p.id) FILTER (WHERE p.variable = 'C') AS poi_c,
        (
            SELECT COUNT(*)
            FROM stations other
            WHERE other.id <> scope.id
              AND NOT (other.types && CAST(:networks AS varchar[]))
              AND ST_Contains(scope.area, other.location)
        ) AS other_mode_count
    FROM scope
    LEFT JOIN pois p ON ST_Contains(scope.area, p.location)
    GROUP BY scope.id, scope.name, scope.code, scope.lines, scope.area
    ORDER BY scope.name
    """
)


def _scale(values: list[float]) -> list[float]:
    """Skala 0 sampai 1 dengan membagi nilai tertinggi.

    Sengaja tidak memakai min-max. Entropy kebal terhadap perkalian tapi tidak
    terhadap pergeseran, jadi menggeser nilai terendah ke nol akan menaikkan
    sebaran kolom T secara semu — dan bobotnya ikut terkerek, padahal kolom
    lain memakai hitungan mentah. Membagi nilai tertinggi tidak menggeser apa
    pun, sekaligus menjaga perbandingan aslinya: dua lin tetap separuh dari
    empat lin.
    """
    high = max(values)
    return [0.0] * len(values) if high == 0 else [v / high for v in values]


def build_matrix(db: Session, minutes: int = 10) -> tuple[list[dict], list[list[float]]]:
    """Kembalikan (rincian per stasiun, matriks keputusan).

    Rinciannya ikut dibawa supaya angka mentahnya bisa ditelusuri — tanpa itu
    skor akhirnya cuma angka yang tidak bisa dipertanggungjawabkan.
    """
    rows = db.execute(
        RAW_QUERY, {"minutes": minutes, "networks": list(SCORED_NETWORKS)}
    ).mappings().all()

    if not rows:
        raise ValueError(
            f"tidak ada stasiun dengan isochrone {minutes} menit. "
            "Jalankan dulu: python -m scripts.ingest_layers"
        )

    details = [dict(row) for row in rows]

    # T tidak punya satu angka alami — ia gabungan tiga hal dengan satuan
    # berbeda: jumlah lin, jumlah halte, jumlah stasiun moda lain. Ketiganya
    # diskalakan dulu ke 0-1 lalu dirata-rata, supaya jumlah halte yang bisa
    # puluhan tidak menenggelamkan jumlah lin yang paling banter empat.
    lines = _scale([float(d["line_count"]) for d in details])
    haltes = _scale([float(d["halte_count"]) for d in details])
    others = _scale([float(d["other_mode_count"]) for d in details])

    matrix: list[list[float]] = []
    for idx, detail in enumerate(details):
        transport = (lines[idx] + haltes[idx] + others[idx]) / 3.0
        detail["raw_t"] = transport
        detail["raw_e"] = float(detail["poi_e"])
        detail["raw_a"] = float(detail["area_km2"])
        detail["raw_u"] = float(detail["poi_u"])
        detail["raw_c"] = float(detail["poi_c"])

        matrix.append(
            [
                detail["raw_t"],
                detail["raw_e"],
                detail["raw_a"],
                detail["raw_u"],
                detail["raw_c"],
            ]
        )

    return details, matrix
