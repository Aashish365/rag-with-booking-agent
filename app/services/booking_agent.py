"""
Custom booking agent — no framework, plain LLM + tool loop.

The LLM is given a system prompt describing available tools and a strict
calling format. Each iteration of the loop:
  1. Call the LLM with the current message history.
  2. Scan the reply for a CALL: line.
  3. If found — execute the tool, inject the result, loop again.
  4. If not found — it's a plain reply; return it to the caller.
"""
from __future__ import annotations
import json
from datetime import date, timedelta, datetime, timezone

from app.core.llm import chat_complete
from app.db.mongo import bookings_col

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a friendly interview booking assistant.

You have two tools available:

TOOL: get_available_slots
  Description: Returns the list of open interview slots.
  Args: none

TOOL: book_interview
  Description: Saves a confirmed booking. Only call this after the user has
               confirmed all details.
  Args: name, email, role, date (YYYY-MM-DD), time (HH:MM)

HOW TO CALL A TOOL
  Output this exact format on its own line — nothing before or after the JSON:
  CALL: {"tool": "tool_name", "args": {}}

BEHAVIOUR RULES
  - When the user expresses intent to book, first call get_available_slots so
    they can pick a time.
  - Extract name, email, and role from whatever the user says.
  - Ask for any missing piece naturally — one question at a time.
  - Once you have name, email, role, and a chosen slot, confirm with the user
    before calling book_interview.
  - After booking, confirm warmly and end the conversation.
  - Never invent slot dates — always call get_available_slots."""

# ── Tool call parser ─────────────────────────────────────────────────────────

def _parse_call(raw: str) -> dict | None:
    """Extract CALL: {...} from LLM output handling nested braces."""
    idx = raw.find("CALL:")
    if idx == -1:
        return None
    tail = raw[idx + 5:].strip()
    start = tail.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(tail[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(tail[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None

# ── Tool implementations ──────────────────────────────────────────────────────

async def _get_available_slots() -> str:
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

    available = [s for s in slots if (s["date"], s["time"]) not in booked]
    if not available:
        return "No slots available at this time."

    lines = [f"{i + 1}. {s['date']} at {s['time']}" for i, s in enumerate(available)]
    return "Available slots:\n" + "\n".join(lines)


async def _book_interview(args: dict, session_id: str) -> tuple[str, dict]:
    booking = {
        "session_id": session_id,
        "name":  args.get("name"),
        "email": args.get("email"),
        "role":  args.get("role"),
        "date":  args.get("date"),
        "time":  args.get("time"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await bookings_col().insert_one(booking)
    booking.pop("_id", None)

    result = (
        f"Booking confirmed for {booking['name']} ({booking['email']}) — "
        f"{booking['role']} interview on {booking['date']} at {booking['time']}."
    )
    return result, booking


# ── Agent runner ──────────────────────────────────────────────────────────────

async def run_agent_turn(
    session_id: str,
    user_message: str,
    history: list[dict[str, str]],
) -> tuple[str, dict | None]:
    """
    Process one user turn.

    Returns:
        reply   — the final text to show the user
        booking — booking dict if a booking was just completed, else None
    """
    messages = (
        [{"role": "system", "content": _SYSTEM_PROMPT}]
        + history
        + [{"role": "user", "content": user_message}]
    )

    completed_booking: dict | None = None

    for _ in range(6):
        raw = await chat_complete(messages)
        call = _parse_call(raw)

        if call is None:
            return raw.strip(), completed_booking

        tool = call.get("tool", "")
        args = call.get("args", {})

        # Execute the tool
        if tool == "get_available_slots":
            tool_result = await _get_available_slots()

        elif tool == "book_interview":
            tool_result, completed_booking = await _book_interview(args, session_id)

        else:
            tool_result = f"Unknown tool: {tool}"

        # Feed result back into the conversation
        messages.append({"role": "assistant", "content": raw})
        messages.append({
            "role": "user",
            "content": f"[Tool result: {tool}]\n{tool_result}",
        })

    return "I ran into trouble completing the booking. Please try again.", None
