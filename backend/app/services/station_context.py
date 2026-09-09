"""Menyusun konteks yang dikirim ke model bahasa sebelum menjawab.

Isinya penjelasan proyek plus ringkasan data yang benar-benar ada di database.
Tanpa ini modelnya cuma menebak dari ingatan umum, dan jawabannya tidak nyambung
dengan data kita.

Konteksnya berlapis. Semua stasiun selalu ikut sebagai daftar ringkas, tapi
rincian isi isochrone cuma disertakan untuk stasiun yang sedang dibuka atau yang
namanya disebut di pertanyaan — kalau semuanya ikut, konteksnya jadi ribuan
baris dan yang penting malah tenggelam.
"""

import re
from collections import defaultdict

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.station import Station

# Batas stasiun yang dirinci sekaligus. Pertanyaan pembanding biasanya menyebut
# dua atau tiga nama; lebih dari itu konteksnya membengkak tanpa perlu.
MAX_DETAILED = 3

# Nama sependek "Duri" gampang tercocok dari kata biasa, jadi pencocokan nama
# dari teks pertanyaan dibatasi ke nama yang cukup panjang.
MIN_NAME_LENGTH = 4

PROJECT_BRIEF = """Kamu asisten di dalam StaSIUN (Station Spatial Intelligence for
Urban Network), sebuah WebGIS untuk menilai potensi ruang komersial stasiun
KAI Commuter di DKI Jakarta.

MASALAH YANG DIKERJAKAN
Pendapatan non-farebox KAI baru sekitar 4% dari total, jauh di bawah operator
sebanding seperti MRT Jakarta yang 30-40%. Penyebabnya ruang komersial stasiun
dihargai dengan perkiraan, bukan pengukuran. UMKM juga ragu menyewa lapak
karena risiko lokasinya tidak terukur.

TIGA FITUR YANG DIRANCANG
1. Ad-Space Opportunity - peringkat kategori merek per zona di dalam stasiun,
   perkiraan nilai sewa, pemicu Facility Sponsorship berbasis CSR.
2. Tenant Valuation - pencocokan kategori tenant untuk lapak kosong, plus
   Tenant Survival Index (TSI) skala 0-100.
3. Naming Rights - perkiraan nilai kontrak tahunan dan peringkat kandidat
   sponsor.

MESIN SKOR
SEPI kependekan dari Spatial Economic Potential Index. Jangan mengarang
kepanjangan lain.
SEPI = w1*T + w2*E + w3*A + w4*U + w5*C, dengan T Transportasi, E Ekonomi,
A Aksesibilitas, U Urban, C Komersial. Bobotnya gabungan Entropy Weighting dan
AHP, peringkat akhirnya memakai TOPSIS. Zonanya poligon isochrone jalan kaki
5, 10, dan 15 menit, bukan lingkaran buffer.

Arti tiap variabel:
- T gabungan jumlah lin KRL, jumlah halte bus, dan jumlah stasiun moda lain di
  dalam isochrone. Sudah berupa skala 0-1, bukan jumlah.
- E jumlah titik ekonomi: ATM dan bank, kantor, kantor swasta.
- A luas wilayah yang terjangkau jalan kaki, dalam kilometer persegi.
- U jumlah titik urban: apartemen, apotek, ibadah, hiburan, museum, wisata.
- C jumlah titik komersial: makanan dan minuman, Alfamart, Indomaret, brand
  coffee shop.

YANG SUDAH ADA DATANYA HARI INI
- Titik stasiun: nama, kode KAI, lin, status dilayani, kecamatan, alamat.
- Poligon isochrone jalan kaki 5, 10, dan 15 menit untuk kelima wilayah DKI.
- Titik minat hasil survei MAPID di kelima wilayah, kategorinya didaftar di
  bawah.
- Skor SEPI dan peringkatnya untuk 46 stasiun KRL, di ketiga pita waktu.
Semua angka yang muncul di konteks ini hasil hitungan sungguhan dan boleh
dipakai menjawab.

YANG BELUM ADA - JANGAN SEKALI-KALI DIKARANG
Tenant Survival Index, nilai naming rights, footfall, dwell-time, arketipe LDA,
dan data mitra MAPID (StrukGo, MenuGo, PropertiGo). Layer Activity sudah dibuat
tapi masih kosong, nol isian. Kalau ditanya soal ini, katakan terus terang
angkanya belum ada, lalu jelaskan bagaimana nanti dihitung.

Satu hal lagi yang harus jujur disebut kalau ditanya seberapa final skornya:
bobot AHP-nya masih angka sementara, menunggu kesepakatan tim.

CARA MENJAWAB SOAL GERAI YANG BELUM ADA
Kalau ditanya kategori apa yang belum ada di sekitar sebuah stasiun, jawab dari
hitungan kategori di bagian rincian stasiun. Kategori bernilai 0 memang tidak
punya satu pun titik di dalam isochrone itu.
Tapi sebutkan juga batasnya. Kita cuma mendata kategori yang ada di daftar
kategori, jadi kamu boleh bilang "belum ada Alfamart" atau "belum ada apotek",
tetapi TIDAK boleh menyimpulkan soal merek atau jenis kuliner yang tidak kita
data - misalnya waralaba ayam goreng, kedai kopi tertentu, atau restoran
spesifik. Jangan mengarang nama merek.

CARA MENJAWAB
Pakai bahasa Indonesia yang santai tapi padat. Jawab dari data di bawah kalau
pertanyaannya memang bisa dijawab dari situ, dan sebut nama stasiunnya. Kalau
pertanyaannya jauh di luar urusan StaSIUN dan perkeretaan Jabodetabek, arahkan
kembali dengan sopan. Balas dalam beberapa kalimat atau daftar pendek.

Tulis dalam teks biasa. Jangan memakai markdown seperti **tebal**, *miring*,
atau judul berawalan #. Jangan memakai notasi LaTeX seperti $...$ atau
subscript w_1; tulis saja w1. Jangan membuat tabel. Kalau perlu daftar, pakai
tanda hubung di awal baris."""

