from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from database import PROJECT_ROOT, get_connection

PROJECT_ID = "PROJ-DEMO-001"

_DEMO_CLAIMS = (
    ("CLM-R3-OWNER-PRIYA", "Payment webhook owner is Priya Shah.", "Owner", "r3_conflicts_a.txt"),
    ("CLM-R3-OWNER-ALEX", "Payment webhook owner is Alex Chen.", "Owner", "r3_conflicts_b.txt"),
    ("CLM-R3-DEADLINE-15", "Release deadline is 15 Nov 2026.", "Decision", "r3_conflicts_a.txt"),
    ("CLM-R3-DEADLINE-18", "Release deadline is 18 Nov 2026.", "Decision", "r3_conflicts_b.txt"),
    ("CLM-R3-RETRY-3", "Webhook retry policy is 3 attempts.", "Decision", "r3_conflicts_a.txt"),
    ("CLM-R3-RETRY-5", "Webhook retry policy is 5 attempts.", "Decision", "r3_conflicts_b.txt"),
    ("CLM-R3-TASK-OWNER-GAP", "Task T-204 is open and has no owner.", "Next action", "r3_gaps.txt"),
    (
        "CLM-R3-DECISION-GAP",
        "Decision: Use Redis for webhook idempotency; date and rationale are not recorded.",
        "Decision",
        "r3_gaps.txt",
    ),
    (
        "CLM-R3-RISK-GAP",
        "Risk: Retry storm may overload the API; mitigation is not recorded.",
        "Risk",
        "r3_gaps.txt",
    ),
)


def seed_conflict_demo(db_path: str | Path | None = None) -> None:
    """Idempotently add the small synthetic Round 3 conflict/gap fixture."""
    demo_dir = PROJECT_ROOT / "data" / "demo_project"
    conn = get_connection(db_path)
    try:
        source_ids: list[str] = []
        for file_name in ("r3_conflicts_a.txt", "r3_conflicts_b.txt", "r3_gaps.txt"):
            source = conn.execute(
                "SELECT source_id FROM sources WHERE project_id = ? AND file_name = ?",
                (PROJECT_ID, file_name),
            ).fetchone()
            if source:
                source_id = source["source_id"]
            else:
                source_id = f"SRC-{uuid.uuid4().hex[:8].upper()}"
                conn.execute(
                    """
                    INSERT INTO sources
                        (source_id, project_id, file_name, file_type, uploaded_at, sensitivity, source_type)
                    VALUES (?, ?, ?, 'TXT', ?, 'public', 'source')
                    """,
                    (source_id, PROJECT_ID, file_name, datetime.now().isoformat()),
                )
            source_ids.append(source_id)
        conn.commit()

        unparsed_ids = [
            source_id
            for source_id in source_ids
            if conn.execute(
                "SELECT 1 FROM evidence_chunks WHERE source_id = ? LIMIT 1",
                (source_id,),
            ).fetchone() is None
        ]
    finally:
        conn.close()

    if not demo_dir.is_dir():
        raise FileNotFoundError(f"Round 3 demo sources are missing from {demo_dir}.")

    if unparsed_ids:
        from source_parser import parse_and_store_sources

        parse_and_store_sources(
            PROJECT_ID,
            source_ids=unparsed_ids,
            db_path=db_path,
            prefer_demo=True,
        )

    conn = get_connection(db_path)
    try:
        evidence = {
            row["file_name"]: row["evidence_id"]
            for row in conn.execute(
                """
                SELECT s.file_name, e.evidence_id
                FROM evidence_chunks e
                JOIN sources s ON s.source_id = e.source_id
                WHERE s.project_id = ? AND s.file_name IN (?, ?, ?)
                """,
                (PROJECT_ID, "r3_conflicts_a.txt", "r3_conflicts_b.txt", "r3_gaps.txt"),
            )
        }
        now = datetime.now().isoformat()
        for claim_id, text, claim_type, file_name in _DEMO_CLAIMS:
            evidence_id = evidence.get(file_name)
            if not evidence_id:
                raise ValueError(f"No evidence excerpt was parsed for {file_name}.")
            conn.execute(
                """
                INSERT OR IGNORE INTO claims
                    (claim_id, project_id, claim_text, claim_type, trust_status, claim_source,
                     review_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'SINGLE_SOURCE', 'cached_demo', 'PENDING', ?, ?)
                """,
                (claim_id, PROJECT_ID, text, claim_type, now, now),
            )
            conn.execute(
                "INSERT OR IGNORE INTO claim_evidence (claim_id, evidence_id) VALUES (?, ?)",
                (claim_id, evidence_id),
            )
        conn.commit()
    finally:
        conn.close()
