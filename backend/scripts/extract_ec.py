"""Ekstrak variabel E dan C dari narasi Activity memakai LLM, dengan verifikasi kutipan.

Pakai:
    python -m scripts.extract_ec
    python -m scripts.extract_ec --batas 20     # coba sedikit dulu
    python -m scripts.extract_ec --fasilitas-ulang   # kondisi fasilitas utk narasi lama
    python -m scripts.extract_ec --stasiun "Jakarta Kota" "Tanah Abang"

Idempoten: narasi yang sudah pernah dibaca model (`llm_ec_at` terisi) dilewati,
termasuk yang memang tidak memuat apa pun.
"""

import argparse
import sys

from app.core.database import SessionLocal
from app.services.activity_extract import (
    ekstrak_fasilitas_ulang,
    ekstrak_harga_ulang,
    ekstrak_semua,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--batas",
        type=int,
        default=None,
        help="berhenti setelah sekian narasi diproses; berguna untuk mencoba dulu",
    )
    p.add_argument(
        "--fasilitas-ulang",
        action="store_true",
        help="ekstrak ulang kondisi fasilitas (positif maupun negatif) untuk narasi "
        "yang dulu diekstrak dengan skema keluhan saja",
    )
    p.add_argument(
        "--harga-ulang",
        action="store_true",
        help="panen harga untuk narasi yang terlanjur diekstrak sebelum skema "
        "memuat bagian harga. Narasi tanpa angka rupiah ditandai selesai tanpa "
        "memanggil model, jadi kuota hanya terpakai untuk yang benar-benar berharga",
    )
    p.add_argument(
        "--menyebut",
        default=None,
        help="hanya narasi yang ISINYA cocok pola ini (regex, tidak peka huruf besar). "
        "Contoh: --menyebut 'iklan|videotron|billboard'. Dipakai bersama --stasiun "
        "supaya kuota yang terbatas jatuh tepat pada narasi yang dicari",
    )
    p.add_argument(
        "--stasiun",
        nargs="+",
        default=None,
        help="batasi ke stasiun tertentu (nama persis). Dipakai saat kuota harian penyedia model terbatas; mengubah urutan kerja, bukan syarat masuk",
    )
    args = p.parse_args()

    session = SessionLocal()
    try:
        if args.harga_ulang:
            hasil = ekstrak_harga_ulang(session, batas=args.batas, stasiun=args.stasiun)
        elif args.fasilitas_ulang:
            hasil = ekstrak_fasilitas_ulang(
                session, batas=args.batas, stasiun=args.stasiun
            )
        else:
            hasil = ekstrak_semua(
                session, batas=args.batas, stasiun=args.stasiun, menyebut=args.menyebut
            )
    except RuntimeError as exc:
        print(f"! {exc}")
        return 1
    finally:
        session.close()

    if hasil.penyedia_terpakai:
        print(f"penyedia model terpakai: {', '.join(hasil.penyedia_terpakai)}")
    print(f"{hasil.diproses} narasi diproses, {hasil.dilewati} dilewati (tidak menyebut iklan/lapak/keluhan)")
    print()
    print(f"  {hasil.iklan:5d} media iklan")
    print(f"  {hasil.klaster:5d} klaster lapak")
    print(f"  {hasil.tenant:5d} tenant")
    print(f"  {hasil.keluhan:5d} catatan kondisi fasilitas ({hasil.fasilitas_positif} bernada positif)")
    print(f"  {hasil.harga:5d} harga menu -> price_references")
    if hasil.harga_luar_stasiun:
        print(
            f"  {hasil.harga_luar_stasiun:5d} harga dilewati karena lapaknya DI LUAR "
            "batas area stasiun (250 m)"
        )
    if hasil.omset_dilewati:
        print(
            f"  {hasil.omset_dilewati:5d} angka rupiah SENGAJA dilewati (omset harian, "
            "bukan harga menu)"
        )

    if hasil.kutipan_ditolak:
        print(
            f"\n{hasil.kutipan_ditolak} ekstraksi DITOLAK karena kutipannya tidak "
            "ditemukan di narasi aslinya."
        )
        print(
            "Ini penjagaan bekerja, bukan kegagalan: model boleh salah membaca,\n"
            "yang tidak boleh adalah salahnya lolos jadi angka yang tak terbantah."
        )
        for c in hasil.contoh_ditolak:
            print(f"  contoh kutipan ditolak: {c!r}")

    if hasil.kena_rate_limit:
        print(
            f"\nBERHENTI: SELURUH penyedia model kehabisan kuota harian. {hasil.kena_rate_limit} "
            "narasi belum sempat diproses.\n"
            "Ini BUKAN kegagalan metode — obatnya menunggu kuota harian pulih,\n"
            "atau menaikkan tier. Jalankan ulang perintah yang sama nanti; yang\n"
            "sudah tersimpan tidak diproses dua kali."
        )
        if hasil.pesan_rate_limit:
            print(f"  pesan penyedia: {hasil.pesan_rate_limit[:160]}")

    if hasil.bentuk_salah:
        print(
            f"\n{hasil.bentuk_salah} bagian balasan berbentuk salah (bukan objek) "
            "dilewati. Tidak ditebak isinya: tanpa objek, tidak ada kutipan yang "
            "bisa diverifikasi."
        )

    if hasil.gagal_parse:
        print(f"\n{hasil.gagal_parse} balasan model tidak terbaca sebagai JSON, dilewati.")

    print(
        "\nCATATAN: hasil ini BELUM boleh menyentuh skor. PRD hal. 16 menetapkan\n"
        "output model berbasis teks dibatasi maksimal 15 persen dan wajib melalui\n"
        "validasi silang spasial (F5-1c)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
