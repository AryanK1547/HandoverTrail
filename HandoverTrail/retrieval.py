from permissions import can_view_sensitivity, normalize_role
from database import get_connection
from masking import mask_sensitive_text


def _mask_row_values(row, keys: tuple[str, ...]) -> dict:
    masked_row = dict(row)
    for key in keys:
        if masked_row.get(key) is not None:
            masked_row[key] = mask_sensitive_text(masked_row[key])[0]
    return masked_row


def _source_is_visible(conn, role: str, source) -> bool:
    if not can_view_sensitivity(role, source["sensitivity"]):
        return False
    if normalize_role(role) != "Incoming" or source["source_type"] != "interview":
        return True
    statuses = conn.execute(
        """
        SELECT c.review_status
        FROM claim_evidence ce
        JOIN claims c ON c.claim_id = ce.claim_id
        JOIN evidence_chunks e ON e.evidence_id = ce.evidence_id
        WHERE e.source_id = ?
        """,
        (source["source_id"],),
    ).fetchall()
    return bool(statuses) and all(row["review_status"] == "APPROVED" for row in statuses)


def _claim_has_only_visible_evidence(conn, role: str, claim_id: str) -> bool:
    linked_sources = conn.execute("""
        SELECT s.source_id, s.sensitivity, s.source_type
        FROM claim_evidence ce
        LEFT JOIN evidence_chunks e ON ce.evidence_id = e.evidence_id
        LEFT JOIN sources s ON e.source_id = s.source_id
        WHERE ce.claim_id = ?
    """, (claim_id,)).fetchall()
    return bool(linked_sources) and all(
        source["source_id"] is not None and _source_is_visible(conn, role, source)
        for source in linked_sources
    )


def get_visible_sources(role: str, project_id: str) -> list:
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT source_id, project_id, file_name, file_type, sensitivity, source_type, uploaded_at
            FROM sources
            WHERE project_id = ?
            ORDER BY file_name
        """, (project_id,)).fetchall()
        visible = [row for row in rows if _source_is_visible(conn, role, row)]
        if normalize_role(role) == "Incoming":
            return [_mask_row_values(row, ("file_name",)) for row in visible]
        return visible
    finally:
        conn.close()


def get_visible_evidence_chunks(role: str, project_id: str) -> list:
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT e.evidence_id, e.source_id, e.chunk_index, e.reference_location,
                   e.excerpt, s.file_name, s.sensitivity, s.source_type
            FROM evidence_chunks e
            JOIN sources s ON e.source_id = s.source_id
            WHERE s.project_id = ?
            ORDER BY s.file_name, e.chunk_index
        """, (project_id,)).fetchall()
        visible = [row for row in rows if _source_is_visible(conn, role, row)]
        if normalize_role(role) == "Incoming":
            return [
                _mask_row_values(row, ("excerpt", "file_name", "reference_location"))
                for row in visible
            ]
        return visible
    finally:
        conn.close()


def get_visible_claims(role: str, project_id: str) -> list:
    conn = get_connection()
    try:
        claims = conn.execute("""
            SELECT claim_id, project_id, claim_text, claim_type, trust_status,
                   claim_source, review_status, validated_at, created_at, updated_at
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
                if is_incoming:
                    visible_claims.append(_mask_row_values(claim, ("claim_text",)))
                else:
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
                   e.excerpt, s.file_name, s.sensitivity, s.source_type
            FROM claim_evidence ce
            JOIN evidence_chunks e ON ce.evidence_id = e.evidence_id
            JOIN sources s ON e.source_id = s.source_id
            WHERE ce.claim_id = ?
            ORDER BY s.file_name, e.chunk_index
        """, (claim_id,)).fetchall()
        visible = [row for row in rows if _source_is_visible(conn, role, row)]
        if normalize_role(role) == "Incoming":
            return [
                _mask_row_values(row, ("excerpt", "file_name", "reference_location"))
                for row in visible
            ]
        return visible
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