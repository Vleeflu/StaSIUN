import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.isochrone import Isochrone
from app.models.reference import PassengerVolume, Poi
from app.models.score import StationScore
from app.models.station import Station
from app.models.tenant_score import TenantScore
from app.services.scoring.tenant import CATEGORY_LABEL
from app.services.sponsorship import (
    peluang_sponsorship,
    sebagai_geojson,
)
from app.services.naming_rights import klasifikasi, periksa_daftar, ringkas
from app.services.scoring.exposure import BOBOT_CEI, hitung_cei, kelas_paparan
from app.services.profil_paparan import profil_paparan
from app.services.station_import import KAI_NETWORKS, LINE_ROSTER, normalize
from app.services.station_areas import area_stasiun

# Apa yang masuk akal dikejar di tiap kelas SEPI (PRD hal. 12).
#
# Kelasnya selama ini dihitung dan disimpan, tetapi tidak pernah sampai ke
# layar - sehingga pembaca melihat angka 67,5 tanpa tahu angka itu menyarankan
# apa. Padahal inilah gunanya klasifikasi: menyaring tiga fitur produk menjadi
# satu yang paling relevan untuk stasiun tersebut.
TRIASE = {
    "Low Potential": {
        "fokus": "Ruang iklan dan mesin penjual otomatis",
        "hindari": "Tenant menetap berbiaya tinggi",
        "alasan": (
            "Potensi ekonomi kawasannya terbatas, sehingga usaha menetap "
            "menanggung risiko besar. Ruang iklan tetap bernilai karena ia "
            "menumpang arus orang, bukan daya beli kawasan."
        ),
    },
    "Moderate Potential": {
        "fokus": "Ekspansi UMKM tipe grab-and-go",
        "hindari": "Sewa premium dan komitmen jangka panjang",
        "alasan": (
            "Kawasannya berkembang dengan aktivitas ekonomi menengah. Usaha "
            "cepat saji berperputaran tinggi paling cocok, dengan harga sewa "
            "standar pasar."
        ),
    },
    "Premium Transit Hub": {
        "fokus": "Hak penamaan dan merek korporat besar",
        "hindari": "Menawarkan dengan tarif standar",
        "alasan": (
            "Kawasan bernilai tinggi dengan perputaran transaksi kuat, cukup "
            "untuk menjustifikasi tarif sewa kelas premium."
        ),
    },
}


router = APIRouter(tags=["stations"])


@router.get("/stations")
def list_stations(
    db: Session = Depends(get_db),
    service_type: str | None = Query(default=None, alias="type"),
    minutes: int = Query(default=10, ge=5, le=15),
):
    stmt = select(
        Station.id,
        Station.name,
        Station.code,
        Station.types,
        Station.lines,
        Station.served,
        Station.kecamatan,
        Station.address,
        func.ST_AsGeoJSON(Station.location).label("geom"),
        StationScore.sepi,
        StationScore.rank,
    ).outerjoin(
        # Stasiun tanpa skor tetap ikut terkirim; peta butuh titiknya walau
        # skornya belum dihitung untuk pita waktu ini.
        StationScore,
        (StationScore.station_id == Station.id) & (StationScore.minutes == minutes),
    ).order_by(Station.name)

    if service_type:
        stmt = stmt.where(Station.types.any(service_type))

    rows = db.execute(stmt).all()

    # Stasiun yang benar-benar didatangi tim, beserta apa yang dibawanya pulang.
    #
    # Dipisahkan TEGAS dari confidence, dan itu disengaja. Survei lapangan
    # menghasilkan catatan, foto, inventaris media iklan, dan skala keramaian
    # dari narasumber - bukti yang tidak bisa didapat dari pemetaan. Tetapi ia
    # TIDAK otomatis membuat variabel skor terukur: dari 9 stasiun yang
    # disurvei, hanya Sudirman yang E dan C-nya lengkap. Menyatukan keduanya
    # dalam satu lencana "data lengkap" akan menjadi klaim yang salah untuk
    # delapan stasiun.
    survei = {
        r.station_id: {"titik": r.titik, "skala": r.skala}
        for r in db.execute(
            text(
                """
                SELECT ap.station_id,
                       COUNT(*) FILTER (WHERE ap.provenance = 'survey tim') AS titik,
                       (SELECT COUNT(*) FROM crowd_ratings cr
                         WHERE cr.station_id = ap.station_id) AS skala
                  FROM activity_points ap
                 WHERE ap.station_id IS NOT NULL
                 GROUP BY ap.station_id
                HAVING COUNT(*) FILTER (WHERE ap.provenance = 'survey tim') > 0
                """
            )
        ).all()
    }

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": r.id,
                "geometry": json.loads(r.geom),
                "properties": {
                    "name": r.name,
                    "code": r.code,
                    "types": r.types,
                    "network": r.types[0] if r.types else None,
                    "lines": r.lines,
                    "primary_line": r.lines[0] if r.lines else None,
                    "is_interchange": len(r.lines) > 1,
                    "line_key": "-".join(r.lines) if r.lines else (r.types[0] if r.types else "none"),
                    "served": r.served,
                    "sepi": r.sepi,
                    "sepi_rank": r.rank,
                    "kecamatan": r.kecamatan,
                    "address": r.address,
                    "survei_tim": r.id in survei,
                    "survei_titik": survei.get(r.id, {}).get("titik", 0),
                    "survei_skala": survei.get(r.id, {}).get("skala", 0),
                },
            }
            for r in rows
        ],
    }


@router.get("/stations/{station_id}/score")
def station_score(
    station_id: int,
    db: Session = Depends(get_db),
    minutes: int = Query(default=10, ge=5, le=15),
):
    """Rincian skor SEPI satu stasiun, lengkap dengan angka mentahnya."""
    row = db.execute(
        select(StationScore).where(
            StationScore.station_id == station_id,
            StationScore.minutes == minutes,
        )
    ).scalar_one_or_none()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Skor pita {minutes} menit belum dihitung untuk stasiun ini",
        )

    total = db.execute(
        select(func.count()).select_from(StationScore).where(StationScore.minutes == minutes)
    ).scalar_one()

    volume = db.execute(
        select(PassengerVolume)
        .where(PassengerVolume.station_id == station_id)
        .order_by(PassengerVolume.accessed_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    return {
        "station_id": row.station_id,
        "minutes": row.minutes,
        "sepi": row.sepi,
        "kelas": row.kelas,
        "keputusan": row.keputusan,
        "rank": row.rank,
        "rank_total": total,
        # Persentil, bukan cuma peringkat. Peringkat 23 dari 45 terdengar buruk;
        # "lebih tinggi daripada 49% stasiun" menyampaikan hal yang sama tanpa
        # menyesatkan. Ini juga yang membuat kelas SEPI bisa dibaca - hampir
        # seluruh stasiun jatuh ke kelas Moderate, sehingga kelas sendirian
        # nyaris tidak membedakan apa pun.
        "persentil": round(100.0 * (total - row.rank) / max(total - 1, 1)),
        # Kekokohan peringkat terhadap pilihan pembobotan (ADJUSTMENT 9.30).
        # Peringkat tunggal tanpa ini menyiratkan kepastian yang tidak ada.
        "sensitivity": row.sensitivity,
        # Kedekatan TOPSIS dikirim TERPISAH dan diberi peringatan, supaya panel
        # tidak tergoda memakainya sebagai skor. Nilainya bergantung pada
        # himpunan stasiun yang ikut dinilai (rank reversal), jadi ia hanya sah
        # sebagai pembanding relatif di dalam himpunan yang sama.
        "topsis": row.topsis,
        "topsis_catatan": (
            "Pembanding relatif dalam himpunan yang dinilai. Jangan dipakai "
            "untuk klasifikasi; pakai `sepi`."
        ),
        # Metadata keyakinan (F5-4). WAJIB ikut ditampilkan: skor dari 3
        # variabel tidak sebanding dengan skor 5 variabel.
        "confidence": row.confidence,
        "variabel_terpakai": row.variabel_terpakai,
        "variabel_total": 5,
        # Nilai yang BENAR-BENAR dipakai menghitung skor - untuk E dan C
        # berarti nilai setelah shrinkage kalau stasiunnya belum disurvey.
        # Sebelum 12 Sep yang dikirim hasil ukur, sehingga panel menampilkan
        # "belum diukur" dan terbaca seolah skornya kurang bahan. Skornya tidak
        # pernah kurang bahan; yang berbeda hanya seberapa banyak yang diukur
        # langsung, dan itu kini dinyatakan terpisah lewat `terukur`.
        "components": {
            "T": row.raw_t,
            "E": row.raw_e,
            "A": row.raw_a,
            "U": row.raw_u,
            "C": row.raw_c,
        },
        "terukur": {
            "T": True,
            "E": row.e_terukur,
            "A": True,
            "U": True,
            "C": row.c_terukur,
        },
        "nilai_ukur": {"E": row.ukur_e, "C": row.ukur_c},
        # CEI - ukuran PAPARAN, terpisah dari SEPI.
        #
        # SEPI menilai potensi ekonomi kawasan; untuk menilai nilai sebuah ruang
        # iklan, yang menentukan adalah berapa banyak orang yang lewat. PRD
        # hal. 13 menetapkan rekomposisi bobotnya: 0,5 T + 0,3 E + 0,2 U.
        # Bedanya nyata - Tanah Abang peringkat 23 menurut SEPI, tetapi kedua
        # tertinggi menurut CEI.
        # TRIASE: kelas SEPI menentukan fitur mana yang masuk akal dikejar di
        # stasiun ini. Ini yang selama ini dihitung tetapi tidak pernah
        # ditampilkan, padahal justru inilah gunanya klasifikasi PRD.
        "triase": TRIASE.get(row.kelas),
        "paparan": {
            "cei": hitung_cei(row.raw_t, row.raw_e, row.raw_u),
            "kelas": kelas_paparan(hitung_cei(row.raw_t, row.raw_e, row.raw_u)),
            "bobot": BOBOT_CEI,
            "catatan": (
                "Composite Exposure Index (PRD hal. 13) - dipakai menilai ruang "
                "iklan dan hak penamaan, BUKAN SEPI. Transportasi diberi bobot "
                "setengah karena yang dibeli pengiklan adalah orang yang lewat."
            ),
        },
        "catatan_peringkat": (
            "Peringkat diurutkan memakai batas bawah skor, bukan nilai titiknya: "
            "untuk tiap variabel yang diestimasi, skor dihitung seolah estimasi "
            "itu meleset satu simpangan baku ke bawah. Stasiun yang datanya "
            "lengkap tidak terkena pengurangan apa pun, sedangkan stasiun "
            "berdata tipis turun sebanyak ketidakpastiannya sendiri. Skor yang "
            "ditampilkan tetap nilai penuhnya."
        ),
        # Variabel yang estimasinya SAMA di seluruh stasiun, dihitung dari data
        # sungguhan - bukan dihardcode.
        #
        # Kenapa ini perlu disebut ke pembaca. Saat sebuah variabel cuma terukur
        # di satu stasiun, shrinkage tidak punya kelompok pembanding yang
        # berbeda-beda untuk dituju, sehingga seluruh stasiun berakhir di angka
        # yang sama persis. Itulah yang terjadi pada E: 0,908 di keempat puluh
        # lima stasiun. Panel menampilkannya berdampingan dengan T dan A yang
        # benar-benar berbeda per stasiun, jadi tanpa keterangan ia terbaca
        # seperti sifat stasiun ini - padahal ia konstanta.
        #
        # Akibatnya pada peringkat: nol. Konstanta menggeser skor semua stasiun
        # sama besar, jadi urutannya tidak berubah sama sekali. Yang hilang bukan
        # ketepatan peringkat, melainkan daya beda variabel itu.
        "seragam_di_semua_stasiun": [
            r[0]
            for r in db.execute(
                text(
                    """
                    SELECT 'E' AS v FROM station_scores WHERE minutes = :menit
                     HAVING COUNT(DISTINCT ROUND(raw_e::numeric, 4)) = 1
                     UNION ALL
                    SELECT 'C' FROM station_scores WHERE minutes = :menit
                     HAVING COUNT(DISTINCT ROUND(raw_c::numeric, 4)) = 1
                    """
                ),
                {"menit": minutes},
            ).all()
        ],
        "catatan_estimasi": (
            "Variabel yang belum terukur diisi estimasi shrinkage terhadap "
            "stasiun berarketipe serupa (PRD hal. 15), bukan dikosongkan. "
            "Skor seluruh stasiun karena itu dihitung dari kelima variabel dan "
            "tetap sebanding; yang berbeda adalah seberapa besar porsi yang "
            "berasal dari pengukuran langsung."
        ),
        "detail": {
            "line_count": row.line_count,
            "halte_count": row.halte_count,
            "other_mode_count": row.other_mode_count,
            "area_km2": row.area_km2,
        },
        # Volume penumpang adalah angka paling nyata yang kita punya, tetapi
        # baru tersedia untuk 10 dari 46 stasiun (22%). Karena di bawah ambang
        # 70%, ia BELUM dipakai sebagai indikator variabel T - jadi dikirim
        # sebagai konteks yang ditampilkan apa adanya, bukan sebagai komponen
        # skor. Membedakan keduanya penting supaya pembaca tidak menyangka
        # peringkatnya sudah memperhitungkan keramaian sebenarnya.
        "passenger_volume": (
            None
            if volume is None
            else {
                "per_day": volume.passengers_per_day,
                "period": volume.period,
                "source": volume.source,
                # Diperbarui 12 Sep: volume SUDAH jadi salah satu indikator T
                # untuk stasiun yang punya datanya (matrix.py), dan sengaja
                # tidak di-shrink. Catatan lama ("bukan komponen skor") keliru.
                "catatan": (
                    "Ikut menghitung indikator T untuk stasiun ini. Cakupannya baru "
                    "10 stasiun; yang lain tidak diberi nol, melainkan dihitung dari "
                    "indikator T lainnya."
                ),
            }
        ),
    }


@router.get("/stations/{station_id}/isochrones")
def station_isochrones(station_id: int, db: Session = Depends(get_db)):
    """Poligon jangkauan jalan kaki satu stasiun, ketiga pita sekaligus.

    Diurutkan dari yang terluas supaya penggambarnya bisa menumpuk begitu saja:
    15 menit di bawah, 5 menit paling atas.
    """
    rows = db.execute(
        select(
            Isochrone.minutes,
            Isochrone.profile,
            func.ST_AsGeoJSON(Isochrone.geom).label("geom"),
        )
        .where(Isochrone.station_id == station_id)
        .order_by(Isochrone.minutes.desc())
    ).all()

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": r.minutes,
                "geometry": json.loads(r.geom),
                "properties": {"minutes": r.minutes, "profile": r.profile},
            }
            for r in rows
        ],
    }


@router.get("/stations/{station_id}/tenants")
def station_tenants(
    station_id: int,
    db: Session = Depends(get_db),
    minutes: int = Query(default=10, ge=5, le=15),
):
    """Tenant Survival Index tiap kategori usaha untuk satu stasiun.

    Diurutkan dari yang paling lapang. Angka mentahnya ikut dikirim karena
    skor 0-100 tanpa pembilang penyebutnya tidak bisa dipakai mengambil
    keputusan sewa.
    """
    rows = db.execute(
        select(TenantScore)
        .where(
            TenantScore.station_id == station_id,
            TenantScore.minutes == minutes,
        )
        .order_by(TenantScore.tsi.desc())
    ).scalars().all()

    total = db.execute(
        select(func.count(func.distinct(TenantScore.station_id))).where(
            TenantScore.minutes == minutes
        )
    ).scalar_one()

    return {
        "station_id": station_id,
        "minutes": minutes,
        "station_count": total,
        "categories": [
            {
                "category": r.category,
                "label": CATEGORY_LABEL.get(r.category, r.category),
                "tsi": r.tsi,
                "rank": r.rank,
                "demand": r.demand,
                "connectivity": r.connectivity,
                "supply": r.supply,
                "supply_luar": r.supply_luar,
                "supply_dalam": r.supply_dalam,
                "dalam_terukur": r.dalam_terukur,
                "confidence": r.confidence,
                "tsi_bawah": r.tsi_bawah,
                "headroom": r.headroom,
            }
            for r in rows
        ],
    }


