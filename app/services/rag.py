from __future__ import annotations
from app.services.embedder import embed_query
from app.services.vector_store import search
from app.core.llm import chat_complete

_SYSTEM_PROMPT = """You are a helpful assistant. Use the document context below to answer the user's question.
You may also reference prior conversation turns in the chat history.
If neither the context nor the history contains enough information, say so clearly.

Document context:
{context}"""


async def answer(
    query: str,
    history: list[dict[str, str]],
    top_k: int = 5,
    doc_ids: list[str] | None = None,
) -> str:
    query_vec = await embed_query(query)
    hits = await search(query_vec, top_k=top_k, doc_ids=doc_ids)
    context = "\n\n---\n\n".join(h["text"] for h in hits) if hits else "No relevant documents found."
    messages = [{"role": "system", "content": _SYSTEM_PROMPT.format(context=context)}, *history, {"role": "user", "content": query}]
    return await chat_complete(messages)
