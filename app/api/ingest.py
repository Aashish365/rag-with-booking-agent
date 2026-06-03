from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.extractor import extract_text
from app.services.chunker import ChunkStrategy, chunk_text
from app.services.embedder import embed_texts
from app.services.vector_store import upsert_chunks
from app.db.mongo import documents_col

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestResponse(BaseModel):
    doc_id: str
    filename: str
    strategy: ChunkStrategy
    chunk_count: int
    created_at: str


@router.get("/", response_model=list[IngestResponse])
async def list_documents():
    cursor = documents_col().find({}, {"_id": 0})
    return [doc async for doc in cursor]


@router.post("/", response_model=IngestResponse)
async def ingest_document(
    file: Annotated[UploadFile, File(description="PDF or TXT file")],
    strategy: Annotated[ChunkStrategy, Form(description="Chunking strategy: fixed | sentence")] = "fixed",
    chunk_size: Annotated[int, Form(description="Chars per chunk (fixed strategy only)")] = 500,
    overlap: Annotated[int, Form(description="Overlap chars (fixed strategy only)")] = 50,
    sentence_window: Annotated[int, Form(description="Sentences per chunk (sentence strategy only)")] = 5,
):
    allowed = {"application/pdf", "text/plain"}
    if file.content_type not in allowed and not (
        file.filename.endswith(".pdf") or file.filename.endswith(".txt")
    ):
        raise HTTPException(status_code=400, detail="Only .pdf and .txt files are supported.")

    raw_bytes = await file.read()

    try:
        text = extract_text(raw_bytes, file.filename)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Text extraction failed: {exc}")

    chunks = chunk_text(
        text,
        strategy=strategy,
        chunk_size=chunk_size,
        overlap=overlap,
        sentence_window=sentence_window,
    )

    if not chunks:
        raise HTTPException(status_code=422, detail="No text could be extracted from the document.")

    try:
        embeddings = await embed_texts(chunks)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Embedding generation failed: {exc}")

    doc_id = uuid.uuid4().hex
    await upsert_chunks(doc_id, chunks, embeddings)

    meta = {
        "doc_id": doc_id,
        "filename": file.filename,
        "strategy": strategy,
        "chunk_count": len(chunks),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await documents_col().insert_one(meta)

    return IngestResponse(**{k: v for k, v in meta.items() if k != "_id"})
