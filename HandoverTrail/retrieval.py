from permissions import can_view_sensitivity, normalize_role
from database import get_connection


def _claim_has_only_visible_evidence(conn, role: str, claim_id: str) -> bool:
    linked_sources = conn.execute("""
        SELECT s.sensitivity
        FROM claim_evidence ce
        LEFT JOIN evidence_chunks e ON ce.evidence_id = e.evidence_id
        LEFT JOIN sources s ON e.source_id = s.source_id
        WHERE ce.claim_id = ?
    """, (claim_id,)).fetchall()
    return bool(linked_sources) and all(
        can_view_sensitivity(role, source["sensitivity"]) for source in linked_sources
    )


def get_visible_sources(role: str, project_id: str) -> list:
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT source_id, project_id, file_name, file_type, sensitivity, uploaded_at
            FROM sources
            WHERE project_id = ?
            ORDER BY file_name
        """, (project_id,)).fetchall()
        return [row for row in rows if can_view_sensitivity(role, row["sensitivity"])]
    finally:
        conn.close()


def get_visible_evidence_chunks(role: str, project_id: str) -> list:
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT e.evidence_id, e.source_id, e.chunk_index, e.reference_location,
                   e.excerpt, s.file_name, s.sensitivity
            FROM evidence_chunks e
            JOIN sources s ON e.source_id = s.source_id
            WHERE s.project_id = ?
            ORDER BY s.file_name, e.chunk_index
        """, (project_id,)).fetchall()
        return [row for row in rows if can_view_sensitivity(role, row["sensitivity"])]
    finally:
        conn.close()


def get_visible_claims(role: str, project_id: str) -> list:
    conn = get_connection()
    try:
        claims = conn.execute("""
            SELECT claim_id, project_id, claim_text, claim_type, trust_status,
                   review_status, created_at, updated_at
            FROM claims
            WHERE project_id = ?
            ORDER BY created_at DESC
        """, (project_id,)).fetchall()
        visible_claims = []
        is_incoming = normalize_role(role) == "Incoming"
        for claim in claims:
            if is_incoming and claim["review_status"] != "APPROVED":
                continue
            if _claim_has_only_visible_evidence(conn, role, claim["claim_id"]):
                visible_claims.append(claim)
        return visible_claims
    finally:
        conn.close()


def get_claim_evidence(role: str, claim_id: str) -> list:
    conn = get_connection()
    try:
        claim = conn.execute(
            "SELECT project_id, review_status FROM claims WHERE claim_id = ?",
            (claim_id,),
        ).fetchone()
        if not claim:
            return []
        if normalize_role(role) == "Incoming" and claim["review_status"] != "APPROVED":
            return []
        if not _claim_has_only_visible_evidence(conn, role, claim_id):
            return []
        rows = conn.execute("""
            SELECT e.evidence_id, e.source_id, e.chunk_index, e.reference_location,
                   e.excerpt, s.file_name, s.sensitivity
            FROM claim_evidence ce
            JOIN evidence_chunks e ON ce.evidence_id = e.evidence_id
            JOIN sources s ON e.source_id = s.source_id
            WHERE ce.claim_id = ?
            ORDER BY s.file_name, e.chunk_index
        """, (claim_id,)).fetchall()
        return [row for row in rows if can_view_sensitivity(role, row["sensitivity"])]
    finally:
        conn.close()


def count_hidden_claims(role: str, project_id: str) -> int:
    if normalize_role(role) != "Incoming":
        return 0
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT COUNT(DISTINCT c.claim_id)
            FROM claims c
            WHERE c.project_id = ?
              AND c.review_status = 'APPROVED'
              AND EXISTS (
                  SELECT 1
                  FROM claim_evidence ce
                  JOIN evidence_chunks e ON ce.evidence_id = e.evidence_id
                  JOIN sources s ON e.source_id = s.source_id
                  WHERE ce.claim_id = c.claim_id
              )
              AND EXISTS (
                  SELECT 1
                  FROM claim_evidence ce
                  JOIN evidence_chunks e ON ce.evidence_id = e.evidence_id
                  JOIN sources s ON e.source_id = s.source_id
                  WHERE ce.claim_id = c.claim_id
                    AND lower(s.sensitivity) <> 'public'
              )
        """, (project_id,)).fetchone()
        return row[0]
    finally:
        conn.close()