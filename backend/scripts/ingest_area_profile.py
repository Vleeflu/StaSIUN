"""Isi `area_profile` (N5 / F2-3) dari poligon guna lahan OpenStreetMap.

Kenapa poligon, bukan titik minat yang sudah kita punya. Tabel `poi` berisi
52.278 titik, tetapi sinyal HUNIAN praktis tidak ada di sana: hanya 25 baris
bertag `building=residential|apartments` dan NOL bertag `landuse=residential`.
Sebabnya struktural - importer POI mengambil titik minat (toko, kantor,
sekolah), sedangkan permukiman di OSM dipetakan sebagai POLIGON guna lahan,
bukan titik. Maka "profil kawasan" yang diminta PRD Tabel 3 memang tidak bisa
dijawab dari data yang sudah ada, dan harus ditarik terpisah.

Cara kerjanya:

1. Tarik poligon `landuse` dan `building` di sekitar tiap stasiun lewat
   Overpass dengan `out geom` - berbeda dari `osm.py` yang memakai
   `out center tags`, karena di sini yang dihitung LUAS, bukan jumlah titik.
2. Masukkan poligon itu ke tabel sementara di PostGIS.
3. Potong dengan poligon isochrone tiap stasiun, lalu jumlahkan luas per kelas.
   Batas kawasan memakai isochrone, bukan lingkaran, konsisten dengan
   ADJUSTMENT 8.6.
4. Simpan proporsinya ke `area_profile` beserta sumber dan tanggal akses,
   sebagaimana disyaratkan PRD.

Batas yang diketahui dan disengaja:

- Hanya `way` bergeometri tertutup yang dipakai. Relation multipolygon dilewati
  karena merakitnya butuh penanganan cincin luar/dalam yang tidak sebanding
  manfaatnya di sini. Jumlah yang dilewati DILAPORKAN, tidak disembunyikan.
- Poligon sekelas yang bertumpuk digabung dengan ST_Union sebelum diukur,
  supaya luas yang sama tidak terhitung dua kali.
- Proporsi dihitung terhadap luas yang BERHASIL diklasifikasi, bukan terhadap
  luas isochrone. Ruang tanpa tag guna lahan di OSM artinya "tidak diamati",
  dan memasukkannya sebagai penyebut akan menyatakan seolah kawasan itu kosong.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import date
from pathlib import Path

from sqlalchemy import text

from app.core.database import SessionLocal
from app.services.osm import ENDPOINTS, fetch

log = logging.getLogger(__name__)

# Pemetaan tag OSM -> kelas kawasan. Sengaja sempit: tag yang maknanya
# bercabang (misalnya `landuse=commercial`, yang bisa kantor bisa pertokoan)
# ditaruh di kelas yang paling sering benar, dan dicatat di sini supaya
# keputusannya bisa diperdebatkan orang lain, bukan tersembunyi di dalam kode.
KELAS_LANDUSE = {
    "residential": "hunian",
    "commercial": "kantor",
    "retail": "niaga",
    "industrial": "industri",
}
KELAS_BUILDING = {
    "apartments": "hunian",
    "residential": "hunian",
    "house": "hunian",
    "dormitory": "hunian",
    "office": "kantor",
    "commercial": "kantor",
    "retail": "niaga",
    "supermarket": "niaga",
}

# Kelas WISATA, ditambahkan atas permintaan Villyan. Stasiun Jakarta Kota
# dikelilingi Kota Tua - Museum Bank Mandiri, Museum Fatahillah, Museum Wayang -
# dan tanpa kelas ini seluruh kawasan itu terbaca "kantor" atau "niaga" saja.
# Bedanya menentukan: pengunjung museum datang siang dan akhir pekan, berjalan
# santai, dan terbuka pada iklan bernada berbeda dari komuter yang bergegas.
# Narasi survey Villyan sendiri menyebut "pelajar dan pengunjung museum" sebagai
# ramai akhir pekan pukul 10-12.
#
# Hotel SENGAJA tidak dimasukkan. Ia memang bagian industri pariwisata, tetapi
# yang diukur di sini fungsi RUANG yang menarik orang datang, bukan tempat
# orang menginap - dan memasukkannya akan membuat kawasan hotel bisnis di
# Sudirman terbaca sebagai kawasan wisata.
KELAS_TOURISM = {
    "museum": "wisata",
    "attraction": "wisata",
    "gallery": "wisata",
    "theme_park": "wisata",
    "zoo": "wisata",
    "aquarium": "wisata",
    "viewpoint": "wisata",
}
KELAS_HISTORIC = {
    "monument": "wisata",
    "memorial": "wisata",
    "building": "wisata",
    "castle": "wisata",
    "ruins": "wisata",
    "city_gate": "wisata",
}

SUMBER_LANTAI = "overpass-landuse-lantai"

RADIUS_M = 1500  # melampaui isochrone 15 menit (rata-rata 2,35 km2 ~ jari-jari 865 m)


def bangun_kueri(pusat: list[tuple[float, float]], radius_m: int = RADIUS_M) -> str:
    """Kueri Overpass untuk poligon guna lahan di sekitar beberapa stasiun."""
    landuse = "|".join(KELAS_LANDUSE)
    building = "|".join(KELAS_BUILDING)
    tourism = "|".join(KELAS_TOURISM)
    historic = "|".join(KELAS_HISTORIC)
    bagian = "".join(
        f'way(around:{radius_m},{lat},{lon})["landuse"~"^({landuse})$"];'
        f'way(around:{radius_m},{lat},{lon})["building"~"^({building})$"];'
        f'way(around:{radius_m},{lat},{lon})["tourism"~"^({tourism})$"];'
        f'way(around:{radius_m},{lat},{lon})["historic"~"^({historic})$"];'
        for lat, lon in pusat
    )
    return f"[out:json][timeout:180];({bagian});out geom;"


def kelas_elemen(tags: dict) -> str | None:
    """Kelas kawasan sebuah elemen.

    Urutan menangnya: `landuse` (hamparan tanah), lalu `tourism`/`historic`,
    baru `building`. Wisata ditaruh di atas `building` dengan sengaja - Museum
    Fatahillah bertag `building=yes` sekaligus `tourism=museum`, dan yang kita
    maksud jelas museumnya, bukan sekadar "ada bangunan di sana".
    """
    if (lu := tags.get("landuse")) in KELAS_LANDUSE:
        return KELAS_LANDUSE[lu]
    if (tr := tags.get("tourism")) in KELAS_TOURISM:
        return KELAS_TOURISM[tr]
    if (hi := tags.get("historic")) in KELAS_HISTORIC:
        return KELAS_HISTORIC[hi]
    if (bd := tags.get("building")) in KELAS_BUILDING:
        return KELAS_BUILDING[bd]
    return None


def jenis_elemen(tags: dict) -> str:
    """`landuse` atau `building` - dua hal yang diperlakukan berbeda saat dibobot.

    Poligon `landuse` adalah hamparan tanah tanpa jumlah lantai; poligon
    `building` punya tapak dan (kadang) jumlah lantai. Pembobotan lantai hanya
    masuk akal untuk yang kedua.
    """
    return "landuse" if tags.get("landuse") in KELAS_LANDUSE else "building"


def lantai_elemen(tags: dict) -> int | None:
    """Jumlah lantai dari tag OSM, atau None kalau tidak tertulis.

    None SENGAJA tidak diganti 1 di sini. Perbedaan antara "bangunan satu
    lantai" dan "tinggi bangunannya tidak diketahui" harus tetap terlihat
    sampai ke laporan, supaya pembaca tahu seberapa banyak yang ditebak.
    """
    nilai = tags.get("building:levels")
    if nilai is None:
        return None
    try:
        # OSM memuat "4", "4.5", dan kadang "4;5" untuk bangunan bertingkat
        # tidak seragam. Ambil angka pertama, bulatkan ke bawah.
        lantai = int(float(str(nilai).split(";")[0].strip()))
    except (ValueError, TypeError):
        return None
    # Batas atas 100: ada tag OSM yang jelas keliru (gedung 999 lantai), dan
    # satu baris seperti itu cukup untuk mendominasi seluruh perhitungan.
    return lantai if 1 <= lantai <= 100 else None


def ke_wkt(geometry: list[dict]) -> str | None:
    """Ubah daftar titik Overpass jadi WKT POLYGON, atau None kalau tak layak.

    Cincin wajib tertutup. Overpass kadang mengirim way terbuka (garis, bukan
    area); itu ditutup sendiri, dan yang titiknya terlalu sedikit dibuang -
    menutup paksa sesuatu yang bukan area akan mengarang luas.
    """
    if not geometry or len(geometry) < 4:
        return None
    titik = [(p["lon"], p["lat"]) for p in geometry if "lon" in p and "lat" in p]
    if len(titik) < 4:
        return None
    if titik[0] != titik[-1]:
        titik.append(titik[0])
    isi = ", ".join(f"{lon} {lat}" for lon, lat in titik)
    return f"POLYGON(({isi}))"


def tarik(
    stasiun: list[tuple[int, float, float]], per_kueri: int, jeda: float
) -> list[dict]:
    """Tarik poligon untuk seluruh stasiun, beberapa pusat sekaligus per kueri."""
    semua: list[dict] = []
    dilewati_relation = 0
    dilewati_geometri = 0

    for i in range(0, len(stasiun), per_kueri):
        potongan = stasiun[i : i + per_kueri]
        pusat = [(lat, lon) for _, lat, lon in potongan]
        log.info(
            "Overpass %d-%d dari %d stasiun", i + 1, i + len(potongan), len(stasiun)
        )
        elemen = fetch(bangun_kueri(pusat))

        for e in elemen:
            if e.get("type") != "way":
                dilewati_relation += 1
                continue
            kelas = kelas_elemen(e.get("tags") or {})
            if kelas is None:
                continue
            wkt = ke_wkt(e.get("geometry") or [])
            if wkt is None:
                dilewati_geometri += 1
                continue
            tags = e.get("tags") or {}
            semua.append(
                {
                    "osm_id": e["id"],
                    "kelas": kelas,
                    "jenis": jenis_elemen(tags),
                    "lantai": lantai_elemen(tags),
                    "wkt": wkt,
                }
            )

        if i + per_kueri < len(stasiun):
            time.sleep(jeda)

    bangunan = [x for x in semua if x["jenis"] == "building"]
    berlantai = [x for x in bangunan if x["lantai"] is not None]
    log.info(
        "Poligon terpakai %d | relation dilewati %d | geometri tak layak %d",
        len(semua),
        dilewati_relation,
        dilewati_geometri,
    )
    log.info(
        "Bangunan %d, di antaranya %d (%.0f%%) punya tag building:levels. "
        "Sisanya dihitung 1 lantai.",
        len(bangunan),
        len(berlantai),
        100 * len(berlantai) / (len(bangunan) or 1),
    )
    return semua


SQL_STASIUN = """
SELECT i.station_id,
       ST_Y(ST_Centroid(i.geom)) AS lat,
       ST_X(ST_Centroid(i.geom)) AS lon
  FROM isochrones i
 WHERE i.minutes = :menit
 ORDER BY i.station_id
