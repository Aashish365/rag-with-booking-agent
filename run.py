"""
Project entry point.

  python run.py

What it does:
  1. Creates a virtual environment (.venv) if it doesn't exist
  2. Installs CLI requirements into the venv
  3. Checks if the backend API is running; starts Docker services if not
  4. Launches the interactive CLI
"""
import subprocess
import sys
import time
from pathlib import Path

# ── paths ─────────────────────────────────────────────────────────────────────
VENV = Path(".venv")
IS_WIN = sys.platform == "win32"
PYTHON = VENV / ("Scripts/python.exe" if IS_WIN else "bin/python")
PIP    = VENV / ("Scripts/pip.exe"    if IS_WIN else "bin/pip")
REQ    = Path("requirements-cli.txt")
CLI    = Path("cli.py")
API    = "http://localhost:8000/health"


def _run(*args, **kwargs):
    return subprocess.run(list(args), **kwargs)


# ── venv setup ────────────────────────────────────────────────────────────────

def setup_venv():
    if not VENV.exists():
        print("[setup] Creating virtual environment...")
        _run(sys.executable, "-m", "venv", str(VENV), check=True)
        _install_requirements()
        return

    # venv exists — check packages are present
    probe = _run(str(PYTHON), "-c", "import httpx, typer, rich", capture_output=True)
    if probe.returncode != 0:
        _install_requirements()


def _install_requirements():
    print("[setup] Installing CLI requirements...")
    _run(str(PIP), "install", "-q", "-r", str(REQ), check=True)
    print("[setup] Requirements ready.\n")


# ── service check ─────────────────────────────────────────────────────────────

def api_ready() -> bool:
    probe = _run(
        str(PYTHON), "-c",
        f"import httpx; r=httpx.get('{API}',timeout=3); exit(0 if r.status_code==200 else 1)",
        capture_output=True,
    )
    return probe.returncode == 0


def start_services():
    print("[docker] Starting backend services (first run may take a minute to build)...")
    result = _run("docker", "compose", "up", "-d", "--build")
    if result.returncode != 0:
        print("\n[error] Docker failed to start. Make sure Docker Desktop is running.")
        print("        Then try: docker compose up --build -d")
        sys.exit(1)

    print("[docker] Waiting for API to be ready", end="", flush=True)
    for _ in range(30):
        time.sleep(3)
        if api_ready():
            print("  ready!\n")
            return
        print(".", end="", flush=True)

    print("\n[warning] API did not respond in time.")
    print("          Check logs: docker logs backend-evaluation-app-1\n")


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    setup_venv()

    if not api_ready():
        start_services()
    else:
        print("[ok] Backend is running.\n")

    _run(str(PYTHON), str(CLI))
