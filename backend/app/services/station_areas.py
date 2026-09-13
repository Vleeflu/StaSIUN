"""Area pengamatan di satu stasiun: bahan katalog Ad-Space dan Tenant per area.

KENAPA AREA DIBENTUK DARI TITIK ACTIVITY, BUKAN DIGAMBAR TANGAN
---------------------------------------------------------------
Katalog Ad-Space dan Tenant yang berguna dibaca per AREA ("Peron 1-2",
"Concourse sisi museum"), bukan per stasiun. Tetapi Activity tidak punya
poligon - hanya titik tempat surveyor berdiri. Menggambar zona indoor per
stasiun (N3) butuh denah yang tidak kita punya.

Maka area diturunkan dari titik itu sendiri: SATU titik survei jadi SATU entri
katalog. Nama areanya diambil dari judul post Activity, yang memang ditulis
surveyor sebagai nama lokasi ("Peron 1 Stasiun Sudirman", "Gate Tap In Lantai
Dua").

Versi sebelumnya menggabungkan titik berdekatan dengan `ST_ClusterDBSCAN`
(eps 35 m) supaya katalog terbaca "per area". Itu dibuang 12 Sep atas keputusan
Villyan: di Sudirman, empat lokasi iklan yang berbeda - Peron 1, Peron 2,
koridor pintu masuk, concourse atas - melebur jadi satu entri, sehingga katalog
menampilkan "1 ruang iklan" untuk stasiun yang punya empat titik.

Pelajarannya lebih umum daripada satu angka eps yang keliru: Activity memberi
TITIK, dan memaksanya jadi poligon menambahkan batas yang tidak pernah diukur
siapa pun. Titik dibiarkan sebagai titik.

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

import re
from collections import defaultdict
from statistics import median_low

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.profil_paparan import (
    format_iklan_dari_singgah,
    profil_paparan,
    sektor_iklan,
    waktu_singgah_narasi)

# Titik lebih jauh dari ini dianggap "kawasan sekitar", bukan area stasiun.
# Ad-Space dan Tenant yang dijual KAI ada di dalam dan menempel stasiun; titik
# Activity umum 800 meter jauhnya (bazar, ruko) tetap ditampilkan, tetapi
# dipisahkan supaya tidak terbaca sebagai inventaris stasiun.
#
# Sempat 250 m, dan itu TERLALU LONGGAR. Di Sudirman, 91 dari 96 titik lolos
# ambang itu dan semuanya berlabel "di dalam stasiun" - termasuk titik 242 m
# yang jelas berdiri di luar gedung. Label yang benar untuk hampir semua hal
# berhenti membedakan apa pun.
#
# 120 m dipilih karena stasiun disimpan sebagai SATU TITIK, biasanya di tengah
# peron, sedangkan peron KRL rangkaian 12 kereta panjangnya sekitar 240 m. Jadi
# setengah panjang peron - 120 m - adalah jarak terjauh yang masih masuk akal
# disebut "di dalam stasiun" diukur dari titik tengahnya.
#
# Angka ini tetap perkiraan: kita tidak punya poligon gedung stasiun, hanya
# titik. Karena itu jaraknya sekarang SELALU ikut ditampilkan di samping
# labelnya, supaya pembaca bisa menilai sendiri dan tidak bergantung pada satu
# ambang yang tidak bisa kami buktikan.
BATAS_AREA_STASIUN_M = 120

# Awalan dan akhiran kerja surveyor, dibuang dari judul yang dibaca pengguna.
#
# Nama titik ditulis surveyor untuk keperluannya sendiri, jadi banyak yang
# berbentuk "Survei 41 - Franchise Auntie Anne's" atau "Terowongan Stasium
# Sudirman Survei". Nomor urut dan kata "survei" itu penting saat mencatat di
# lapangan, tetapi di katalog ia cuma kebisingan: pembaca sedang mencari tempat,
# bukan mencari nomor catatan.
#
# Yang dibuang HANYA awalan dan akhirannya. Isi judulnya tidak pernah disentuh -
# surveyor yang tahu apa yang dilihatnya, dan menyunting lebih jauh berarti
# menebak maksud orang lain.
_AWALAN_SURVEI = re.compile(r"^\s*surve[iy]\s*\d*\s*[-:,  ]?\s*", re.IGNORECASE)
_AKHIRAN_SURVEI = re.compile(r"\s*[-:,  ]?\s*surve[iy]\s*$", re.IGNORECASE)


def _judul_bersih(nama: str | None) -> str:
    if not nama:
        return "Tanpa judul"

    bersih = _AKHIRAN_SURVEI.sub("", _AWALAN_SURVEI.sub("", nama)).strip()

    # Kalau yang tersisa kosong, judul aslinya memang cuma penanda kerja -
    # lebih baik menampilkannya apa adanya daripada baris tanpa nama.
    if not bersih:
        return nama.strip()

    # Huruf pertama dibesarkan hanya kalau seluruh kata pertamanya huruf kecil,
    # supaya "halte bus" jadi "Halte bus" tanpa merusak "iPhone" atau "BNI".
    if bersih[0].islower():
        bersih = bersih[0].upper() + bersih[1:]

    return bersih

SQL_TITIK = text(
    """
    WITH berisi AS (
        SELECT ap.id, ap.name, ap.provenance, ap.photo_urls, ap.observed_at,
               ap.location, ap.narrative,
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
    SELECT id, name, provenance, photo_urls, observed_at, jarak_m, narrative,
           ST_X(location) AS lon, ST_Y(location) AS lat
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
    titik = db.execute(SQL_TITIK, {"sid": station_id}).mappings().all()

    # Profil paparan tingkat stasiun dihitung SEKALI, lalu dipakai seluruh
    # katalog. Kelompok pengunjung berlaku untuk kawasan, sedangkan yang
    # berbeda antar-titik adalah pola singgahnya - dan justru perpaduan
    # keduanya yang menentukan sektor apa yang masuk akal beriklan di sana.
    paparan = profil_paparan(db, station_id)
    ids = [t["id"] for t in titik]

    iklan = _per_titik(
        db,
        "SELECT activity_point_id, media_type, media_count, status, visibility_note "
        "FROM ad_spots WHERE activity_point_id = ANY(:ids)",
        ids)
    tenant = _per_titik(
        db,
        "SELECT activity_point_id, name, category, status "
        "FROM tenants WHERE activity_point_id = ANY(:ids)",
        ids)
    rating = _per_titik(
        db,
        "SELECT activity_point_id, time_window, rating, scale_min, scale_max, respondent_ref "
        "FROM crowd_ratings WHERE activity_point_id = ANY(:ids)",
        ids)
    fasilitas = _per_titik(
        db,
        "SELECT activity_point_id, issue_type, description, sentiment_score "
        "FROM facility_issues WHERE activity_point_id = ANY(:ids)",
        ids)

    # SATU TITIK SURVEI = SATU KATALOG. Titik dibiarkan sebagai titik.
    kelompok: dict[int, list] = defaultdict(list)
    for t in titik:
        kelompok[t["id"]].append(t)

    areas = []
    for anggota in kelompok.values():
        pid = [t["id"] for t in anggota]
        semua_iklan = [i for p in pid for i in iklan[p]]
        semua_tenant = [i for p in pid for i in tenant[p]]
        semua_rating = [i for p in pid for i in rating[p]]
        semua_fasilitas = [i for p in pid for i in fasilitas[p]]

        # Nama area diambil dari judul post Activity-nya.
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
        singgah = waktu_singgah_narasi([t["narrative"] for t in anggota if t["narrative"]])
        # Kalau narasi titik ini tidak menyebut perilaku singgah sama sekali,
        # pakai pola tingkat stasiun - DENGAN penanda, supaya pembaca tahu
        # angkanya bukan dari titik itu sendiri. Membiarkannya kosong berarti
        # katalognya diam justru pada hal yang paling menentukan format iklan.
        if singgah.get("label") == "tidak terbaca" and paparan.waktu_singgah.get(
            "label"
        ) not in (None, "tidak terbaca"):
            singgah = {**paparan.waktu_singgah, "dari_pola_stasiun": True}
        areas.append(
            {
                "id": f"{station_id}-{utama['id']}",
                "nama": _judul_bersih(utama["name"]),
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
                # Waktu singgah dihitung PER AREA, bukan sekali untuk seluruh
                # stasiun. Satu stasiun bisa punya peron yang cuma dilewati dan
                # concourse tempat orang menunggu; menyamakan keduanya membuat
                # rekomendasi format iklan kehilangan gunanya justru di tingkat
                # yang paling dipakai - orang memasang iklan di titik tertentu,
                # bukan di "stasiun" sebagai satu gumpalan.
                "waktu_singgah": singgah,
                "format_iklan": format_iklan_dari_singgah(singgah, paparan.keramaian),
                "sektor_iklan": sektor_iklan(paparan.audiens, singgah),
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
        {"sid": station_id}).mappings().first()
    total_titik = db.execute(
        text("SELECT count(*) FROM activity_points WHERE station_id = :sid"), {"sid": station_id}
    ).scalar_one()

    return {
        "station_id": station_id,
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
