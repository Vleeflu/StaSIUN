# app/services/gemini_service.py
from openai import AsyncOpenAI, APIError, RateLimitError
from app.core.config import settings
from app.schemas.chat import Message

class GeminiService:
    def __init__(self):
        self._client = AsyncOpenAI(
            api_key=settings.GEMINI_API_KEY,
            base_url=settings.GEMINI_BASE_URL,
        )
        self._model = settings.GEMINI_MODEL

    async def chat(self, message: str, history: list[Message]) -> str:
        messages = [{"role": m.role.value, "content": m.content} for m in history]
        messages.append({"role": "user", "content": message})

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
            )
        except RateLimitError as e:
            raise RuntimeError("Gemini rate limit exceeded") from e
        except APIError as e:
            raise RuntimeError(f"Gemini API error: {e}") from e

        return response.choices[0].message.content

gemini_service = GeminiService()