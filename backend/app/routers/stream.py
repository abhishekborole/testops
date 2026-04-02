import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.kafka_service import kafka_service

router = APIRouter(prefix="/runs", tags=["Stream"])

KEEPALIVE_INTERVAL = 25  # seconds — prevents proxy/browser timeouts


@router.get("/{run_id}/stream", summary="SSE stream of Kafka events for a run")
async def stream_run_events(run_id: str):
    """
    Server-Sent Events endpoint.

    The frontend monitoring agent connects here after creating a run.
    Messages are fanned out from the Kafka consumer — one SSE line per
    Kafka message that carries a matching run_id.

    Closes automatically when a 'run_completed' event is received.
    """
    q = kafka_service.subscribe(run_id)

    async def generate():
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=KEEPALIVE_INTERVAL)
                    yield f"data: {json.dumps(msg)}\n\n"
                    if msg.get("event") == "run_completed":
                        break
                except asyncio.TimeoutError:
                    # Keep the connection alive
                    yield ": keepalive\n\n"
        finally:
            kafka_service.unsubscribe(run_id, q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
            "Connection": "keep-alive",
        },
    )
