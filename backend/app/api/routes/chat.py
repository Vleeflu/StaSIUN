# app/api/routes/chat.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.gemini_service import gemini_service
from app.services.station_context import build_chat_context

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    # Konteks disusun ulang tiap permintaan supaya isinya selalu ikut database
    # terbaru. Querynya cuma puluhan baris, jadi murah.
    context = build_chat_context(db, req.station_id)

    try:
        reply = await gemini_service.chat(req.message, req.history, context=context)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return ChatResponse(reply=reply)