CATEGORY_COUNT_QUERY = text(
    """
    SELECT i.minutes, p.category, COUNT(p.id) AS jumlah
    FROM isochrones i
    LEFT JOIN pois p ON ST_Contains(i.area, p.location)
    WHERE i.station_id = :station_id
    GROUP BY i.minutes, p.category
    """
)

AREA_QUERY = text(
    """
    SELECT minutes, ST_Area(ST_Transform(area, 3857)) / 1000000.0 AS km2
    FROM isochrones
    WHERE station_id = :station_id
    ORDER BY minutes
    """
)

SCORE_QUERY = text(
    """
    SELECT minutes, sepi, rank
    FROM station_scores
    WHERE station_id = :station_id
    ORDER BY minutes
    """
)

KNOWN_CATEGORY_QUERY = text("SELECT DISTINCT category FROM pois ORDER BY category")


def _station_line(row) -> str:
    parts = [row.name]

    if row.code:
        parts.append(f"[{row.code}]")

    if row.lines:
        parts.append("lin " + ",".join(row.lines))

    if len(row.lines) > 1:
        parts.append("interchange")

    if not row.served:
        parts.append("TIDAK dilayani, kereta lewat tanpa berhenti")

    if row.kecamatan:
        parts.append(row.kecamatan)

    return "- " + " | ".join(parts)


def build_station_digest(db: Session) -> str:
    """Ringkasan seluruh stasiun, dikelompokkan per jaringan."""
    rows = db.execute(
        select(
            Station.name,
            Station.code,
            Station.types,
            Station.lines,
            Station.served,
            Station.kecamatan,
        ).order_by(Station.name)
    ).all()

    if not rows:
        return "DAFTAR STASIUN\n(database masih kosong)"

    by_network: dict[str, list] = defaultdict(list)
    for row in rows:
        network = row.types[0] if row.types else "Lainnya"
        by_network[network].append(row)

    blocks = [f"DAFTAR STASIUN DI DATABASE ({len(rows)} titik)"]

    for network in sorted(by_network, key=lambda n: -len(by_network[n])):
        group = by_network[network]
        blocks.append(f"\n{network} ({len(group)} stasiun):")
        blocks.extend(_station_line(row) for row in group)

    return "\n".join(blocks)


def build_category_list(db: Session) -> str:
    """Kategori titik minat yang benar-benar terisi, beserta jumlahnya.

    Penting disertakan. Tanpa ini modelnya tidak tahu batas datanya, lalu
    menyimpulkan sesuatu tidak ada padahal memang tidak pernah didata.
    """
    rows = db.execute(
        text(
            "SELECT category, variable, COUNT(*) AS jumlah "
            "FROM pois GROUP BY category, variable ORDER BY category"
        )
    ).all()

    if not rows:
        return "KATEGORI TITIK MINAT\n(belum ada data)"

    total = sum(r.jumlah for r in rows)
    lines = [
        f"KATEGORI TITIK MINAT YANG DIDATA ({len(rows)} kategori, "
        f"{total} titik se-DKI)",
        "Di luar kategori ini kita tidak punya data apa pun.",
    ]
    lines.extend(f"- {r.category} (variabel {r.variable}): {r.jumlah}" for r in rows)
    return "\n".join(lines)


