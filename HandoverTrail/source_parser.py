import csv
import os
import re
import uuid
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Iterable

from database import PROJECT_ROOT, get_connection

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
UPLOADS_DIR = Path(
    os.environ.get("HANDOVERTRAIL_UPLOADS_DIR", PROJECT_ROOT / "uploads")
).expanduser()


def sanitize_upload_filename(name: str) -> str:
    """Return a safe basename and reject names that are not supported uploads."""
    safe_name = Path(name.replace("\\", "/")).name
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", safe_name)
    if safe_name in {"", ".", ".."}:
        raise ValueError("Please choose a file with a valid name.")
    if Path(safe_name).suffix.lower() not in {".txt", ".md", ".csv"}:
        raise ValueError("Only .txt, .md, and .csv files are supported.")
    return safe_name


def persist_uploaded_file(project_id: str, name: str, contents: bytes) -> tuple[Path, bool]:
    """Validate and save upload bytes; return the saved path and replacement status."""
    safe_name = sanitize_upload_filename(name)
    if not contents:
        raise ValueError(f"{safe_name} is empty. Choose a file containing data.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise ValueError(f"{safe_name} exceeds the 2 MB upload limit.")

    project_dir = UPLOADS_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    destination = project_dir / safe_name
    replaced = destination.exists()
    destination.write_bytes(contents)
    return destination, replaced


def _read_text(file_path: Path) -> str:
    data = file_path.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def _csv_row_text(row: dict) -> str:
    fields = []
    for key, value in row.items():
        if key is None:
            if isinstance(value, list) and value:
                fields.append(f"Extra columns: {', '.join(str(item).strip() for item in value)}")
            continue
        if not isinstance(key, str):
            continue
        if isinstance(value, str) and value.strip():
            fields.append(f"{key.strip()}: {value.strip()}")
    return ", ".join(fields)


def _source_path(project_id: str, file_name: str, prefer_demo: bool = False) -> Path:
    demo_path = PROJECT_ROOT / "data" / "demo_project" / file_name
    upload_path = UPLOADS_DIR / project_id / file_name
    candidates = (
        (demo_path, upload_path, PROJECT_ROOT / file_name)
        if prefer_demo
        else (upload_path, demo_path, PROJECT_ROOT / file_name)
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Source file {file_name!r} is missing from uploads and demo data.")


def parse_and_store_sources(
    project_id: str = "PROJ-DEMO-001",
    force_reparse: bool = False,
    source_ids: Iterable[str] | None = None,
    db_path: str | Path | None = None,
    prefer_demo: bool = False,
) -> int:
    """Parse only pending or explicitly changed sources into evidence chunks."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        query = """
            SELECT s.source_id, s.file_name, s.file_type
            FROM sources s
            WHERE s.project_id = ?
        """
        params: list[str] = [project_id]
        selected_ids = list(source_ids) if source_ids is not None else None
        if selected_ids is not None:
            if not selected_ids:
                return 0
            placeholders = ",".join("?" for _ in selected_ids)
            query += f" AND s.source_id IN ({placeholders})"
            params.extend(selected_ids)
        elif not force_reparse:
            query += """
                AND NOT EXISTS (
                    SELECT 1 FROM evidence_chunks e WHERE e.source_id = s.source_id
                )
            """
        sources = cursor.execute(query, params).fetchall()

        total_chunks_created = 0
        for source in sources:
            source_id = source["source_id"]
            file_name = source["file_name"]
            file_path = _source_path(project_id, file_name, prefer_demo)
            suffix = Path(file_name).suffix.lower()
            text = _read_text(file_path)
            chunks = []

            if suffix == ".csv":
                reader = csv.DictReader(StringIO(text))
                for row_index, row in enumerate(reader, start=1):
                    row_details = _csv_row_text(row)
                    if not row_details:
                        continue
                    task_id = row.get("task_id") or f"Row-{row_index}"
                    chunks.append((
                        f"EVD-{uuid.uuid4().hex[:8].upper()}",
                        source_id,
                        row_index - 1,
                        row_details,
                        f"{file_name} [Row {row_index}: {task_id}]",
                        datetime.now().isoformat(),
                    ))
            elif suffix in {".txt", ".md"}:
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                window_size = 3
                for chunk_index, start in enumerate(range(0, len(lines), window_size)):
                    chunk_lines = lines[start:start + window_size]
                    chunks.append((
                        f"EVD-{uuid.uuid4().hex[:8].upper()}",
                        source_id,
                        chunk_index,
                        "\n".join(chunk_lines),
                        f"{file_name} [Lines {start + 1}-{start + len(chunk_lines)}]",
                        datetime.now().isoformat(),
                    ))
            else:
                raise ValueError(
                    f"Unsupported source type for {file_name!r}; use .txt, .md, or .csv."
                )

            cursor.execute("DELETE FROM evidence_chunks WHERE source_id = ?", (source_id,))
            if chunks:
                cursor.executemany("""
                    INSERT INTO evidence_chunks
                        (evidence_id, source_id, chunk_index, excerpt, reference_location, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, chunks)
            total_chunks_created += len(chunks)

        conn.commit()
        return total_chunks_created
    finally:
        conn.close()


if __name__ == "__main__":
    count = parse_and_store_sources(force_reparse=True)
    print(f"\nDone! Total chunks created across all sources: {count}")
