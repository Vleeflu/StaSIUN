"""Endpoint ekspor ringkasan analisis per stasiun."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.station import Station
from app.services.ekspor import PERSONA, prompt_pembuka, susun_dokumen
from app.services.llm_penyedia import Rantai

router = APIRouter(tags=["ekspor"])

# Simpanan paragraf pembuka per (stasiun, persona).
#
# Disimpan di memori, bukan di database: isinya bisa dibuat ulang kapan saja,
# dan tabel baru sehari sebelum tenggat adalah risiko yang tidak sebanding.
# Konsekuensinya jujur - simpanan ini hilang saat container dimulai ulang, dan
# dokumen pertama setelah itu memanggil model sekali lagi.
_SIMPANAN: dict[tuple[int, str], str] = {}


def _ambil_data(db: Session, station_id: int) -> dict:
    """Kumpulkan data tiap fitur dengan memanggil fungsi yang sama dengan API.

    Dipanggil ulang di sini alih-alih menyalin logikanya, supaya dokumen tidak
    pernah menampilkan angka yang berbeda dari yang terlihat di layar.
    """
    from app.api.routes.stations import (
        station_areas,
        station_naming,
        station_score,
        station_tenants,
    )
    from app.services.sponsorship import peluang_sponsorship

    data: dict = {}
    try:
        skor = station_score(station_id, db=db, minutes=10)
        data["skor"] = skor
        data["paparan"] = skor.get("paparan")
    except HTTPException:
        data["skor"] = {}
    try:
        data["tenant"] = station_tenants(station_id, db=db, minutes=10)
    except HTTPException:
        data["tenant"] = {}
    try:
        data["areas"] = station_areas(station_id, db=db)
    except HTTPException:
        data["areas"] = {}
    try:
        data["naming"] = station_naming(station_id, db=db)
    except HTTPException:
        data["naming"] = {}

    hasil = peluang_sponsorship(db, station_id=station_id, menit=10)
    data["sponsorship"] = {"peluang": hasil.peluang}
    return data


@router.get("/stations/{station_id}/ekspor", response_class=HTMLResponse)
def ekspor(
    station_id: int,
    db: Session = Depends(get_db),
    persona: str = Query(default="pengelola"),
):
    """Ringkasan analisis satu stasiun sebagai dokumen HTML siap cetak.

    HTML, bukan PDF, dan itu pilihan sadar: browser sudah bisa mencetaknya jadi
    PDF, sedangkan pustaka PDF menambah puluhan megabita ke image demi hasil
    yang sama. Dokumennya juga tetap bisa dibuka siapa pun tanpa aplikasi
    khusus.
    """
    if persona not in PERSONA:
        raise HTTPException(
            status_code=400,
            detail=f"persona tidak dikenal. Pilihannya: {', '.join(PERSONA)}",
        )
    stasiun = db.get(Station, station_id)
    if stasiun is None:
        raise HTTPException(status_code=404, detail="Stasiun tidak ditemukan")

    data = _ambil_data(db, station_id)

    # Paragraf pembuka: ambil dari simpanan, atau panggil model sekali.
    # Kegagalan apa pun di sini TIDAK membatalkan dokumen - ia hanya terbit
    # tanpa pembuka, dan itu jauh lebih baik daripada tombol ekspor yang mati
    # gara-gara kuota model habis.
    kunci = (station_id, persona)
    pembuka = _SIMPANAN.get(kunci)
    if pembuka is None:
        try:
            balasan = Rantai().panggil(
                messages=prompt_pembuka(stasiun.name, persona, data),
                max_tokens=320,
            )
            if balasan is not None:
                pembuka = (balasan.choices[0].message.content or "").strip() or None
                if pembuka:
                    _SIMPANAN[kunci] = pembuka
        except Exception:  # noqa: BLE001 - kuota habis, jaringan, apa pun
            pembuka = None

    return HTMLResponse(
        susun_dokumen(
            stasiun.name,
            persona,
            data,
            pembuka,
            date.today().strftime("%d %B %Y"),
        )
    )


@router.get("/persona")
def daftar_persona():
    """Persona yang tersedia untuk ekspor, beserta labelnya."""
    return {
        "persona": [{"id": k, "label": v["label"]} for k, v in PERSONA.items()],
        "catatan": (
            "Persona mengubah urutan dan penekanan bagian, BUKAN angkanya. "
            "Metadata keyakinan selalu ikut di semua persona."
        ),
    }