def build_ranking(db: Session, limit: int = 10) -> str:
    """Peringkat SEPI teratas dan terbawah pada pita 10 menit."""
    rows = db.execute(
        text(
            "SELECT s.name, sc.sepi, sc.rank "
            "FROM station_scores sc JOIN stations s ON s.id = sc.station_id "
            "WHERE sc.minutes = 10 ORDER BY sc.rank"
        )
    ).all()

    if not rows:
        return "SKOR SEPI\n(belum dihitung, jalankan compute_sepi)"

    lines = [f"SKOR SEPI PITA 10 MENIT ({len(rows)} stasiun KRL, skala 0-100)"]
    lines.append(f"Tertinggi {limit}:")
    lines.extend(f"- #{r.rank} {r.name}: {r.sepi:.1f}" for r in rows[:limit])
    lines.append(f"Terendah {limit}:")
    lines.extend(f"- #{r.rank} {r.name}: {r.sepi:.1f}" for r in rows[-limit:])
    return "\n".join(lines)


def build_station_detail(db: Session, station: Station) -> str:
    """Isi isochrone satu stasiun: skor, luas, dan hitungan tiap kategori."""
    params = {"station_id": station.id}

    scores = db.execute(SCORE_QUERY, params).all()
    areas = db.execute(AREA_QUERY, params).all()
    counts = db.execute(CATEGORY_COUNT_QUERY, params).all()

    if not areas:
        return (
            f"RINCIAN {station.name.upper()}\n"
            "Belum ada poligon isochrone untuk stasiun ini, jadi isi sekitarnya "
            "belum bisa dihitung."
        )

    bands = [row.minutes for row in areas]
    lines = [f"RINCIAN {station.name.upper()}"]

    if scores:
        lines.append(
            "Skor SEPI: "
            + " | ".join(
                f"{r.minutes} menit {r.sepi:.1f} (peringkat {r.rank} dari 46)"
                for r in scores
            )
        )
    else:
        lines.append("Skor SEPI: belum dihitung untuk stasiun ini.")

    lines.append(
        "Luas jangkauan jalan kaki: "
        + " | ".join(f"{r.minutes} menit {r.km2:.2f} km2" for r in areas)
    )

    # Kategori yang tidak muncul sama sekali di hasil query berarti nol di semua
    # pita, jadi tetap harus ditulis nol — bukan dilewati.
    grid: dict[str, dict[int, int]] = defaultdict(dict)
    for row in counts:
        if row.category is not None:
            grid[row.category][row.minutes] = row.jumlah

    known = [r.category for r in db.execute(KNOWN_CATEGORY_QUERY).all()]

    header = " / ".join(f"{m} menit" for m in bands)
    lines.append(f"Jumlah titik minat di dalam isochrone ({header}):")
    for category in known:
        values = [grid.get(category, {}).get(m, 0) for m in bands]
        lines.append(f"- {category}: " + " / ".join(str(v) for v in values))

    # Baris berikut yang paling sering dipakai menjawab "apa yang belum ada".
    for minutes in bands:
        empty = [c for c in known if grid.get(c, {}).get(minutes, 0) == 0]
        if empty:
            lines.append(
                f"Kategori tanpa satu pun titik dalam {minutes} menit: "
                + ", ".join(empty)
            )
        else:
            lines.append(f"Dalam {minutes} menit semua kategori ada isinya.")

    return "\n".join(lines)


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower())


def find_mentioned(db: Session, message: str) -> list[Station]:
    """Cari stasiun yang namanya disebut di pertanyaan.

    Supaya pertanyaan seperti "gerai apa yang belum ada di Gondangdia" tetap
    dapat rinciannya walau panel stasiunnya belum dibuka.
    """
    if not message:
        return []

    haystack = f" {_normalize(message)} "
    stations = db.execute(select(Station).order_by(Station.name)).scalars().all()

    matched = [
        station
        for station in stations
        if len(station.name) >= MIN_NAME_LENGTH
        and f" {_normalize(station.name)} " in haystack
    ]

    # Nama terpanjang menang, supaya "Jakarta Kota" tidak kalah oleh stasiun
    # lain yang namanya kebetulan jadi bagian darinya.
    matched.sort(key=lambda s: -len(s.name))
    return matched[:MAX_DETAILED]


def build_chat_context(
    db: Session, station_id: int | None = None, message: str | None = None
) -> str:
    """Gabungan penjelasan proyek, ringkasan data, dan rincian stasiun terkait."""
    parts = [
        PROJECT_BRIEF,
        "",
        build_station_digest(db),
        "",
        build_category_list(db),
        "",
        build_ranking(db),
    ]

    detailed: list[Station] = []
    seen: set[int] = set()

    focus = db.get(Station, station_id) if station_id is not None else None
    if focus:
        detailed.append(focus)
        seen.add(focus.id)

    for station in find_mentioned(db, message or ""):
        if station.id not in seen and len(detailed) < MAX_DETAILED:
            detailed.append(station)
            seen.add(station.id)

    for station in detailed:
        parts.extend(["", build_station_detail(db, station)])

    if focus:
        parts.append(
            "\nSTASIUN YANG SEDANG DIBUKA USER DI PANEL: "
            f"{focus.name}. Anggap pertanyaan tanpa penyebutan nama merujuk "
            "ke stasiun ini."
        )

    return "\n".join(parts)
