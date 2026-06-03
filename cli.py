"""
Interactive CLI — run with: python cli.py
(or via the entry point: python run.py)
"""
from __future__ import annotations

import calendar
import os
import uuid
from datetime import date as Date
from pathlib import Path

import httpx
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

API_URL = os.getenv("API_URL", "http://localhost:8000")
console = Console()


def _client() -> httpx.Client:
    return httpx.Client(base_url=API_URL, timeout=120)


# ── UI helpers ────────────────────────────────────────────────────────────────

def _banner():
    console.print()
    console.print(Panel.fit(
        "[bold cyan]RAG Backend CLI[/bold cyan]\n"
        "[dim]Chat with Documents   |   Book an Interview[/dim]",
        border_style="cyan",
        padding=(1, 4),
    ))
    console.print()


def _section(title: str):
    console.print()
    console.rule(f"[bold cyan]{title}[/bold cyan]")
    console.print()


def _success(msg: str):
    console.print(f"[green]{msg}[/green]")


def _error(msg: str):
    console.print(f"[red]{msg}[/red]")


def _info(msg: str):
    console.print(f"[dim]{msg}[/dim]")


# ── Main menu ─────────────────────────────────────────────────────────────────

_QUIT_WORDS = {"q", "quit", "exit", "bye", "goodbye"}


def _main_menu() -> str:
    console.print("[bold]What would you like to do?[/bold]\n")
    console.print("  [cyan](1)[/cyan]  Chat with Documents")
    console.print("  [cyan](2)[/cyan]  Book an Interview")
    console.print("  [cyan](q)[/cyan]  Quit\n")
    while True:
        choice = Prompt.ask("Choose").strip().lower()
        if choice in _QUIT_WORDS:
            return "q"
        if choice in ("1", "2"):
            return choice
        console.print("[dim]Enter 1, 2, or q[/dim]")


# ── Document mode ─────────────────────────────────────────────────────────────

def _doc_menu() -> str:
    console.print("[bold]Document Options[/bold]\n")
    console.print("  [cyan](1)[/cyan]  Upload a document")
    console.print("  [cyan](2)[/cyan]  Talk with documents")
    console.print("  [cyan](b)[/cyan]  Back\n")
    return Prompt.ask("Choose", choices=["1", "2", "b"], default="2")


def _upload():
    _section("Upload Document")
    raw = Prompt.ask("[bold]File path[/bold]").strip().strip('"')
    path = Path(raw)

    if not path.exists():
        _error(f"File not found: {path}")
        return

    if path.suffix.lower() not in (".pdf", ".txt"):
        _error("Only .pdf and .txt files are supported.")
        return

    strategy = Prompt.ask(
        "Chunking strategy",
        choices=["fixed", "sentence"],
        default="fixed",
    )

    console.print(f"\nIngesting [bold]{path.name}[/bold]...")

    with _client() as c:
        try:
            with open(path, "rb") as f:
                r = c.post(
                    "/ingest/",
                    files={"file": (path.name, f, "application/octet-stream")},
                    data={"strategy": strategy},
                )
        except httpx.RequestError as e:
            _error(f"Request failed: {e}")
            return

    if r.status_code != 200:
        _error(f"Error {r.status_code}: {r.text}")
        return

    d = r.json()
    _success("Ingested successfully!")
    console.print(f"  doc_id  : [yellow]{d['doc_id']}[/yellow]")
    console.print(f"  chunks  : {d['chunk_count']}")
    console.print(f"  strategy: {d['strategy']}")


def _fetch_docs() -> list[dict]:
    with _client() as c:
        r = c.get("/ingest/")
    return r.json() if r.status_code == 200 else []


def _pick_docs(docs: list[dict]) -> tuple[list[str] | None, str]:
    """
    Let user pick from the doc list.
    Returns (doc_ids, label). doc_ids=None means search all.
    """
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Filename")
    table.add_column("Strategy", style="dim")
    table.add_column("Chunks", justify="right", style="dim")

    for i, doc in enumerate(docs, 1):
        table.add_row(str(i), doc["filename"], doc["strategy"], str(doc["chunk_count"]))

    console.print(table)
    console.print(
        "  [dim]Enter a number, comma-separated numbers for multiple, or [bold]all[/bold][/dim]\n"
    )

    raw = Prompt.ask("Select document(s)").strip()

    if raw.lower() == "all":
        return None, "all documents"

    try:
        indices = [int(x.strip()) - 1 for x in raw.split(",")]
        selected = [docs[i] for i in indices if 0 <= i < len(docs)]
        if not selected:
            raise ValueError
        return [d["doc_id"] for d in selected], ", ".join(d["filename"] for d in selected)
    except (ValueError, IndexError):
        _error("Invalid selection.")
        return [], ""


