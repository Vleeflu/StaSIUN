"""Alat yang boleh dipanggil asisten AI, di atas mesin skor kita sendiri.

GARIS YANG DIPEGANG: AI MEMILIH APA YANG DIHITUNG, BUKAN BERAPA HASILNYA
------------------------------------------------------------------------
Tiap fungsi di sini mengembalikan angka hasil perhitungan sungguhan dari
database dan mesin skor. Model bahasa hanya memutuskan alat mana yang dipanggil
dan dengan argumen apa, lalu menyusun kalimat dari hasilnya. Ia tidak pernah
mengarang angka, dan tidak pernah menghitung sendiri.

Bedanya menentukan. Model bahasa cukup pandai menghasilkan angka yang terlihat
masuk akal untuk pertanyaan seperti "berapa skor Manggarai kalau transportasi
dibobot 50%" - dan angka itu akan salah tanpa ada yang tahu. Dengan alat, ia
harus benar-benar memanggil mesin skornya.

Karena itu daftar alat di bawah sengaja sempit. Asisten TIDAK bisa menjawab di
luar keempatnya, dan itu memang maksudnya: ruang yang tidak tercakup alat adalah
ruang tempat jawaban dikarang.

Ini menjawab pola integrasi AI yang dicontohkan coaching MAPID:
  pola 1  AI memanggil method yang ada di kode kita
  pola 3  analisis MCDA lewat prompt - bobot, filter, dan parameter diatur
          lewat kalimat, bukan lewat klik
  pola 4  hasilnya diolah dan diformat ulang oleh AI
Pola 2 (web search kalau input kosong) sengaja TIDAK dipakai: kita tidak punya
sumber pencarian yang bisa dipertanggungjawabkan, dan "aproksimasi koordinat"
persis jenis jawaban yang seluruh proyek ini berusaha cegah.
"""

from __future__ import annotations

import json

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.scoring import (
    CRITERIA,
    bobot_entropy,
    build_matrix,
    gabung_bobot,
    hitung_sepi,
)
from app.services.scoring.matrix import (  # noqa: F401  (SCORED_NETWORKS dipakai di docstring)
    BATAS_MODIFIER_TEKS,
    SCORED_NETWORKS,
)

# Batas jumlah baris yang boleh dikembalikan satu alat. Konteks model punya
# batas; mengirim 46 stasiun berisi belasan kolom akan mendesak keluar bagian
# brief yang justru menjaga jawabannya tetap jujur.
MAX_BARIS = 15


class ToolError(RuntimeError):
    """Alat gagal dengan alasan yang bisa disampaikan apa adanya ke pengguna."""


def _bobot_dari_permintaan(permintaan: dict[str, float] | None) -> np.ndarray:
    """Ubah permintaan bobot pengguna jadi vektor ternormalisasi.

    Pengguna boleh menyebut sebagian saja ("transportasi 50%"). Sisanya dibagi
    rata dari porsi yang tersisa, bukan dinolkan - menolkan variabel yang tidak
    disebut akan diam-diam mengubah pertanyaan "utamakan transportasi" menjadi
    "hanya pakai transportasi".
    """
    if not permintaan:
        raise ToolError("bobot tidak disebutkan")

    diminta = {k.upper(): float(v) for k, v in permintaan.items() if v is not None}
    tak_dikenal = set(diminta) - set(CRITERIA)
    if tak_dikenal:
        raise ToolError(
            f"variabel tidak dikenal: {', '.join(sorted(tak_dikenal))}. "
            f"Yang ada cuma {', '.join(CRITERIA)}."
        )

    # Terima 50 maupun 0,5 sebagai "setengah".
    if sum(diminta.values()) > 1.5:
        diminta = {k: v / 100.0 for k, v in diminta.items()}

    total_diminta = sum(diminta.values())
    if total_diminta > 1.0001:
        raise ToolError(
            f"jumlah bobot yang diminta {total_diminta:.2f}, tidak boleh lebih dari 1"
        )

    sisa = [c for c in CRITERIA if c not in diminta]
    per_sisa = (1.0 - total_diminta) / len(sisa) if sisa else 0.0

    return np.array([diminta.get(c, per_sisa) for c in CRITERIA], dtype=float)


