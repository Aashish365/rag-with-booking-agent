from __future__ import annotations
from typing import Literal
import nltk

# Download punkt tokenizer data on first use (silent if already present)
try:
    nltk.data.find("tokenizers/punkt_tab")
except LookupError:
    nltk.download("punkt_tab", quiet=True)


ChunkStrategy = Literal["fixed", "sentence"]


def chunk_text(
    text: str,
    strategy: ChunkStrategy = "fixed",
    chunk_size: int = 500,
    overlap: int = 50,
    sentence_window: int = 5,
) -> list[str]:
    if strategy == "fixed":
        return _fixed_chunks(text, chunk_size, overlap)
    if strategy == "sentence":
        return _sentence_chunks(text, sentence_window)
    raise ValueError(f"Unknown chunking strategy: {strategy}")


def _fixed_chunks(text: str, size: int, overlap: int) -> list[str]:
    """Split by character count with a sliding overlap window."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end].strip())
        start += size - overlap
    return [c for c in chunks if c]


def _sentence_chunks(text: str, window: int) -> list[str]:
    """Group consecutive sentences into windows of `window` sentences."""
    sentences = nltk.sent_tokenize(text)
    chunks: list[str] = []
    for i in range(0, len(sentences), window):
        chunk = " ".join(sentences[i : i + window]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks
