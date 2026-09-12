"""Tenant Survival Index: seberapa aman satu jenis usaha dibuka di satu stasiun.

Pertanyaan yang dijawab persis pertanyaan pemilik UMKM sebelum tanda tangan
sewa — kalau saya buka warung kopi di sini, pelanggannya cukup atau sudah
diperebutkan terlalu banyak orang?

Jawabannya satu perbandingan sederhana: berapa calon pelanggan yang bisa
berjalan kaki ke sini, dibagi berapa pesaing sejenis yang sudah ada. Semua
bahannya terukur, tidak ada satu pun yang diasumsikan.

Pesaing punya batas pita sendiri (MENIT_PESAING): berapa pun pita yang diminta
untuk calon pelanggan, pesaing tidak pernah dihitung lebih jauh dari itu.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.scoring.tenant_dalam import (
    CONFIDENCE_TAKSIRAN,
    CONFIDENCE_TERUKUR,
    cacah_per_stasiun,
    taksir,
)

# Kategori yang masuk akal mengisi lapak stasiun. Sisanya sengaja tidak
# diskor: masjid, museum, dan halte bukan sesuatu yang disewakan, dan kantor
# tidak muat di lapak peron.
# Lajur bawaan adalah "mapid", bukan "overpass". Kategori di bawah adalah nama
# layer GEO MAPID; lajur Overpass hanya punya 11 kelas kasar (ritel,
# makanan_minuman, ...) sehingga saringan `category = 'alfamart'` tidak akan
# pernah cocok di sana. Peran ini sudah ditetapkan di ADJUSTMENT 8.5: MAPID
# menjadi sisi PASOKAN GapScore, justru karena taksonominya lebih halus.
TENANT_CATEGORIES = ["makanan_minuman", "coffee_shop", "minimarket", "apotek"]

# Dikelompokkan per SEKTOR USAHA, bukan per lajur data.
#
# Sebelumnya Alfamart dan Indomaret jadi dua kategori terpisah - karena di
# MAPID keduanya memang dua layer berbeda. Tetapi calon penyewa tidak sedang
# memilih antara "Alfamart" dan "Indomaret"; ia memilih apakah membuka
# MINIMARKET masuk akal di sini. Memisahkannya juga membuat hitungan pesaing
# keliru: Alfamart tidak dihitung sebagai pesaing Indomaret, padahal jelas iya.
#
# "Kedai kopi merek" diganti "Kedai kopi" - kata "merek" tidak menambah apa pun
# selain kebingungan.
SEKTOR_TENANT: dict[str, dict] = {
    "minimarket": {"label": "Minimarket", "poi": ["alfamart", "indomaret"]},
    "makanan_minuman": {"label": "Makanan & minuman", "poi": ["makanan_minuman"]},
    "coffee_shop": {"label": "Kedai kopi", "poi": ["coffee_shop"]},
    "apotek": {"label": "Apotek & obat", "poi": ["apotek"]},
}

CATEGORY_LABEL = {k: v["label"] for k, v in SEKTOR_TENANT.items()}

SCORED_NETWORKS = ("KAI Commuter", "KAI")

# Pita terjauh yang masih dihitung sebagai PESAING, berapa pun pita yang
# diminta untuk calon pelanggan.
#
# Alasan batas ini ada sama sekali: calon pelanggan wajar ditarik dari pita
# lebar - pekerja kantor yang berjalan 12 menit ke stasiun tetap melewati
# lapaknya saat pulang - sedangkan pesaing tidak begitu. Kedai yang 15 menit
# jauhnya melayani kerumunan lain dan tidak memperebutkan pembeli yang sama.
# Jadi pita 15 menit tetap menghitung pesaingnya sampai 10 menit saja.
#
# Nilainya sempat 5 menit, dan itu KELIRU. Penyempitannya bekerja terlalu baik:
# pesaing jadi nol di 24 dari 45 stasiun untuk kedai kopi dan 15 dari 45 untuk
# apotek. Penyebut yang seragam satu membuat pembagiannya berhenti membedakan
# apa pun, dan TSI merosot jadi peringkat calon pelanggan - terbukti dari
# Tanah Abang yang lalu memuncaki tiga dari empat sektor sekaligus. Padahal
# seluruh alasan TSI dipecah per sektor adalah menjawab "di stasiun ini, usaha
# jenis apa yang paling aman", dan jawaban itu hilang kalau juaranya sama di
# mana-mana. Pada 10 menit, pesaing nol tinggal 1 dari 45 (apotek) dan daftar
# teratas tiap sektor kembali berbeda-beda.
#
# Catatan buat yang menurunkannya lagi: periksa dulu sebaran `supply`, bukan
# rata-ratanya. Yang merusak bukan angka yang mengecil, melainkan angka yang
# menumpuk di nol.
MENIT_PESAING = 10


class TenantError(RuntimeError):
    """Raised when the inputs TSI depends on are not ready."""


# Basis pelanggan dihitung dari seluruh titik minat yang mengisi variabel U:
# kantor, bank, hunian, tempat ibadah, faskes, hiburan, makan-minum. Halte
# (fungsi `transportasi`) dikeluarkan karena menyuapi variabel T, bukan U.
#
# Versi sebelumnya menyaring `variable IN ('E','U')`. Kolom itu sudah tidak ada:
# menurut PRD Tabel 6 variabel E bersumber dari survey Activity di dalam
# stasiun, bukan dari titik minat di luarnya (ADJUSTMENT 8.2).
BASE_QUERY = text(
    """
    SELECT
        s.id AS station_id,
        s.name,
        COUNT(p.id) FILTER (WHERE COALESCE(p.fungsi, p.category) <> 'transportasi') AS demand,
        -- Pesaing dihitung di pita yang lebih sempit (ip), bukan pita calon
        -- pelanggan (i). Lihat MENIT_PESAING untuk alasannya.
        COUNT(p.id) FILTER (
            WHERE p.category = ANY(:kategori_poi)
              AND ST_Contains(ip.geom, p.location)
        ) AS supply,
        -- Penjaga: kalau pita pesaingnya belum pernah dibuat untuk stasiun ini,
        -- ST_Contains di atas bernilai NULL dan pesaingnya terhitung nol -
        -- angka yang tetap terlihat wajar padahal tidak pernah dihitung.
        BOOL_OR(ip.station_id IS NOT NULL) AS ada_pita_pesaing
    FROM stations s
    JOIN isochrones i ON i.station_id = s.id AND i.minutes = :minutes
    LEFT JOIN isochrones ip
        ON ip.station_id = s.id AND ip.minutes = :menit_pesaing
    -- p.source WAJIB disaring. Tabel poi menampung dua lajur (overpass dan
    -- mapid) yang sistem kategorinya bukan partisi yang sama; tanpa saringan
    -- ini permintaan terhitung dua kali dari dua pemetaan berbeda.
    LEFT JOIN poi p ON p.source = :sumber AND ST_Contains(i.geom, p.location)
    WHERE s.types && CAST(:networks AS varchar[])
      AND s.served
   -- `s.served` WAJIB. Stasiun yang dilintasi KRL TANPA berhenti tidak punya
   -- arus penumpang commuter sama sekali, jadi menskornya sebagai peluang
   -- komersial itu keliru - dan ia ikut mencemari normalisasi max-scaling serta
   -- bobot entropi seluruh stasiun lain. Gambir sempat terskor di peringkat 32
   -- karena saringan ini belum ada.
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
    db: Session, category: str, minutes: int, sumber: str = "mapid"
) -> list[dict]:
    """Hitung TSI satu kategori untuk seluruh stasiun KRL."""
    # Pita pesaing tidak pernah lebih lebar dari pita yang diminta. Kalau yang
    # dihitung memang pita 5 menit, keduanya berimpit dan tidak ada asimetri.
    menit_pesaing = min(minutes, MENIT_PESAING)

    rows = (
        db.execute(
            BASE_QUERY,
            {
                "kategori_poi": SEKTOR_TENANT[category]["poi"],
                "minutes": minutes,
                "menit_pesaing": menit_pesaing,
                "sumber": sumber,
                "networks": list(SCORED_NETWORKS),
            },
        )
        .mappings()
        .all()
    )

    if not rows:
        return []

    tanpa_pita = [r["name"] for r in rows if not r["ada_pita_pesaing"]]
    if tanpa_pita:
        raise TenantError(
            f"{len(tanpa_pita)} stasiun belum punya isochrone {menit_pesaing} menit "
            f"({', '.join(tanpa_pita[:3])}...), padahal pita itulah yang dipakai "
            f"menghitung pesaing. Jalankan dulu pembuatan isochrone untuk pita "
            f"{menit_pesaing} menit."
        )

    # Kategori yang tidak ada di lajur terpilih memberi supply = 0 di SETIAP
    # stasiun. Akibatnya headroom seragam, dan seluruh kategori menghasilkan
    # TSI yang identik - keluaran yang tetap terlihat rapi, berperingkat, dan
    # bisa disimpan, padahal sepenuhnya keliru. Persis begitulah bug ini
    # sempat lolos: alfamart/indomaret/apotek dicari di lajur 'overpass' yang
    # taksonominya cuma 11 kelas kasar.
    if not any(r["supply"] for r in rows):
        raise TenantError(
            f"kategori {category!r} nol di seluruh {len(rows)} stasiun pada lajur "
            f"{sumber!r}, pita pesaing {menit_pesaing} menit. Kemungkinan besar "
            f"kategorinya memang tidak ada di lajur itu, bukan benar-benar tidak "
            f"ada pesaingnya. Kategori tenant berasal dari nama layer GEO MAPID, "
            f"jadi lajurnya harus 'mapid'."
        )

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

    # Sisi DALAM stasiun (PRD hal. 13). Terpisah dari sisi luar karena asal
    # datanya berbeda: yang luar terpetakan untuk semua stasiun, yang dalam
    # hanya untuk stasiun yang sudah disurvei.
    cacah_dalam, disurvei = cacah_per_stasiun(db)
    titik_survei = {sid: sum(v.values()) for sid, v in cacah_dalam.items()}
    id_stasiun = [r["station_id"] for r in rows]
    dalam = taksir(category, id_stasiun, cacah_dalam, disurvei, titik_survei)

    entries: list[dict] = []
    for row in rows:
        # T bernilai 0-1, dipakai sebagai pengali 1,0 sampai 2,0. Stasiun yang
        # terhubung ke banyak moda melewatkan orang yang tidak tinggal maupun
        # bekerja di sekitarnya, dan orang-orang itu tetap calon pembeli.
        multiplier = 1.0 + connectivity.get(row["station_id"], 0.0)

        nilai_dalam, sebaran_dalam, terukur = dalam[row["station_id"]]
        pesaing = row["supply"] + nilai_dalam

        # Pesaing ditambah satu: satu untuk gerai yang mau dibuka sendiri.
        # Tanpa itu, lokasi tanpa pesaing hasilnya tak terhingga.
        headroom = (row["demand"] * multiplier) / (pesaing + 1)

        # Batas bawah: seandainya taksiran pesaing dalam stasiun meleset satu
        # simpangan KE ATAS. Arahnya sengaja yang merugikan - pertanyaan yang
        # dijawab TSI adalah "apakah aman membuka di sini", dan pada pertanyaan
        # semacam itu tebakan yang optimistis jauh lebih mahal daripada yang
        # pesimistis.
        headroom_bawah = (row["demand"] * multiplier) / (pesaing + sebaran_dalam + 1)

        entries.append(
            {
                "station_id": row["station_id"],
                "name": row["name"],
                "minutes": minutes,
                "category": category,
                "demand": row["demand"],
                "connectivity": round(multiplier, 4),
                "supply": round(pesaing, 2),
                "supply_luar": row["supply"],
                "supply_dalam": round(nilai_dalam, 2),
                "dalam_terukur": terukur,
                "confidence": CONFIDENCE_TERUKUR if terukur else CONFIDENCE_TAKSIRAN,
                "menit_pesaing": menit_pesaing,
                "headroom": round(headroom, 2),
                "headroom_bawah": round(headroom_bawah, 2),
            }
        )

    # Dua skor dari SATU pembentangan yang sama. Kalau batas bawah dibentangkan
    # sendiri, ia akan ikut meregang memenuhi 0-100 dan berhenti terbaca sebagai
    # "lebih rendah daripada skornya" - padahal justru selisih itulah maknanya.
    semua = [e["headroom"] for e in entries] + [e["headroom_bawah"] for e in entries]
    bentang = _scale_to_100(semua)
    n = len(entries)
    for entry, atas, bawah in zip(entries, bentang[:n], bentang[n:]):
        entry["tsi"] = round(atas, 2)
        entry["tsi_bawah"] = round(min(bawah, atas), 2)

    # Diurutkan memakai BATAS BAWAH, bukan skornya. Stasiun yang pesaing dalam
    # stasiunnya belum pernah diperiksa membawa ketidakpastian lebih besar,
    # sehingga batas bawahnya jatuh lebih jauh - dan ia tidak bisa menang hanya
    # karena pesaingnya belum sempat dihitung. Begitu surveinya masuk,
    # ketidakpastiannya mengecil dan peringkatnya naik dengan sendirinya.
    entries.sort(key=lambda e: (-e["tsi_bawah"], -e["tsi"], e["name"]))
    for position, entry in enumerate(entries, start=1):
        entry["rank"] = position

    return entries


def compute_all(db: Session, minutes: int, sumber: str = "mapid") -> list[dict]:
    """Hitung TSI untuk semua kategori tenant sekaligus."""
    result: list[dict] = []
    for category in TENANT_CATEGORIES:
        result.extend(compute_category(db, category, minutes, sumber))
    return result
