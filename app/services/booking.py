from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from app.core.llm import chat_complete
from app.db.mongo import bookings_col

_BOOKING_KEYWORDS = {"book", "interview", "schedule", "appointment", "slot", "meeting"}

_EXTRACTION_PROMPT = """Extract interview booking details from the user message.
Respond ONLY with a JSON object — no explanation, no markdown, no extra text.

If the user wants to book, output:
{"wants_booking":true,"name":"...","email":"...","date":"YYYY-MM-DD","time":"HH:MM","role":"..."}

Use null for any field that is missing.
- role: the job title or purpose of the interview (e.g. "AI Engineer", "Backend Developer"), null if not mentioned.
If the user does NOT want to book, output:
{"wants_booking":false}"""


def _looks_like_booking(message: str) -> bool:
    words = set(message.lower().split())
    return bool(words & _BOOKING_KEYWORDS)


def _extract_json(text: str) -> dict | None:
    """Try to parse JSON directly, then fall back to extracting a {...} block."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


async def detect_and_save_booking(
    session_id: str,
    user_message: str,
) -> dict | None:
    if not _looks_like_booking(user_message):
        return None

    messages = [
        {"role": "system", "content": _EXTRACTION_PROMPT},
        {"role": "user", "content": user_message},
    ]

    raw = await chat_complete(messages)
    data = _extract_json(raw)

    if not data or not data.get("wants_booking"):
        return None

    booking = {
        "session_id": session_id,
        "name": data.get("name"),
        "email": data.get("email"),
        "role": data.get("role"),
        "date": data.get("date"),
        "time": data.get("time"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await bookings_col().insert_one(booking)
    booking.pop("_id", None)
    return booking