def hitung_ulang_sepi(
    db: Session,
    bobot: dict[str, float] | None = None,
    menit: int = 10,
    batas: int = 10,
    batas_maks: int = MAX_BARIS,
) -> dict:
    """Jalankan ulang MCDA dengan bobot pilihan pengguna (pola 3).

    Ini bukan mengubah angka yang sudah tersimpan - ia menghitung ulang dari
    matriks keputusan yang sama, hanya dengan bobot berbeda, lalu mengembalikan
    peringkat barunya. Skor yang tersimpan di database tidak tersentuh.
    """
    if menit not in (5, 10, 15):
        raise ToolError(f"cincin isochrone cuma 5, 10, atau 15 menit, bukan {menit}")

    details, matriks = build_matrix(db, minutes=menit)
    # Jalur hitung SAMA PERSIS dengan compute_sepi: nilai hasil shrinkage untuk
    # skor, hasil ukur untuk entropi dan kelengkapan, penalti sentimen dibatasi
    # 15 persen. Kalau jalurnya berbeda, simulasi dan skor resmi akan menjawab
    # beda untuk pertanyaan yang sama, dan tidak ada yang tahu mana yang benar.
    x = np.asarray(matriks, dtype=float)
    terukur = np.asarray([d["terukur"] for d in details], dtype=bool)
    penalti = [d["penalti_sentimen"] for d in details]

    if bobot:
        w = _bobot_dari_permintaan(bobot)
        asal = "pilihan pengguna"
    else:
        # Tanpa permintaan khusus, pakai bobot entropi murni supaya jelas ini
        # perbandingan, bukan pengulangan skor resmi.
        ada = ~np.all(np.isnan(x), axis=0)
        w = np.zeros(x.shape[1])
        if ada.any():
            w[ada] = bobot_entropy(x[:, ada])
        w = gabung_bobot(w, np.full(len(CRITERIA), 1 / len(CRITERIA)), 0.5)
        asal = "entropy + bobot rata"

    skor = hitung_sepi(
        [d["id"] for d in details],
        [d["name"] for d in details],
        x,
        w,
        terukur=terukur,
        penalti=penalti,
        batas_modifier=BATAS_MODIFIER_TEKS,
    )
    # `batas_maks` ada supaya pemakai HTTP bisa meminta peringkat penuh.
    # MAX_BARIS melindungi konteks model bahasa, dan pembatasan itu tidak
    # berlaku untuk UI - di sana peringkat terpotong justru menyesatkan, karena
    # stasiun di luar potongan tampil seolah tidak punya skor.
    urut = sorted(skor, key=lambda s: -s.nilai)[: min(batas, batas_maks)]

    return {
        "cincin_menit": menit,
        "asal_bobot": asal,
        "bobot_dipakai": {c: round(float(w[i]), 3) for i, c in enumerate(CRITERIA)},
        "variabel_terukur": urut[0].variabel_terpakai if urut else 0,
        "variabel_total": len(CRITERIA),
        "catatan": (
            "Peringkat ini dihitung ulang khusus untuk permintaan ini dan TIDAK "
            "menggantikan skor resmi di database. Variabel yang belum terukur "
            "diestimasi dari rata-rata arketipe stasiun (shrinkage), tidak diisi "
            "nol; confidence tetap menyatakan berapa variabel yang benar-benar "
            "terukur."
        ),
        "peringkat": [
            {
                "peringkat": i,
                "stasiun": s.station_name,
                "sepi": round(s.nilai, 2),
                "kelas": s.kelas,
                "confidence": round(s.confidence, 2),
            }
            for i, s in enumerate(urut, start=1)
        ],
    }


SQL_CARI = """
SELECT s.name,
       sc.sepi, sc.kelas, sc.rank, sc.confidence,
       sc.line_count, sc.halte_count, sc.other_mode_count,
       round(sc.area_km2::numeric, 2) AS area_km2,
       pv.passengers_per_day
  FROM station_scores sc
  JOIN stations s ON s.id = sc.station_id
  LEFT JOIN passenger_volume pv ON pv.station_id = s.id
 WHERE sc.minutes = :menit
   -- CAST wajib. Saringan opsional dikirim sebagai NULL saat tidak dipakai, dan
   -- Postgres tidak bisa menebak tipe parameter yang hanya muncul di `IS NULL`
   -- - hasilnya "could not determine data type of parameter". Menyebut tipenya
   -- di sini juga membuat maksud tiap saringan terbaca langsung dari SQL-nya.
   AND (CAST(:min_line  AS integer)          IS NULL OR sc.line_count >= :min_line)
   AND (CAST(:min_sepi  AS double precision) IS NULL OR sc.sepi       >= :min_sepi)
   AND (CAST(:maks_sepi AS double precision) IS NULL OR sc.sepi       <= :maks_sepi)
   AND (CAST(:kelas     AS text)             IS NULL OR sc.kelas ILIKE :kelas)
 ORDER BY sc.sepi DESC
 LIMIT :batas
"""


def cari_stasiun(
    db: Session,
    min_line: int | None = None,
    min_sepi: float | None = None,
    maks_sepi: float | None = None,
    kelas: str | None = None,
    menit: int = 10,
    batas: int = 10,
) -> dict:
    """Saring stasiun menurut kriteria (site selection, pola 3).

    Semua saringan opsional dan digabung dengan DAN. Yang tidak disebut tidak
    membatasi apa pun.
    """
    baris = db.execute(
        text(SQL_CARI),
        {
            "menit": menit,
            "min_line": min_line,
            "min_sepi": min_sepi,
            "maks_sepi": maks_sepi,
            "kelas": f"%{kelas}%" if kelas else None,
            "batas": min(batas, MAX_BARIS),
        },
    ).mappings().all()

    return {
        "jumlah_cocok": len(baris),
        "saringan": {
            "min_line": min_line,
            "min_sepi": min_sepi,
            "maks_sepi": maks_sepi,
            "kelas": kelas,
            "cincin_menit": menit,
        },
        "stasiun": [dict(r) for r in baris],
    }


