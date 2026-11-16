"""Guided walkthrough for judges and first-time visitors.

Each step names the role to use, the page to open, what to do, and how to tell
it worked. Completion is read from stored workspace data, so the tour reflects
what actually happened rather than what the visitor clicked.
"""
from __future__ import annotations

from database import get_connection

REVIEW = "pages/2_Review_Claims.py"
UPLOAD = "pages/1_Upload_Sources.py"
INTERVIEW = "pages/4_Exit_Interview.py"
HANDOVER = "pages/3_Handover_View.py"


def get_tour_state(project_id: str) -> dict[str, int]:
    """Counts that decide which tour steps are complete for one workspace."""
    conn = get_connection()
    try:
        def scalar(sql: str) -> int:
            return conn.execute(sql, (project_id,)).fetchone()[0]

        return {
            "sources": scalar("SELECT COUNT(*) FROM sources WHERE project_id = ?"),
            "evidence": scalar(
                """
                SELECT COUNT(*) FROM evidence_chunks e
                JOIN sources s ON s.source_id = e.source_id WHERE s.project_id = ?
                """
            ),
            "claims": scalar("SELECT COUNT(*) FROM claims WHERE project_id = ?"),
            "unvalidated": scalar(
                "SELECT COUNT(*) FROM claims WHERE project_id = ? AND validated_at IS NULL"
            ),
            "conflicts": scalar(
                """
                SELECT COUNT(*) FROM claim_conflicts
                WHERE project_id = ? AND status IN ('CONFLICTING', 'POSSIBLE_CONFLICT')
                """
            ),
            "resolved_conflicts": scalar(
                """
                SELECT COUNT(*) FROM claim_conflicts
                WHERE project_id = ? AND resolution <> 'UNRESOLVED'
                  AND status IN ('CONFLICTING', 'POSSIBLE_CONFLICT')
                """
            ),
            "approved": scalar(
                "SELECT COUNT(*) FROM claims WHERE project_id = ? AND review_status = 'APPROVED'"
            ),
            "edited": scalar(
                """
                SELECT COUNT(DISTINCT v.claim_id) FROM claim_versions v
                JOIN claims c ON c.claim_id = v.claim_id WHERE c.project_id = ?
                """
            ),
            "questions_sent": scalar(
                """
                SELECT COUNT(*) FROM questions q JOIN gaps g ON g.id = q.gap_id
                WHERE g.project_id = ? AND q.status IN ('SENT', 'ANSWERED')
                """
            ),
            "answers": scalar(
                """
                SELECT COUNT(*) FROM answers a
                JOIN questions q ON q.id = a.question_id
                JOIN gaps g ON g.id = q.gap_id WHERE g.project_id = ?
                """
            ),
            "answer_claims_approved": scalar(
                """
                SELECT COUNT(DISTINCT c.claim_id) FROM claims c
                JOIN claim_evidence ce ON ce.claim_id = c.claim_id
                JOIN evidence_chunks e ON e.evidence_id = ce.evidence_id
                JOIN sources s ON s.source_id = e.source_id
                WHERE c.project_id = ? AND s.source_type = 'interview'
                  AND c.review_status = 'APPROVED'
                """
            ),
            "releases": scalar("SELECT COUNT(*) FROM handover_versions WHERE project_id = ?"),
            "acknowledged": scalar(
                """
                SELECT COUNT(*) FROM handover_acks a
                JOIN handover_versions v ON v.id = a.handover_version_id
                WHERE v.project_id = ?
                """
            ),
        }
    finally:
        conn.close()


