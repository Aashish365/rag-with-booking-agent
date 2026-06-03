from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.api import ingest, chat, bookings, booking_agent
from app.db.mongo import close_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_client()


app = FastAPI(
    title="RAG Backend",
    lifespan=lifespan,
)

app.include_router(ingest.router)
app.include_router(chat.router)
app.include_router(bookings.router)
app.include_router(booking_agent.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