@router.get("/stations/{station_id}/pois")
def station_pois(
    station_id: int,
    db: Session = Depends(get_db),
    minutes: int = Query(default=10, ge=5, le=15),
    source: str = Query(default="mapid", pattern="^(mapid|overpass)$"),
):
    """Titik minat yang jatuh di dalam isochrone satu stasiun.

    Sengaja per stasiun, bukan seluruh DKI: tabelnya 52 ribu baris, dan yang
    berguna dilihat cuma yang ada di sekitar stasiun yang sedang dibuka.

    `source` WAJIB disaring. Tabel poi menampung dua lajur yang saling tumpang
    tindih secara geografis; tanpa saringan ini satu tempat nyata muncul dua
    kali di peta, sekali dari tiap lajur. Bawaannya "mapid" karena taksonominya
    yang halus (alfamart, apotek, coffee_shop) itulah yang dipakai label peta
    dan sisi pasokan TSI.
    """
    area = (
        select(Isochrone.geom)
        .where(
            Isochrone.station_id == station_id,
            Isochrone.minutes == minutes,
        )
        .scalar_subquery()
    )

    rows = db.execute(
        select(
            Poi.name,
            Poi.category,
            Poi.fungsi,
            func.ST_AsGeoJSON(Poi.location).label("geom"),
        )
        .where(Poi.source == source, func.ST_Contains(area, Poi.location))
        .order_by(Poi.category, Poi.name)
    ).all()

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": index,
                "geometry": json.loads(r.geom),
                "properties": {
                    "name": r.name,
                    "category": r.category,
                    "fungsi": r.fungsi,
                },
            }
            for index, r in enumerate(rows)
        ],
    }


@router.get("/stations/{station_id}/areas")
def station_areas(station_id: int, db: Session = Depends(get_db)):
    """Area pengamatan Activity di satu stasiun: iklan, tenant, keramaian, fasilitas.

    Bahan katalog Ad-Space dan Tenant per area. Area dibentuk dari pengelompokan
    titik Activity yang berdekatan - lihat services/station_areas.py.
    """
    if db.get(Station, station_id) is None:
        raise HTTPException(status_code=404, detail="Stasiun tidak ditemukan")
    return area_stasiun(db, station_id)


@router.get("/stations/{station_id}/paparan")
def station_paparan(station_id: int, db: Session = Depends(get_db)):
    """Profil paparan satu stasiun - dasar Ad-Space (PRD bagian h).

    Menjawab "siapa yang MELINTAS di sini", bukan "siapa yang berbelanja" -
    yang kedua itu profil pembeli, dasar Tenant Valuation, dan PRD memisahkan
    keduanya dengan tegas.

    Seluruhnya disusun dari kamus dan hitungan, tanpa model bahasa, sehingga
    tetap hidup saat kuota model habis. Angkanya menghitung jumlah NARASI,
    bukan jumlah orang: tidak ada data identitas maupun pengukuran arus
    individual (PRD Out-of-Scope, UU 27/2022).
    """
    if db.get(Station, station_id) is None:
        raise HTTPException(status_code=404, detail="Stasiun tidak ditemukan")
    p = profil_paparan(db, station_id)
    return {
        "station_id": p.station_id,
        "stasiun": p.station_name,
        "kawasan": p.kawasan,
        "keramaian": p.keramaian,
        "audiens": p.audiens,
        "waktu_singgah": p.waktu_singgah,
        "format_iklan_disarankan": p.format_iklan,
        "dasar": p.dasar,
    }


# Peringkat paparan di antara stasiun KRL - dasar potensi hak penamaan.
SQL_PERINGKAT_CEI = """
WITH nilai AS (
    SELECT station_id,
           (0.5 * raw_t + 0.3 * raw_e + 0.2 * raw_u) AS cei
      FROM station_scores
     WHERE minutes = 10 AND raw_t IS NOT NULL AND raw_e IS NOT NULL
       AND raw_u IS NOT NULL
)
SELECT (SELECT COUNT(*) FROM nilai) AS total,
       (SELECT COUNT(*) + 1 FROM nilai n2
         WHERE n2.cei > (SELECT cei FROM nilai WHERE station_id = :sid)) AS peringkat
"""

# Merek yang BENAR-BENAR ada di sekitar stasiun, sebagai calon sponsor.
#
# PRD merencanakan kandidat sponsor dari NER atas narasi Activity, dan itu
# belum dibangun. Tetapi ada sumber lain yang sudah tersedia dan justru lebih
# langsung: nama merek pada titik minat di dalam isochrone. Bank yang ATM-nya
# ada di depan stasiun, dan kantor pusat yang gedungnya berjarak 300 meter,
# adalah pihak yang kelekatannya pada kawasan bisa ditunjukkan, bukan ditebak.
#
# Yang diambil hanya kategori yang pemiliknya berupa badan usaha bermerek -
# bank dan perkantoran. Warung dan tempat ibadah tidak masuk: keduanya nyata,
# tetapi bukan calon pembeli hak penamaan stasiun.
# Jarak lurus yang masih disebut "inti kawasan stasiun", untuk MENANDAI calon
# sponsor - bukan untuk menyaringnya.
#
# Pertanyaan ini pernah diajukan dan jawabannya jujur: PRD TIDAK menetapkan
# radius apa pun untuk calon sponsor. Di sana kandidat direncanakan datang dari
# NER atas narasi Activity lalu diranking TOPSIS, tanpa menyebut jarak.
#
# Saringan yang berjalan sekarang adalah isochrone 10 menit jalan kaki, dan itu
# pilihan kami. Konsekuensinya harus disebut: isochrone mengikuti jalan, dan 10
# menit pada kecepatan jalan kaki wajar setara sekitar 800 m tempuh - jadi di
# koridor lurus seperti Sudirman, titik 636 m garis lurus memang sah masuk.
#
# 400 m dipakai sebagai penanda karena itu konvensi pedestrian shed yang lazim
# pada perencanaan kawasan berorientasi transit - kira-kira lima menit jalan
# kaki, jarak yang orang tempuh tanpa berpikir dua kali. Merek yang berdiri di
# dalamnya masuk akal disebut "melekat pada stasiun ini"; yang di luarnya tetap
# ditampilkan, hanya diberi keterangan supaya tidak dibaca setara.
BATAS_INTI_KAWASAN_M = 400