"""

SQL_TEMP = """
CREATE TEMP TABLE lu_sementara (
    osm_id BIGINT,
    kelas  TEXT,
    jenis  TEXT,
    lantai INTEGER,
    geom   geometry(Geometry, 4326)
)
"""

SQL_ISI_TEMP = """
INSERT INTO lu_sementara (osm_id, kelas, jenis, lantai, geom)
VALUES (:osm_id, :kelas, :jenis, :lantai, ST_MakeValid(ST_GeomFromText(:wkt, 4326)))
"""

# ST_Union per kelas sebelum ST_Area: tanpa itu, dua poligon hunian yang
# bertumpuk membuat luas hunian lebih besar daripada luas kawasannya sendiri.
SQL_HITUNG = """
SELECT i.station_id,
       COALESCE(ST_Area(ST_Union(ST_Intersection(l.geom, i.geom))
                FILTER (WHERE l.kelas = 'hunian')::geography), 0)   AS hunian,
       COALESCE(ST_Area(ST_Union(ST_Intersection(l.geom, i.geom))
                FILTER (WHERE l.kelas = 'kantor')::geography), 0)   AS kantor,
       COALESCE(ST_Area(ST_Union(ST_Intersection(l.geom, i.geom))
                FILTER (WHERE l.kelas = 'niaga')::geography), 0)    AS niaga,
       COALESCE(ST_Area(ST_Union(ST_Intersection(l.geom, i.geom))
                FILTER (WHERE l.kelas = 'industri')::geography), 0) AS industri,
       COALESCE(ST_Area(ST_Union(ST_Intersection(l.geom, i.geom))
                FILTER (WHERE l.kelas = 'wisata')::geography), 0)   AS wisata
  FROM isochrones i
  JOIN lu_sementara l
    ON ST_Intersects(l.geom, i.geom)
 WHERE i.minutes = :menit
   AND i.station_id = ANY(:hanya)
 GROUP BY i.station_id
