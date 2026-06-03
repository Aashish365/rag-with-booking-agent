from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel

from app.services.memory import append_turn, get_history, clear_history
from app.services.booking import detect_and_save_booking
from app.services.rag import answer

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str
    message: str
    doc_ids: list[str] | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    booking: dict | None = None


@router.post("/", response_model=ChatResponse)
async def chat(req: ChatRequest):
    history = await get_history(req.session_id)

    booking = await detect_and_save_booking(req.session_id, req.message)

    if booking:
        reply = _booking_confirmation(booking)
    else:
        reply = await answer(req.message, history, doc_ids=req.doc_ids)

    await append_turn(req.session_id, "user", req.message)
    await append_turn(req.session_id, "assistant", reply)

    return ChatResponse(session_id=req.session_id, reply=reply, booking=booking)


@router.delete("/{session_id}", status_code=204)
async def reset_session(session_id: str):
    await clear_history(session_id)


def _booking_confirmation(booking: dict) -> str:
    parts = ["Your interview has been booked!"]
    if booking.get("role"):
        parts.append(f"Role: {booking['role']}")
    if booking.get("name"):
        parts.append(f"Name: {booking['name']}")
    if booking.get("email"):
        parts.append(f"Email: {booking['email']}")
    if booking.get("date"):
        parts.append(f"Date: {booking['date']}")
    if booking.get("time"):
        parts.append(f"Time: {booking['time']}")
    return "\n".join(parts)