JENIS_KANDIDAT = {
    "atm_bank": "bank",
    "kantor": "perkantoran",
    "kantor_swasta": "perkantoran",
    "coffee_shop": "kedai kopi",
    "alfamart": "minimarket",
    "indomaret": "minimarket",
}

# Calon sponsor = MEREK yang punya kehadiran fisik bernama di sekitar stasiun.
#
# Mesin ATM SENGAJA dibuang, dan ini koreksi. Sebelumnya kategori `atm_bank`
# masuk seluruhnya, sehingga "ATM BANK BCA 2094-RAMAYANA RAGUNAN" tampil sebagai
# calon sponsor. Sebuah mesin yang dititipkan di gedung orang lain tidak
# menyatakan apa pun tentang kelekatan merek pada kawasan - yang menyatakan itu
# adalah kantor, cabang, atau gerai.
#
# Saringannya memakai BATAS KATA, bukan awalan. Versi pertama menyaring nama
# yang DIAWALI "ATM", dan itu meloloskan 814 mesin yang menaruh katanya di
# tengah atau di akhir: "BANK BRI ATM", "MANDIRI ATM", "BII ATM KCP TANAH ABANG
# BLOK A". Ketahuan dari tangkapan layar Villyan, bukan dari pengujian kode.
#
# Batas kata juga yang menjaga cabang tetap masuk: "BANK BTN", "CIMB NIAGA
# (SURYOPRANOTO)", dan "BNI KLN TANAH ABANG" tidak mengandung kata ATM sama
# sekali, jadi tidak ikut tersaring.
#
# Gerai ritel berjenama justru DITAMBAHKAN, karena preseden terkuatnya ada di
# sana: Cipete Raya TUKU dinamai begitu sebab gerai pertama TUKU berdiri di
# situ, dan Fatmawati Indomaret mengikuti pola yang sama. Kedai kopi dan
# minimarket adalah merek yang benar-benar membeli hak penamaan di Jakarta,
# sedangkan mesin ATM tidak pernah.
SQL_KANDIDAT_SPONSOR = """
SELECT p.name,
       p.category,
       ST_X(p.location) AS lon,
       ST_Y(p.location) AS lat,
       ROUND(ST_Distance(p.location::geography, s.location::geography)::numeric) AS jarak_m
  FROM isochrones i
  JOIN poi p ON ST_Contains(i.geom, p.location)
  JOIN stations s ON s.id = i.station_id
 WHERE i.station_id = :sid AND i.minutes = 10
   AND p.source = 'mapid'
   AND p.category IN (
         'kantor', 'kantor_swasta', 'atm_bank',
         'coffee_shop', 'alfamart', 'indomaret'
       )
   AND p.name IS NOT NULL
   AND NOT (p.category = 'atm_bank' AND p.name ~* '\y(ATM|CDM|CRM|SETOR TUNAI)\y')
 ORDER BY jarak_m
 LIMIT 12
"""


SQL_PERINGKAT_SEPI = """
SELECT s.name, sc.sepi AS nilai, sc.sepi_bawah, sc.rank, sc.confidence, sc.kelas
  FROM station_scores sc JOIN stations s ON s.id = sc.station_id
 WHERE sc.minutes = :menit
 ORDER BY sc.rank
"""

SQL_PERINGKAT_PAPARAN = """
SELECT s.name,
       (0.5 * sc.raw_t + 0.3 * sc.raw_e + 0.2 * sc.raw_u) * 100 AS nilai,
       sc.confidence
  FROM station_scores sc JOIN stations s ON s.id = sc.station_id
 WHERE sc.minutes = :menit AND sc.raw_t IS NOT NULL
 ORDER BY nilai DESC
"""

SQL_PERINGKAT_TENANT = """
SELECT s.name, ts.category, ts.tsi AS nilai, ts.rank, ts.supply,
       ts.confidence, ts.tsi_bawah
  FROM tenant_scores ts JOIN stations s ON s.id = ts.station_id
 WHERE ts.minutes = :menit
 ORDER BY ts.category, ts.rank
"""


@router.get("/peringkat")
def peringkat(db: Session = Depends(get_db), minutes: int = Query(default=10, ge=5, le=15)):
    """Seluruh peringkat dalam satu tempat: SEPI, paparan iklan, dan kelayakan usaha.

    KENAPA DIKUMPULKAN. Tiap fitur memakai ukurannya sendiri, sehingga satu
    stasiun bisa berada di peringkat berbeda-beda: Tanah Abang peringkat 23
    menurut SEPI tetapi 2 menurut paparan iklan. Selama ini pembaca hanya
    melihat satu peringkat pada satu waktu, tanpa cara membandingkannya - dan
    perbedaan itu justru inti pesan produknya: pertanyaan yang berbeda menuntut
    ukuran yang berbeda.
    """
    sepi = [
        {
            "peringkat": r["rank"],
            "stasiun": r["name"],
            "nilai": round(float(r["nilai"]), 1),
            "nilai_bawah": round(float(r["sepi_bawah"]), 1),
            "confidence": round(float(r["confidence"]), 2),
            "kelas": r["kelas"],
        }
        for r in db.execute(text(SQL_PERINGKAT_SEPI), {"menit": minutes}).mappings()
    ]
    paparan = [
        {
            "peringkat": i,
            "stasiun": r["name"],
            "nilai": round(float(r["nilai"]), 1),
            "confidence": round(float(r["confidence"]), 2),
        }
        for i, r in enumerate(
            db.execute(text(SQL_PERINGKAT_PAPARAN), {"menit": minutes}).mappings(), start=1
        )
    ]
    tenant: dict[str, list] = {}
    for r in db.execute(text(SQL_PERINGKAT_TENANT), {"menit": minutes}).mappings():
        tenant.setdefault(CATEGORY_LABEL.get(r["category"], r["category"]), []).append(
            {
                "peringkat": r["rank"],
                "stasiun": r["name"],
                "nilai": round(float(r["nilai"]), 1),
                "nilai_bawah": round(float(r["tsi_bawah"]), 1),
                "confidence": round(float(r["confidence"]), 2),
                "pesaing": round(float(r["supply"])),
            }
        )

    return {
        "minutes": minutes,
        "sepi": sepi,
        "paparan": paparan,
        "tenant": tenant,
        "catatan": (
            "Satu stasiun bisa berperingkat berbeda di tiap daftar, dan itu "
            "disengaja: SEPI menilai potensi ekonomi kawasan, paparan menilai "
            "nilai ruang iklan, kelayakan usaha menilai kelapangan pasar per "
            "sektor. Membandingkan peringkat antar-daftar tidak bermakna."
        ),
    }


