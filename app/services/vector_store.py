from __future__ import annotations
import uuid
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchAny
from app.core.config import settings

_client: AsyncQdrantClient | None = None


def get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    return _client


async def ensure_collection(vector_size: int) -> None:
    client = get_client()
    exists = await client.collection_exists(settings.qdrant_collection)
    if not exists:
        await client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


async def upsert_chunks(
    doc_id: str,
    chunks: list[str],
    embeddings: list[list[float]],
) -> None:
    client = get_client()
    await ensure_collection(len(embeddings[0]))

    points = [
        PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}_{i}")),
            vector=embedding,
            payload={"doc_id": doc_id, "chunk_index": i, "text": chunk},
        )
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]
    await client.upsert(collection_name=settings.qdrant_collection, points=points)


async def search(
    query_vector: list[float],
    top_k: int = 5,
    doc_ids: list[str] | None = None,
) -> list[dict]:
    client = get_client()
    query_filter = (
        Filter(must=[FieldCondition(key="doc_id", match=MatchAny(any=doc_ids))])
        if doc_ids
        else None
    )
    response = await client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    )
    return [
        {"text": r.payload["text"], "score": r.score, "doc_id": r.payload["doc_id"]}
        for r in response.points
    ]
