"""Sajikan foto survei berformat HEIC sebagai JPEG.

MASALAHNYA
----------
76 dari sekitar 3.400 foto Activity berformat HEIC - bawaan kamera iPhone.
Hanya Safari yang menampilkannya; di Chrome dan Firefox yang terlihat kotak
rusak. CDN MAPID tidak menyediakan konversi: diuji dengan `?format=jpg` dan
`?f=jpg`, balasannya tetap `Content-Type: image/heic`.

Menyembunyikan foto itu bukan jawaban - justru foto lapangan yang membuat
katalog ruang iklan bisa dipercaya. Maka konversinya dikerjakan di sini.

KEPUTUSAN YANG MENENTUKAN KEAMANANNYA
-------------------------------------
Endpoint ini mengambil URL dari parameter, dan itu persis bentuk yang bisa
berubah jadi proxy terbuka - orang memakai server kita untuk menarik apa pun
dari mana pun, termasuk alamat di dalam jaringan kita sendiri (SSRF).

Karena itu host-nya dibatasi ke daftar tertutup di `HOST_DIIZINKAN`. Alamat di
luar daftar ditolak 400, bukan dicoba dulu. Daftar tertutup dipilih alih-alih
"tolak yang mencurigakan", karena yang kedua selalu ketinggalan satu langkah
dari cara baru menuliskan alamat yang sama.

Hanya HEIC yang dikonversi. Foto JPEG dan PNG tidak melewati endpoint ini sama
sekali - tampilan memakai URL aslinya langsung, supaya kita tidak menyalurkan
ribuan gambar yang sudah bisa ditampilkan browser tanpa bantuan apa pun.
"""

from __future__ import annotations

import io
from urllib.parse import urlparse

import httpx
import pillow_heif
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from PIL import Image

pillow_heif.register_heif_opener()

router = APIRouter(tags=["foto"])

# Daftar tertutup. Hanya CDN tempat foto Activity benar-benar disimpan.
HOST_DIIZINKAN = {
    "mapid-app-chat.cdn.mapid.io",
    "mapid.cdn.mapid.io",
}

# Sisi terpanjang setelah konversi. Foto aslinya 4000x3000 piksel dan hampir
# 3 MB; ditampilkan sebagai gambar kecil di katalog, ukuran itu pemborosan
# murni. 1600 piksel masih tajam saat foto dibuka penuh.
SISI_MAKS = 1600

BATAS_UNDUH = 25 * 1024 * 1024  # foto HEIC terbesar yang masuk akal


@router.get("/foto")
async def foto(url: str = Query(..., description="URL foto Activity berformat HEIC")):
    """Ambil satu foto HEIC dari CDN MAPID, kembalikan sebagai JPEG."""
    alamat = urlparse(url)
    if alamat.scheme not in ("http", "https") or alamat.hostname not in HOST_DIIZINKAN:
        raise HTTPException(
            status_code=400,
            detail="Hanya foto dari CDN MAPID yang bisa dikonversi lewat endpoint ini.",
        )

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as klien:
            balasan = await klien.get(url)
            balasan.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Gagal mengambil foto: {exc}") from exc

    if len(balasan.content) > BATAS_UNDUH:
        raise HTTPException(status_code=413, detail="Foto terlalu besar untuk dikonversi.")

    try:
        gambar = Image.open(io.BytesIO(balasan.content))
        gambar.thumbnail((SISI_MAKS, SISI_MAKS))
        keluaran = io.BytesIO()
        gambar.convert("RGB").save(keluaran, "JPEG", quality=82, optimize=True)
    except Exception as exc:  # noqa: BLE001 - format rusak, bukan satu jenis galat
        raise HTTPException(
            status_code=415, detail=f"Foto tidak bisa dibaca sebagai gambar: {exc}"
        ) from exc

    return Response(
        content=keluaran.getvalue(),
        media_type="image/jpeg",
        headers={
            # Foto survei tidak pernah berubah isinya, jadi boleh disimpan lama.
            # Tanpa ini tiap pembukaan katalog mengunduh ulang 3 MB per foto.
            "Cache-Control": "public, max-age=604800, immutable"
        },
    )
