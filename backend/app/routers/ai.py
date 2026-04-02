from typing import Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx

from app.core.config import settings

router = APIRouter(prefix="/ai", tags=["AI"])

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class AIRequest(BaseModel):
    model: str
    messages: list[dict[str, Any]]
    system: str | None = None
    max_tokens: int = 1000


@router.post("/stream")
async def stream_ai(req: AIRequest):
    if not settings.AI_API_KEY:
        raise HTTPException(status_code=503, detail="AI API key not configured on server")

    payload: dict[str, Any] = {
        "model": req.model,
        "max_tokens": req.max_tokens,
        "stream": True,
        "messages": req.messages,
    }
    if req.system:
        payload["system"] = req.system

    headers = {
        "Content-Type": "application/json",
        "x-api-key": settings.AI_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
    }

    async def generate():
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", ANTHROPIC_URL, json=payload, headers=headers) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    yield body
                    return
                async for chunk in resp.aiter_bytes():
                    yield chunk

    return StreamingResponse(generate(), media_type="text/event-stream")