SQL_TENANT = """
SELECT s.name, ts.tsi, ts.rank, ts.demand, ts.supply, ts.headroom
  FROM tenant_scores ts
  JOIN stations s ON s.id = ts.station_id
 WHERE ts.minutes = :menit AND ts.category = :kategori
 ORDER BY ts.rank
 LIMIT :batas
"""


def peringkat_tenant(
    db: Session, kategori: str, menit: int = 10, batas: int = 10
) -> dict:
    """Peringkat stasiun untuk satu kategori usaha, menurut TSI."""
    baris = db.execute(
        text(SQL_TENANT),
        {"kategori": kategori, "menit": menit, "batas": min(batas, MAX_BARIS)},
    ).mappings().all()

    if not baris:
        tersedia = db.execute(
            text("SELECT DISTINCT category FROM tenant_scores ORDER BY category")
        ).scalars().all()
        raise ToolError(
            f"kategori {kategori!r} tidak ada. Yang diskor cuma: "
            f"{', '.join(tersedia) if tersedia else '(belum ada satu pun)'}"
        )

    return {
        "kategori": kategori,
        "cincin_menit": menit,
        "catatan": (
            "TSI dibentangkan 0-100 PER KATEGORI, jadi angkanya tidak sebanding "
            "antar kategori. Ia mengukur kelapangan pasar, bukan kecocokan merek."
        ),
        # Rumusnya ikut dikirim supaya model MEMBACA, bukan mengingat. Terbukti
        # perlu: saat hanya ada di brief, model menyederhanakannya jadi
        # "calon / (pesaing + 1)" dan menghilangkan pengali konektivitas.
        "rumus_headroom": (
            "headroom = (calon_pelanggan x pengali_konektivitas) / (pesaing + 1). "
            "Pengali konektivitas 1,0-2,0 berasal dari komponen T, dan pesaing "
            "ditambah satu untuk gerai yang mau dibuka sendiri. Pesaing dihitung "
            "paling jauh 10 menit jalan kaki, jadi pada pita 15 menit angkanya "
            "lebih kecil daripada jumlah gerai sejenis yang terlihat di peta - dan "
            "pesaing 0 berarti tidak ada gerai sejenis dalam jangkauan yang "
            "dihitung, bukan tidak ada pesaing sama sekali. Pakai rumus INI kalau "
            "ditanya, jangan menyederhanakannya."
        ),
        "peringkat": [dict(r) for r in baris],
    }


SQL_TENANT_STASIUN = """
SELECT ts.category, ts.tsi, ts.rank, ts.demand, ts.supply, ts.headroom
  FROM tenant_scores ts
  JOIN stations s ON s.id = ts.station_id
 WHERE ts.minutes = :menit AND s.name = :nama
 -- Diurutkan menurut headroom, BUKAN tsi. Bedanya menentukan: di Manggarai,
 -- Indomaret ber-TSI lebih tinggi (45,5) daripada Alfamart (30,7), padahal
 -- Alfamart yang pasarnya paling lapang (headroom 72,25 lawan 18,06). TSI
 -- dibentangkan per kategori sehingga tidak sebanding antar kategori.
 --
 -- Urutan ini bukan kosmetik. Model membaca baris pertama sebagai jawaban, dan
 -- saat diurutkan menurut tsi ia benar-benar menjawab Indomaret - padahal
 -- catatan di balasan yang sama sudah melarangnya. Menaruh jawaban yang benar
 -- di baris pertama lebih tahan banting daripada menambah satu larangan lagi.
 ORDER BY ts.headroom DESC
"""