@router.get("/stations/{station_id}/naming")
def station_naming(station_id: int, db: Session = Depends(get_db)):
    """Status hak penamaan stasiun ini, beserta kelompok pembandingnya.

    Yang DITAMPILKAN: apakah hak penamaan stasiun ini sudah terjual dan kepada
    siapa, ditambah berapa banyak stasiun MRT/LRT lain yang sudah maupun belum.

    Yang TIDAK ditampilkan: nilai kontrak dalam rupiah. Ia butuh pembanding
    transaksi naming rights nyata di Indonesia (PRD hal. 13), dan pembanding itu
    belum ada. Menebaknya akan menghasilkan angka yang tidak bisa
    dipertanggungjawabkan - justru pada fitur yang angkanya paling mudah dikutip
    orang.

    Pembandingnya sengaja hanya MRT dan LRT. Stasiun KAI Commuter tidak pernah
    memperjualbelikan hak penamaan dengan cara yang sama, jadi memasukkannya
    sebagai "belum bersponsor" akan mencampur dua sebab yang berbeda.
    """
    stasiun = db.get(Station, station_id)
    if stasiun is None:
        raise HTTPException(status_code=404, detail="Stasiun tidak ditemukan")

    daftar = klasifikasi(db)
    ini = next((d for d in daftar if d.station_id == station_id), None)
    ringkasan = ringkas(daftar)

    skor = db.execute(
        select(StationScore).where(
            StationScore.station_id == station_id, StationScore.minutes == 10
        )
    ).scalar_one_or_none()
    cei = hitung_cei(skor.raw_t, skor.raw_e, skor.raw_u) if skor else None

    peringkat = total_krl = None
    if cei is not None:
        r = db.execute(text(SQL_PERINGKAT_CEI), {"sid": station_id}).mappings().first()
        if r:
            peringkat, total_krl = r["peringkat"], r["total"]

    kandidat = [
        {
            "nama": r["name"],
            "jenis": JENIS_KANDIDAT.get(r["category"], "perkantoran"),
            "jarak_m": int(r["jarak_m"]),
            # Koordinat ikut dikirim supaya calon sponsor bisa disorot di peta.
            # Daftar nama saja menyisakan pertanyaan yang paling praktis bagi
            # pembaca - "sebelah mana?" - padahal jawabannya sudah kita punya.
            "lon": r["lon"],
            "lat": r["lat"],
            "dalam_inti": int(r["jarak_m"]) <= BATAS_INTI_KAWASAN_M,
        }
        for r in db.execute(text(SQL_KANDIDAT_SPONSOR), {"sid": station_id})
        .mappings()
        .all()
    ]

    return {
        "station_id": station_id,
        "stasiun": stasiun.name,
        "dalam_lingkup": ini is not None,
        "status": (
            None
            if ini is None
            else {
                "bersponsor": ini.bersponsor,
                "sponsor": ini.sponsor,
                "nama_dasar": ini.nama_dasar,
                "jaringan": ini.jaringan,
            }
        ),
        "pembanding": ringkasan,
        "catatan": (
            "Stasiun ini di luar lingkup: hak penamaan hanya diperjualbelikan di "
            "jaringan MRT dan LRT, sedangkan KAI Commuter tidak."
            if ini is None
            else "Nama sponsor berasal dari OpenStreetMap, bukan pengumuman resmi "
            "operator. Sebelum dipakai sebagai dasar valuasi, daftarnya wajib "
            "dicocokkan ke sumber resmi MRT Jakarta dan LRT."
        ),
        # POTENSI stasiun ini sebagai calon hak penamaan.
        #
        # Inilah inti fiturnya untuk KRL, dan kenapa "di luar lingkup" bukan
        # jawaban yang cukup: justru KARENA hampir tidak ada stasiun KRL yang
        # hak penamaannya terjual, di situlah peluangnya. MRT dan LRT
        # membuktikan pasarnya nyata di Jakarta - 12 dari 31 sudah terjual -
        # sementara 46 stasiun KRL nyaris seluruhnya belum tersentuh.
        "potensi": {
            "cei": cei,
            "kelas_paparan": kelas_paparan(cei),
            "peringkat_paparan": peringkat,
            "dari_stasiun_krl": total_krl,
            # Ditulis untuk calon pembaca, bukan untuk penguji metodologi.
            # Versi sebelumnya menyebut nomor halaman PRD dan membantah SEPI -
            # keduanya urusan internal tim, dan pembaca yang baru membuka tab ini
            # tidak sedang bertanya variabel mana yang kami pakai.
            "catatan": (
                "Yang dibeli sponsor adalah jumlah orang yang melihat namanya "
                "setiap hari. Angka ini mengukur itu: seberapa banyak mata yang "
                "melintasi stasiun ini dibanding stasiun KRL lain."
            ),
        },
        "peluang_pasar": {
            "mrt_lrt_terjual": ringkasan["bersponsor"],
            "mrt_lrt_total": ringkasan["total"],
            "krl_terjual": 0,
            "krl_total": total_krl,
            # Angkanya sudah tampil sebagai dua baris di panel, jadi kalimat
            # yang mengulanginya cuma menambah panjang - apalagi kalimat yang
            # menyimpulkan sendiri bahwa ini peluang. Pembaca yang melihat
            # "0 dari 45" sanggup menarik kesimpulan itu tanpa dibantu.
            "catatan": "",
        },
        "kandidat_sponsor": kandidat,
        "batas_inti_kawasan_m": BATAS_INTI_KAWASAN_M,
        # Dua penjelasan yang selama ini tidak pernah diberikan: dari mana
        # angkanya, dan kenapa nama-nama itu yang muncul.
        "cara_hitung": {
            "indeks": (
                "Angka paparan menggabungkan tiga hal yang bisa diukur: seberapa "
                "banyak moda lain bertemu di stasiun ini (bobot 50%), seberapa "
                "ramai stasiunnya menurut catatan lapangan (30%), dan seberapa "
                "padat bangunan di sekitarnya (20%). Ketiganya disamakan dulu ke "
                "skala 0-100 sebelum digabung, lalu hasilnya dibandingkan dengan "
                "44 stasiun KRL lain untuk menentukan peringkat."
            ),
            "kenapa_bobot": (
                "Jumlah moda diberi bobot terbesar karena stasiun yang menjadi "
                "titik pindah dilewati orang yang tidak tinggal maupun bekerja di "
                "sekitarnya - dan mereka tetap melihat namanya."
            ),
            "kandidat": (
                "Calon sponsor dipilih dari merek yang punya kantor, cabang, atau "
                "gerai bernama dalam jangkauan jalan kaki, lalu diurutkan dari "
                "yang terdekat. Mesin ATM tidak dihitung: ia dititipkan di gedung "
                "pihak lain dan tidak menyatakan kelekatan merek pada kawasan."
            ),
        },
        "catatan_kandidat": (
            f"Calon sponsor diambil dari seluruh titik dalam jangkauan jalan "
            f"kaki 10 menit. Yang berjarak lebih dari {BATAS_INTI_KAWASAN_M} m "
            f"garis lurus ditandai terpisah: masih terjangkau jalan kaki, tetapi "
            f"di luar jarak yang biasanya disebut inti kawasan stasiun."
        ),
        "nilai_kontrak": None,
        "alasan_nilai_kosong": (
            "Nilai kontrak baru bisa dihitung kalau ada data transaksi hak "
            "penamaan yang benar-benar terjadi di Indonesia sebagai pembanding. "
            "Data itu belum tersedia untuk ditampilkan di sini."
        ),
        "selisih_daftar": periksa_daftar(db),
    }


