from __future__ import annotations
from openai import AsyncOpenAI
from app.core.config import llm_config


def _get_embed_client() -> AsyncOpenAI:
    cfg = llm_config["embeddings"]
    return AsyncOpenAI(
        api_key=cfg.get("api_key", "ollama"),
        base_url=cfg.get("base_url") or None,
    )


def _get_embed_model() -> str:
    return llm_config["embeddings"]["model"]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return one embedding vector per input text."""
    client = _get_embed_client()
    model = _get_embed_model()
    response = await client.embeddings.create(input=texts, model=model)
    return [item.embedding for item in response.data]


async def embed_query(text: str) -> list[float]:
    vectors = await embed_texts([text])
    return vectors[0]
