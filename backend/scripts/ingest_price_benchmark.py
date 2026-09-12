"""Isi `price_references` dengan benchmark hasil riset sumber terbuka (N6).

Dua jalur harga yang mengisi tabel ini, dan bedanya penting:

- `source = 'survey activity'` -> harga menu yang DISEBUT narasumber di
  lapangan, dipanen `activity_extract._simpan_harga`. Data primer.
- `source = 'riset'` (berkas ini) -> benchmark pasar dari laporan industri.
  Data sekunder, berlaku untuk kawasan, bukan untuk satu lapak.

PRD hal. 9 mensyaratkan pencatatan sumber dan tanggal akses untuk keduanya,
dan melarang kanal pesan-antar daring (gofood, grabfood) sebagai sumber harga
menu karena memuat harga setelah markup. Benchmark di berkas ini bukan harga
menu, jadi larangan itu tidak berlaku - tetapi sumbernya tetap dicatat.

`station_id` sengaja NULL. Angka-angka ini berlaku untuk pasar Jakarta secara
keseluruhan atau untuk CBD, bukan untuk satu stasiun tertentu. Menempelkannya
ke stasiun satu per satu akan mengubah benchmark jadi seolah hasil pengukuran
di tempat itu.
"""

from __future__ import annotations

import argparse
from datetime import date

from sqlalchemy import text

from app.core.database import SessionLocal

# Tiap baris WAJIB membawa sumber, tautan, dan tanggal akses. Kalau sebuah
# angka tidak punya ketiganya, ia tidak masuk ke sini - lebih baik kosong
# daripada angka yang tidak bisa ditelusuri asalnya.
BENCHMARK = [
    {
        "kind": "sewa",
        "category": "ritel_jakarta",
        "item_name": "tarif sewa dasar rata-rata pusat perbelanjaan Jakarta",
        "price_idr": 480_400,
        "unit": "per m2 per bulan",
        "source": "Colliers Quarterly Property Market Report Q1 2026 Jakarta Retail",
        "source_url": "https://www.colliers.com/id-id/research/colliers-quarterly-property-market-report-q1-2026-jakarta-retail",
        "accessed_at": date(2026, 9, 12),
    },
    {
        "kind": "sewa",
        "category": "ritel_cbd",
        "item_name": "tarif sewa dasar rata-rata pusat perbelanjaan di CBD",
        "price_idr": 593_300,
        "unit": "per m2 per bulan",
        "source": "Colliers Quarterly Property Market Report Q1 2026 Jakarta Retail",
        "source_url": "https://www.colliers.com/id-id/research/colliers-quarterly-property-market-report-q1-2026-jakarta-retail",
        "accessed_at": date(2026, 9, 12),
    },
]

# N7 - benchmark tarif per seribu paparan (CPM) iklan luar ruang Indonesia.
#
# Batas bawah dan batas atas disimpan sebagai DUA BARIS terpisah, bukan
# dirata-ratakan jadi satu angka. Rentang 45.000-95.000 itu selisih dua kali
# lipat; memampatkannya jadi "70.000" menyembunyikan ketidakpastian yang justru
# harus ikut ditampilkan saat harga wajar sebuah ruang iklan ditawarkan.
#
# Angkanya data 2025 yang diakses 2026. Selisih tahun itu ditulis di nama
# sumbernya, bukan disamarkan - pembaca berhak tahu benchmark ini setahun lebih
# tua daripada tanggal aksesnya.
_CPM_SUMBER = "Lestari Ads - OOH CPM benchmarks Indonesia (data 2025)"
_CPM_URL = (
    "https://www.lestariads.com/en/blog/marketing/"
    "expected-cpm-cpc-and-roi-benchmarks-for-ooh-advertising-in-indonesia-2025-data.html"
)
_CPM_DIAKSES = date(2026, 9, 12)

for _kategori, _bawah, _atas in [
    ("ooh_transit_kereta", 45_000, 95_000),
    ("ooh_digital_cbd", 60_000, 120_000),
    ("ooh_billboard_statis", 38_000, 75_000),
    ("ooh_indoor_dooh", 30_000, 55_000),
]:
    for _sisi, _nilai in (("batas bawah", _bawah), ("batas atas", _atas)):
        BENCHMARK.append(
            {
                "kind": "ooh",
                "category": _kategori,
                "item_name": _sisi,
                "price_idr": _nilai,
                "unit": "per seribu paparan",
                "source": _CPM_SUMBER,
                "source_url": _CPM_URL,
                "accessed_at": _CPM_DIAKSES,
            }
        )

SQL_ADA = """
SELECT id FROM price_references
 WHERE kind = :kind AND category = :category AND source = :source
   AND item_name IS NOT DISTINCT FROM :item_name
   AND station_id IS NULL
"""

SQL_SISIP = """
INSERT INTO price_references
       (kind, category, item_name, price_idr, unit, station_id,
        source, source_url, accessed_at, created_at, updated_at)
VALUES (:kind, :category, :item_name, :price_idr, :unit, NULL,
        :source, :source_url, :accessed_at, now(), now())
"""

SQL_PERBARUI = """
UPDATE price_references
   SET item_name = :item_name, price_idr = :price_idr, unit = :unit,
       source_url = :source_url, accessed_at = :accessed_at, updated_at = now()
 WHERE id = :id
"""


def main() -> None:
    p = argparse.ArgumentParser(description="Isi benchmark harga hasil riset.")
    p.add_argument("--tampilkan", action="store_true", help="tampilkan isi tabel lalu keluar")
    args = p.parse_args()

    session = SessionLocal()
    try:
        if args.tampilkan:
            baris = session.execute(
                text(
                    """SELECT kind, category, price_idr, unit, source, accessed_at,
                              station_id
                         FROM price_references ORDER BY kind, category, id"""
                )
            ).all()
            print(f"{len(baris)} baris price_references:")
            for r in baris:
                lingkup = f"stasiun {r.station_id}" if r.station_id else "kawasan Jakarta"
                print(
                    f"  [{r.kind}] {r.category:18} Rp{int(r.price_idr):>10,} {r.unit:18} "
                    f"{lingkup:16} <- {r.source[:38]} ({r.accessed_at})"
                )
            return

        baru = diperbarui = 0
        for b in BENCHMARK:
            ada = session.execute(SQL_ADA_TEKS, b).first()
            if ada:
                session.execute(text(SQL_PERBARUI), {**b, "id": ada.id})
                diperbarui += 1
            else:
                session.execute(text(SQL_SISIP), b)
                baru += 1
        session.commit()
        print(f"{baru} benchmark baru, {diperbarui} diperbarui.")
        print(
            "station_id NULL -> angka ini benchmark kawasan, bukan pengukuran "
            "di satu stasiun."
        )
    finally:
        session.close()


SQL_ADA_TEKS = text(SQL_ADA)


if __name__ == "__main__":
    main()
