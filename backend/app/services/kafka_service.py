import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError

from app.core.config import settings

logger = logging.getLogger(__name__)


class KafkaService:
    """
    Consumes testops-topic and fans out messages to per-run SSE subscribers.

    Lifecycle
    ---------
    start()  — called from FastAPI lifespan, spawns background consumer task
    stop()   — called on shutdown, cancels task and closes consumer

    Subscription
    ------------
    q = service.subscribe(run_id)   → asyncio.Queue fed with parsed dicts
    service.unsubscribe(run_id, q)  → remove the queue when SSE client disconnects
    """

    BUFFER_SIZE = 200  # max messages buffered per run_id for late-joining clients

    def __init__(self):
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task | None = None
        # run_id → list of subscriber queues
        self._queues: dict[str, list[asyncio.Queue]] = {}
        # run_id → recent messages (replayed to late-joining SSE clients)
        self._buffer: dict[str, list[dict]] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def subscribe(self, run_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        # Replay any already-received messages so late-joining clients catch up
        for msg in self._buffer.get(run_id, []):
            q.put_nowait(msg)
        self._queues.setdefault(run_id, []).append(q)
        logger.debug("SSE subscriber added for run %s (replayed=%d total_subs=%d)",
                     run_id, len(self._buffer.get(run_id, [])), len(self._queues[run_id]))
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        subscribers = self._queues.get(run_id, [])
        self._queues[run_id] = [x for x in subscribers if x is not q]
        if not self._queues[run_id]:
            del self._queues[run_id]
        logger.debug("SSE subscriber removed for run %s", run_id)

    async def start(self) -> None:
        self._task = asyncio.create_task(self._consume_loop(), name="kafka-consumer")
        logger.info("Kafka consumer task started (broker=%s topic=%s)", settings.KAFKA_BROKER, settings.KAFKA_TOPIC)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._consumer:
            try:
                await self._consumer.stop()
            except Exception:
                pass
        logger.info("Kafka consumer stopped")

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _consume_loop(self) -> None:
        """Reconnects automatically on errors."""
        while True:
            try:
                await self._run_consumer()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Kafka consumer error (%s), retrying in 5 s…", exc)
                await asyncio.sleep(5)

    async def _run_consumer(self) -> None:
        self._consumer = AIOKafkaConsumer(
            settings.KAFKA_TOPIC,
            bootstrap_servers=settings.KAFKA_BROKER,
            group_id=settings.KAFKA_GROUP_ID,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
        )
        await self._consumer.start()
        logger.info("Kafka consumer connected — listening on '%s'", settings.KAFKA_TOPIC)
        try:
            async for msg in self._consumer:
                await self._dispatch(msg.value)
        finally:
            await self._consumer.stop()
            self._consumer = None

    async def _dispatch(self, data: dict) -> None:
        run_id = data.get("run_id")
        if not run_id:
            return
        # Buffer message for late-joining SSE clients
        buf = self._buffer.setdefault(run_id, [])
        buf.append(data)
        if len(buf) > self.BUFFER_SIZE:
            buf.pop(0)
        # Clear buffer on run completion to free memory
        if data.get("event") == "run_completed":
            self._buffer.pop(run_id, None)

        subscribers = self._queues.get(run_id, [])
        logger.debug("Dispatching event='%s' to %d subscriber(s) for run %s",
                     data.get("event"), len(subscribers), run_id)
        for q in subscribers:
            await q.put(data)


kafka_service = KafkaService()
