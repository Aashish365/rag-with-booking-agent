from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel

from app.services.booking_agent import run_agent_turn
from app.services.memory import get_history, append_turn

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentRequest(BaseModel):
    session_id: str
    message: str


@router.post("/booking")
async def booking_agent(req: AgentRequest):
    history = await get_history(req.session_id)
    reply, booking = await run_agent_turn(req.session_id, req.message, history)

    await append_turn(req.session_id, "user", req.message)
    await append_turn(req.session_id, "assistant", reply)

    return {"session_id": req.session_id, "reply": reply, "booking": booking}
