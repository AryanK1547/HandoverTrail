import uuid
from datetime import datetime

from database import get_connection

_ROLE_NAMES = {
    "admin": "Admin",
    "reviewer": "Reviewer",
    "incoming": "Incoming",
}


def normalize_role(role: str) -> str | None:
    if not isinstance(role, str):
        return None
    return _ROLE_NAMES.get(role.strip().casefold())


def can_view_sensitivity(role: str, sensitivity: str) -> bool:
    normalized_role = normalize_role(role)
    if normalized_role in {"Admin", "Reviewer"}:
        return True
    return normalized_role == "Incoming" and isinstance(sensitivity, str) and sensitivity.casefold() == "public"


def can_review(role: str) -> bool:
    return normalize_role(role) in {"Admin", "Reviewer"}


def require_role(role: str, action: str) -> None:
    if not can_review(role):
        raise PermissionError(f"The selected role is not permitted to {action}.")


def perform_claim_review(role: str, claim_id: str, action: str) -> None:
    """Authorize and persist a review plus its audit record."""
    action = action.upper()
    if action not in {"APPROVED", "REJECTED"}:
        raise ValueError("Review action must be APPROVED or REJECTED.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        normalized_role = normalize_role(role)
        actor = None
        if normalized_role:
            actor = cursor.execute(
                "SELECT user_id FROM users WHERE lower(role) = lower(?)",
                (normalized_role,),
            ).fetchone()
        if not actor:
            raise PermissionError("No demo user is configured for the selected role.")

        actor_id = actor["user_id"]
        now = datetime.now().isoformat()
        try:
            require_role(role, action.lower())
        except PermissionError:
            cursor.execute("""
                INSERT INTO audit_logs (log_id, actor_id, action, target_type, target_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                f"AUD-{uuid.uuid4().hex[:8].upper()}",
                actor_id,
                f"DENIED_{action}",
                "claim",
                claim_id,
                now,
            ))
            conn.commit()
            raise

        claim = cursor.execute(
            "SELECT claim_id FROM claims WHERE claim_id = ?",
            (claim_id,),
        ).fetchone()
        if not claim:
            raise ValueError("The claim no longer exists.")

        cursor.execute("""
            UPDATE claims
            SET review_status = ?, updated_at = ?
            WHERE claim_id = ?
        """, (action, now, claim_id))
        cursor.execute("""
            INSERT INTO reviews (review_id, claim_id, reviewer_id, action, comment, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            f"REV-{uuid.uuid4().hex[:8].upper()}",
            claim_id,
            actor_id,
            action,
            "Reviewed via Streamlit UI",
            now,
        ))
        cursor.execute("""
            INSERT INTO audit_logs (log_id, actor_id, action, target_type, target_id, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            f"AUD-{uuid.uuid4().hex[:8].upper()}",
            actor_id,
            action,
            "claim",
            claim_id,
            now,
        ))
        conn.commit()
    finally:
        conn.close()