"""

# Catatan penting soal `i.station_id = ANY(:hanya)`.
#
# Isochrone antar-stasiun SALING TUMPANG TINDIH - di koridor Sudirman
# jangkauan 10 menit beberapa stasiun berpotongan. Tanpa penyaring ini,
# menarik poligon untuk 3 stasiun menghasilkan 16 baris profil: stasiun yang
# TIDAK ditanya ikut terhitung dari poligon yang kebetulan menyenggol
# isochrone-nya. Profil semacam itu dihitung dari cakupan poligon yang tidak
# lengkap, jadi proporsinya menyesatkan - dan diam-diam, karena angkanya tetap
# tampak wajar. Yang ditulis hanya stasiun yang pusatnya benar-benar ditarik.

# Proporsi berbobot lantai - jawaban atas cacat yang ditemukan Villyan.
#
# Versi berbasis luas tanah menyatakan BNI City 57% hunian. Ditelusuri, 71%
# dari luas hunian itu berasal dari SATU poligon kampung 6,9 hektar
# (OSM way 483113879, dikelilingi Balai RW dan Posyandu), sementara Wisma 46 -
# salah satu menara tertinggi di Jakarta - hanya menyumbang 4.106 m2 tapak.
# Kampung menang telak dalam hektar, menara menang telak dalam manusia, dan
# untuk profil paparan yang menentukan jelas yang kedua.
#
# Rumusnya:
#   bangunan -> luas tapak x jumlah lantai (tanpa tag lantai dihitung 1)
#   guna lahan -> luas SISA setelah dikurangi seluruh tapak bangunan, x 1
#
# Pengurangan tapak itu yang menjaga keseimbangan. Tanpa ia, poligon
# `landuse=residential` yang menaungi apartemen akan terhitung dua kali.
# Dengan ia, kampung yang di OSM hanya dipetakan sebagai hamparan tanah tetap
# ikut terhitung - satu lantai, sebagaimana kenyataannya - alih-alih hilang
# sama sekali seperti kalau kita hanya menghitung bangunan.
SQL_HITUNG_LANTAI = """
WITH iso AS (
    SELECT station_id, geom
      FROM isochrones
     WHERE minutes = :menit AND station_id = ANY(:hanya)
),
pot AS (
    SELECT i.station_id, l.kelas, l.jenis, COALESCE(l.lantai, 1) AS lantai,
           ST_Intersection(l.geom, i.geom) AS g
      FROM lu_sementara l
      JOIN iso i ON ST_Intersects(l.geom, i.geom)
),
bangunan AS (
    SELECT station_id, kelas, SUM(ST_Area(g::geography) * lantai) AS luas
      FROM pot WHERE jenis = 'building'
     GROUP BY station_id, kelas
),
tapak AS (
    SELECT station_id, ST_Union(g) AS g
      FROM pot WHERE jenis = 'building'
     GROUP BY station_id
),
lahan AS (
    -- Subkueri, bukan MAX(t.g): PostgreSQL tidak punya agregat MAX untuk
    -- geometry. `tapak` sudah satu baris per stasiun, jadi subkueri skalar
    -- adalah bentuk yang benar sekaligus yang paling terbaca.
    SELECT p.station_id, p.kelas,
           ST_Area(ST_Difference(
               ST_Union(p.g),
               COALESCE(
                   (SELECT t.g FROM tapak t WHERE t.station_id = p.station_id),
                   ST_GeomFromText('POLYGON EMPTY', 4326)
               )
           )::geography) AS luas
      FROM pot p
     WHERE p.jenis = 'landuse'
     GROUP BY p.station_id, p.kelas
)
SELECT station_id, kelas, SUM(luas) AS luas
  FROM (SELECT station_id, kelas, luas FROM bangunan
        UNION ALL
        SELECT station_id, kelas, luas FROM lahan) x
 GROUP BY station_id, kelas