def _chat_loop(session_id: str, doc_ids: list[str] | None, label: str):
    _section("Chat Session")
    console.print(f"[bold]Talking with:[/bold] [white]{label}[/white]")
    _info(f"Session: {session_id}   |   'back' to return to menu   |   'quit' or 'exit' to close\n")

    _BACK_WORDS = {"/quit", "quit", "exit", "q", "bye", "goodbye", "/back", "back", "b", "menu"}
    _info(f"Session: {session_id}   |   type 'exit' or 'back' to return to main menu\n")

    with _client() as c:
        while True:
            try:
                message = Prompt.ask("[bold green]You[/bold green]")
            except (KeyboardInterrupt, EOFError):
                console.print()
                break

            if message.strip().lower() in _BACK_WORDS:
                break

            payload: dict = {"session_id": session_id, "message": message}
            if doc_ids:
                payload["doc_ids"] = doc_ids

            try:
                with console.status("[dim]Thinking...[/dim]"):
                    r = c.post("/chat/", json=payload)
            except httpx.ReadTimeout:
                _error("Timed out — the LLM may be busy. Try again.")
                continue
            except httpx.RequestError as e:
                _error(f"Request failed: {e}")
                continue

            if r.status_code != 200:
                _error(f"Error {r.status_code}: {r.text}")
                continue

            data = r.json()

            if data.get("booking"):
                b = data["booking"]
                console.print(Panel(
                    f"[bold]Name:[/bold]  {b.get('name') or '-'}\n"
                    f"[bold]Email:[/bold] {b.get('email') or '-'}\n"
                    f"[bold]Date:[/bold]  {b.get('date') or '-'}\n"
                    f"[bold]Time:[/bold]  {b.get('time') or '-'}",
                    title="[green]Interview Booked[/green]",
                    border_style="green",
                ))
            else:
                console.print(f"\n[bold cyan]Assistant:[/bold cyan] {data['reply']}\n")


def _talk():
    _section("Talk with Documents")
    docs = _fetch_docs()

    if not docs:
        console.print("[yellow]No documents ingested yet. Upload one first.[/yellow]")
        return

    doc_ids, label = _pick_docs(docs)
    if doc_ids == []:
        return  # invalid selection

    session_id = uuid.uuid4().hex[:8]
    _chat_loop(session_id, doc_ids, label)


# ── Booking mode ──────────────────────────────────────────────────────────────

def _extract_info(message: str) -> dict:
    """Call the backend to extract name/email/role from the user's message."""
    with _client() as c:
        try:
            r = c.post("/bookings/extract", json={"message": message})
            return r.json() if r.status_code == 200 else {}
        except httpx.RequestError:
            return {}


def _show_slots(slots: list[dict]):
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Day")
    table.add_column("Date", style="white")
    table.add_column("Time", style="white")
    for i, slot in enumerate(slots, 1):
        d = Date.fromisoformat(slot["date"])
        table.add_row(str(i), calendar.day_name[d.weekday()], slot["date"], slot["time"])
    console.print(table)


def _ai(msg: str):
    console.print(f"\n[bold cyan]Assistant:[/bold cyan] {msg}\n")


def _booking():
    _section("Book an Interview")
    _ai("Hi! Tell me what you're looking for — job role, your name, email, anything you want to share.")

    session_id = uuid.uuid4().hex[:8]
    _STOP = {"back", "b", "exit", "quit", "bye", "goodbye"}

    with _client() as c:
        while True:
            try:
                message = Prompt.ask("[bold green]You[/bold green]").strip()
            except (KeyboardInterrupt, EOFError):
                console.print()
                break

            if message.lower() in _STOP:
                _ai("No problem — come back whenever you're ready!")
                break

            try:
                with console.status("[dim]...[/dim]"):
                    r = c.post("/agent/booking", json={"session_id": session_id, "message": message})
            except httpx.ReadTimeout:
                _error("Timed out — the model may be busy. Try again.")
                continue
            except httpx.RequestError as e:
                _error(f"Request failed: {e}")
                continue

            if r.status_code != 200:
                _error(f"Error {r.status_code}: {r.text}")
                continue

            data = r.json()
            _ai(data["reply"])

            if data.get("booking"):
                b = data["booking"]
                lines = []
                if b.get("role"):
                    lines.append(f"[bold]Role:[/bold]  {b['role']}")
                lines += [
                    f"[bold]Name:[/bold]  {b.get('name') or '-'}",
                    f"[bold]Email:[/bold] {b.get('email') or '-'}",
                    f"[bold]Date:[/bold]  {b.get('date') or '-'}",
                    f"[bold]Time:[/bold]  {b.get('time') or '-'}",
                ]
                console.print(Panel(
                    "\n".join(lines),
                    title="[green]Interview Booked[/green]",
                    border_style="green",
                    padding=(1, 2),
                ))
                break

    console.print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    console.clear()
    _banner()

    while True:
        choice = _main_menu()

        if choice == "q":
            console.print("\n[dim]Goodbye![/dim]\n")
            break

        elif choice == "1":
            while True:
                _section("Document Mode")
                sub = _doc_menu()
                if sub == "b":
                    console.clear()
                    _banner()
                    break
                elif sub == "1":
                    _upload()
                elif sub == "2":
                    _talk()

        elif choice == "2":
            _booking()
            console.rule(style="dim")


if __name__ == "__main__":
    main()