def tenant_untuk_stasiun(db: Session, nama: str, menit: int = 10) -> dict:
    """SELURUH kategori usaha untuk SATU stasiun, diurutkan dari TSI tertinggi.

    Ada karena `peringkat_tenant` menjawab arah sebaliknya - satu kategori untuk
    banyak stasiun. Tanpa alat ini, pertanyaan "kategori apa yang paling lapang
    di stasiun X" memaksa model memanggil `peringkat_tenant` lima kali berturut
    turut, satu per kategori, dan itu benar-benar terjadi sampai menabrak batas
    putaran tool calling.
    """
    baris = db.execute(
        text(SQL_TENANT_STASIUN), {"nama": nama, "menit": menit}
    ).mappings().all()

    if not baris:
        raise ToolError(
            f"stasiun {nama!r} tidak punya skor tenant. Pakai nama persis seperti "
            "di daftar stasiun, dan ingat stasiun yang dilintasi tanpa berhenti "
            "memang tidak diskor."
        )

    teratas = baris[0]
    return {
        "stasiun": nama,
        "cincin_menit": menit,
        # Jawabannya disebut eksplisit supaya model tidak perlu memutuskan
        # sendiri kolom mana yang sah dibandingkan.
        "paling_lapang": {
            "kategori": teratas["category"],
            "headroom": teratas["headroom"],
            "alasan": (
                f"headroom tertinggi ({teratas['headroom']}), yaitu calon pelanggan "
                f"per pesaing. JANGAN memakai kolom `tsi` untuk perbandingan ini."
            ),
        },
        "catatan": (
            "TSI dibentangkan 0-100 PER KATEGORI, jadi membandingkan angkanya "
            "antar kategori TIDAK sah. Yang sah dibandingkan adalah `headroom`."
        ),
        "rumus_headroom": (
            "headroom = (calon_pelanggan x pengali_konektivitas) / (pesaing + 1). "
            "Pengali konektivitas 1,0-2,0 berasal dari komponen T, dan pesaing "
            "ditambah satu untuk gerai yang mau dibuka sendiri. Pesaing dihitung "
            "paling jauh 10 menit jalan kaki, jadi pada pita 15 menit angkanya "
            "lebih kecil daripada jumlah gerai sejenis yang terlihat di peta - dan "
            "pesaing 0 berarti tidak ada gerai sejenis dalam jangkauan yang "
            "dihitung, bukan tidak ada pesaing sama sekali. Pakai rumus INI kalau "
            "ditanya, jangan menyederhanakannya."
        ),
        "kategori": [dict(r) for r in baris],
    }


SQL_BANDING = """
SELECT s.name, sc.sepi, sc.kelas, sc.rank, sc.confidence, sc.variabel_terpakai,
       sc.raw_t, sc.raw_e, sc.raw_a, sc.raw_u, sc.raw_c,
       sc.line_count, sc.halte_count, sc.other_mode_count,
       round(sc.area_km2::numeric, 2) AS area_km2
  FROM station_scores sc
  JOIN stations s ON s.id = sc.station_id
 WHERE sc.minutes = :menit AND s.name = ANY(:nama)
 ORDER BY sc.sepi DESC
"""


def bandingkan_stasiun(db: Session, nama: list[str], menit: int = 10) -> dict:
    """Bandingkan beberapa stasiun berdampingan, variabel demi variabel."""
    if not nama:
        raise ToolError("tidak ada nama stasiun yang disebut")

    baris = db.execute(
        text(SQL_BANDING), {"nama": list(nama)[:6], "menit": menit}
    ).mappings().all()

    ketemu = {r["name"] for r in baris}
    hilang = [n for n in nama if n not in ketemu]

    return {
        "cincin_menit": menit,
        # Nama yang tidak ketemu DISEBUT, bukan didiamkan. Kalau tidak, model
        # akan menjawab seolah stasiun itu ikut dibandingkan padahal tidak.
        "tidak_ditemukan": hilang,
        "stasiun": [dict(r) for r in baris],
    }


SQL_KOKOH = """
SELECT s.name, sc.rank, sc.sepi, sc.kelas, sc.sensitivity
  FROM station_scores sc
  JOIN stations s ON s.id = sc.station_id
 WHERE sc.minutes = :menit
 ORDER BY sc.rank
"""


def kekokohan_peringkat(db: Session, nama: str | None = None, menit: int = 10) -> dict:
    """Seberapa kokoh peringkat terhadap pilihan pembobotan (ADJUSTMENT 9.30).

    Tanpa `nama`: stasiun yang masuk N besar di SEMUA skema, dan yang 10 besar
    resminya rapuh. Dengan `nama`: rincian satu stasiun.
    """
    baris = db.execute(text(SQL_KOKOH), {"menit": menit}).mappings().all()
    if not baris or baris[0]["sensitivity"] is None:
        raise ToolError(
            "analisis sensitivitas belum dijalankan untuk skor ini. "
            "Jalankan compute_sepi di backend."
        )

    penjelasan = (
        "Peringkat dihitung ulang di 5 skema pembobotan yang sama-sama sah (resmi, "
        "AHP murni, entropi murni, entropi dari hasil ukur, bobot rata) ditambah "
        "1.000 undian Monte Carlo (lambda acak 0-1, bobot AHP +-25%). Matriks data "
        "TIDAK diubah. Kokoh terhadap bobot BUKAN berarti pasti benar: kalau isi "
        "matriksnya bias, peringkatnya bisa kokoh sekaligus keliru."
    )

    if nama:
        r = next((b for b in baris if b["name"] == nama), None)
        if r is None:
            raise ToolError(f"stasiun {nama!r} tidak punya skor. Pakai nama persis.")
        sens = r["sensitivity"]
        return {
            "stasiun": nama,
            "peringkat_resmi": r["rank"],
            "sepi": r["sepi"],
            "kelas": r["kelas"],
            "peringkat_per_skema": sens["peringkat_per_skema"],
            "kelas_per_skema": sens["kelas_per_skema"],
            "rentang_peringkat": [sens["peringkat_min"], sens["peringkat_maks"]],
            "monte_carlo_5_95_persen": [sens["mc_p05"], sens["mc_p95"]],
            "peluang_masuk_n_besar": sens["peluang_n_besar"],
            "n_besar": sens["n_besar"],
            "kokoh": sens["kokoh_n_besar"],
            "cara_menghitung": penjelasan,
        }

    n = baris[0]["sensitivity"]["n_besar"]
    return {
        "n_besar": n,
        "kokoh_di_semua_skema": [
            {"stasiun": b["name"], "peringkat_resmi": b["rank"],
             "rentang": [b["sensitivity"]["peringkat_min"], b["sensitivity"]["peringkat_maks"]]}
            for b in baris if b["sensitivity"]["kokoh_n_besar"]
        ],
        "sepuluh_besar_resmi_yang_rapuh": [
            {"stasiun": b["name"], "peringkat_resmi": b["rank"],
             "rentang": [b["sensitivity"]["peringkat_min"], b["sensitivity"]["peringkat_maks"]],
             "peluang_masuk_n_besar": b["sensitivity"]["peluang_n_besar"]}
            for b in baris[:n] if not b["sensitivity"]["kokoh_n_besar"]
        ],
        "cara_menghitung": penjelasan,
    }


