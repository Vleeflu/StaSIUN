"""Susun matriks keputusan SEPI dari isi database.

Tiap baris satu stasiun, tiap kolom satu variabel. Angkanya dihitung di dalam
poligon isochrone stasiun itu, bukan lingkaran radius — perbedaan yang penting,
karena rel dan sungai bikin jangkauan jalan kaki jauh dari bundar.

RANCANGAN: berkas ini TIDAK menulis SQL-nya sendiri. Ia memanggil
`indicators.hitung_urban` dan `indicators.hitung_transportasi`. Alasannya bukan
kerapian: pemetaan titik minat ke variabel SEPI adalah tempat salah tafsir PRD
pernah masuk (lihat ADJUSTMENT 8.2), dan menyalin logika itu ke dua tempat
adalah cara paling pasti untuk membuatnya hidup kembali di salah satunya.

E DAN C SENGAJA KOSONG (NaN). PRD Tabel 6 menetapkan keduanya bersumber dari
survey Activity di DALAM stasiun — rentang harga tenant, keterisian lapak,
media iklan terpasang, indeks sentimen fasilitas. Tidak satu pun terbaca dari
titik minat di luar stasiun. Versi sebelumnya mengisinya dengan cacahan POI
`variable IN ('E','C')`, dan itu memberi angka yang terlihat masuk akal untuk
sesuatu yang belum diukur sama sekali.

NaN di sini bukan kegagalan, melainkan pernyataan "belum diukur". `topsis.py`
memperlakukannya sebagai tidak menyumbang jarak, bukan sebagai nol — sebab nol
akan menaruh stasiun di sudut terburuk karena datanya belum masuk, bukan karena
kondisinya memang buruk. Begitu blocker N1 tertutup, dua kolom ini terisi tanpa
mengubah apa pun di sini selain sumbernya.
"""

import math

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.indicators import (
    hitung_ekonomi,
    hitung_keramaian,
    hitung_komersial,
    hitung_transportasi,
    hitung_urban,
    hitung_volume_penumpang,
)
from app.services.scoring.uncertainty import estimasi_k, shrinkage

# Batas kontribusi output model berbasis teks terhadap skor akhir. Ditetapkan
# PRD hal. 16, bukan pilihan tim: "modifier dengan kontribusi maksimal 15 persen
# terhadap skor akhir".
BATAS_MODIFIER_TEKS = 0.15

# Kelompok pembanding shrinkage: arketipe LDA dominan tiap stasiun, yaitu topik
# yang paling sering dominan di titik-titik Activity-nya. PRD Tabel 7 menyebut
# arketipe "menjadi kelompok pembanding pada mekanisme shrinkage".
SQL_ARKETIPE = text(
    """
    WITH hitung AS (
        SELECT ap.station_id, ae.archetype, count(*) AS n,
               row_number() OVER (
                   PARTITION BY ap.station_id
                   ORDER BY count(*) DESC, ae.archetype
               ) AS urut
          FROM activity_extractions ae
          JOIN activity_points ap ON ap.id = ae.activity_point_id
         WHERE ap.station_id IS NOT NULL
         GROUP BY ap.station_id, ae.archetype
    )
    SELECT station_id, archetype FROM hitung WHERE urut = 1
    """
)

# Pengamatan PER REKAMAN, satu baris per pengamatan. Inilah bahan `estimasi_k`,
# yang butuh sebaran di dalam tiap stasiun (sigma^2) terpisah dari sebaran antar
# stasiun (tau^2). Memberinya nilai per-stasiun akan membuat sigma^2 kebesaran,
# k meledak jadi tak hingga, dan seluruh stasiun — termasuk yang disurvey —
# ditarik penuh ke rata-rata arketipe.
SQL_PENGAMATAN = text(
    """
    SELECT 'keramaian' AS ukuran, station_id,
           (rating - scale_min)::float / (scale_max - scale_min) AS nilai
      FROM crowd_ratings WHERE station_id IS NOT NULL
    UNION ALL
    SELECT 'sentimen', station_id, sentiment_score
      FROM facility_issues WHERE sentiment_score IS NOT NULL
    UNION ALL
    SELECT 'E', station_id, CASE WHEN status = 'aktif' THEN 1.0 ELSE 0.0 END
      FROM tenants
    UNION ALL
    SELECT 'C', station_id, media_count::float
      FROM ad_spots
    """
)

