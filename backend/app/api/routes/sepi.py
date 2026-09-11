"""Simulasi SEPI: hitung ulang peringkat dengan parameter pilihan pengguna.

Membungkus `ai_tools.hitung_ulang_sepi`, alat yang sama yang dipanggil asisten
AI. Itu disengaja: kalau UI dan asisten memakai jalur hitung yang berbeda,
cepat atau lambat keduanya akan menjawab beda untuk pertanyaan yang sama, dan
tidak ada yang tahu mana yang benar. Dengan satu sumber, perbedaan itu mustahil.

Hasilnya TIDAK disimpan. Simulasi adalah "bagaimana kalau", bukan revisi skor
resmi - membiarkannya menulis ke `station_scores` akan membuat angka yang
dilaporkan bergantung pada siapa yang terakhir menggeser slider.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import ai_tools

router = APIRouter(prefix="/sepi", tags=["sepi"])


class PermintaanSimulasi(BaseModel):
    # Bobot per variabel, 0-1. Boleh disebut sebagian; sisanya dibagi rata oleh
    # alatnya. Dibiarkan opsional supaya UI bisa meminta "bawaan" tanpa harus
    # tahu angkanya.
    bobot: dict[str, float] | None = None
    menit: int = Field(default=10)
    batas: int = Field(default=46, ge=1, le=50)
    station_id: int | None = None


@router.post("/simulasi")
def simulasi(req: PermintaanSimulasi, db: Session = Depends(get_db)):
    """Hitung ulang peringkat SEPI tanpa menyentuh skor tersimpan."""
    try:
        hasil = ai_tools.hitung_ulang_sepi(
            db,
            bobot=req.bobot,
            menit=req.menit,
            batas=req.batas,
            batas_maks=req.batas,
        )
    except ai_tools.ToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Posisi stasiun yang sedang dibuka ikut dicari di sini, bukan di frontend.
    # Kalau frontend yang mencarinya, ia harus tahu bahwa peringkat dipotong
    # `batas` - dan stasiun yang jatuh di luar potongan akan terlihat seperti
    # "tidak ada", bukan "di luar sepuluh besar".
    if req.station_id is not None:
        nama = db.execute(
            text("SELECT name FROM stations WHERE id = :i"), {"i": req.station_id}
        ).scalar()
        hasil["stasiun_dipilih"] = next(
            (r for r in hasil["peringkat"] if r["stasiun"] == nama), None
        )

    return hasil
