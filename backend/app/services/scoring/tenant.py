"""Tenant Survival Index: seberapa aman satu jenis usaha dibuka di satu stasiun.

Pertanyaan yang dijawab persis pertanyaan pemilik UMKM sebelum tanda tangan
sewa — kalau saya buka warung kopi di sini, pelanggannya cukup atau sudah
diperebutkan terlalu banyak orang?

Jawabannya satu perbandingan sederhana: berapa calon pelanggan yang bisa
berjalan kaki ke sini, dibagi berapa pesaing sejenis yang sudah ada. Semua
bahannya terukur, tidak ada satu pun yang diasumsikan.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

# Kategori yang masuk akal mengisi lapak stasiun. Sisanya sengaja tidak
# diskor: masjid, museum, dan halte bukan sesuatu yang disewakan, dan kantor
# tidak muat di lapak peron.
TENANT_CATEGORIES = [
    "makanan_minuman",
    "coffee_shop",
    "alfamart",
    "indomaret",
    "apotek",
]

# Nama yang enak dibaca di panel. Alfamart dan Indomaret dibiarkan terpisah
# karena datanya memang dua layer berbeda, bukan satu kategori minimarket.
CATEGORY_LABEL = {
    "makanan_minuman": "Makanan & minuman",
    "coffee_shop": "Kedai kopi merek",
    "alfamart": "Minimarket Alfamart",
    "indomaret": "Minimarket Indomaret",
    "apotek": "Apotek",
}

SCORED_NETWORKS = ("KAI Commuter", "KAI")


class TenantError(RuntimeError):
    """Raised when the inputs TSI depends on are not ready."""


# Basis pelanggan dihitung dari titik ekonomi dan urban: kantor, bank, hunian,
# tempat ibadah, faskes, hiburan. Variabel C sengaja TIDAK ikut — itu justru
# pasokan komersial, dan memakainya bikin hitungannya berputar: daerah yang
# sudah padat warung akan tercatat butuh lebih banyak warung.
BASE_QUERY = text(
    """
    SELECT
        s.id AS station_id,
        s.name,
        COUNT(p.id) FILTER (WHERE p.variable IN ('E', 'U')) AS demand,
        COUNT(p.id) FILTER (WHERE p.category = :category) AS supply
    FROM stations s
    JOIN isochrones i ON i.station_id = s.id AND i.minutes = :minutes
    LEFT JOIN pois p ON ST_Contains(i.area, p.location)
    WHERE s.types && CAST(:networks AS varchar[])
    GROUP BY s.id, s.name
    ORDER BY s.name
    """
)

CONNECTIVITY_QUERY = text(
    """
    SELECT station_id, raw_t
    FROM station_scores
    WHERE minutes = :minutes
    """
)


def _scale_to_100(values: list[float]) -> list[float]:
    """Bentangkan ke 0-100 memakai nilai terendah dan tertinggi.

    Di sini min-max justru yang benar, kebalikan dari matriks SEPI. Skornya
    dibaca manusia sebagai peringkat relatif antar stasiun, bukan disuapkan ke
    entropy — jadi memakai seluruh rentang malah bikin bedanya kebaca.
    """
    low, high = min(values), max(values)
    span = high - low

    if span == 0:
        return [50.0] * len(values)

    return [100.0 * (v - low) / span for v in values]


def compute_category(
    db: Session, category: str, minutes: int
) -> list[dict]:
    """Hitung TSI satu kategori untuk seluruh stasiun KRL."""
    rows = (
        db.execute(
            BASE_QUERY,
            {
                "category": category,
                "minutes": minutes,
                "networks": list(SCORED_NETWORKS),
            },
        )
        .mappings()
        .all()
    )

    if not rows:
        return []

    connectivity = {
        r.station_id: r.raw_t
        for r in db.execute(CONNECTIVITY_QUERY, {"minutes": minutes}).all()
    }

    # Tanpa penjagaan ini, stasiun yang belum punya skor SEPI diam-diam dapat
    # pengali 1,0 - skornya tetap keluar, cuma salah. Lebih baik gagal terang.
    missing = [r["name"] for r in rows if r["station_id"] not in connectivity]
    if missing:
        raise TenantError(
            f"pita {minutes} menit: {len(missing)} stasiun belum punya skor SEPI "
            f"({', '.join(missing[:3])}...). "
            f"Jalankan dulu: python -m scripts.compute_sepi --minutes {minutes}"
        )

    entries: list[dict] = []
    for row in rows:
        # T bernilai 0-1, dipakai sebagai pengali 1,0 sampai 2,0. Stasiun yang
        # terhubung ke banyak moda melewatkan orang yang tidak tinggal maupun
        # bekerja di sekitarnya, dan orang-orang itu tetap calon pembeli.
        multiplier = 1.0 + connectivity.get(row["station_id"], 0.0)

        # Pesaing ditambah satu: satu untuk gerai yang mau dibuka sendiri.
        # Tanpa itu, lokasi tanpa pesaing hasilnya tak terhingga.
        headroom = (row["demand"] * multiplier) / (row["supply"] + 1)

        entries.append(
            {
                "station_id": row["station_id"],
                "name": row["name"],
                "minutes": minutes,
                "category": category,
                "demand": row["demand"],
                "connectivity": round(multiplier, 4),
                "supply": row["supply"],
                "headroom": round(headroom, 2),
            }
        )

    scores = _scale_to_100([e["headroom"] for e in entries])
    for entry, score in zip(entries, scores):
        entry["tsi"] = round(score, 2)

    entries.sort(key=lambda e: -e["tsi"])
    for position, entry in enumerate(entries, start=1):
        entry["rank"] = position

    return entries


def compute_all(db: Session, minutes: int) -> list[dict]:
    """Hitung TSI untuk semua kategori tenant sekaligus."""
    result: list[dict] = []
    for category in TENANT_CATEGORIES:
        result.extend(compute_category(db, category, minutes))
    return result
