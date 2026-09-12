# app/api/routes/chat.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.ai_actions import susun_aksi
from app.services.llm_service import llm_service
from app.services.station_context import build_chat_context

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    context = build_chat_context(db, req.station_id, req.message)

    try:
        # `db` diteruskan supaya model boleh memanggil alat hitung di
        # `ai_tools` — MCDA dengan bobot pilihan pengguna, penyaringan stasiun,
        # peringkat tenant, perbandingan. Tanpa argumen ini asisten kembali jadi
        # tanya-jawab biasa yang hanya membaca konteks.
        reply, log = await llm_service.chat(
            req.message, req.history, context=context, db=db
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return ChatResponse(
        reply=reply, actions=susun_aksi(db, reply, log, req.station_id)
    )
