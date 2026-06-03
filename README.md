# RAG Backend

**Demo:** [Watch on YouTube](https://youtu.be/TJgc1pr8nX0)

Two ways to use this project: **interactive CLI** or **REST API** (Swagger / Postman / curl).

---

## Prerequisites

- Python 3.10+
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — running before you start
- [Ollama](https://ollama.com/) — installed and running locally (not in Docker)

Pull the required models once:
```bash
ollama pull gemma4:e2b
ollama pull nomic-embed-text
```

---

## Quick Start

```bash
python run.py
```

This single command:
1. Creates a `.venv` virtual environment if it doesn't exist
2. Installs CLI dependencies automatically
3. Starts Docker services (API, MongoDB, Qdrant, Redis) if not already running
4. Opens the interactive CLI

To start Docker services only (for API/Postman use):
```bash
docker compose up --build -d
```

---

## Using the CLI

Run `python run.py`. The main menu appears:

    (1)  Chat with Documents
    (2)  Book an Interview
    (q)  Quit

---

### Option 1 — Chat with Documents

**Upload a document (1)**
- Enter the path to a `.pdf` or `.txt` file
- Choose a chunking strategy: `fixed` (character count with overlap) or `sentence` (sentence groups)
- The document is stored — you get back a `doc_id`

**Talk with documents (2)**
- All ingested documents are listed with numbers
- Enter a number for one document, comma-separated for multiple (e.g. `1,3`), or `all` for everything
- A chat session opens — type your questions freely
- Type `back` to return to the menu, `exit` or `quit` to return to the main menu

---

### Option 2 — Book an Interview

The booking mode is a fully conversational AI agent — no forms, no fixed steps.
Just talk naturally. Share as much or as little as you want in one message.
The agent understands your intent, fetches available slots internally, and only asks for what's missing.

Example — full info in one message:

    You:       I want to book for AI Engineer role, I'm John Doe, john@company.com
    Assistant: Got it! Here are the available slots... which time works for you?
    You:       2026-06-05 at 10:00
    Assistant: Perfect — confirming John Doe for AI Engineer on June 5 at 10:00. Shall I confirm?
    You:       yes
    Assistant: Booked! See you then.

Example — minimal message, agent asks for the rest:

    You:       I want to book an interview
    Assistant: Sure! What role are you interviewing for?
    You:       Data Scientist
    Assistant: Got it. What's your name?
    You:       Jane
    Assistant: And your email?
    ...

Type `exit` or `quit` at any time to return to the main menu.

---

## Using the API

Once Docker services are running, the API is at `http://localhost:8000`.

**Swagger UI:** `http://localhost:8000/docs`

---

### Health check

**GET** `/health`

    curl http://localhost:8000/health

---

### Ingest a document

**POST** `/ingest/`

Accepts `.pdf` or `.txt`. Returns a `doc_id` you can use to scope chat queries.

**Postman:** Body → form-data

| Key | Type | Required | Default | Notes |
|---|---|---|---|---|
| `file` | File | Yes | — | `.pdf` or `.txt` |
| `strategy` | Text | No | `fixed` | `fixed` or `sentence` |
| `chunk_size` | Text | No | `500` | Characters per chunk (`fixed` only) |
| `overlap` | Text | No | `50` | Overlap between chunks (`fixed` only) |
| `sentence_window` | Text | No | `5` | Sentences per chunk (`sentence` only) |

**curl:**

    curl -X POST http://localhost:8000/ingest/ \
      -F "file=@/path/to/document.pdf" \
      -F "strategy=fixed"

**Response:**

    {
      "doc_id": "d9ef09fd305b47d890af2c93fe069ee9",
      "filename": "document.pdf",
      "strategy": "fixed",
      "chunk_count": 12,
      "created_at": "2025-07-10T09:00:00+00:00"
    }

---

### List ingested documents

**GET** `/ingest/`

    curl http://localhost:8000/ingest/

---

### Chat with documents

**POST** `/chat/`

Ask a question. Reuse the same `session_id` for multi-turn conversation — history is kept in Redis automatically.

`doc_ids` (optional) — list of `doc_id` values to search within. Omit to search all documents.

    curl -X POST http://localhost:8000/chat/ \
      -H "Content-Type: application/json" \
      -d '{
        "session_id": "user123",
        "message": "What topics are covered?",
        "doc_ids": ["d9ef09fd305b47d890af2c93fe069ee9"]
      }'

**Response:**

    {
      "session_id": "user123",
      "reply": "The document covers ...",
      "booking": null
    }

---

### Clear a chat session

**DELETE** `/chat/{session_id}`

    curl -X DELETE http://localhost:8000/chat/user123

---

### Booking agent (conversational)

**POST** `/agent/booking`

A multi-turn conversational agent that handles the entire booking flow.
Send messages one at a time with the same `session_id` — the agent maintains context, calls internal tools to fetch available slots, and saves the booking once confirmed.

**Turn 1 — state your intent:**

    curl -X POST http://localhost:8000/agent/booking \
      -H "Content-Type: application/json" \
      -d '{"session_id": "s1", "message": "I want to book for AI Engineer, I am John Doe, john@test.com"}'

**Response:**

    {
      "session_id": "s1",
      "reply": "Got it! Here are the available slots: ...\nWhich time works for you?",
      "booking": null
    }

**Turn 2 — pick a slot:**

    curl -X POST http://localhost:8000/agent/booking \
      -H "Content-Type: application/json" \
      -d '{"session_id": "s1", "message": "2026-06-05 at 10:00"}'

**Turn 3 — confirm:**

    curl -X POST http://localhost:8000/agent/booking \
      -H "Content-Type: application/json" \
      -d '{"session_id": "s1", "message": "yes confirm"}'

**Final response (booking saved):**

    {
      "session_id": "s1",
      "reply": "Your interview has been booked! See you then.",
      "booking": {
        "name": "John Doe",
        "email": "john@test.com",
        "role": "AI Engineer",
        "date": "2026-06-05",
        "time": "10:00",
        "created_at": "2025-07-10T09:00:00+00:00"
      }
    }

The `booking` field is `null` until the agent finalises and saves the booking.

---

### Get available slots

**GET** `/bookings/slots`

Returns open slots for the next 5 business days (9:00–16:00 hourly), excluding already-booked times.

    curl http://localhost:8000/bookings/slots

---

### List all bookings

**GET** `/bookings/`

    curl http://localhost:8000/bookings/

---

## Switching the LLM or Embedding Model

Edit `llm_config.yaml` and restart the app:

    llm:
      provider: ollama        # ollama | openai | anthropic
      model: gemma4:e2b
      base_url: http://host.docker.internal:11434/v1
      api_key: ollama

    embeddings:
      provider: ollama
      model: nomic-embed-text
      base_url: http://host.docker.internal:11434/v1
      api_key: ollama

    docker restart backend-evaluation-app-1

To use OpenAI: `provider: openai`, `model: gpt-4o-mini`, `base_url: null`, `api_key: sk-...`

---

## Useful Commands

    # Start all services
    docker compose up --build -d

    # Stop all services
    docker compose down

    # Live app logs
    docker logs backend-evaluation-app-1 -f

    # Restart app after editing llm_config.yaml
    docker restart backend-evaluation-app-1

    # Rebuild app after code changes
    docker compose up --build -d app

---

### Option 1 — Chat with Documents

**Upload a document (1)**
- Enter the path to a `.pdf` or `.txt` file
- Choose a chunking strategy: `fixed` (character count with overlap) or `sentence` (sentence groups)
- The document is stored — you get back a `doc_id`

**Talk with documents (2)**
- All ingested documents are listed with numbers
- Enter a number for one document, comma-separated for multiple (e.g. `1,3`), or `all` for everything
- A chat session opens — type your questions freely
- Type `back` to return to the menu, `exit` or `quit` to go back to main menu

---

### Option 2 — Book an Interview

The booking mode is a fully conversational AI agent. Just talk to it naturally — share as much or as little as you want in one message. The agent figures out what's missing and asks only for that.

```
Assistant: Hi! Tell me what you're looking for — job role, your name, email...

You: I want to book for AI Engineer role, I'm John Doe, john@company.com