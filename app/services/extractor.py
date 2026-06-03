from pathlib import Path
import uuid
import shutil

import opendataloader_pdf

from app.core.config import settings


def extract_text(file_bytes: bytes, filename: str) -> str:
    if filename.lower().endswith(".txt"):
        return file_bytes.decode("utf-8", errors="replace")
    return _extract_pdf(file_bytes, filename)


def _extract_pdf(file_bytes: bytes, filename: str) -> str:
    tmp_root = Path(settings.tmp_dir)
    tmp_root.mkdir(exist_ok=True)

    job_id = uuid.uuid4().hex
    input_dir = tmp_root / job_id / "in"
    output_dir = tmp_root / job_id / "out"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    input_path = input_dir / filename
    input_path.write_bytes(file_bytes)

    opendataloader_pdf.convert(
        input_path=[str(input_path)],
        output_dir=str(output_dir),
        format="text",
    )

    stem = Path(filename).stem
    txt_file = output_dir / f"{stem}.txt"

    if not txt_file.exists():
        candidates = list(output_dir.rglob("*.txt"))
        if not candidates:
            raise RuntimeError(f"opendataloader_pdf produced no text output for {filename}")
        txt_file = candidates[0]

    text = txt_file.read_text(encoding="utf-8")
    shutil.rmtree(tmp_root / job_id, ignore_errors=True)
    return text