def peluang_sponsorship_alat(
    db: Session, nama: str | None = None, menit: int = 10
) -> dict:
    """Peluang Facility Sponsorship dari keluhan fasilitas yang lolos validasi."""
    from app.services.sponsorship import peluang_sponsorship

    sid = None
    if nama:
        sid = db.execute(
            text("SELECT id FROM stations WHERE name = :n"), {"n": nama}
        ).scalar()
        if sid is None:
            raise ToolError(f"stasiun {nama!r} tidak ada. Pakai nama persis.")

    hasil = peluang_sponsorship(db, station_id=sid, menit=menit)
    return {
        "stasiun": nama,
        "jumlah": len(hasil.peluang),
        "dibantah_validasi_spasial": hasil.dibantah,
        "bukan_keluhan_fasilitas": hasil.bukan_fasilitas,
        "catatan": (
            "Keluhan yang dibantah query spasial sudah dibuang. Status "
            "'pengamatan langsung' berarti tidak ada data yang bisa mengujinya - "
            "sebutkan itu apa adanya, jangan menyebutnya tervalidasi."
        ),
        "peluang": [
            {
                "stasiun": p["stasiun"],
                "jenis": p["jenis"],
                "keluhan": p["keluhan"][:160],
                "status_validasi": p["validasi"]["status"],
                "dasar_validasi": p["validasi"]["catatan"],
                "usulan_sponsorship": p["usulan"]["bentuk"] or "belum ada usulan baku",
                "jarak_dari_stasiun_m": p["lokasi"]["jarak_m"],
            }
            for p in hasil.peluang[:MAX_BARIS]
        ],
    }


# Definisi alat dalam format OpenAI-compatible. Deskripsinya ditulis untuk
# dibaca model, jadi batas dan peringatannya ikut ditulis di sini - bukan cuma
# di docstring Python yang tidak pernah dilihat model.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "hitung_ulang_sepi",
            "description": (
                "Hitung ULANG peringkat SEPI dengan bobot variabel pilihan pengguna. "
                "Pakai kalau pengguna ingin tahu 'bagaimana kalau transportasi lebih "
                "penting', 'pakai bobot sama rata', atau sejenisnya. Hasilnya TIDAK "
                "menggantikan skor resmi; sebutkan itu saat menjawab."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bobot": {
                        "type": "object",
                        "description": (
                            "Bobot per variabel, kunci T/E/A/U/C. Boleh sebagian saja; "
                            "sisanya dibagi rata. Nilai boleh 0-1 atau persen."
                        ),
                        "additionalProperties": {"type": "number"},
                    },
                    "menit": {
                        "type": "integer",
                        "enum": [5, 10, 15],
                        "description": "Cincin isochrone, bawaan 10",
                    },
                    "batas": {"type": "integer", "description": "Berapa stasiun teratas, bawaan 10"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cari_stasiun",
            "description": (
                "Saring stasiun menurut kriteria: jumlah minimum line KRL, rentang skor "
                "SEPI, atau kelas. Pakai untuk pertanyaan site selection seperti "
                "'stasiun mana yang punya minimal 3 line' atau 'stasiun kelas Moderate'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "min_line": {"type": "integer", "description": "Jumlah minimum line KRL"},
                    "min_sepi": {"type": "number"},
                    "maks_sepi": {"type": "number"},
                    "kelas": {
                        "type": "string",
                        "description": "Low Potential / Moderate Potential / Premium Transit Hub",
                    },
                    "menit": {"type": "integer", "enum": [5, 10, 15]},
                    "batas": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "peringkat_tenant",
            "description": (
                "Peringkat stasiun terbaik untuk satu kategori usaha menurut Tenant "
                "Survival Index. Kategori yang ada: makanan_minuman, coffee_shop, "
                "alfamart, indomaret, apotek."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kategori": {"type": "string"},
                    "menit": {"type": "integer", "enum": [5, 10, 15]},
                    "batas": {"type": "integer"},
                },
                "required": ["kategori"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tenant_untuk_stasiun",
            "description": (
                "SELURUH kategori usaha untuk SATU stasiun sekaligus, diurutkan dari "
                "TSI tertinggi. Pakai ini untuk pertanyaan 'kategori usaha apa yang "
                "paling cocok / paling lapang pasarnya di stasiun X'. JANGAN memanggil "
                "peringkat_tenant berkali-kali untuk stasiun yang sama."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nama": {"type": "string", "description": "Nama stasiun persis"},
                    "menit": {"type": "integer", "enum": [5, 10, 15]},
                },
                "required": ["nama"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bandingkan_stasiun",
            "description": (
                "Bandingkan beberapa stasiun berdampingan, lengkap dengan nilai tiap "
                "variabel SEPI dan angka mentahnya. Pakai nama stasiun persis."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nama": {"type": "array", "items": {"type": "string"}},
                    "menit": {"type": "integer", "enum": [5, 10, 15]},
                },
                "required": ["nama"],
            },
        },
    },
]