# Urutan kolom. Dipakai juga oleh berkas AHP, jadi keduanya harus sama.
CRITERIA = ["T", "E", "A", "U", "C"]

# Variabel yang sumbernya survey Activity, bukan titik minat. Selama N1 belum
# tertutup, kolomnya NaN.
MENUNGGU_SURVEY = ("E", "C")

# Jaringan yang dinilai. MRT dan LRT tidak ikut diskor — yang dijual KAI adalah
# ruang di stasiunnya sendiri; moda lain masuk hitungan sebagai penyambung.
SCORED_NETWORKS = ("KAI Commuter", "KAI")

SQL_AKSESIBILITAS = text(
    """
    SELECT s.id AS station_id,
           i.area_m2 / 1000000.0 AS area_km2,
           i.permeability_index
      FROM stations s
      JOIN isochrones i ON i.station_id = s.id AND i.minutes = :minutes
     WHERE s.types && CAST(:networks AS varchar[])
       AND s.served
   -- `s.served` WAJIB. Stasiun yang dilintasi KRL TANPA berhenti tidak punya
   -- arus penumpang commuter sama sekali, jadi menskornya sebagai peluang
   -- komersial itu keliru - dan ia ikut mencemari normalisasi max-scaling serta
   -- bobot entropi seluruh stasiun lain. Gambir sempat terskor di peringkat 32
   -- karena saringan ini belum ada.
    """
)


def _scale_opsional(nilai: list[float | None]) -> list[float | None]:
    """Skala 0-1 HANYA atas stasiun yang punya nilainya; sisanya tetap None.

    Bedanya dengan `_scale` menentukan, dan pernah salah sekali: `_scale` atas
    daftar yang sebagian None (diubah jadi 0,0 dulu) membuat stasiun yang BELUM
    disurvey mendapat nilai 0 - yaitu "terburuk di antara yang ada". Entropi
    kemudian membaca sebaran timpang itu sebagai discriminating power yang
    tinggi, bobot variabelnya melonjak, dan satu-dua stasiun yang kebetulan
    sudah disurvey terlempar ke puncak peringkat hanya karena datanya ada.

    Terjadi sungguhan saat menguji dengan 3 stasiun bersurvey: bobot entropi C
    melonjak ke 0,881 dan Sudirman naik ke "Premium Transit Hub". None yang
    dipertahankan membuat stasiun itu tidak menyumbang apa pun ke kolom
    tersebut, yang memang keadaan sebenarnya.
    """
    ada = [v for v in nilai if v is not None]
    if not ada:
        return [None] * len(nilai)
    tertinggi = max(ada)
    if tertinggi == 0:
        return [0.0 if v is not None else None for v in nilai]
    return [(v / tertinggi) if v is not None else None for v in nilai]


