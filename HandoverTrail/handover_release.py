from __future__ import annotations

import json
import uuid
from datetime import datetime

from database import get_connection
from masking import mask_sensitive_text
from permissions import normalize_role, require_role


def _actor_id(conn, role: str) -> str:
    normalized_role = normalize_role(role)
    if normalized_role not in {"Admin", "Reviewer"}:
        raise PermissionError("Only Admin or Reviewer can release a handover.")
    actor = conn.execute(
        "SELECT user_id FROM users WHERE lower(role) = lower(?)",
        (normalized_role,),
    ).fetchone()
    if not actor:
        raise PermissionError("No demo reviewer is configured for the selected role.")
    return actor["user_id"]


def _masked(value: str | None) -> str | None:
    return mask_sensitive_text(value)[0] if value is not None else None


def _build_snapshot(conn, project_id: str) -> list[dict]:
    claims = conn.execute(
        """
        SELECT c.claim_id, c.claim_text, c.claim_type, c.trust_status, c.review_status,
               c.claim_source
        FROM claims c
        WHERE c.project_id = ? AND c.review_status = 'APPROVED'
          AND EXISTS (
              SELECT 1 FROM claim_evidence ce
              JOIN evidence_chunks e ON e.evidence_id = ce.evidence_id
              WHERE ce.claim_id = c.claim_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM claim_evidence ce
              JOIN evidence_chunks e ON e.evidence_id = ce.evidence_id
              JOIN sources s ON s.source_id = e.source_id
              WHERE ce.claim_id = c.claim_id
                AND lower(COALESCE(s.sensitivity, '')) <> 'public'
          )
        ORDER BY c.claim_type, c.claim_id
        """,
        (project_id,),
    ).fetchall()
    snapshot_claims = []
    for claim in claims:
        evidence = conn.execute(
            """
            SELECT e.evidence_id, e.chunk_index, e.reference_location, e.excerpt,
                   s.file_name, s.source_type
            FROM claim_evidence ce
            JOIN evidence_chunks e ON e.evidence_id = ce.evidence_id
            JOIN sources s ON s.source_id = e.source_id
            WHERE ce.claim_id = ? AND lower(s.sensitivity) = 'public'
            ORDER BY s.file_name, e.chunk_index, e.evidence_id
            """,
            (claim["claim_id"],),
        ).fetchall()
        if not evidence:
            continue
        snapshot_claims.append(
            {
                "claim_id": claim["claim_id"],
                "claim_text": _masked(claim["claim_text"]),
                "claim_type": claim["claim_type"],
                "trust_status": claim["trust_status"],
                "review_status": claim["review_status"],
                "claim_source": claim["claim_source"],
                "evidence": [
                    {
                        "evidence_id": row["evidence_id"],
                        "chunk_index": row["chunk_index"],
                        "file_name": _masked(row["file_name"]),
                        "reference_location": _masked(row["reference_location"]),
                        "excerpt": _masked(row["excerpt"]),
                        "source_type": row["source_type"],
                        "sensitivity": "public",
                    }
                    for row in evidence
                ],
            }
        )
    return snapshot_claims


def release_handover(role: str, project_id: str) -> dict:
    require_role(role, "release the handover")
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        actor_id = _actor_id(conn, role)
        project = conn.execute(
            "SELECT project_id FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if not project:
            raise ValueError("The project no longer exists.")
        claims = _build_snapshot(conn, project_id)
        if not claims:
            raise ValueError(
                "Release requires at least one approved claim with public evidence."
            )
        latest_version = conn.execute(
            "SELECT MAX(version) FROM handover_versions WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
        version = (latest_version or 0) + 1
        released_at = datetime.now().isoformat()
        snapshot = {
            "schema_version": 1,
            "project_id": project_id,
            "version": version,
            "released_at": released_at,
            "claims": claims,
        }
        version_id = f"HOV-{uuid.uuid4().hex[:12].upper()}"
        conn.execute(
            """
            INSERT INTO handover_versions
                (id, project_id, version, released_by, released_at, snapshot_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                project_id,
                version,
                actor_id,
                released_at,
                json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
            ),
        )
        conn.execute(
            """
            INSERT INTO audit_logs (log_id, actor_id, action, target_type, target_id, timestamp)
            VALUES (?, ?, 'RELEASE_HANDOVER', 'handover_version', ?, ?)
            """,
            (f"AUD-{uuid.uuid4().hex[:12].upper()}", actor_id, version_id, released_at),
        )
        conn.commit()
        return {
            "id": version_id,
            "project_id": project_id,
            "version": version,
            "released_by": actor_id,
            "released_at": released_at,
            "snapshot": snapshot,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_latest_release(role: str, project_id: str) -> dict | None:
    if normalize_role(role) not in {"Admin", "Reviewer", "Incoming"}:
        raise PermissionError("The selected role cannot view a released handover.")
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, project_id, version, released_by, released_at, snapshot_json
            FROM handover_versions
            WHERE project_id = ?
            ORDER BY version DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["snapshot"] = json.loads(result.pop("snapshot_json"))
        acknowledgements = conn.execute(
            """
            SELECT a.user_id, u.name AS user_name, a.acknowledged_at
            FROM handover_acks a
            JOIN users u ON u.user_id = a.user_id
            WHERE a.handover_version_id = ?
            ORDER BY a.acknowledged_at
            """,
            (row["id"],),
        ).fetchall()
        result["acknowledgements"] = [dict(ack) for ack in acknowledgements]
        return result
    finally:
        conn.close()


def acknowledge_latest_release(role: str, project_id: str) -> dict:
    if normalize_role(role) != "Incoming":
        raise PermissionError("Only Incoming can acknowledge a released handover.")
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        actor = conn.execute(
            "SELECT user_id FROM users WHERE user_id = 'USR-DEMO-INCOMING'"
        ).fetchone()
        if not actor:
            raise PermissionError("No demo Incoming identity is configured.")
        release = conn.execute(
            """
            SELECT id, version FROM handover_versions
            WHERE project_id = ? ORDER BY version DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if not release:
            raise ValueError("There is no released handover to acknowledge.")
        already_acknowledged = conn.execute(
            """
            SELECT acknowledged_at FROM handover_acks
            WHERE handover_version_id = ? AND user_id = ?
            """,
            (release["id"], actor["user_id"]),
        ).fetchone()
        if already_acknowledged:
            raise ValueError(
                f"Version {release['version']} was already acknowledged "
                f"at {already_acknowledged['acknowledged_at']}."
            )
        acknowledged_at = datetime.now().isoformat()
        conn.execute(
            """
            INSERT INTO handover_acks (id, handover_version_id, user_id, acknowledged_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                f"HAC-{uuid.uuid4().hex[:12].upper()}",
                release["id"],
                actor["user_id"],
                acknowledged_at,
            ),
        )
        conn.execute(
            """
            INSERT INTO audit_logs (log_id, actor_id, action, target_type, target_id, timestamp)
            VALUES (?, ?, 'ACKNOWLEDGE_HANDOVER', 'handover_version', ?, ?)
            """,
            (
                f"AUD-{uuid.uuid4().hex[:12].upper()}",
                actor["user_id"],
                release["id"],
                acknowledged_at,
            ),
        )
        conn.commit()
        return {
            "version": release["version"],
            "user_id": actor["user_id"],
            "acknowledged_at": acknowledged_at,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