"""

SQL_SIMPAN = """
INSERT INTO area_profile
       (station_id, profile, office_share, residential_share, komposisi,
        source, source_url, accessed_at)
VALUES (:station_id, :profile, :office_share, :residential_share,
        CAST(:komposisi AS jsonb),
        :source, :source_url, :accessed_at)
ON CONFLICT (station_id, source) DO UPDATE
   SET profile           = EXCLUDED.profile,
       office_share      = EXCLUDED.office_share,
       residential_share = EXCLUDED.residential_share,
       komposisi         = EXCLUDED.komposisi,
       source_url        = EXCLUDED.source_url,
       accessed_at       = EXCLUDED.accessed_at,
       updated_at        = now()
"""


# `tetapkan_profil` dengan ambang 0,6 DIHAPUS di sini.
#
# Ia memberi satu label ("hunian"/"perkantoran"/"campuran") dari proporsi luas,
# dan itulah yang membuat Jakarta Kota berlabel "campuran" padahal kelas
# terbesarnya kantor - label dan komposisi bercerita berbeda soal stasiun yang
# sama. Setelah komposisi penuh tersimpan, ambangnya tidak punya pekerjaan lagi:
# `profile` kini diisi kelas terbesar apa adanya, dan pembaca menilai sendiri
# dari porsinya (ADJUSTMENT 9.45).

KELAS_URUT = ("hunian", "kantor", "niaga", "wisata", "industri")


def susun_komposisi(luas: dict[str, float], ukuran: str, catatan: dict) -> dict:
    """Proporsi SELURUH kelas apa adanya, beserta cara ia diukur.

    Kenapa bukan satu label saja. Satu kata membuang informasi yang justru
    menentukan: "campuran 55/45" dan "campuran 90/10" jadi terlihat sama.
    Villyan menunjuk ini langsung - simpan semua kategori dan rasionya, dan
    biarkan pembacanya yang memutuskan.

    `dominasi` adalah porsi kelas terbesar. Ia dipakai untuk tahu apakah
    sebuah label layak dipercaya sama sekali: kawasan dengan dominasi 0,38
    tidak pantas disebut apa pun selain campuran.
    """
    total = sum(luas.get(k, 0.0) for k in KELAS_URUT)
    if total <= 0:
        return {}
    porsi = {k: round(luas.get(k, 0.0) / total, 4) for k in KELAS_URUT}
    terbesar = max(porsi, key=lambda k: porsi[k])
    return {
        "porsi": porsi,
        "luas_m2": {k: round(luas.get(k, 0.0), 1) for k in KELAS_URUT},
        "kelas_terbesar": terbesar,
        "dominasi": porsi[terbesar],
        "ukuran": ukuran,
        **catatan,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Isi area_profile dari guna lahan OSM.")
    p.add_argument("--menit", type=int, default=10, help="pita isochrone sebagai batas kawasan")
    p.add_argument("--per-kueri", type=int, default=3, help="stasiun per permintaan Overpass")
    p.add_argument("--jeda", type=float, default=3.0, help="jeda antar permintaan, detik")
    p.add_argument("--batas", type=int, default=0, help="hanya N stasiun pertama (0 = semua)")
    p.add_argument("--simpan-mentah", default="", help="tulis poligon mentah ke berkas JSON")
    p.add_argument(
        "--dari-berkas",
        default="",
        help="hitung ulang dari berkas poligon mentah, TANPA menghubungi Overpass. "
        "Dipakai untuk audit dan untuk mengubah cara menghitung tanpa menarik "
        "ulang 10 ribu poligon",
    )
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    session = SessionLocal()
    try:
        baris = session.execute(text(SQL_STASIUN), {"menit": args.menit}).all()
        stasiun = [(r.station_id, float(r.lat), float(r.lon)) for r in baris]
        if args.batas:
            stasiun = stasiun[: args.batas]
        if not stasiun:
            raise SystemExit(
                f"Tidak ada isochrone {args.menit} menit. Jalankan importer isochrone dulu."
            )

        print(f"{len(stasiun)} stasiun berisochrone {args.menit} menit.")
        if args.dari_berkas:
            poligon = json.loads(Path(args.dari_berkas).read_text(encoding="utf-8"))
            print(f"{len(poligon)} poligon dibaca dari {args.dari_berkas} (tanpa Overpass).")
        else:
            poligon = tarik(stasiun, args.per_kueri, args.jeda)
        if not poligon:
            raise SystemExit("Tidak ada satu pun poligon guna lahan.")

        bangunan = [x for x in poligon if x.get("jenis") == "building"]
        berlantai = [x for x in bangunan if x.get("lantai") is not None]
        cakupan_lantai = round(len(berlantai) / (len(bangunan) or 1), 3)

        if args.simpan_mentah:
            Path(args.simpan_mentah).write_text(
                json.dumps(poligon, ensure_ascii=False), encoding="utf-8"
            )
            print(f"Poligon mentah ditulis ke {args.simpan_mentah}")

        session.execute(text(SQL_TEMP))
        session.execute(text(SQL_ISI_TEMP), poligon)

        hasil = session.execute(
            text(SQL_HITUNG),
            {"menit": args.menit, "hanya": [sid for sid, _, _ in stasiun]},
        ).all()
        hari_ini = date.today()
        ditulis = 0
        ringkas: dict[str, int] = {}
        profil_luas: dict[int, str] = {}
        komposisi_luas: dict[int, dict] = {}

        for r in hasil:
            luas_kelas = {
                "hunian": float(r.hunian),
                "kantor": float(r.kantor),
                "niaga": float(r.niaga),
                "wisata": float(r.wisata),
                "industri": float(r.industri),
            }
            total = sum(luas_kelas.values())
            if total <= 0:
                continue
            office = luas_kelas["kantor"] / total
            residential = luas_kelas["hunian"] / total
            komposisi_luas[r.station_id] = susun_komposisi(
                luas_kelas,
                ukuran="luas_tanah",
                catatan={
                    "arti": (
                        "porsi LUAS TANAH per fungsi di dalam isochrone. Tidak "
                        "menyatakan jumlah orang maupun jenis pekerjaan mereka."
                    )
                },
            )
            # Label = kelas terbesar apa adanya, TANPA ambang 0,6.
            #
            # Ambang itu warisan desain yang mengandaikan satu label saja, dan
            # ia sempat membuat Jakarta Kota berlabel "campuran" padahal kelas
            # terbesarnya kantor - label dan komposisi bercerita berbeda soal
            # stasiun yang sama. Villyan setuju membiarkan pembaca menilai:
            # yang disajikan komposisi penuh, dan label hanya penunjuk kelas
            # terbesar, bukan kesimpulan.
            profil = komposisi_luas[r.station_id]["kelas_terbesar"]
            ringkas[profil] = ringkas.get(profil, 0) + 1
            profil_luas[r.station_id] = profil
            session.execute(
                text(SQL_SIMPAN),
                {
                    "station_id": r.station_id,
                    "profile": profil,
                    "office_share": round(office, 4),
                    "residential_share": round(residential, 4),
                    "komposisi": json.dumps(komposisi_luas[r.station_id], ensure_ascii=False),
                    "source": "overpass-landuse",
                    "source_url": ENDPOINTS[0],
                    "accessed_at": hari_ini,
                },
            )
            ditulis += 1

        # ---- lajur kedua: berbobot lantai -------------------------------
        #
        # Ditulis sebagai BARIS TERPISAH dengan `source` berbeda, bukan
        # menimpa yang pertama. Keduanya sah menjawab pertanyaan yang berbeda -
        # "guna lahan apa yang menguasai tanah di sini" versus "di mana
        # orangnya" - dan menyimpan keduanya membuat selisihnya bisa diperiksa
        # siapa pun. Penyusun profil paparan memakai yang kedua.
        berbobot: dict[int, dict[str, float]] = {}
        for r in session.execute(
            text(SQL_HITUNG_LANTAI),
            {"menit": args.menit, "hanya": [sid for sid, _, _ in stasiun]},
        ).all():
            berbobot.setdefault(r.station_id, {})[r.kelas] = float(r.luas or 0)

        ditulis_lantai = 0
        ringkas_lantai: dict[str, int] = {}
        pindah: list[tuple[int, str, str]] = []
        for sid, per_kelas in berbobot.items():
            total = sum(per_kelas.values())
            if total <= 0:
                continue
            office = per_kelas.get("kantor", 0.0) / total
            residential = per_kelas.get("hunian", 0.0) / total
            komposisi = susun_komposisi(
                per_kelas,
                ukuran="luas_lantai",
                catatan={
                    "arti": (
                        "porsi LUAS LANTAI TERBANGUN per fungsi (tapak x jumlah "
                        "lantai). Ukuran kapasitas ruang, BUKAN jumlah orang dan "
                        "bukan jenis pekerjaan mereka."
                    ),
                    "bias_diketahui": (
                        "Hamparan guna lahan tanpa bangunan terpetakan dihitung 1 "
                        "lantai. Permukiman padat di OSM sering hanya dipetakan "
                        "sebagai hamparan, sehingga lantainya TERKECILKAN dan "
                        "porsi kantor cenderung terlalu besar."
                    ),
                    "cakupan_tag_lantai": cakupan_lantai,
                },
            )
            profil = komposisi["kelas_terbesar"]
            ringkas_lantai[profil] = ringkas_lantai.get(profil, 0) + 1
            session.execute(
                text(SQL_SIMPAN),
                {
                    "station_id": sid,
                    "profile": profil,
                    "office_share": round(office, 4),
                    "residential_share": round(residential, 4),
                    "komposisi": json.dumps(komposisi, ensure_ascii=False),
                    "source": SUMBER_LANTAI,
                    "source_url": ENDPOINTS[0],
                    "accessed_at": hari_ini,
                },
            )
            ditulis_lantai += 1
            sebelumnya = profil_luas.get(sid)
            if sebelumnya and sebelumnya != profil:
                pindah.append((sid, sebelumnya, profil))

        session.commit()
        print(f"\n{ditulis} baris area_profile ditulis (sumber overpass-landuse).")
        for k, v in sorted(ringkas.items(), key=lambda x: -x[1]):
            print(f"  {k:12} {v}")
        print(f"\n{ditulis_lantai} baris berbobot lantai ditulis (sumber {SUMBER_LANTAI}).")
        for k, v in sorted(ringkas_lantai.items(), key=lambda x: -x[1]):
            print(f"  {k:12} {v}")
        if pindah:
            print(f"\n{len(pindah)} stasiun BERUBAH label setelah dibobot lantai:")
            for sid, a, b in pindah[:20]:
                print(f"  stasiun {sid}: {a} -> {b}")
        if ditulis < len(stasiun):
            print(
                f"  {len(stasiun) - ditulis} stasiun tanpa poligon guna lahan sama sekali "
                "-> sengaja TIDAK ditulis, supaya tidak tercatat sebagai kawasan kosong."
            )
    finally:
        session.close()


if __name__ == "__main__":
    main()
