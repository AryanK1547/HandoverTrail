"""Reviewer-facing explanation of why each claim has its trust level.

Everything here is derived from stored data at read time (no schema change, no
provider call). The evidence-match check is lexical: it reports how many of a
claim's key words and numbers appear in the excerpts the claim cites. It can
reveal a claim that its own citation does not support; it cannot prove a claim
is true or that a paraphrase is wrong.
"""
from __future__ import annotations

import re

from database import get_connection
from permissions import require_role

WEAK_MATCH_THRESHOLD = 0.6
MIN_TERMS_FOR_MATCH_CHECK = 3

_STOPWORDS = frozenset(
    """
    that this with from have been were will would should could their there which
    about into than then them they also only must need needs when what where while
    after before over under each other some such using used uses answer question
    """.split()
)

_GAP_LABELS = {
    "task_without_owner": "Task has no owner",
    "decision_missing_date": "Decision has no date",
    "decision_missing_rationale": "Decision has no rationale",
    "risk_missing_mitigation": "Risk has no mitigation",
}


def _terms(text: str) -> set[str]:
    terms = set()
    for token in re.findall(r"[a-z0-9]+", text.casefold()):
        if token in _STOPWORDS:
            continue
        if len(token) >= 4 or any(char.isdigit() for char in token):
            terms.add(token)
    return terms


def evidence_match(claim_text: str, excerpts: list[str]) -> dict:
    """Share of the claim's key terms that occur in its cited excerpts."""
    terms = _terms(claim_text)
    if len(terms) < MIN_TERMS_FOR_MATCH_CHECK or not excerpts:
        return {"assessed": False, "ratio": None, "missing": [], "weak": False}
    evidence_tokens = set(re.findall(r"[a-z0-9]+", " ".join(excerpts).casefold()))
    stems = {token[:5] for token in evidence_tokens if len(token) >= 5}
    missing = sorted(
        term
        for term in terms
        if term not in evidence_tokens and not (len(term) >= 5 and term[:5] in stems)
    )
    ratio = 1 - len(missing) / len(terms)
    return {
        "assessed": True,
        "ratio": ratio,
        "missing": missing,
        "weak": ratio < WEAK_MATCH_THRESHOLD,
    }


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def _reason(claim, sources: list[str], conflicts: list[dict]) -> str:
    status = claim["trust_status"]
    if not claim["validated_at"]:
        return "Not validated yet. Run validation to check this claim's evidence links."
    if status == "MISSING_EVIDENCE" or not sources:
        return "No readable evidence is linked to this claim, so it cannot be checked."
    open_conflicts = [
        item for item in conflicts
        if item["status"] != "CORROBORATED" and item["resolution"] == "UNRESOLVED"
    ]
    if status == "CONFLICTING" or open_conflicts:
        other = ", ".join(sorted({name for item in open_conflicts for name in item["other_sources"]}))
        return (
            "Another claim gives a different value for the same subject"
            + (f" ({other})" if other else "")
            + ". Decide which is right before relying on this."
        )
    if status == "VERIFIED":
        agreeing = sorted({
            name for item in conflicts if item["status"] == "CORROBORATED"
            for name in item["other_sources"]
        })
        return (
            "Corroborated: "
            + (", ".join(agreeing) if agreeing else "a second source")
            + " states the same value."
        )
    if len(sources) == 1:
        return f"Single source: only {sources[0]} supports this, and nothing else confirms it yet."
    return (
        f"Cited by {len(sources)} sources, but no matching statement was compared, "
        "so agreement has not been checked."
    )