# key, role, page, improvement label, title, what to do, what you should see, done(state), optional
TOUR_STEPS = (
    (
        "connect", "Reviewer", UPLOAD, "Core", "Connect the project sources",
        "Open Connect sources. The packaged project has meeting notes, chat, a repository "
        "export, tasks, and one restricted file. You can also upload your own .txt, .md, or "
        ".csv files in a separate workspace.",
        "Eight sources and 17 evidence excerpts, each tagged Public or Restricted.",
        lambda s: s["sources"] > 0 and s["evidence"] > 0,
        False,
    ),
    (
        "verify", "Reviewer", REVIEW, "Improvement 1", "Verify the claims against their evidence",
        "Open Extract and review claims. In step 2 click “Validate evidence links”. Look at "
        "the verification report: corroborated, single-source, conflicting, and weak "
        "evidence-match counts.",
        "Every claim has a plain-language reason for its trust level and a quoted excerpt.",
        lambda s: s["claims"] > 0 and s["unvalidated"] == 0,
        False,
    ),
    (
        "conflicts", "Reviewer", REVIEW, "Improvement 1", "Resolve a conflict",
        "Open “Conflicts and gaps”. Compare Version A and Version B with their citations, then "
        "choose Keep A, Keep B, or Keep both. The choice is saved to the audit log.",
        "Three deliberate disagreements: owner, release date, and retry policy.",
        lambda s: s["resolved_conflicts"] > 0,
        False,
    ),
    (
        "approve", "Reviewer", REVIEW, "Core", "Approve claims after checking the evidence",
        "In step 3 approve a few claims. Approve only after reading the quoted evidence. "
        "Reject one to see the confirmation step.",
        "Approved claims leave the “Needs review” view and become eligible for handover.",
        lambda s: s["approved"] > 0,
        False,
    ),
    (
        "edit", "Reviewer", REVIEW, "Improvement 3", "Edit a claim and see its history (optional)",
        "Open “Edit, history and details” on a claim, change the wording, and give a reason. "
        "The old text is kept in History and the claim returns to pending review.",
        "An append-only version list showing who changed what and why.",
        lambda s: s["edited"] > 0,
        True,
    ),
    (
        "questions", "Reviewer", INTERVIEW, "Improvement 2", "Turn gaps into interview questions",
        "Open Exit interview. Generate questions from open gaps, edit one, then send the drafts "
        "to the departing teammate.",
        "A short editable question list, each tied to a gap such as “task has no owner”.",
        lambda s: s["questions_sent"] > 0,
        False,
    ),
    (
        "answer", "Departing", INTERVIEW, "Improvement 2", "Answer as the departing teammate",
        "Switch to the Departing role. Answer one question and choose its visibility. "
        "Departing sees only the questions assigned to them.",
        "The answer is saved as interview evidence with author and timestamp and becomes a "
        "pending claim.",
        lambda s: s["answers"] > 0,
        False,
    ),
    (
        "approve_answer", "Reviewer", REVIEW, "Improvement 2", "Review the answer like any other claim",
        "Back as Reviewer, approve the claim created from the answer. Interview answers go "
        "through the same review as every other claim.",
        "Approving it closes the gap it answered.",
        lambda s: s["answer_claims_approved"] > 0,
        False,
    ),
    (
        "release", "Reviewer", HANDOVER, "Improvement 3", "Release a fixed handover version",
        "Open Release and handover. Read what the release includes and excludes, then confirm. "
        "Claims that rely on a restricted source are left out.",
        "Version 1, a snapshot that later edits cannot change.",
        lambda s: s["releases"] > 0,
        False,
    ),
    (
        "incoming", "Incoming", HANDOVER, "Improvement 3", "Pick up the work as the incoming teammate",
        "Switch to Incoming. Read “Where to pick up” (Day 1, Week 1, Month 1), open a claim's "
        "source evidence, and confirm the restricted file never appears. Then acknowledge the "
        "version you received.",
        "Your acknowledgement is recorded against that exact version.",
        lambda s: s["acknowledged"] > 0,
        False,
    ),
)


def build_tour(state: dict[str, int]) -> dict:
    """Steps with completion flags, the current step, and overall progress."""
    steps = []
    for key, role, page, tag, title, todo, expect, done_check, optional in TOUR_STEPS:
        steps.append(
            {
                "key": key,
                "role": role,
                "page": page,
                "tag": tag,
                "title": title,
                "todo": todo,
                "expect": expect,
                "done": bool(done_check(state)),
                "optional": optional,
            }
        )
    current = next((step for step in steps if not step["done"] and not step["optional"]), None)
    required = [step for step in steps if not step["optional"]]
    return {
        "steps": steps,
        "current": current["key"] if current else None,
        "done_required": sum(step["done"] for step in required),
        "total_required": len(required),
        "complete": current is None,
    }
