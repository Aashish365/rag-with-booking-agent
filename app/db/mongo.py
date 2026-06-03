from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongo_uri)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    return get_client()[settings.mongo_db]


# Convenience accessors for the two collections used across the app
def documents_col():
    return get_db()["documents"]


def bookings_col():
    return get_db()["bookings"]


async def close_client() -> None:
    global _client
    if _client:
        _client.close()
        _client = None
