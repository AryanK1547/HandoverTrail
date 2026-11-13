from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime
from difflib import SequenceMatcher

from database import get_connection
from permissions import normalize_role, require_role

_SLOT_PATTERNS = (
    re.compile(
        r"^(?P<subject>.+?)\s+(?P<attribute>owner)\s*(?:is|:)\s*(?P<value>[^.;\n]+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?P<subject>.+?)\s+(?P<attribute>deadline|due date|launch date)\s*(?:is|:)\s*(?P<value>[^.;\n]+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?P<subject>.+?)\s+(?P<attribute>retry policy)\s*(?:is|:)\s*(?P<value>[^.;\n]+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?P<subject>.+?)\s+(?P<attribute>decision)\s*(?:is|:)\s*(?P<value>[^.;\n]+)",
        re.IGNORECASE,
    ),
)
_DATE_PATTERNS = (
    (re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$"), "%Y-%m-%d"),
    (re.compile(r"^(\d{1,2})[ -]([A-Za-z]{3,9})[ ,/-](\d{4})$"), "%d %b %Y"),
    (re.compile(r"^([A-Za-z]{3,9})[ -](\d{1,2}),?[ -](\d{4})$"), "%b %d %Y"),
    (re.compile(r"^(\d{1,2})[ -]([A-Za-z]{3,9})$"), "%d %b"),
)
_DATE_ATTRIBUTES = {"deadline", "due date", "launch date", "date"}


def normalize_text(value: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", value.casefold()).split())


def normalize_value(attribute: str, value: str) -> str:
    cleaned = " ".join(value.strip().split()).strip(" .")
    if attribute.casefold() in _DATE_ATTRIBUTES:
        for pattern, date_format in _DATE_PATTERNS:
            match = pattern.fullmatch(cleaned)
            if not match:
                continue
            try:
                if date_format == "%Y-%m-%d":
                    parsed = datetime.strptime(cleaned, date_format)
                    return parsed.strftime("%Y-%m-%d")
                if date_format == "%d %b %Y":
                    parsed = datetime.strptime(
                        f"{match.group(1)} {match.group(2)[:3]} {match.group(3)}",
                        date_format,
                    )
                    return parsed.strftime("%Y-%m-%d")
                if date_format == "%b %d %Y":
                    parsed = datetime.strptime(
                        f"{match.group(1)[:3]} {match.group(2)} {match.group(3)}",
                        date_format,
                    )
                    return parsed.strftime("%Y-%m-%d")
                parsed = datetime.strptime(
                    f"{match.group(1)} {match.group(2)[:3]}",
                    date_format,
                )
                return parsed.strftime("--%m-%d")
            except ValueError:
                break
    return normalize_text(cleaned)


def extract_claim_slots(claim_text: str) -> list[dict[str, str]]:
    slots = []
    for pattern in _SLOT_PATTERNS:
        match = pattern.search(claim_text.strip())
        if not match:
            continue
        subject = match.group("subject").strip(" .:")
        attribute = match.group("attribute").strip().casefold()
        value = match.group("value").strip(" .")
        if subject and value:
            slots.append({
                "subject": subject,
                "attribute": attribute,
                "value": value,
                "normalized_value": normalize_value(attribute, value),
            })
        break
    return slots


def _date_values_equal(left: str, right: str) -> bool:
    if left == right:
        return True
    if left.startswith("--") and right.endswith(left[1:]):
        return True
    if right.startswith("--") and left.endswith(right[1:]):
        return True
    return False


def _subjects_match(left: str, right: str) -> tuple[bool, bool]:
    left_normalized = normalize_text(left)
    right_normalized = normalize_text(right)
    if left_normalized == right_normalized:
        return True, False
    similarity = SequenceMatcher(None, left_normalized, right_normalized).ratio()
    return similarity >= 0.82, True


def _values_equal(attribute: str, left: str, right: str) -> bool:
    if attribute in _DATE_ATTRIBUTES:
        return _date_values_equal(left, right)
    return left == right


def detect_project_conflicts(role: str, project_id: str) -> dict[str, int]:
    require_role(role, "detect conflicts and evidence gaps")
    conn = get_connection()
    try:
        claims = conn.execute(
            """
            SELECT c.claim_id, c.claim_text, c.claim_type
            FROM claims c
            WHERE c.project_id = ?
            ORDER BY c.claim_id
            """,
            (project_id,),
        ).fetchall()
        conn.execute(
            """
            DELETE FROM claim_slots
            WHERE claim_id IN (SELECT claim_id FROM claims WHERE project_id = ?)
            """,
            (project_id,),
        )
        slot_map: dict[str, list[dict[str, str]]] = {}
        for claim in claims:
            slots = extract_claim_slots(claim["claim_text"])
            slot_map[claim["claim_id"]] = slots
            conn.executemany(
                """
                INSERT OR IGNORE INTO claim_slots
                    (claim_id, subject, attribute, value, normalized_value)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        claim["claim_id"],
                        slot["subject"],
                        slot["attribute"],
                        slot["value"],
                        slot["normalized_value"],
                    )
                    for slot in slots
                ],
            )

        source_map = {
            row["claim_id"]: set(row["source_ids"].split("|"))
            for row in conn.execute(
                """
                SELECT ce.claim_id, group_concat(DISTINCT e.source_id) AS source_ids
                FROM claim_evidence ce
                JOIN evidence_chunks e ON e.evidence_id = ce.evidence_id
                JOIN claims c ON c.claim_id = ce.claim_id
                WHERE c.project_id = ?
                GROUP BY ce.claim_id
                """,
                (project_id,),
            )
        }
        counts = {"CONFLICTING": 0, "POSSIBLE_CONFLICT": 0, "CORROBORATED": 0}
        now = datetime.now().isoformat()
        slot_claims = list(slot_map)
        detected_keys = set()
        for index, claim_a in enumerate(slot_claims):
            for claim_b in slot_claims[index + 1 :]:
                sources_a = source_map.get(claim_a, set())
                sources_b = source_map.get(claim_b, set())
                if not sources_a or not sources_b or sources_a == sources_b:
                    continue
                for slot_a in slot_map[claim_a]:
                    for slot_b in slot_map[claim_b]:
                        if slot_a["attribute"] != slot_b["attribute"]:
                            continue
                        subject_matches, fuzzy_subject = _subjects_match(
                            slot_a["subject"], slot_b["subject"]
                        )
                        if not subject_matches:
                            continue
                        values_equal = _values_equal(
                            slot_a["attribute"],
                            slot_a["normalized_value"],
                            slot_b["normalized_value"],
                        )
                        if values_equal:
                            status = "CORROBORATED"
                        elif fuzzy_subject:
                            status = "POSSIBLE_CONFLICT"
                        else:
                            status = "CONFLICTING"
                        subject = slot_a["subject"]
                        left_id, right_id = sorted((claim_a, claim_b))
                        key = (normalize_text(subject), slot_a["attribute"], left_id, right_id)
                        detected_keys.add(key)
                        existing = conn.execute(
                            """
                            SELECT conflict_id, resolution, resolved_by, resolved_at
                            FROM claim_conflicts
                            WHERE project_id = ? AND subject = ? AND attribute = ?
                              AND claim_a = ? AND claim_b = ?
                            """,
                            (project_id, subject, slot_a["attribute"], left_id, right_id),
                        ).fetchone()
                        if existing:
                            conn.execute(
                                """
                                UPDATE claim_conflicts SET status = ?
                                WHERE conflict_id = ?
                                """,
                                (status, existing["conflict_id"]),
                            )
                        else:
                            conn.execute(
                                """
                                INSERT INTO claim_conflicts
                                    (conflict_id, project_id, subject, attribute, claim_a, claim_b,
                                     status, resolution, created_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, 'UNRESOLVED', ?)
                                """,
                                (
                                    f"CNF-{uuid.uuid4().hex[:12].upper()}",
                                    project_id,
                                    subject,
                                    slot_a["attribute"],
                                    left_id,
                                    right_id,
                                    status,
                                    now,
                                ),
                            )
                        counts[status] += 1

        for row in conn.execute(
            "SELECT conflict_id, subject, attribute, claim_a, claim_b FROM claim_conflicts WHERE project_id = ?",
            (project_id,),
        ).fetchall():
            row_key = (
                normalize_text(row["subject"]),
                row["attribute"],
                row["claim_a"],
                row["claim_b"],
            )
            if row_key not in detected_keys:
                conn.execute(
                    "UPDATE claim_conflicts SET status = 'STALE' WHERE conflict_id = ?",
                    (row["conflict_id"],),
                )

        gap_count = _detect_gaps(conn, project_id, claims, now)
        conn.commit()
        return {**counts, "GAPS": gap_count}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _add_gap(
    conn,
    project_id: str,
    gap_type: str,
    subject: str,
    claim_id: str,
    now: str,
) -> bool:
    key = f"{project_id}|{gap_type}|{subject}|{claim_id}"
    gap_id = f"GAP-{hashlib.sha256(key.encode('utf-8')).hexdigest()[:16].upper()}"
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO gaps (id, project_id, gap_type, subject, related_claim_id, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'open', ?)
        """,
        (gap_id, project_id, gap_type, subject, claim_id, now),
    )
    return cursor.rowcount > 0


def _detect_gaps(conn, project_id: str, claims, now: str) -> int:
    added = 0
    for claim in claims:
        text = claim["claim_text"]
        normalized = normalize_text(text)
        evidence_count = conn.execute(
            """
            SELECT COUNT(DISTINCT e.source_id)
            FROM claim_evidence ce
            JOIN evidence_chunks e ON e.evidence_id = ce.evidence_id
            WHERE ce.claim_id = ?
            """,
            (claim["claim_id"],),
        ).fetchone()[0]
        gap_candidates = []
        task_match = re.search(r"\btask\s+([A-Z0-9-]+)\b", text, re.IGNORECASE)
        if claim["claim_type"] == "Next action" or task_match:
            owner_match = re.search(
                r"\bowner\s*(?:is|:)\s*([^.;,\n]+)|\bassigned to\s+([^.;,\n]+)",
                text,
                re.IGNORECASE,
            )
            owner_value = (
                (owner_match.group(1) or owner_match.group(2)).strip()
                if owner_match
                else ""
            )
            has_owner = bool(owner_value) and not re.fullmatch(
                r"(?:missing|unassigned|not recorded|not assigned|none|unknown)",
                owner_value,
                re.IGNORECASE,
            )
            if not has_owner:
                gap_candidates.append((
                    "task_without_owner",
                    task_match.group(1) if task_match else claim["claim_text"][:80],
                ))
        if claim["claim_type"] == "Decision" or re.search(r"\bdecision\b", normalized):
            if not re.search(
                r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}\s+[a-z]{3,9}(?:\s+\d{4})?)\b",
                normalized,
            ):
                gap_candidates.append(("decision_missing_date", claim["claim_text"][:80]))
            if not re.search(
                r"\b(?:because|rationale|reason|so that|in order to)\b",
                normalized,
            ):
                gap_candidates.append(("decision_missing_rationale", claim["claim_text"][:80]))
        if (
            claim["claim_type"] == "Risk" or re.search(r"\brisk\b", normalized)
        ) and not re.search(r"\b(?:mitigat|prevent|fallback|contingency)\w*\b", normalized):
            gap_candidates.append(("risk_missing_mitigation", claim["claim_text"][:80]))
        if evidence_count == 1:
            gap_candidates.append(("single_source_claim", claim["claim_text"][:80]))
        for gap_type, subject in gap_candidates:
            added += _add_gap(
                conn,
                project_id,
                gap_type,
                subject,
                claim["claim_id"],
                now,
            )
    return added


