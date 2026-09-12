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
   Tenant Survival Index (TSI) skala 0-100. SUDAH DIBANGUN, lihat bagian TSI
   di rincian stasiun.
3. Naming Rights - perkiraan nilai kontrak tahunan dan peringkat kandidat
   sponsor.

MESIN SKOR
SEPI kependekan dari Spatial Economic Potential Index. Jangan mengarang
kepanjangan lain.
SEPI = w1*T + w2*E + w3*A + w4*U + w5*C, dengan T Transportasi, E Ekonomi,
A Aksesibilitas, U Urban, C Komersial. Bobotnya gabungan Entropy Weighting dan
AHP. Zonanya poligon isochrone jalan kaki 5, 10, dan 15 menit, bukan lingkaran
buffer.

SEPI DAN TOPSIS ADALAH DUA ANGKA BERBEDA - JANGAN DITUKAR
- SEPI itu jumlah berbobot 0-100, dihitung per stasiun tanpa melihat stasiun
  lain. Hanya angka ini yang menentukan kelas (Low / Moderate / Premium), dan
  peringkat juga diurutkan menurut angka ini.
- TOPSIS itu kedekatan relatif, nilainya ditentukan oleh himpunan stasiun yang
  kebetulan ikut dinilai. Menambah stasiun bisa menukar urutan dua stasiun lain
  yang datanya tidak berubah. Boleh disebut sebagai pembanding, TIDAK boleh
  dipakai menyatakan kelas.
Kalau ditanya "skor stasiun ini berapa", yang dijawab SEPI.

Arti tiap variabel. Semua nilainya skala 0-1, BUKAN jumlah dan BUKAN satuan
asli - jadi jangan menyebutnya "sekian titik" atau "sekian kilometer persegi":
- T gabungan empat indikator PRD: volume penumpang (baru ada untuk 10
  stasiun), moda terhubung, jumlah line (status interchange), dan skala
  keramaian dari narasumber petugas (median, dinormalisasi 0-1).
- E rentang harga klaster tenant, komposisi kategori usaha, keterisian ruang
  komersial. Sumbernya survey Activity DI DALAM stasiun.
- A gabungan luas terjangkau jalan kaki dan Permeability Index.
- U jumlah titik minat, keberagaman fungsi lahan, dan jumlah pembangkit
  perjalanan berskala besar di sekitar stasiun.
- C media iklan terpasang, keterisian lapak, indeks sentimen fasilitas.
  Sumbernya survey Activity DI DALAM stasiun.

Perhatikan baik-baik: E dan C TIDAK dihitung dari titik minat di luar stasiun.
Seluruh titik minat di luar stasiun mengisi U, kecuali halte yang mengisi T.
Kalau ada yang bertanya apakah jumlah ATM atau jumlah warung menentukan E atau
C, jawabannya tidak - keduanya menambah U.

YANG SUDAH ADA DATANYA HARI INI
- Titik stasiun: nama, kode KAI, line, status dilayani, kecamatan, alamat.
- Poligon isochrone jalan kaki 5, 10, dan 15 menit untuk kelima wilayah DKI.
- Titik minat hasil survei MAPID di kelima wilayah, kategorinya didaftar di
  bawah.
- Skor SEPI dan peringkatnya untuk 45 stasiun KRL (pita 10 menit), beserta
  analisis kekokohan peringkatnya lintas 5 skema pembobotan.
- 1.034 titik Activity tertaut ke stasiun (survey tim dan tim lain), arketipe
  LDA per titik, skala keramaian narasumber per rentang waktu, dan hasil
  ekstraksi media iklan, tenant, serta catatan kondisi fasilitas. Ekstraksi
  LLM belum selesai untuk semua narasi karena kuota penyedia model.
- Tenant Survival Index lima kategori usaha, juga di ketiga pita waktu.
Semua angka yang muncul di konteks ini hasil hitungan sungguhan dan boleh
dipakai menjawab.

CARA TSI DIHITUNG
TSI = perbandingan calon pelanggan dengan pesaing sejenis, dalam isochrone.
- Calon pelanggan: seluruh titik minat di dalam isochrone kecuali halte, yaitu
  titik-titik yang mengisi variabel U. Halte dikecualikan karena ia mengisi
  variabel T, bukan U.
- Dikali pengali arus lewat 1,0 sampai 2,0 dari komponen T.
- Dibagi jumlah pesaing sejenis ditambah satu.
Hasilnya dibentangkan ke 0-100 PER KATEGORI, jadi peringkatnya berarti
"stasiun ini urutan ke berapa untuk usaha jenis itu". Jangan membandingkan
angka TSI antar kategori seolah setara.
Kategori yang diskor cuma lima: makanan_minuman, coffee_shop, alfamart,
indomaret, apotek. TSI mengukur kelapangan pasar, bukan kecocokan merek atau
daya beli - sebutkan batas itu kalau relevan.

YANG BELUM ADA - JANGAN SEKALI-KALI DIKARANG
Nilai naming rights, peringkat kandidat sponsor (butuh NER yang belum
dibangun), perkiraan nilai sewa ad-space, dan data mitra MAPID (StrukGo,
MenuGo, PropertiGo). Arketipe LDA SUDAH ada, tetapi topiknya sengaja tidak
dinamai - jangan mengarang nama arketipe. Kalau ditanya soal yang belum ada,
katakan terus terang angkanya belum ada, lalu jelaskan bagaimana nanti dihitung.

