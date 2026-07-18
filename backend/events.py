"""In-process and Redis job progress fan-out."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict

from backend.config import settings
from backend.contracts import JobEvent, JobStatus

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def subscribe(self, job_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._subs[job_id].append(q)
        return q

    async def unsubscribe(self, job_id: str, q: asyncio.Queue) -> None:
        async with self._lock:
            if q in self._subs.get(job_id, []):
                self._subs[job_id].remove(q)

    async def publish_local(self, event: JobEvent) -> None:
        async with self._lock:
            queues = list(self._subs.get(event.job_id, []))
        for q in queues:
            await q.put(event)

    def publish_redis(self, event: JobEvent) -> None:
        if not settings.use_worker:
            return
        try:
            import redis

            r = redis.from_url(settings.redis_url)
            r.publish(f"job:{event.job_id}", event.model_dump_json())
        except Exception:
            logger.debug("Redis publish failed", exc_info=True)

    async def publish(self, event: JobEvent) -> None:
        await self.publish_local(event)
        await asyncio.to_thread(self.publish_redis, event)

    async def listen_redis(self, job_id: str, q: asyncio.Queue) -> None:
        """Background task: forward Redis messages into q."""
        try:
            import redis.asyncio as aioredis
        except Exception:
            return
        try:
            r = aioredis.from_url(settings.redis_url)
            pubsub = r.pubsub()
            await pubsub.subscribe(f"job:{job_id}")
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                data = message.get("data")
                if isinstance(data, bytes):
                    data = data.decode()
                payload = json.loads(data)
                await q.put(JobEvent.model_validate(payload))
                if payload.get("status") in (
                    JobStatus.succeeded.value,
                    JobStatus.failed.value,
                    JobStatus.cancelled.value,
                ):
                    break
            await pubsub.unsubscribe(f"job:{job_id}")
            await pubsub.close()
            await r.close()
        except Exception:
            logger.debug("Redis listen ended", exc_info=True)


event_bus = EventBus()
