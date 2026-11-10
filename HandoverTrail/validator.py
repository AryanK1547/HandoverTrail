from database import get_connection
from permissions import require_role


def validate_project_claims(role: str, project_id: str = "PROJ-DEMO-001") -> int:
    """Inspects all claims for a project, validates evidence references in claim_evidence,
    computes trust_status (VERIFIED, SINGLE_SOURCE, MISSING_EVIDENCE, CONFLICTING),
    and updates the database.
    Returns the number of validated claims."""

    require_role(role, "validate claims")
    conn = get_connection()
    cursor = conn.cursor()

    # Fetch all claims for the project
    cursor.execute("SELECT claim_id, claim_text FROM claims WHERE project_id = ?", (project_id,))
    claims = cursor.fetchall()

    validated_count = 0

    for claim in claims:
        claim_id = claim["claim_id"]

        # Count distinct evidence chunks and sources linked to this claim
        cursor.execute("""
            SELECT ce.evidence_id, e.source_id, s.file_name
            FROM claim_evidence ce
            JOIN evidence_chunks e ON ce.evidence_id = e.evidence_id
            JOIN sources s ON e.source_id = s.source_id
            WHERE ce.claim_id = ?
        """, (claim_id,))
        evidence_records = cursor.fetchall()

        if not evidence_records:
            # Rule 1: No evidence linked or evidence IDs do not exist in DB
            new_trust_status = "MISSING_EVIDENCE"
        else:
            # Count distinct source files supporting this claim
            distinct_sources = set(r["file_name"] for r in evidence_records)

            if len(distinct_sources) >= 2:
                # Rule 2: Supported by 2 or more distinct sources
                new_trust_status = "VERIFIED"
            else:
                # Rule 3: Supported by a single source
                new_trust_status = "SINGLE_SOURCE"

        # Update trust status in database
        cursor.execute("""
            UPDATE claims
            SET trust_status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE claim_id = ?
        """, (new_trust_status, claim_id))
        validated_count += 1

    conn.commit()
    conn.close()
    return validated_count


if __name__ == "__main__":
    count = validate_project_claims("Admin")
    print(f"Validation complete. Total claims evaluated and updated: {count}")