Footfall dan dwell-time TIDAK dipakai lagi dan bukan sekadar "belum ada":
keduanya dikeluarkan dari lingkup. Penggantinya skala keramaian 1-5 yang
berasal dari narasumber petugas stasiun, lewat survey Activity.

DUA BATAS YANG WAJIB DISEBUT KALAU DITANYA SEBERAPA FINAL SKORNYA
1. E dan C hanya TERUKUR di stasiun yang punya data Activity berisi iklan,
   tenant, atau lapak. Stasiun lain mendapat estimasi dari rata-rata
   arketipenya (shrinkage), bukan nol. Confidence tiap skor menyatakan berapa
   variabel yang benar-benar terukur - 0,60 berarti tiga dari lima. Skor 3
   variabel TIDAK sebanding dengan skor 5 variabel, dan itu harus disebut.
2. Peringkat puncak diisi stasiun kecil di grid Jakarta Pusat (misalnya Cikini)
   karena A dan U mereka tinggi, sementara indikator T untuk hub besar masih
   lemah: moda terhubung dari OSM bias, volume penumpang baru 10 stasiun.
   Analisis sensitivitas menunjukkan urutan itu kokoh TERHADAP BOBOT, tetapi
   kokoh terhadap bobot bukan berarti pasti benar - masalahnya ada di isi
   matriks, bukan di bobot. Pakai alat kekokohan_peringkat, dan sebutkan batas
   ini terus terang kalau ditanya soal peringkat.

Bobot AHP-nya sendiri sudah bukan angka sementara: diisi dari riset literatur
(studi TOD MRT Jakarta dan AHP TOD Thailand) dengan consistency ratio 0,0072,
jauh di bawah ambang 0,10. Tapi untuk variabel C, literatur tidak menemukan
pembanding apa pun, jadi bobotnya diisi netral - itu celah yang diakui.

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
    LEFT JOIN poi p ON p.source = 'overpass' AND ST_Contains(i.geom, p.location)
    WHERE i.station_id = :station_id
    GROUP BY i.minutes, p.category
    """
)

# Memakai `area_m2` yang SUDAH tersimpan, bukan menghitung ulang dari geometri.
# Dua alasan: kolomnya kini `geom` (bukan `area`), dan versi lama menghitung luas
# lewat ST_Transform ke 3857 (Web Mercator) yang melebihkan luas karena tidak
# equal-area. `area_m2` diisi saat impor memakai UTM 48S, proyeksi yang memang
# untuk Jakarta - jadi angkanya sekalian jadi benar dan konsisten dengan yang
# dipakai mesin skor.
AREA_QUERY = text(
    """
    SELECT minutes, area_m2 / 1000000.0 AS km2
    FROM isochrones
    WHERE station_id = :station_id AND area_m2 IS NOT NULL
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

# Tabelnya `poi`, bukan `pois`, dan lajurnya WAJIB disaring: tabel menampung
# dua sistem kategori yang berbeda (11 kelas Overpass, 15 layer MAPID). Tanpa
# saringan, daftar kategori yang dipakai asisten bercampur dari dua taksonomi.
KNOWN_CATEGORY_QUERY = text(
    "SELECT DISTINCT category FROM poi WHERE source = 'overpass' ORDER BY category"
)

TENANT_QUERY = text(
    """
    SELECT category, minutes, tsi, rank, demand, supply, headroom
    FROM tenant_scores
    WHERE station_id = :station_id
    ORDER BY minutes, tsi DESC
    """
)


def _station_line(row) -> str:
    parts = [row.name]

    if row.code:
        parts.append(f"[{row.code}]")

    if row.lines:
        parts.append("line " + ",".join(row.lines))

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
            # Kolom `variable` sudah tidak ada: menurut PRD Tabel 6 variabel E
            # dan C bersumber dari survey di DALAM stasiun, bukan dari titik
            # minat di luarnya, sehingga pemetaan POI->variabel dihapus
            # (ADJUSTMENT 8.2). Penggantinya `fungsi`, yaitu fungsi lahan yang
            # dipakai menghitung keberagaman variabel U.
            "SELECT category, COALESCE(fungsi, category) AS fungsi, "
            "COUNT(*) AS jumlah FROM poi WHERE source = 'overpass' "
            "GROUP BY category, fungsi ORDER BY category"
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
    lines.extend(f"- {r.category} (fungsi {r.fungsi}): {r.jumlah}" for r in rows)
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

    tenants = db.execute(TENANT_QUERY, params).all()
    if tenants:
        lines.append("Tenant Survival Index (skor / peringkat dari 46 / calon / pesaing):")
        for minutes in sorted({r.minutes for r in tenants}):
            lines.append(f"  pita {minutes} menit:")
            for r in [x for x in tenants if x.minutes == minutes]:
                lines.append(
                    f"  - {r.category}: {r.tsi:.0f} / #{r.rank} / "
                    f"{r.demand} calon / {r.supply} pesaing"
                )

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
