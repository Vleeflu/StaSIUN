# app/routers/chat.py
from fastapi import APIRouter, HTTPException
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.gemini_service import gemini_service

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        reply = await gemini_service.chat(req.message, req.history)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return ChatResponse(reply=reply)