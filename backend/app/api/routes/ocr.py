from fastapi import APIRouter, UploadFile, File, HTTPException

from app.services.ocr import extract_text, OCRSpaceError

router = APIRouter(prefix="/ocr", tags=["ocr"])

ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_FILE_SIZE_BYTES = 1 * 1024 * 1024  # OCR.space free tier limit


@router.post("/extract")
async def extract_text_endpoint(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(400, f"Unsupported content type: {file.content_type}")

    image_bytes = await file.read()

    if len(image_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(413, "File exceeds 1MB limit for free OCR.space tier")

    try:
        result = await extract_text(image_bytes, file.filename, file.content_type)
    except OCRSpaceError as e:
        raise HTTPException(502, str(e)) from e

    return {"filename": file.filename, "full_text": result["full_text"]}