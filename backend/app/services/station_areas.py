"""Area pengamatan di satu stasiun: bahan katalog Ad-Space dan Tenant per area.

KENAPA AREA DIBENTUK DARI TITIK ACTIVITY, BUKAN DIGAMBAR TANGAN
---------------------------------------------------------------
Katalog Ad-Space dan Tenant yang berguna dibaca per AREA ("Peron 1-2",
"Concourse sisi museum"), bukan per stasiun. Tetapi Activity tidak punya
poligon - hanya titik tempat surveyor berdiri. Menggambar zona indoor per
stasiun (N3) butuh denah yang tidak kita punya.

Maka area diturunkan dari titik itu sendiri: titik-titik yang jaraknya
berdekatan dikelompokkan dengan `ST_ClusterDBSCAN` (pengelompokan berbasis
kepadatan - titik dianggap satu kelompok kalau jaraknya ke tetangga terdekat di
bawah `eps`). Nama areanya diambil dari judul post Activity, yang memang ditulis
surveyor sebagai nama lokasi.

Konsekuensi yang harus diakui: dua sisi peron yang berjarak kurang dari `eps`
bisa tergabung, dan satu koridor panjang bisa terpecah. `eps` 35 meter dipilih
kira-kira sepanjang satu rangkaian 3 kereta KRL; itu pilihan kami, bukan dari
PRD.

APA YANG DIHITUNG PER AREA
--------------------------
  media iklan    jumlah per jenis dan status (terpakai/kosong), dari ad_spots
  tenant         nama, kategori, status, dari tenants
  keramaian      median per rentang waktu, dari crowd_ratings - dinormalisasi
                 (r - min) / (max - min) lalu MEDIAN DISKRET, sama dengan
                 indikator skor (PRD hal. 10)
  fasilitas      catatan kondisi beserta polaritasnya, dari facility_issues

Semuanya hasil ukur. Tidak ada estimasi, tidak ada shrinkage di sini - katalog
menunjukkan apa yang benar-benar dicatat di lapangan.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import median_low

from sqlalchemy import text
from sqlalchemy.orm import Session

EPS_METER = 35
# Titik lebih jauh dari ini dianggap "kawasan sekitar", bukan area stasiun.
# Ad-Space dan Tenant yang dijual KAI ada di dalam dan menempel stasiun; titik
# Activity umum 800 meter jauhnya (bazar, ruko) tetap ditampilkan, tetapi
# dipisahkan supaya tidak terbaca sebagai inventaris stasiun.
BATAS_AREA_STASIUN_M = 250

SQL_TITIK = text(
    """
    WITH berisi AS (
        SELECT ap.id, ap.name, ap.provenance, ap.photo_urls, ap.observed_at,
               ap.location,
               ST_Distance(ST_Transform(ap.location, 32748),
                           ST_Transform(s.location, 32748)) AS jarak_m
          FROM activity_points ap
          JOIN stations s ON s.id = ap.station_id
         WHERE ap.station_id = :sid
           AND (EXISTS (SELECT 1 FROM ad_spots a WHERE a.activity_point_id = ap.id)
             OR EXISTS (SELECT 1 FROM tenants t WHERE t.activity_point_id = ap.id)
             OR EXISTS (SELECT 1 FROM crowd_ratings c WHERE c.activity_point_id = ap.id)
             OR EXISTS (SELECT 1 FROM facility_issues f WHERE f.activity_point_id = ap.id))
    )
    SELECT id, name, provenance, photo_urls, observed_at, jarak_m,
           ST_X(location) AS lon, ST_Y(location) AS lat,
           ST_ClusterDBSCAN(ST_Transform(location, 32748), eps := :eps, minpoints := 1)
               OVER () AS klaster
      FROM berisi
     ORDER BY jarak_m
    """
)


def _per_titik(db: Session, sql: str, ids: list[int]) -> dict[int, list[dict]]:
    hasil: dict[int, list[dict]] = defaultdict(list)
    if not ids:
        return hasil
    for r in db.execute(text(sql), {"ids": ids}).mappings().all():
        hasil[r["activity_point_id"]].append(dict(r))
    return hasil


def _profil_keramaian(rating: list[dict]) -> dict:
    per_jendela: dict[str, list[float]] = defaultdict(list)
    for r in rating:
        per_jendela[r["time_window"]].append(
            (r["rating"] - r["scale_min"]) / (r["scale_max"] - r["scale_min"])
        )
    profil = {}
    for jendela in ("pagi", "siang", "sore"):
        nilai = per_jendela.get(jendela)
        if not nilai:
            profil[jendela] = None
            continue
        normal = median_low(sorted(nilai))
        profil[jendela] = {
            "normal": round(normal, 3),
            # Padanan skala 1-5, HANYA untuk ditampilkan.
            "setara_1_5": round(1 + 4 * normal, 1),
            "jumlah_penilaian": len(nilai),
        }
    return profil


def area_stasiun(db: Session, station_id: int) -> dict:
    titik = db.execute(SQL_TITIK, {"sid": station_id, "eps": EPS_METER}).mappings().all()
    ids = [t["id"] for t in titik]

    iklan = _per_titik(
        db,
        "SELECT activity_point_id, media_type, media_count, status, visibility_note "
        "FROM ad_spots WHERE activity_point_id = ANY(:ids)",
        ids,
    )
    tenant = _per_titik(
        db,
        "SELECT activity_point_id, name, category, status "
        "FROM tenants WHERE activity_point_id = ANY(:ids)",
        ids,
    )
    rating = _per_titik(
        db,
        "SELECT activity_point_id, time_window, rating, scale_min, scale_max, respondent_ref "
        "FROM crowd_ratings WHERE activity_point_id = ANY(:ids)",
        ids,
    )
    fasilitas = _per_titik(
        db,
        "SELECT activity_point_id, issue_type, description, sentiment_score "
        "FROM facility_issues WHERE activity_point_id = ANY(:ids)",
        ids,
    )

    kelompok: dict[int, list] = defaultdict(list)
    for t in titik:
        kelompok[t["klaster"]].append(t)

    areas = []
    for anggota in kelompok.values():
        pid = [t["id"] for t in anggota]
        semua_iklan = [i for p in pid for i in iklan[p]]
        semua_tenant = [i for p in pid for i in tenant[p]]
        semua_rating = [i for p in pid for i in rating[p]]
        semua_fasilitas = [i for p in pid for i in fasilitas[p]]

        # Nama area: judul post yang paling banyak membawa isi. Judul lain ikut
        # dikirim, supaya penggabungan oleh DBSCAN bisa diperiksa pembaca.
        def bobot_isi(t):
            p = t["id"]
            return len(iklan[p]) + len(tenant[p]) + len(rating[p]) + len(fasilitas[p])

        utama = max(anggota, key=bobot_isi)
        per_jenis: dict[str, dict] = defaultdict(lambda: {"terpakai": 0, "kosong": 0})
        for i in semua_iklan:
            per_jenis[i["media_type"]][i["status"]] += i["media_count"]

        foto = []
        for t in anggota:
            for url in (t["photo_urls"] or [])[:2]:
                if len(foto) < 4:
                    foto.append(url)

        jarak = min(t["jarak_m"] for t in anggota)
        areas.append(
            {
                "id": f"{station_id}-{utama['id']}",
                "nama": utama["name"] or "Tanpa judul",
                "judul_lain": sorted({t["name"] for t in anggota if t["name"]} - {utama["name"]}),
                "jumlah_titik": len(anggota),
                "dari_survey_tim": sum(1 for t in anggota if t["provenance"] == "survey tim"),
                "jarak_m": round(jarak),
                "di_stasiun": jarak <= BATAS_AREA_STASIUN_M,
                "lon": utama["lon"],
                "lat": utama["lat"],
                "foto": foto,
                "iklan": {
                    "total": sum(i["media_count"] for i in semua_iklan),
                    "kosong": sum(i["media_count"] for i in semua_iklan if i["status"] == "kosong"),
                    "per_jenis": [
                        {"jenis": j, **v} for j, v in sorted(per_jenis.items())
                    ],
                    "kutipan": [i["visibility_note"] for i in semua_iklan if i["visibility_note"]][:3],
                },
                "tenant": [
                    {"nama": t["name"], "kategori": t["category"], "status": t["status"]}
                    for t in semua_tenant
                ],
                "keramaian": _profil_keramaian(semua_rating),
                "narasumber": sorted(
                    {r["respondent_ref"] for r in semua_rating if r["respondent_ref"]}
                ),
                "fasilitas": [
                    {
                        "jenis": f["issue_type"],
                        "ringkasan": f["description"],
                        "sentimen": f["sentiment_score"],
                    }
                    for f in semua_fasilitas
                ],
            }
        )

    areas.sort(key=lambda a: (not a["di_stasiun"], a["jarak_m"]))

    semua_rating = [i for p in ids for i in rating[p]]
    semua_iklan = [i for p in ids for i in iklan[p]]
    semua_fasilitas = [i for p in ids for i in fasilitas[p]]
    arketipe = db.execute(
        text(
            """
            SELECT ae.archetype, count(*) AS n
              FROM activity_extractions ae
              JOIN activity_points ap ON ap.id = ae.activity_point_id
             WHERE ap.station_id = :sid
             GROUP BY ae.archetype ORDER BY n DESC LIMIT 1
            """
        ),
        {"sid": station_id},
    ).mappings().first()
    total_titik = db.execute(
        text("SELECT count(*) FROM activity_points WHERE station_id = :sid"), {"sid": station_id}
    ).scalar_one()

    return {
        "station_id": station_id,
        "eps_meter": EPS_METER,
        "batas_area_stasiun_m": BATAS_AREA_STASIUN_M,
        "ringkasan": {
            "titik_activity": total_titik,
            "titik_berisi": len(ids),
            "keramaian": _profil_keramaian(semua_rating),
            "jumlah_penilaian_keramaian": len(semua_rating),
            "media_iklan": sum(i["media_count"] for i in semua_iklan) if semua_iklan else None,
            "media_iklan_kosong": (
                sum(i["media_count"] for i in semua_iklan if i["status"] == "kosong")
                if semua_iklan
                else None
            ),
            "tenant_tercatat": sum(len(tenant[p]) for p in ids),
            "fasilitas_positif": sum(1 for f in semua_fasilitas if (f["sentiment_score"] or 0) > 0),
            "fasilitas_negatif": sum(1 for f in semua_fasilitas if (f["sentiment_score"] or 0) < 0),
            "arketipe": arketipe["archetype"] if arketipe else None,
        },
        "areas": areas,
    }
