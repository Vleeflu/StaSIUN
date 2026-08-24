# app/services/gemini_service.py
from openai import AsyncOpenAI, APIError, RateLimitError
from app.config import settings
from app.schemas.chat import Message

class GeminiService:
    def __init__(self):
        self._client = AsyncOpenAI(
            api_key=settings.gemini_api_key,
            base_url=settings.gemini_base_url,
        )
        self._model = settings.gemini_model

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