def get_claim_insights(role: str, project_id: str) -> dict[str, dict]:
    """Map claim_id to its evidence, conflicts, gaps, evidence match, and reason."""
    require_role(role, "inspect claim verification")
    conn = get_connection()
    try:
        claims = conn.execute(
            """
            SELECT claim_id, claim_text, claim_type, trust_status, review_status, validated_at
            FROM claims WHERE project_id = ?
            """,
            (project_id,),
        ).fetchall()
        evidence_by_claim: dict[str, list[dict]] = {}
        for row in conn.execute(
            """
            SELECT ce.claim_id, e.evidence_id, e.excerpt, e.reference_location,
                   s.file_name, s.sensitivity, s.source_type
            FROM claim_evidence ce
            JOIN evidence_chunks e ON e.evidence_id = ce.evidence_id
            JOIN sources s ON s.source_id = e.source_id
            WHERE s.project_id = ?
            ORDER BY s.file_name, e.chunk_index
            """,
            (project_id,),
        ):
            evidence_by_claim.setdefault(row["claim_id"], []).append(dict(row))

        def source_names(claim_id: str) -> list[str]:
            return sorted({item["file_name"] for item in evidence_by_claim.get(claim_id, [])})

        conflicts_by_claim: dict[str, list[dict]] = {}
        for row in conn.execute(
            """
            SELECT cf.claim_a, cf.claim_b, cf.status, cf.resolution, cf.attribute,
                   a.claim_text AS text_a, b.claim_text AS text_b
            FROM claim_conflicts cf
            JOIN claims a ON a.claim_id = cf.claim_a
            JOIN claims b ON b.claim_id = cf.claim_b
            WHERE cf.project_id = ?
              AND cf.status IN ('CONFLICTING', 'POSSIBLE_CONFLICT', 'CORROBORATED')
            """,
            (project_id,),
        ):
            for own, other, other_text in (
                (row["claim_a"], row["claim_b"], row["text_b"]),
                (row["claim_b"], row["claim_a"], row["text_a"]),
            ):
                conflicts_by_claim.setdefault(own, []).append(
                    {
                        "other_claim_id": other,
                        "other_text": other_text,
                        "other_sources": source_names(other),
                        "status": row["status"],
                        "resolution": row["resolution"],
                        "attribute": row["attribute"],
                    }
                )
        gaps_by_claim: dict[str, list[str]] = {}
        for row in conn.execute(
            """
            SELECT related_claim_id, gap_type FROM gaps
            WHERE project_id = ? AND status = 'open' AND related_claim_id IS NOT NULL
            """,
            (project_id,),
        ):
            gaps_by_claim.setdefault(row["related_claim_id"], []).append(row["gap_type"])
    finally:
        conn.close()

    insights: dict[str, dict] = {}
    for claim in claims:
        claim_id = claim["claim_id"]
        evidence = evidence_by_claim.get(claim_id, [])
        sources = source_names(claim_id)
        conflicts = conflicts_by_claim.get(claim_id, [])
        match = evidence_match(claim["claim_text"], [item["excerpt"] for item in evidence])
        open_conflicts = [
            item for item in conflicts
            if item["status"] != "CORROBORATED" and item["resolution"] == "UNRESOLVED"
        ]
        flags: list[tuple[str, str]] = []
        if not claim["validated_at"]:
            flags.append(("warning", "Not validated"))
        if not evidence:
            flags.append(("danger", "No evidence linked"))
        if open_conflicts:
            flags.append(("conflict", "Unresolved conflict"))
        if match["weak"]:
            flags.append(("warning", "Weak evidence match"))
        for gap_type in gaps_by_claim.get(claim_id, []):
            label = _GAP_LABELS.get(gap_type)
            if label:
                flags.append(("warning", label))
        insights[claim_id] = {
            "evidence": evidence,
            "sources": sources,
            "conflicts": conflicts,
            "open_conflicts": open_conflicts,
            "gaps": gaps_by_claim.get(claim_id, []),
            "match": match,
            "reason": _reason(claim, sources, conflicts),
            "flags": flags,
            "attention": bool(flags),
        }
    return insights


def summarize_insights(claims: list, insights: dict[str, dict]) -> dict:
    """Counts for the verification report."""
    summary = {
        "total": len(claims),
        "VERIFIED": 0,
        "SINGLE_SOURCE": 0,
        "CONFLICTING": 0,
        "MISSING_EVIDENCE": 0,
        "weak_match": 0,
        "attention": 0,
        "unvalidated": 0,
        "last_validated": None,
    }
    for claim in claims:
        info = insights.get(claim["claim_id"])
        summary[claim["trust_status"]] = summary.get(claim["trust_status"], 0) + 1
        if not claim["validated_at"]:
            summary["unvalidated"] += 1
        elif summary["last_validated"] is None or claim["validated_at"] > summary["last_validated"]:
            summary["last_validated"] = claim["validated_at"]
        if info:
            summary["weak_match"] += bool(info["match"]["weak"])
            summary["attention"] += bool(info["attention"])
    return summary