TOOL_SCHEMAS.append(
    {
        "type": "function",
        "function": {
            "name": "kekokohan_peringkat",
            "description": (
                "Seberapa KOKOH peringkat SEPI terhadap pilihan pembobotan. Pakai saat "
                "ditanya 'apakah peringkat ini bisa dipercaya', 'stasiun mana yang "
                "pasti unggul', 'kenapa X di atas Y', atau sebelum merekomendasikan "
                "stasiun teratas. Tanpa nama: daftar stasiun yang kokoh dan yang rapuh. "
                "Dengan nama: rincian satu stasiun. Selalu sebut bahwa kokoh terhadap "
                "bobot tidak sama dengan pasti benar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nama": {"type": "string", "description": "Nama stasiun persis (opsional)"},
                    "menit": {"type": "integer", "enum": [5, 10, 15]},
                },
            },
        },
    }
)

TOOL_SCHEMAS.append(
    {
        "type": "function",
        "function": {
            "name": "peluang_sponsorship",
            "description": (
                "Keluhan fasilitas yang bisa diubah jadi peluang Facility Sponsorship "
                "(CSR), lengkap dengan usulan bentuk sponsorship dan status validasi "
                "spasialnya. Pakai saat ditanya soal keluhan, fasilitas rusak, peluang "
                "CSR, atau kemitraan perbaikan fasilitas. Tanpa nama: seluruh stasiun."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nama": {"type": "string", "description": "Nama stasiun persis (opsional)"},
                    "menit": {"type": "integer", "enum": [5, 10, 15]},
                },
            },
        },
    }
)

SQL_PAPARAN_PERINGKAT = """
SELECT s.name,
       (0.5 * sc.raw_t + 0.3 * sc.raw_e + 0.2 * sc.raw_u) * 100 AS cei,
       sc.rank AS peringkat_sepi,
       sc.sepi,
       sc.confidence
  FROM station_scores sc
  JOIN stations s ON s.id = sc.station_id
 WHERE sc.minutes = :menit
   AND sc.raw_t IS NOT NULL AND sc.raw_e IS NOT NULL AND sc.raw_u IS NOT NULL
 ORDER BY cei DESC
 LIMIT :batas
"""


def peringkat_paparan(db: Session, menit: int = 10, batas: int = 10) -> dict:
    """Peringkat stasiun menurut PAPARAN (CEI), bukan menurut SEPI.

    Inilah alat yang benar untuk pertanyaan "stasiun mana yang paling bagus
    untuk memasang iklan". SEPI menilai potensi ekonomi kawasan dan memberi
    bobot besar pada aksesibilitas serta keberagaman kawasan - berguna untuk
    menilai kelayakan usaha, keliru untuk menilai paparan iklan.

    Bedanya nyata: Tanah Abang peringkat 23 menurut SEPI padahal nilai
    transportasinya tertinggi, dan menjadi peringkat 2 menurut CEI.
    """
    if menit not in (5, 10, 15):
        raise ToolError(f"cincin isochrone cuma 5, 10, atau 15 menit, bukan {menit}")

    baris = db.execute(
        text(SQL_PAPARAN_PERINGKAT),
        {"menit": menit, "batas": min(batas, MAX_BARIS)},
    ).mappings().all()

    return {
        "cincin_menit": menit,
        "rumus": "CEI = 0,5 x Transportasi + 0,3 x Ekonomi + 0,2 x Urban (PRD hal. 13)",
        "catatan": (
            "Peringkat ini memakai Composite Exposure Index, bukan SEPI. Untuk "
            "pertanyaan penempatan iklan dan hak penamaan, inilah ukuran yang "
            "benar. Sebutkan juga confidence-nya."
        ),
        "peringkat": [
            {
                "peringkat": i,
                "stasiun": r["name"],
                "cei": round(float(r["cei"]), 1),
                "peringkat_sepi": r["peringkat_sepi"],
                "sepi": round(float(r["sepi"]), 1),
                "confidence": round(float(r["confidence"]), 2),
            }
            for i, r in enumerate(baris, start=1)
        ],
    }


