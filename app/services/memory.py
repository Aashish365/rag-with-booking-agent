from __future__ import annotations
import json
import redis.asyncio as aioredis
from app.core.config import settings

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
        )
    return _redis


_HISTORY_TTL = 60 * 60 * 2  # 2 hours


async def get_history(session_id: str) -> list[dict[str, str]]:
    raw = await get_redis().get(f"chat:{session_id}")
    if raw is None:
        return []
    return json.loads(raw)


async def append_turn(session_id: str, role: str, content: str) -> None:
    history = await get_history(session_id)
    history.append({"role": role, "content": content})
    await get_redis().setex(f"chat:{session_id}", _HISTORY_TTL, json.dumps(history))


async def clear_history(session_id: str) -> None:
    await get_redis().delete(f"chat:{session_id}")