@router.get("/sepi/kekokohan")
def sepi_kekokohan(
    db: Session = Depends(get_db),
    minutes: int = Query(default=10, ge=5, le=15),
):
    """Peringkat resmi seluruh stasiun beserta rentang peringkatnya lintas skema."""
    rows = db.execute(
        select(Station.id, Station.name, StationScore.sepi, StationScore.kelas,
               StationScore.rank, StationScore.sensitivity)
        .join(StationScore, StationScore.station_id == Station.id)
        .where(StationScore.minutes == minutes)
        .order_by(StationScore.rank)
    ).all()
    return {
        "minutes": minutes,
        "stasiun": [
            {
                "station_id": r.id,
                "nama": r.name,
                "sepi": r.sepi,
                "kelas": r.kelas,
                "rank": r.rank,
                "sensitivity": r.sensitivity,
            }
            for r in rows
        ],
    }


@router.get("/sponsorship")
def sponsorship(
    db: Session = Depends(get_db),
    station_id: int | None = Query(default=None),
    minutes: int = Query(default=10, ge=5, le=15),
    format: str = Query(default="json", pattern="^(json|geojson)$"),
):
    """Facility Sponsorship Trigger (F6-2): keluhan fasilitas jadi peluang CSR.

    `geojson` untuk penanda peta, `json` untuk panel. Keluhan yang DIBANTAH
    query spasial tidak ikut di keduanya - jumlahnya tetap dilaporkan supaya
    penyaringannya terlihat, bukan diam-diam.
    """
    hasil = peluang_sponsorship(db, station_id=station_id, menit=minutes)

    if format == "geojson":
        return sebagai_geojson(hasil)

    return {
        "minutes": minutes,
        "station_id": station_id,
        "jumlah": len(hasil.peluang),
        "dibantah_validasi_spasial": hasil.dibantah,
        "bukan_keluhan_fasilitas": hasil.bukan_fasilitas,
        "di_luar_lingkup_krl": hasil.di_luar_lingkup,
        "tanpa_bentuk_sponsorship": hasil.tanpa_bentuk,
        "laporan_digabung": hasil.digabung,
        "terlalu_jauh_dari_stasiun": hasil.terlalu_jauh,
        "catatan": (
            "Status 'tervalidasi' berarti klaimnya diuji ke data spasial dan cocok. "
            "'pengamatan langsung' berarti tidak ada data yang bisa mengujinya - ia "
            "berdiri di atas pengamatan surveyor. Keluhan yang dibantah data tidak "
            "ditampilkan."
        ),
        "peluang": hasil.peluang,
    }