SQL_CARI_POI = """
WITH st AS (SELECT id FROM stations WHERE name = :stasiun)
SELECT 'di dalam stasiun' AS lingkup,
       t.name             AS nama,
       t.category         AS kategori,
       NULL::float        AS jarak_m
  FROM tenants t, st
 WHERE t.station_id = st.id AND t.name ILIKE :pola
UNION ALL
SELECT 'di sekitar stasiun',
       p.name,
       p.category,
       ST_Distance(p.location::geography, s.location::geography)
  FROM poi p, isochrones i, stations s, st
 WHERE i.station_id = st.id AND i.minutes = :menit
   AND s.id = st.id
   AND ST_Contains(i.geom, p.location)
   AND p.name ILIKE :pola
 ORDER BY lingkup, jarak_m NULLS FIRST
 LIMIT :batas
"""


def cari_poi(db: Session, stasiun: str, kata_kunci: str, menit: int = 10, batas: int = 12) -> dict:
    """Cari tempat atau merek tertentu di satu stasiun dan sekitarnya.

    Urutannya menirukan cara orang bertanya: DI DALAM stasiun dulu, baru
    kawasan sekitarnya dalam jangkauan jalan kaki. Pertanyaan "ada ATM BCA di
    Tanah Abang?" sebelumnya tidak terjawab sama sekali karena asisten tidak
    punya alat untuk memeriksa nama tempat - ia hanya bisa melihat angka
    agregat, sehingga menjawab ngawur atau mengelak.

    Pencarian memakai kecocokan sebagian pada nama, jadi "BCA" menemukan "ATM
    BCA" maupun "Bank BCA KCP Tanah Abang".
    """
    sid = db.execute(
        text("SELECT id FROM stations WHERE name = :n"), {"n": stasiun}
    ).scalar()
    if sid is None:
        raise ToolError(f"stasiun {stasiun!r} tidak ada. Pakai nama persis.")
    if menit not in (5, 10, 15):
        raise ToolError(f"cincin isochrone cuma 5, 10, atau 15 menit, bukan {menit}")

    baris = db.execute(
        text(SQL_CARI_POI),
        {
            "stasiun": stasiun,
            "pola": f"%{kata_kunci}%",
            "menit": menit,
            "batas": min(batas, MAX_BARIS),
        },
    ).mappings().all()

    di_dalam = [r for r in baris if r["lingkup"] == "di dalam stasiun"]
    di_sekitar = [r for r in baris if r["lingkup"] != "di dalam stasiun"]

    return {
        "stasiun": stasiun,
        "dicari": kata_kunci,
        "cincin_menit": menit,
        "jumlah_di_dalam_stasiun": len(di_dalam),
        "jumlah_di_sekitar": len(di_sekitar),
        "hasil": [
            {
                "nama": r["nama"],
                "kategori": r["kategori"],
                "lingkup": r["lingkup"],
                "jarak_m": round(r["jarak_m"]) if r["jarak_m"] is not None else None,
            }
            for r in baris
        ],
        "catatan": (
            "Kosong berarti tidak tercatat di data kami, BUKAN berarti tidak "
            "ada di lapangan. Titik minat berasal dari OpenStreetMap dan survei "
            "MAPID; gerai yang belum dipetakan tidak akan muncul."
            if not baris
            else "Yang di dalam stasiun berasal dari survei tenant; yang di "
            "sekitar dari titik minat dalam jangkauan jalan kaki."
        ),
    }


def profil_paparan_alat(db: Session, nama: str) -> dict:
    """Profil paparan satu stasiun: siapa yang melintas dan format iklan yang cocok.

    KENAPA ALAT INI ADA. Sebelum ini asisten hanya punya SEPI untuk menjawab
    pertanyaan penempatan iklan, dan SEPI bukan ukuran kecocokan iklan - ia
    potensi ekonomi kawasan. Akibatnya pertanyaan apa pun soal iklan dijawab
    dengan stasiun berskor tertinggi: ditanya iklan perbankan, jawabannya
    Pondok Jati; ditanya iklan apa pun yang lain, jawabannya Pondok Jati lagi.

    Dengan alat ini asisten bisa memeriksa profil pengunjung dan pola singgah
    sebelum merekomendasikan penempatan - dua hal yang justru menentukan
    kecocokan sektor iklan, dan tidak terbaca sama sekali dari skor SEPI.
    """
    from app.services.profil_paparan import profil_paparan, sektor_iklan

    sid = db.execute(
        text("SELECT id FROM stations WHERE name = :n"), {"n": nama}
    ).scalar()
    if sid is None:
        raise ToolError(f"stasiun {nama!r} tidak ada. Pakai nama persis.")

    p = profil_paparan(db, sid)
    sektor = sektor_iklan(p.audiens, p.waktu_singgah)
    return {
        "stasiun": p.station_name,
        "profil_pengunjung": p.audiens,
        "keramaian": p.keramaian,
        "waktu_singgah": p.waktu_singgah,
        "format_iklan": p.format_iklan,
        "sektor_iklan_cocok": sektor,
        "catatan": (
            "Kecocokan sektor iklan ditentukan profil pengunjung dan pola "
            "singgah, BUKAN oleh skor SEPI. SEPI mengukur potensi ekonomi "
            "kawasan, bukan kecocokan iklan."
        ),
    }


