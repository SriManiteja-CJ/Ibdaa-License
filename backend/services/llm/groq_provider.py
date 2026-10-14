import base64
import io
import PIL.Image
from typing import List
from .base_provider import BaseVisionProvider
from config import settings


def _pil_to_base64_url(image: PIL.Image.Image) -> str:
    buf = io.BytesIO()
    image = image.convert("RGB")
    image.thumbnail((2048, 2048), PIL.Image.Resampling.LANCZOS)
    image.save(buf, format="JPEG", quality=85, optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


class GroqProvider(BaseVisionProvider):
    """Groq cloud API provider with vision support."""

    def __init__(self):
        from groq import AsyncGroq
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL

    async def analyze_document(
        self, images: List[PIL.Image.Image], prompt: str
    ) -> str:
        content = [{"type": "text", "text": prompt}]
        for img in images:
            content.append({
                "type": "image_url",
                "image_url": {"url": _pil_to_base64_url(img)},
            })

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            response_format={"type": "json_object"},
            max_tokens=4096,
        )
        return response.choices[0].message.content

    async def health_check(self) -> dict:
        try:
            models = await self.client.models.list()
            return {
                "status": "ok",
                "provider": "groq",
                "model": self.model,
                "available_models": [m.id for m in models.data],
            }
        except Exception as e:
            return {"status": "error", "provider": "groq", "error": str(e)}