@router.get("/lines")
def rute_line(db: Session = Depends(get_db)):
    """Garis rute tiap line KRL, disusun dari urutan stasiun pada roster.

    KENAPA DARI ROSTER, BUKAN GEOMETRI REL. Kita tidak punya data rel; yang ada
    hanya titik stasiun. Menyambung stasiun berurutan menghasilkan garis
    SKEMATIK - ia lurus di tempat rel sebenarnya membelok, tetapi urutan dan
    persinggungan antar-line-nya benar, dan justru itu yang dipakai orang untuk
    menelusuri jaringan. Jadi garisnya dilabeli skematik, bukan disamarkan
    sebagai jalur asli.

    Stasiun di luar DKI tidak ada di basis data, jadi ruas menuju Bogor atau
    Cikarang berhenti di batas wilayah studi. Itu bukan data yang hilang -
    memang cuma sejauh itu cakupan produknya.
    """
    # Koordinatnya dibongkar oleh PostGIS, bukan oleh Shapely: paket itu tidak
    # terpasang di image backend, dan menambahkannya berarti memikul GEOS hanya
    # untuk membaca dua angka yang sudah bisa diminta lewat SQL.
    baris = db.execute(
        text(
            "SELECT name, types, ST_X(location) AS lon, ST_Y(location) AS lat "
            "FROM stations WHERE location IS NOT NULL"
        )
    ).mappings().all()

    # Satu nama bisa muncul di beberapa moda (Cawang KRL dan Cawang LRT berjarak
    # 1,4 km). Roster ini milik KAI, jadi hanya stasiun KAI yang boleh dipetik.
    titik: dict[str, tuple[float, float]] = {}
    for r in baris:
        if not any(t.upper() in KAI_NETWORKS for t in (r["types"] or [])):
            continue
        titik[normalize(r["name"])] = (r["lon"], r["lat"])

    fitur = []
    for kode, blob in LINE_ROSTER.items():
        urutan = [normalize(n) for n in blob.split(";") if normalize(n)]
        koordinat = [titik[k] for k in urutan if k in titik]
        if len(koordinat) < 2:
            continue
        fitur.append(
            {
                "type": "Feature",
                "id": kode,
                "geometry": {"type": "LineString", "coordinates": koordinat},
                "properties": {
                    "line": kode,
                    "jumlah_stasiun": len(koordinat),
                    "skematik": True,
                },
            }
        )

    return {"type": "FeatureCollection", "features": fitur}


@router.get("/kesegaran")
def kesegaran_data(db: Session = Depends(get_db)):
    """Kapan tiap kumpulan data terakhir diperbarui, dan hasil penyegaran terakhir.

    KENAPA PERLU. Begitu aplikasinya publik, yang membaca angka tidak punya cara
    tahu apakah yang dilihatnya hasil kemarin atau hasil tiga bulan lalu. Tanggal
    penyegaran bukan hiasan: keputusan sewa dan tarif iklan diambil dari angka
    ini, dan angka yang usang tetap terlihat meyakinkan.

    Dibaca dari stempel waktu baris yang sudah ada, bukan dari tabel pencatat
    baru. Tabel pencatat bisa bercerita berbeda dari datanya sendiri kalau ada
    tahap yang gagal separuh jalan; stempel waktu barisnya tidak bisa.
    """
    baris = db.execute(
        text(
            """
            SELECT 'Activity' AS kumpulan, MAX(updated_at) AS terakhir,
                   COUNT(*) AS jumlah FROM activity_points
            UNION ALL
            SELECT 'Titik minat', MAX(updated_at), COUNT(*) FROM poi
            UNION ALL
            SELECT 'Guna lahan kawasan', MAX(updated_at), COUNT(*) FROM area_profile
            UNION ALL
            -- `station_scores` dan `tenant_scores` TIDAK punya kolom stempel
            -- waktu, jadi tanggalnya dibiarkan kosong alih-alih diisi tanggal
            -- hari ini. Angka kosong yang jujur lebih baik daripada tanggal
            -- yang seolah-olah hasil pencatatan. Kesegarannya terbaca dari
            -- `penyegaran_terakhir` di bawah.
            SELECT 'Skor SEPI', NULL, COUNT(*) FROM station_scores
            UNION ALL
            SELECT 'Indeks kelayakan usaha', NULL, COUNT(*) FROM tenant_scores
            """
        )
    ).mappings().all()

    # Ringkasan penyegaran terakhir, kalau orkestratornya pernah jalan.
    jalan_terakhir = None
    jalur = Path(os.environ.get("REFRESH_STATUS", "/tmp/stasiun_refresh.json"))
    try:
        if jalur.exists():
            jalan_terakhir = json.loads(jalur.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # Status yang tidak terbaca bukan alasan endpoint ini gagal; data
        # kesegarannya sendiri sudah cukup menjawab pertanyaan utamanya.
        jalan_terakhir = None

    return {
        "kumpulan": [
            {
                "nama": r["kumpulan"],
                "terakhir_diperbarui": r["terakhir"].isoformat() if r["terakhir"] else None,
                "jumlah_baris": r["jumlah"],
            }
            for r in baris
        ],
        "penyegaran_terakhir": jalan_terakhir,
        "catatan": (
            "Tanggal di atas menunjukkan kapan baris terakhir pada tiap kumpulan "
            "data ditulis. Penyegaran dijalankan terjadwal melalui "
            "scripts.refresh_data; tahap yang menarik data dari Overpass "
            "dijalankan terpisah karena memerlukan waktu jauh lebih lama."
        ),
    }