TOOL_SCHEMAS.append(
    {
        "type": "function",
        "function": {
            "name": "cari_poi",
            "description": (
                "Cari tempat, merek, atau jenis usaha tertentu di satu stasiun "
                "dan kawasan sekitarnya. Pakai untuk pertanyaan seperti 'apakah "
                "ada ATM BCA di Tanah Abang', 'ada Indomaret tidak di sini', "
                "atau 'kedai kopi apa saja yang ada'. Memeriksa DI DALAM "
                "stasiun lebih dulu, lalu kawasan dalam jangkauan jalan kaki."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "stasiun": {"type": "string", "description": "Nama stasiun persis"},
                    "kata_kunci": {
                        "type": "string",
                        "description": "Nama atau merek yang dicari, misal 'BCA' atau 'Indomaret'",
                    },
                    "menit": {"type": "integer", "enum": [5, 10, 15]},
                },
                "required": ["stasiun", "kata_kunci"],
            },
        },
    }
)


TOOL_SCHEMAS.append(
    {
        "type": "function",
        "function": {
            "name": "peringkat_paparan",
            "description": (
                "Peringkat stasiun menurut PAPARAN IKLAN (Composite Exposure "
                "Index: 0,5 transportasi + 0,3 ekonomi + 0,2 urban). WAJIB "
                "dipakai untuk pertanyaan 'stasiun mana yang paling bagus untuk "
                "iklan' atau hak penamaan. JANGAN pakai peringkat SEPI untuk "
                "itu - SEPI memberi bobot besar pada aksesibilitas dan "
                "keberagaman kawasan, sehingga stasiun tersibuk justru bisa "
                "tampil rendah."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "menit": {"type": "integer", "enum": [5, 10, 15]},
                    "batas": {"type": "integer"},
                },
            },
        },
    }
)


TOOL_SCHEMAS.append(
    {
        "type": "function",
        "function": {
            "name": "profil_paparan",
            "description": (
                "Profil paparan satu stasiun: siapa yang melintas, pola keramaian "
                "per rentang waktu, lama singgah, format iklan yang sesuai, dan "
                "sektor usaha yang cocok beriklan. WAJIB dipakai untuk pertanyaan "
                "penempatan iklan, target audiens, atau sektor apa yang cocok - "
                "skor SEPI TIDAK menjawab itu, karena SEPI mengukur potensi "
                "ekonomi kawasan, bukan kecocokan iklan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nama": {"type": "string", "description": "Nama stasiun persis"}
                },
                "required": ["nama"],
            },
        },
    }
)


TOOLS = {
    "hitung_ulang_sepi": hitung_ulang_sepi,
    "profil_paparan": profil_paparan_alat,
    "cari_poi": cari_poi,
    "peringkat_paparan": peringkat_paparan,
    "cari_stasiun": cari_stasiun,
    "peringkat_tenant": peringkat_tenant,
    "tenant_untuk_stasiun": tenant_untuk_stasiun,
    "bandingkan_stasiun": bandingkan_stasiun,
    "kekokohan_peringkat": kekokohan_peringkat,
    "peluang_sponsorship": peluang_sponsorship_alat,
}


def jalankan_terekam(db: Session, nama: str, argumen: dict) -> tuple[str, dict | None]:
    """Seperti `jalankan`, tetapi juga mengembalikan hasilnya sebagai dict.

    Dict itu dipakai `ai_actions` untuk menyusun tombol aksi dari hasil alat
    yang SUNGGUH dipanggil - bukan dari kalimat yang dikarang model.
    """
    teks = jalankan(db, nama, argumen)
    try:
        hasil = json.loads(teks)
    except json.JSONDecodeError:
        return teks, None
    return teks, (None if "error" in hasil else hasil)


def jalankan(db: Session, nama: str, argumen: dict) -> str:
    """Jalankan satu alat, kembalikan hasilnya sebagai JSON untuk model.

    Error ikut dikembalikan sebagai JSON, bukan dilempar. Model perlu TAHU
    bahwa panggilannya gagal supaya bisa menyampaikannya apa adanya; melempar
    hanya akan memutus percakapan dengan 500.
    """
    fungsi = TOOLS.get(nama)
    if fungsi is None:
        return json.dumps({"error": f"alat {nama!r} tidak ada"}, ensure_ascii=False)

    try:
        hasil = fungsi(db, **argumen)
    except ToolError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    except TypeError as exc:
        return json.dumps(
            {"error": f"argumen tidak cocok untuk {nama}: {exc}"}, ensure_ascii=False
        )

    return json.dumps(hasil, ensure_ascii=False, default=str)
