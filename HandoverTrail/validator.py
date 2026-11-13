from database import get_connection
from permissions import require_role
from conflict_detection import detect_project_conflicts


def validate_project_claims(role: str, project_id: str = "PROJ-DEMO-001") -> int:
    """Rebuilds claim comparisons and gaps, then updates claim trust status.

    VERIFIED requires an agreeing normalized slot comparison; links to multiple
    sources alone are insufficient.
    Returns the number of validated claims."""

    require_role(role, "validate claims")
    detect_project_conflicts(role, project_id)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        claims = cursor.execute(
            "SELECT claim_id FROM claims WHERE project_id = ?",
            (project_id,),
        ).fetchall()
        validated_count = 0
        for claim in claims:
            claim_id = claim["claim_id"]
            evidence_count = cursor.execute(
                """
                SELECT COUNT(DISTINCT e.source_id)
                FROM claim_evidence ce
                JOIN evidence_chunks e ON ce.evidence_id = e.evidence_id
                WHERE ce.claim_id = ?
                """,
                (claim_id,),
            ).fetchone()[0]
            if evidence_count == 0:
                new_trust_status = "MISSING_EVIDENCE"
            else:
                conflict_status = cursor.execute(
                    """
                    SELECT 1 FROM claim_conflicts
                    WHERE (claim_a = ? OR claim_b = ?)
                      AND status = 'CONFLICTING'
                    LIMIT 1
                    """,
                    (claim_id, claim_id),
                ).fetchone()
                corroborated = cursor.execute(
                    """
                    SELECT 1 FROM claim_conflicts
                    WHERE (claim_a = ? OR claim_b = ?)
                      AND status = 'CORROBORATED'
                    LIMIT 1
                    """,
                    (claim_id, claim_id),
                ).fetchone()
                if conflict_status:
                    new_trust_status = "CONFLICTING"
                elif corroborated:
                    new_trust_status = "VERIFIED"
                else:
                    new_trust_status = "SINGLE_SOURCE"
            cursor.execute(
                """
                UPDATE claims
                SET trust_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE claim_id = ?
                """,
                (new_trust_status, claim_id),
            )
            validated_count += 1
        conn.commit()
        return validated_count
    finally:
        conn.close()


if __name__ == "__main__":
    count = validate_project_claims("Admin")
    print(f"Validation complete. Total claims evaluated and updated: {count}")