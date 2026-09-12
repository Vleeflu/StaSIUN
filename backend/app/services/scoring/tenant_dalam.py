"""Pesaing yang beroperasi DI DALAM stasiun, dan taksirannya bila belum disurvei.

PRD hal. 13: "Komponen supply mencakup titik minat di luar stasiun maupun tenant
yang telah beroperasi di dalam stasiun, sehingga kategori yang sebenarnya sudah
tersedia tidak akan muncul sebagai kesenjangan semu."

Sisi luar sudah terhitung sejak awal lewat lajur POI. Sisi dalam yang belum, dan
menambahkannya tidak sesederhana menjumlahkan dua angka - karena survei lapangan
baru mencakup 14 dari 45 stasiun.

KENAPA NOL BUKAN JAWABAN UNTUK STASIUN YANG BELUM DISURVEI
-----------------------------------------------------------
Kalau 31 stasiun sisanya diberi nol, mereka justru naik peringkat: penyebutnya
lebih kecil, jadi peluangnya tampak lebih lapang. Artinya sistem menghadiahi
ketidaktahuan, dan stasiun yang kita periksa dengan susah payah malah dihukum
karena pesaingnya jadi ketahuan. Itu kebalikan dari yang seharusnya.

Jadi sisi dalam ditaksir dengan shrinkage estimator yang sama seperti indikator
lain (PRD hal. 15): condong ke rata-rata stasiun sejenis ketika sampelnya
sedikit, condong ke data sendiri ketika sampelnya banyak. Taksirannya lalu
diberi simpangan, dan TSI dihitung dua kali - sekali dengan taksiran, sekali
dengan taksiran yang meleset ke arah merugikan. Yang kedua dipakai mengurutkan
peringkat.
"""

from __future__ import annotations

import math

from sqlalchemy import text
from sqlalchemy.orm import Session

# Kategori tenant survei ditulis BEBAS oleh surveyor - 60 ejaan berbeda untuk
# 128 tenant, dari "kuliner" sampai "bolu kukus dan aneka jajanan kemasan".
# Tidak ada taksonomi yang bisa disandarkan, jadi pencocokannya lewat kata
# kunci, dan yang tidak cocok TIDAK dipaksa masuk salah satu sektor.
#
# Urutannya penting: sektor yang lebih sempit diperiksa lebih dulu, supaya
# "kedai kopi" tidak keburu tertangkap kata "kedai" milik makanan & minuman.
KATA_KUNCI: list[tuple[str, tuple[str, ...]]] = [
    ("coffee_shop", ("kopi", "coffee", "cafe", "kafe")),
    ("apotek", ("apotek", "apotik", "farmasi")),
    ("minimarket", ("minimarket", "convenience", "kelontong", "swalayan")),
    (
        "makanan_minuman",
        (
            "makan", "minum", "kuliner", "jajan", "food", "beverage", "resto",
            "warung", "bakso", "roti", "bakery", "dessert", "camilan", "snack",
            "padang", "kedai", "gerobak", "cimol", "bolu", "olahan buah",
            "street food", "boga", "katering", "es ",
        ),
    ),
]

# Sebutan yang TIDAK menunjuk sektor apa pun. Didaftar terpisah supaya jelas
# bahwa ia diabaikan dengan sengaja, bukan lolos karena kata kuncinya kurang.
#
# "UMKM" dan "booth" menerangkan bentuk usahanya, bukan dagangannya; "pijat",
# "shuttle", dan "penginapan" jelas bukan sektor yang diskor. Semuanya tetap
# tercatat di katalog, hanya tidak dihitung sebagai pesaing sektor mana pun.
TIDAK_TERBACA = (
    "umkm", "lainnya", "booth", "gerai", "franchise", "musiman", "merchandise",
    "shuttle", "pijat", "hotel", "penginapan", "bazar", "event", "kios",
    "health", "klinik",
)

# Konstanta k pada w = n / (n + k). Dengan k = 3, stasiun bersurvei 3 titik
# sudah setengah percaya datanya sendiri. Dipilih kecil karena jumlah titik
# survei per stasiun memang sedikit - k besar akan membuat SEMUA stasiun
# memakai rata-rata kelompok, dan survei lapangan jadi sia-sia.
K_SHRINKAGE = 3.0

