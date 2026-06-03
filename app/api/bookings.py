from __future__ import annotations
import json
import re
from datetime import date, timedelta
from fastapi import APIRouter
from pydantic import BaseModel
from app.db.mongo import bookings_col
from app.core.llm import chat_complete

router = APIRouter(prefix="/bookings", tags=["bookings"])

_EXTRACT_PROMPT = """Extract interview booking details from the user message.
Respond ONLY with valid JSON — no explanation, no markdown.

Output format:
{"name": null, "email": null, "role": null}

Rules:
- name: full name if clearly mentioned, else null
- email: email address if mentioned, else null
- role: job role or position if mentioned (e.g. "AI Engineer", "Backend Developer"), else null"""


class ExtractRequest(BaseModel):
    message: str


@router.post("/extract")
async def extract_booking_info(req: ExtractRequest) -> dict:
    messages = [
        {"role": "system", "content": _EXTRACT_PROMPT},
        {"role": "user", "content": req.message},
    ]
    raw = await chat_complete(messages)

    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(match.group()) if match else {}

    return {
        "name":  data.get("name"),
        "email": data.get("email"),
        "role":  data.get("role"),
    }


@router.get("/")
async def list_bookings():
    cursor = bookings_col().find({}, {"_id": 0})
    return [doc async for doc in cursor]


@router.get("/slots")
async def available_slots():
    slots: list[dict] = []
    day = date.today() + timedelta(days=1)
    business_days = 0

    while business_days < 5:
        if day.weekday() < 5:
            for hour in range(9, 17):
                slots.append({"date": day.isoformat(), "time": f"{hour:02d}:00"})
            business_days += 1
        day += timedelta(days=1)

    booked: set[tuple[str, str]] = set()
    async for b in bookings_col().find({}, {"_id": 0, "date": 1, "time": 1}):
        if b.get("date") and b.get("time"):
            booked.add((b["date"], b["time"]))

    return [s for s in slots if (s["date"], s["time"]) not in booked]
