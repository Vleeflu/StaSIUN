import httpx

from app.core.config import settings

class OCRSpaceError(Exception):
    pass


async def extract_text(image_bytes: bytes, filename: str, content_type: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                settings.OCR_SPACE_URL,
                files={"file": (filename, image_bytes, content_type)},
                data={
                    "apikey": settings.OCR_SPACE_API,
                    "language": "eng",
                    "OCREngine": "2",  # engine 2 has better accuracy for most cases
                },
            )
        except httpx.RequestError as e:
            raise OCRSpaceError(f"OCR.space request failed: {e}") from e

    if response.status_code != 200:
        raise OCRSpaceError(f"OCR.space returned status {response.status_code}")

    payload = response.json()

    if payload.get("IsErroredOnProcessing"):
        error_msg = payload.get("ErrorMessage", ["Unknown OCR error"])
        raise OCRSpaceError(", ".join(error_msg) if isinstance(error_msg, list) else str(error_msg))

    parsed_results = payload.get("ParsedResults") or []
    if not parsed_results:
        raise OCRSpaceError("No text detected in image")

    return {
        "full_text": parsed_results[0].get("ParsedText", "").strip(),
        "raw": payload,
    }