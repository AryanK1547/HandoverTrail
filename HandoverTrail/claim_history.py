from __future__ import annotations

import uuid
from datetime import datetime

from database import get_connection
from permissions import normalize_role, require_role


def edit_claim(role: str, claim_id: str, new_text: str, reason: str) -> int:
    claim_text = new_text.strip()
    edit_reason = reason.strip()
    if not claim_text:
        raise ValueError("Claim text cannot be empty.")
    if not edit_reason:
        raise ValueError("Enter a reason for this edit.")
    require_role(role, "edit claims")

    conn = get_connection()
    try:
        normalized_role = normalize_role(role)
        actor = conn.execute(
            "SELECT user_id FROM users WHERE lower(role) = lower(?)",
            (normalized_role,),
        ).fetchone()
        if not actor:
            raise PermissionError("No demo reviewer is configured for this role.")
        claim = conn.execute(
            """
            SELECT project_id, claim_text
            FROM claims
            WHERE claim_id = ?
            """,
            (claim_id,),
        ).fetchone()
        if not claim:
            raise ValueError("The claim no longer exists.")
        if claim_text == claim["claim_text"].strip():
            raise ValueError("The edited claim is unchanged.")

        latest_version = conn.execute(
            "SELECT MAX(version) FROM claim_versions WHERE claim_id = ?",
            (claim_id,),
        ).fetchone()[0]
        archived_version = (latest_version or 0) + 1
        now = datetime.now().isoformat()
        actor_id = actor["user_id"]
        conn.execute(
            """
            INSERT INTO claim_versions
                (id, claim_id, version, text, editor_id, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"CLV-{uuid.uuid4().hex[:12].upper()}",
                claim_id,
                archived_version,
                claim["claim_text"],
                actor_id,
                edit_reason,
                now,
            ),
        )
        conn.execute(
            """
            UPDATE claims
            SET claim_text = ?, review_status = 'EDITED_PENDING_REVIEW',
                validated_at = NULL, updated_at = ?
            WHERE claim_id = ?
            """,
            (claim_text, now, claim_id),
        )
        conn.execute(
            """
            INSERT INTO reviews
                (review_id, claim_id, reviewer_id, action, comment, timestamp)
            VALUES (?, ?, ?, 'EDITED', ?, ?)
            """,
            (f"REV-{uuid.uuid4().hex[:12].upper()}", claim_id, actor_id, edit_reason, now),
        )
        conn.execute(
            """
            INSERT INTO audit_logs (log_id, actor_id, action, target_type, target_id, timestamp)
            VALUES (?, ?, 'EDIT_CLAIM', 'claim', ?, ?)
            """,
            (f"AUD-{uuid.uuid4().hex[:12].upper()}", actor_id, claim_id, now),
        )
        conn.commit()
        from validator import validate_project_claims

        validate_project_claims(role, claim["project_id"])
        return archived_version
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_claim_history(role: str, claim_id: str) -> dict:
    require_role(role, "view claim history")
    conn = get_connection()
    try:
        claim = conn.execute(
            "SELECT claim_text, review_status FROM claims WHERE claim_id = ?",
            (claim_id,),
        ).fetchone()
        if not claim:
            raise ValueError("The claim no longer exists.")
        versions = conn.execute(
            """
            SELECT v.version, v.text, v.reason, v.created_at, u.name AS editor_name
            FROM claim_versions v
            JOIN users u ON u.user_id = v.editor_id
            WHERE v.claim_id = ?
            ORDER BY v.version
            """,
            (claim_id,),
        ).fetchall()
        return {
            "current_text": claim["claim_text"],
            "review_status": claim["review_status"],
            "versions": [dict(row) for row in versions],
        }
    finally:
        conn.close()