# Keyakinan saat sisi dalam sepenuhnya taksiran. Bukan nol: sisi luar tetap
# terukur penuh, dan sisi luar itulah bagian terbesar penyebutnya.
CONFIDENCE_TAKSIRAN = 0.6
CONFIDENCE_TERUKUR = 1.0


def sektor_dari_kategori(kategori: str) -> str | None:
    """Petakan kategori tulisan-bebas surveyor ke satu sektor TSI, atau None."""
    teks = (kategori or "").strip().lower()
    if not teks:
        return None

    for sektor, kunci in KATA_KUNCI:
        if any(k in teks for k in kunci):
            return sektor

    return None


SQL_TENANT_DALAM = text(
    """
    SELECT station_id, category
      FROM tenants
     WHERE status = 'aktif'
    """
)


def cacah_per_stasiun(db: Session) -> tuple[dict[int, dict[str, int]], set[int]]:
    """Hitung tenant dalam stasiun per sektor, dan daftar stasiun yang disurvei.

    Stasiun yang muncul di tabel `tenants` dianggap SUDAH diperiksa, sekalipun
    cacahnya nol untuk sektor tertentu - nol di stasiun yang disurvei adalah
    temuan, berbeda dari nol karena belum pernah didatangi.
    """
    cacah: dict[int, dict[str, int]] = {}
    disurvei: set[int] = set()

    for row in db.execute(SQL_TENANT_DALAM).mappings():
        sid = row["station_id"]
        disurvei.add(sid)
        sektor = sektor_dari_kategori(row["category"])
        if sektor is None:
            continue
        cacah.setdefault(sid, {}).setdefault(sektor, 0)
        cacah[sid][sektor] += 1

    return cacah, disurvei


def _sebaran(nilai: list[float]) -> float:
    """Simpangan baku sampel; nol kalau datanya terlalu sedikit untuk punya sebaran."""
    if len(nilai) < 2:
        return 0.0
    rata = sum(nilai) / len(nilai)
    ragam = sum((v - rata) ** 2 for v in nilai) / (len(nilai) - 1)
    return math.sqrt(ragam)


def taksir(
    sektor: str,
    id_stasiun: list[int],
    cacah: dict[int, dict[str, int]],
    disurvei: set[int],
    titik_survei: dict[int, int],
) -> dict[int, tuple[float, float, bool]]:
    """Sisi dalam tiap stasiun: (nilai, simpangan, terukur).

    Stasiun yang belum disurvei mendapat rata-rata stasiun yang sudah disurvei,
    dengan simpangan sebesar sebaran antar-stasiun itu. Stasiun yang sudah
    disurvei tetapi titiknya sedikit ditarik sebagian ke rata-rata tersebut,
    mengikuti w = n / (n + k).
    """
    terukur = [float(cacah.get(sid, {}).get(sektor, 0)) for sid in id_stasiun if sid in disurvei]
    rata_grup = sum(terukur) / len(terukur) if terukur else 0.0
    sebaran_grup = _sebaran(terukur)

    hasil: dict[int, tuple[float, float, bool]] = {}
    for sid in id_stasiun:
        n = float(titik_survei.get(sid, 0)) if sid in disurvei else 0.0

        # n = 0 berarti taksiran murni, dan itu mencakup DUA keadaan: stasiun
        # yang belum pernah didatangi, dan stasiun yang sudah didatangi tetapi
        # tak satu pun kategori tenantnya terbaca sebagai sektor yang diskor
        # ("UMKM", "booth", "lainnya"). Keduanya sama-sama tidak memberi
        # informasi tentang sektor ini, jadi keduanya tidak boleh mengaku
        # terukur - sempat begitu, dan akibatnya stasiun tanpa satu pun kategori
        # terbaca tetap berkeyakinan penuh.
        if n == 0:
            hasil[sid] = (rata_grup, sebaran_grup, False)
            continue

        sendiri = float(cacah.get(sid, {}).get(sektor, 0))
        w = n / (n + K_SHRINKAGE)
        nilai = w * sendiri + (1.0 - w) * rata_grup
        # Makin condong ke data sendiri, makin kecil sisa ketidakpastiannya.
        hasil[sid] = (nilai, (1.0 - w) * sebaran_grup, True)

    return hasil