def _susut(
    nilai: list[float | None],
    ids: list[int],
    arketipe: dict[int, str],
    pengamatan: dict[int, list[float]],
) -> tuple[list[float | None], dict]:
    """Shrinkage ke rata-rata arketipe — mekanisme PRD hal. 15 untuk kelengkapan timpang.

    Menyelesaikan B21: sebelum ini, stasiun yang BELUM disurvey sekadar dilewati
    untuk variabel tersebut, sehingga ia "bebas" dari nilai rendah, sementara
    stasiun yang disurvey dan kekurangannya ketahuan justru turun peringkat.
    Diukur jadi merugikan.

    Sekarang setiap stasiun mendapat estimasi:

        nilai_akhir = w * nilai_stasiun + (1 - w) * rata_rata_arketipe
        w = n / (n + k)

    - Stasiun tanpa pengamatan: n = 0, w = 0, nilainya rata-rata arketipenya.
      Ia tidak lagi lolos bebas, tapi juga tidak dihukum nol.
    - Stasiun berpengamatan sedikit: ditarik ke arah arketipenya.
    - Stasiun berpengamatan banyak: w mendekati 1, nilainya sendiri dipercaya.

    k = sigma^2 / tau^2 diestimasi dari PENGAMATAN PER REKAMAN lewat
    `estimasi_k`, bukan ditebak. Kalau hasilnya tak hingga, artinya data tidak
    menunjukkan perbedaan antar-stasiun di atas derau pengambilan sampel, dan
    semua stasiun jatuh ke rata-rata arketipe. Itu kesimpulan yang sah, dan k
    ikut dilaporkan supaya kejadiannya terlihat.

    Rata-rata arketipe dihitung dari stasiun TERUKUR saja. Arketipe tanpa satu
    pun stasiun terukur memakai rata-rata global.

    Mengembalikan (nilai setelah shrinkage, keterangan untuk pelaporan).
    """
    terukur = [v is not None and v == v for v in nilai]
    if not any(terukur):
        return list(nilai), {"k": None, "terukur": 0, "kelompok": 0}

    k = estimasi_k(
        [np.asarray(pengamatan[sid]) for sid in ids if len(pengamatan.get(sid, [])) >= 2]
    )

    per_kelompok: dict[str, list[float]] = {}
    for i, sid in enumerate(ids):
        if terukur[i] and arketipe.get(sid) is not None:
            per_kelompok.setdefault(arketipe[sid], []).append(float(nilai[i]))
    rata_global = float(np.mean([float(nilai[i]) for i in range(len(ids)) if terukur[i]]))
    rata_kelompok = {g: float(np.mean(vs)) for g, vs in per_kelompok.items()}

    hasil: list[float | None] = []
    for i, sid in enumerate(ids):
        acuan = rata_kelompok.get(arketipe.get(sid), rata_global)
        if terukur[i]:
            # Stasiun terukur minimal dihitung satu pengamatan. Tanpa lantai ini,
            # stasiun yang terukur lewat indikator tanpa rekaman per-baris
            # (misalnya klaster lapak) mendapat n = 0 dan nilainya sendiri hilang.
            n = max(1, len(pengamatan.get(sid, [])))
            v, _ = shrinkage(float(nilai[i]), acuan, n, k)
        else:
            v, _ = shrinkage(0.0, acuan, 0, k)
        hasil.append(v)

    return hasil, {
        "k": None if math.isinf(k) else round(k, 3),
        "k_tak_hingga": math.isinf(k),
        "terukur": int(sum(terukur)),
        "kelompok": len(rata_kelompok),
    }


def _rata_tersedia(nilai: list[float | None]) -> float:
    """Rata-rata indikator yang benar-benar ada; NaN kalau tidak ada satu pun.

    Dipakai untuk E dan C, yang indikatornya menyusul satu per satu seiring
    survey Activity masuk. Satu indikator terisi sudah cukup untuk membuat
    variabelnya hidup - lebih jujur daripada menunggu ketiganya lengkap, karena
    `hitung_sepi` memang dirancang menerima variabel yang datanya belum penuh.
    """
    ada = [v for v in nilai if v is not None]
    return sum(ada) / len(ada) if ada else math.nan


def _scale(values: list[float]) -> list[float]:
    """Skala 0 sampai 1 dengan membagi nilai tertinggi.

    Sengaja tidak memakai min-max. Entropy kebal terhadap perkalian tapi tidak
    terhadap pergeseran, jadi menggeser nilai terendah ke nol akan menaikkan
    sebaran kolom secara semu — dan bobotnya ikut terkerek, padahal kolom lain
    memakai hitungan mentah. Membagi nilai tertinggi tidak menggeser apa pun,
    sekaligus menjaga perbandingan aslinya: dua line tetap separuh dari empat.

    Diadopsi apa adanya dari branch main; alasannya benar.
    """
    high = max(values) if values else 0.0
    return [0.0] * len(values) if high == 0 else [v / high for v in values]


