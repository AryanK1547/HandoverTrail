"""Rule-based "where to start" plan for an incoming teammate.

The plan reorders and groups the claims a reviewer already approved and
released. It adds no facts: each step quotes a released claim and cites the
source it came from. Ordering follows claim type, not a project schedule.
"""
from __future__ import annotations

MAX_STEPS_PER_HORIZON = 4
MAX_FOCUS_SOURCES = 4

HORIZONS = (
    ("Day 1", "Things that can stop work or fail soon."),
    ("Week 1", "Work already queued and the people to ask."),
    ("Month 1", "Open questions and dependencies to settle."),
)

# (claim type, verb shown before the claim, horizon, why it is in that horizon).
# The buckets are fixed rules from claim type, not estimates of effort or dates.
_STEP_RULES = (
    ("Blocker", "Unblock", "Day 1", "Work cannot continue until this is resolved."),
    ("Risk", "Watch", "Day 1", "Known way this work can fail."),
    ("Next action", "Do next", "Week 1", "Work the previous owner had queued."),
    ("Owner", "Ask the owner", "Week 1", "The person who knows this area best."),
    ("Open question", "Find the answer", "Month 1", "Nobody has settled this yet."),
    ("Dependency", "Check the dependency", "Month 1", "Something this work relies on."),
)
_CONFLICT_RULE = (
    "Settle which is right", "Day 1", "Another released claim gives a different value."
)

TOPIC_SECTIONS = (
    ("Start here", "Work in flight. Pick these up first.", ("Blocker", "Next action")),
    ("Know the risks", "Open risks and unanswered questions.", ("Risk", "Open question")),
    ("Who owns what", "Ask these people before changing the related area.", ("Owner",)),
    (
        "Decisions already made",
        "Treat as settled unless new evidence contradicts them.",
        ("Decision",),
    ),
    ("What you depend on", "Systems and teams this work relies on.", ("Dependency",)),
)


def _citation(claim: dict) -> str:
    evidence = claim.get("evidence") or []
    if not evidence:
        return "No citation available"
    first = evidence[0].get("reference_location") or evidence[0].get("file_name")
    extra = len(evidence) - 1
    return f"{first} (+{extra} more)" if extra > 0 else str(first)


def _needs_confirmation(claim: dict) -> str | None:
    status = claim.get("trust_status")
    if status == "CONFLICTING":
        return "Confirm the right value with the people involved before acting."
    if status == "SINGLE_SOURCE":
        return "Only one source supports this. Confirm before acting."
    if status == "MISSING_EVIDENCE":
        return "No evidence was linked. Confirm before acting."
    return None


def build_pickup_plan(claims: list[dict]) -> dict:
    """Return ordered first steps, files to open first, and claims grouped by topic."""
    horizon_steps: dict[str, list[dict]] = {name: [] for name, _ in HORIZONS}
    seen: set[str] = set()

    def add(claim: dict, verb: str, horizon: str, why: str) -> None:
        bucket = horizon_steps[horizon]
        if claim["claim_id"] in seen or len(bucket) >= MAX_STEPS_PER_HORIZON:
            return
        seen.add(claim["claim_id"])
        bucket.append(
            {
                "claim_id": claim["claim_id"],
                "verb": verb,
                "horizon": horizon,
                "text": claim["claim_text"],
                "why": why,
                "source": _citation(claim),
                "confirm": _needs_confirmation(claim),
                "claim_type": claim["claim_type"],
            }
        )

    # Blockers first, then claims whose sources disagree, then the rest of the rules.
    for claim in claims:
        if claim["claim_type"] == "Blocker":
            add(claim, "Unblock", "Day 1", _STEP_RULES[0][3])
    for claim in claims:
        if claim.get("trust_status") == "CONFLICTING":
            add(claim, *_CONFLICT_RULE)
    for claim_type, verb, horizon, why in _STEP_RULES[1:]:
        for claim in claims:
            if claim["claim_type"] == claim_type:
                add(claim, verb, horizon, why)
    steps = [step for name, _ in HORIZONS for step in horizon_steps[name]]

    source_counts: dict[str, int] = {}
    for claim in claims:
        for name in {
            item.get("file_name") for item in claim.get("evidence") or [] if item.get("file_name")
        }:
            source_counts[name] = source_counts.get(name, 0) + 1
    focus_sources = sorted(source_counts.items(), key=lambda item: (-item[1], item[0]))[
        :MAX_FOCUS_SOURCES
    ]

    topics = []
    for title, guidance, claim_types in TOPIC_SECTIONS:
        members = [claim for claim in claims if claim["claim_type"] in claim_types]
        if members:
            topics.append({"title": title, "guidance": guidance, "claims": members})

    return {
        "steps": steps,
        "horizons": [
            {"name": name, "guidance": guidance, "steps": horizon_steps[name]}
            for name, guidance in HORIZONS
            if horizon_steps[name]
        ],
        "focus_sources": focus_sources,
        "topics": topics,
        "needs_confirmation": sum(1 for claim in claims if _needs_confirmation(claim)),
        "total": len(claims),
    }