def get_conflict_records(role: str, project_id: str) -> list[dict]:
    require_role(role, "view conflicts")
    conn = get_connection()
    try:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT cf.*, a.claim_text AS claim_a_text, b.claim_text AS claim_b_text
                FROM claim_conflicts cf
                JOIN claims a ON a.claim_id = cf.claim_a
                JOIN claims b ON b.claim_id = cf.claim_b
                WHERE cf.project_id = ?
                  AND cf.status IN ('CONFLICTING', 'POSSIBLE_CONFLICT', 'CORROBORATED')
                ORDER BY cf.status, cf.subject, cf.attribute
                """,
                (project_id,),
            )
        ]
    finally:
        conn.close()


def get_gap_records(role: str, project_id: str) -> list[dict]:
    require_role(role, "view evidence gaps")
    conn = get_connection()
    try:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT g.*, c.claim_text
                FROM gaps g
                LEFT JOIN claims c ON c.claim_id = g.related_claim_id
                WHERE g.project_id = ? AND g.status = 'open'
                ORDER BY g.gap_type, g.created_at
                """,
                (project_id,),
            )
        ]
    finally:
        conn.close()


def resolve_conflict(role: str, conflict_id: str, resolution: str) -> None:
    require_role(role, "resolve conflicts")
    if resolution not in {"KEEP_A", "KEEP_B", "KEEP_BOTH", "UNRESOLVED"}:
        raise ValueError("Choose keep A, keep B, keep both as context, or unresolved.")
    normalized_role = normalize_role(role)
    conn = get_connection()
    try:
        actor = conn.execute(
            "SELECT user_id FROM users WHERE lower(role) = lower(?)",
            (normalized_role,),
        ).fetchone()
        conflict = conn.execute(
            "SELECT conflict_id FROM claim_conflicts WHERE conflict_id = ?",
            (conflict_id,),
        ).fetchone()
        if not actor:
            raise PermissionError("No demo reviewer is configured for this role.")
        if not conflict:
            raise ValueError("The conflict is no longer available.")
        now = datetime.now().isoformat()
        conn.execute(
            """
            UPDATE claim_conflicts
            SET resolution = ?, resolved_by = ?, resolved_at = ?
            WHERE conflict_id = ?
            """,
            (resolution, actor["user_id"], now, conflict_id),
        )
        conn.execute(
            """
            INSERT INTO audit_logs (log_id, actor_id, action, target_type, target_id, timestamp)
            VALUES (?, ?, ?, 'claim_conflict', ?, ?)
            """,
            (
                f"AUD-{uuid.uuid4().hex[:12].upper()}",
                actor["user_id"],
                f"RESOLVE_CONFLICT_{resolution}",
                conflict_id,
                now,
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