def build_matrix(
    db: Session, minutes: int = 10, sumber: str = "overpass"
) -> tuple[list[dict], list[list[float]]]:
    """Kembalikan (rincian per stasiun, matriks keputusan).

    Rinciannya ikut dibawa supaya angka mentahnya bisa ditelusuri — tanpa itu
    skor akhirnya cuma angka yang tidak bisa dipertanggungjawabkan.
    """
    akses = {
        r.station_id: r
        for r in db.execute(
            SQL_AKSESIBILITAS,
            {"minutes": minutes, "networks": list(SCORED_NETWORKS)},
        ).all()
    }
    if not akses:
        raise ValueError(
            f"tidak ada stasiun {'/'.join(SCORED_NETWORKS)} dengan isochrone "
            f"{minutes} menit. Jalankan dulu: python -m scripts.ingest_layers isochrones"
        )

    urban = {u.station_id: u for u in hitung_urban(db, menit=minutes, sumber=sumber)}
    transportasi = {t.station_id: t for t in hitung_transportasi(db)}

    # E dan C datang dari survey Activity. Keduanya mengembalikan daftar kosong
    # selama tabelnya belum terisi, dan itu keadaan yang diharapkan sekarang -
    # bukan kegagalan. Kolomnya tetap NaN, dan hitung_sepi menormalisasi ulang
    # bobot atas variabel yang ada.
    ekonomi = {e.station_id: e for e in hitung_ekonomi(db)}
    komersial = {c.station_id: c for c in hitung_komersial(db)}

    # Dua indikator T yang PRD Tabel 6 daftarkan tetapi belum pernah terpakai
    # sampai 11 Sep, karena datanya memang belum ada.
    keramaian = {k.station_id: k for k in hitung_keramaian(db)}
    volume = hitung_volume_penumpang(db)

    # Bahan shrinkage (F3-7): kelompok pembanding dan pengamatan per rekaman.
    arketipe = {r.station_id: r.archetype for r in db.execute(SQL_ARKETIPE).all()}
    pengamatan: dict[str, dict[int, list[float]]] = {}
    for r in db.execute(SQL_PENGAMATAN).all():
        pengamatan.setdefault(r.ukuran, {}).setdefault(r.station_id, []).append(float(r.nilai))

    # Hanya stasiun yang lengkap ketiganya. Stasiun tanpa isochrone tidak bisa
    # dinilai variabel A maupun U-nya, dan menyertakannya dengan nol akan
    # menghukumnya karena poligonnya belum dibangkitkan (lihat blocker N13).
    ids = sorted(set(akses) & set(urban) & set(transportasi), key=lambda i: urban[i].station_name)

    details = []
    for sid in ids:
        a, u, t = akses[sid], urban[sid], transportasi[sid]
        details.append(
            {
                "id": sid,
                "name": u.station_name,
                "line_count": t.jumlah_line,
                "moda_rel": t.moda_rel,
                "moda_jalan": t.moda_jalan,
                "interchange": t.interchange,
                "area_km2": float(a.area_km2),
                "permeability_index": float(a.permeability_index or 0.0),
                "poi_u": u.jumlah_poi,
                "kepadatan_per_km2": u.kepadatan_per_km2,
                "keberagaman": u.keberagaman,
                "pembangkit_perjalanan": u.pembangkit_perjalanan,
                "ekonomi": ekonomi.get(sid),
                "komersial": komersial.get(sid),
                "keramaian": keramaian.get(sid),
                "volume_penumpang": volume.get(sid),
            }
        )

    # ---- Variabel T: KEEMPAT indikator PRD Tabel 6 ----
    #
    # PRD menetapkan T disusun dari "volume penumpang, jumlah moda terhubung,
    # status interchange, penilaian keramaian per rentang waktu". Sampai 11 Sep
    # implementasinya cuma memakai SATU di antaranya (moda terhubung), dipecah
    # jadi dua lalu dirata-rata. Itu akar B16: bukan cuma rumusnya yang cacat,
    # tetapi separuh indikatornya memang tidak pernah masuk.
    #
    # Dua yang hilang sekarang tersedia: volume penumpang (data sekunder) dan
    # skala keramaian narasumber (survey Activity).
    #
    # "Jumlah moda terhubung" digabung jadi SATU indikator, bukan dua yang
    # dirata-rata terpisah. Memisahkannya membuat stasiun tanpa moda rel di
    # dekatnya kehilangan sepertiga nilai T, padahal PRD menyebutnya satu hal.
    #
    # `moda_jalan` TETAP dipakai walau bias cakupan OSM-nya terbukti (B11),
    # karena PRD menamai OpenStreetMap sebagai sumber indikator ini. Membuangnya
    # justru penyimpangan dari PRD; batasnya dicatat, bukan indikatornya dibuang.
    moda = _scale([float(d["moda_rel"] + d["moda_jalan"]) for d in details])

    # "Status interchange" di PRD bersifat boolean. Di sini dipakai jumlah line
    # yang diskalakan, karena boolean membuang perbedaan nyata antara
    # interchange 2 line dan 3 line. Elaborasi ini dicatat di ADJUSTMENT 9.23.
    interchange = _scale([float(d["line_count"]) for d in details])

    # Dua indikator berikut TIDAK dimiliki semua stasiun. Yang belum terukur
    # dibiarkan None, bukan nol — nol berarti "paling sepi", dan menempelkannya
    # ke stasiun yang belum disurvey akan menghukumnya karena datanya belum ada.
    ids = [d["id"] for d in details]
    keterangan_susut: dict[str, dict] = {}

    # Sudah 0-1 dengan batas teoretis skala tiap penilaian - lihat
    # `indicators.normalkan_skala`. SENGAJA tidak lewat `_scale_opsional`:
    # membagi nilai tertinggi di data memperlakukan skala ordinal seolah punya
    # titik nol sungguhan (PRD hal. 10).
    keramaian_ukur = [d["keramaian"].skala_normal if d["keramaian"] else None for d in details]
    # Keramaian adalah ukuran Activity yang cakupannya timpang (hanya stasiun
    # tersurvey), jadi di-shrink ke rata-rata arketipe — lihat `_susut`. Tanpa
    # ini stasiun berkeramaian rendah yang disurvey turun, sementara yang belum
    # disurvey lolos bebas: pola B21 yang sama, di tingkat indikator.
    keramaian_skala, keterangan_susut["keramaian"] = _susut(
        keramaian_ukur, ids, arketipe, pengamatan.get("keramaian", {})
    )

    # Volume penumpang TIDAK di-shrink. Ia data sekunder, bukan Activity, dan
    # arketipe LDA — topik narasi survey — bukan kelompok pembanding yang masuk
    # akal untuk jumlah penumpang. PRD hal. 15 membatasi mekanisme shrinkage pada
    # kelengkapan antar-titik Activity. Stasiun tanpa data volume tetap sekadar
    # tidak mendapat indikator itu.
    volume_skala = _scale_opsional([d["volume_penumpang"] for d in details])

    # A juga gabungan: seberapa luas yang terjangkau, dan seberapa efisien
    # jaringan jalannya mengisi luas itu (Permeability Index).
    luas = _scale([d["area_km2"] for d in details])
    pi = _scale([d["permeability_index"] for d in details])

    # U memakai ketiga indikator PRD sekaligus: cacah, keberagaman fungsi lahan,
    # dan pembangkit perjalanan berskala besar.
    # Indikator Activity diskalakan hanya kalau ADA yang terisi. `_scale` atas
    # daftar yang seluruhnya None tidak punya arti, dan memaksakannya akan
    # mengarang angka 0 untuk sesuatu yang belum diukur.
    harga_mentah = [d["ekonomi"].harga_median_idr if d["ekonomi"] else None for d in details]
    iklan_mentah = [float(d["komersial"].media_iklan) if d["komersial"] and d["komersial"].media_iklan is not None else None for d in details]
    sentimen_mentah = [d["komersial"].sentimen_fasilitas if d["komersial"] else None for d in details]
    harga = _scale_opsional(harga_mentah)
    iklan = _scale_opsional(iklan_mentah)
    # SENTIMEN TIDAK LAGI MASUK KOMPOSIT C.
    #
    # PRD Tabel 6 memang mendaftarkan "indeks sentimen fasilitas" di bawah C,
    # tetapi PRD Tabel 7 dan hal. 16 menetapkan cara kerjanya: Sentiment
    # Analysis adalah model berbasis teks, keluarannya "polaritas kenyamanan
    # sebagai PENALTI bagi zona bermasalah", dan output model teks dibatasi
    # "maksimal 15 persen terhadap skor akhir". Versi sebelumnya memasukkannya
    # ke C dengan bobot penuh — melampaui batas itu.
    #
    # Ada alasan kedua yang lebih mendesak. `facility_issues` isinya KELUHAN,
    # jadi rata-rata sentimennya hampir pasti negatif begitu ada satu catatan.
    # Jakarta Kota (2 keluhan, sentimen -0,8, nol pengamatan iklan) karena itu
    # mendapat C = 0,05 dan jatuh dari peringkat 1 ke 16, sementara Tanah Abang
    # yang belum punya satu pun catatan lolos bebas (ADJUSTMENT 9.28).
    #
    # Sekarang sentimen di-shrink ke rata-rata arketipe (stasiun tanpa catatan
    # tidak lagi lolos), lalu dipakai sebagai penalti berpengali di hitung_sepi:
    #     SEPI_akhir = SEPI_dasar x (1 - 0,15 x penalti),  penalti = max(0, -sentimen)
    sentimen_susut, keterangan_susut["sentimen"] = _susut(
        sentimen_mentah, ids, arketipe, pengamatan.get("sentimen", {})
    )

    cacah = _scale([float(d["poi_u"]) for d in details])
    ragam = _scale([d["keberagaman"] for d in details])
    pembangkit = _scale([float(d["pembangkit_perjalanan"]) for d in details])

    # Lintasan 1 — nilai HASIL UKUR. Inilah yang ditampilkan dan dipakai entropi.
    # Yang tidak terukur tetap NaN; ia tidak pernah menyamar jadi angka.
    ukur_e: list[float] = []
    ukur_c: list[float] = []
    for i, d in enumerate(details):
        ukur_e.append(
            _rata_tersedia(
                [
                    d["ekonomi"].komposisi_usaha if d["ekonomi"] else None,
                    d["ekonomi"].keterisian_komersial if d["ekonomi"] else None,
                    harga[i],
                ]
            )
        )
        ukur_c.append(
            _rata_tersedia(
                [
                    iklan[i],
                    d["komersial"].keterisian_lapak if d["komersial"] else None,
                ]
            )
        )

    # Lintasan 2 — nilai SETELAH SHRINKAGE. Inilah yang dipakai menghitung skor,
    # supaya skor lima variabel dan skor tiga variabel sebanding.
    susut_e, keterangan_susut["E"] = _susut(
        [v if v == v else None for v in ukur_e], ids, arketipe, pengamatan.get("E", {})
    )
    susut_c, keterangan_susut["C"] = _susut(
        [v if v == v else None for v in ukur_c], ids, arketipe, pengamatan.get("C", {})
    )

    matrix: list[list[float]] = []
    for i, d in enumerate(details):
        d["ukur_t"] = _rata_tersedia(
            [volume_skala[i], moda[i], interchange[i], keramaian_ukur[i]]
        )
        d["raw_t"] = _rata_tersedia(
            [volume_skala[i], moda[i], interchange[i], keramaian_skala[i]]
        )
        d["raw_a"] = d["ukur_a"] = (luas[i] + pi[i]) / 2.0
        d["raw_u"] = d["ukur_u"] = (cacah[i] + ragam[i] + pembangkit[i]) / 3.0
        d["ukur_e"], d["ukur_c"] = ukur_e[i], ukur_c[i]
        d["raw_e"] = susut_e[i] if susut_e[i] is not None else math.nan
        d["raw_c"] = susut_c[i] if susut_c[i] is not None else math.nan

        # Kelengkapan dihitung dari HASIL UKUR, bukan dari nilai hasil shrinkage.
        # Kalau dari yang kedua, semua stasiun tampil "5 dari 5" dengan confidence
        # 1,00 — estimasi menyamar jadi pengukuran.
        d["terukur"] = [
            True,
            d["ukur_e"] == d["ukur_e"],
            True,
            True,
            d["ukur_c"] == d["ukur_c"],
        ]
        d["menunggu_survey"] = [
            v for v, ok in (("E", d["terukur"][1]), ("C", d["terukur"][4])) if not ok
        ]

        s = sentimen_susut[i]
        d["penalti_sentimen"] = max(0.0, -float(s)) if s is not None else 0.0
        d["sentimen_terukur"] = sentimen_mentah[i] is not None

        # Objek indikator tidak ikut dibawa keluar: isinya sudah terserap, dan
        # menyertakannya membuat `details` tidak bisa di-JSON-kan.
        d.pop("ekonomi", None)
        d.pop("komersial", None)
        d.pop("keramaian", None)

        matrix.append([d["raw_t"], d["raw_e"], d["raw_a"], d["raw_u"], d["raw_c"]])

    # Keterangan shrinkage ikut dibawa di rincian pertama supaya pemanggil bisa
    # melaporkannya tanpa mengubah bentuk nilai kembalian fungsi ini.
    if details:
        details[0]["_keterangan_susut"] = keterangan_susut

    return details, matrix
