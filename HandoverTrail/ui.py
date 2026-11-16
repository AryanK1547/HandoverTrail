from __future__ import annotations

import functools
import html
import json
import os
import subprocess

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from database import DEMO_PROJECT_ID, PROJECT_ROOT, get_connection
from handover_release import get_release_readiness
from permissions import normalize_role
from retrieval import (
    count_hidden_claims,
    get_visible_claims,
    get_visible_evidence_chunks,
    get_visible_sources,
)
from ui_helpers import render_role_selector
from workspace import get_active_project_id

COLORS = {
    "bg": "#0B1220",
    "surface": "#111B2E",
    "surface_2": "#18243B",
    "border": "#27344D",
    "text": "#E6EBF5",
    "muted": "#9AA7BF",
    "primary": "#5558D9",
    "primary_text": "#A5B4FC",
    "success": "#34D399",
    "warning": "#FBBF24",
    "danger": "#F87171",
    "conflict": "#FB923C",
    "restricted": "#C4B5FD",
    "public": "#7DD3FC",
}

_TEXT_COLORS = (
    "text",
    "muted",
    "primary_text",
    "success",
    "warning",
    "danger",
    "conflict",
    "restricted",
    "public",
)
_BACKGROUND_COLORS = ("bg", "surface", "surface_2")
TEXT_BACKGROUND_PAIRS = tuple(
    (foreground, background)
    for foreground in _TEXT_COLORS
    for background in _BACKGROUND_COLORS
) + (("text", "primary"),)

_BADGE_VARIANTS = {
    "neutral": "•",
    "primary": "●",
    "success": "✓",
    "warning": "!",
    "danger": "×",
    "conflict": "↔",
    "restricted": "◈",
    "public": "○",
}

_ROLE_DESCRIPTIONS = {
    "Admin": "Can inspect sources and manage claims for the selected workspace.",
    "Reviewer": "Can inspect evidence and approve or reject claims.",
    "Incoming": "Can read the latest reviewer-released handover only.",
    "Departing": "Can answer only interview questions assigned to the demo leaver.",
}

_REVIEW_ROLES = frozenset({"Admin", "Reviewer"})
# Sidebar navigation in workflow order: (page, label, roles allowed to use it).
_NAVIGATION = (
    ("app.py", "Overview", frozenset({"Admin", "Reviewer", "Incoming", "Departing"})),
    (
        "pages/0_Guided_Tour.py",
        "Guided tour",
        frozenset({"Admin", "Reviewer", "Incoming", "Departing"}),
    ),
    ("pages/1_Upload_Sources.py", "1 · Connect sources", _REVIEW_ROLES),
    ("pages/2_Review_Claims.py", "2 · Extract and review claims", _REVIEW_ROLES),
    ("pages/4_Exit_Interview.py", "3 · Exit interview", _REVIEW_ROLES | {"Departing"}),
    ("pages/3_Handover_View.py", "4 · Release and handover", _REVIEW_ROLES | {"Incoming"}),
)

_WORKFLOW = (
    ("Connect", "pages/1_Upload_Sources.py"),
    ("Reconstruct", "pages/2_Review_Claims.py"),
    ("Verify", "pages/2_Review_Claims.py"),
    ("Review", "pages/2_Review_Claims.py"),
    ("Interview", "pages/4_Exit_Interview.py"),
    ("Handover", "pages/3_Handover_View.py"),
)


_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --ht-bg: #0B1220;
  --ht-surface: #111B2E;
  --ht-surface-2: #18243B;
  --ht-border: #27344D;
  --ht-text: #E6EBF5;
  --ht-muted: #9AA7BF;
  --ht-primary: #5558D9;
  --ht-primary-text: #A5B4FC;
}

html, body, button, input, textarea {
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
}

h1, h2, h3 { letter-spacing: -0.025em; }
p, li, label { line-height: 1.55; }

.ht-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  border: 1px solid var(--ht-border);
  border-left-width: 3px;
  border-radius: 999px;
  padding: 0.22rem 0.65rem;
  color: var(--ht-text);
  background: var(--ht-surface);
  font-size: 0.82rem;
  font-weight: 600;
  line-height: 1.3;
}
.ht-badge__icon { font-weight: 700; }
.ht-badge--neutral { border-left-color: var(--ht-muted); }
.ht-badge--primary { border-left-color: var(--ht-primary); }
.ht-badge--success { border-left-color: #34D399; }
.ht-badge--warning { border-left-color: #FBBF24; }
.ht-badge--danger { border-left-color: #F87171; }
.ht-badge--conflict { border-left-color: #FB923C; }
.ht-badge--restricted { border-left-color: #C4B5FD; }
.ht-badge--public { border-left-color: #7DD3FC; }

.ht-claim-type {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ht-primary-text, #A5B4FC);
  margin-bottom: 0.15rem;
}
.ht-claim-text {
  font-size: 1.2rem;
  font-weight: 600;
  line-height: 1.4;
  color: var(--ht-text);
  margin: 0.2rem 0 0.5rem 0;
  overflow-wrap: anywhere;
}
.ht-why { color: var(--ht-muted); font-size: 0.9rem; margin: 0.35rem 0 0.6rem 0; }
.ht-quote {
  border-left: 3px solid var(--ht-border);
  background: var(--ht-surface);
  border-radius: 0 8px 8px 0;
  padding: 0.55rem 0.8rem;
  margin: 0.4rem 0;
  overflow-wrap: anywhere;
}
.ht-quote__source { color: var(--ht-muted); font-size: 0.78rem; margin-bottom: 0.2rem; }
.ht-quote__text { color: var(--ht-text); font-size: 0.92rem; white-space: pre-wrap; }
.ht-step { display: flex; gap: 0.75rem; align-items: flex-start; margin: 0.2rem 0 0.7rem 0; }
.ht-step__num {
  flex: 0 0 1.9rem; height: 1.9rem; border-radius: 999px; background: var(--ht-primary);
  color: #fff; font-weight: 700; display: flex; align-items: center; justify-content: center;
}
.ht-step__body { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.ht-step__verb { color: var(--ht-primary-text, #A5B4FC); font-weight: 700; font-size: 0.8rem;
  text-transform: uppercase; letter-spacing: 0.06em; }

[data-testid="stAlert"] { border-radius: 10px; }
[data-testid="stExpander"] { border-color: var(--ht-border); border-radius: 10px; }
[data-testid="stMetric"] { min-width: 0; }
[data-testid="stMetricValue"] { overflow-wrap: anywhere; }
[data-testid="stPageLink"] a, [data-testid="stLinkButton"] a {
  border-radius: 8px;
  font-size: 0.78rem;
  padding-left: 0.35rem;
  padding-right: 0.35rem;
  white-space: normal;
}
.st-key-workflow-step-current [data-testid="stPageLink"] a {
  border: 1px solid var(--ht-primary);
  background: #18243B;
  font-weight: 700;
}
button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible,
[role="button"]:focus-visible {
  outline: 3px solid #A5B4FC !important;
  outline-offset: 3px !important;
  box-shadow: none !important;
}
.stButton > button { border-radius: 8px; font-weight: 600; min-height: 2.65rem; }
[data-testid="stPageLink"] { min-height: 2.5rem; }

.st-key-workflow-rail-mobile { display: none; }
@media (max-width: 640px) {
  .st-key-workflow-rail-desktop { display: none; }
  .st-key-workflow-rail-mobile { display: block; }
  [data-testid="stHorizontalBlock"] { gap: 0.5rem; }
  .stButton > button { min-height: 2.8rem; }
  [data-testid="stAppViewContainer"] section.main > div { padding-left: 1rem; padding-right: 1rem; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; transition-duration: 0.01ms !important; }
}
"""


def configure_page(title: str, icon: str = "H", layout: str = "wide") -> None:
    st.set_page_config(page_title=title, page_icon=icon, layout=layout)


def apply_theme() -> None:
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)


def _dashboard_counts(role: str) -> dict[str, int]:
    project_id = get_active_project_id()
    sources = get_visible_sources(role, project_id)
    evidence = get_visible_evidence_chunks(role, project_id)
    claims = get_visible_claims(role, project_id)
    source_count_override = None
    evidence_count_override = None
    question_status = {"DRAFT": 0, "SENT": 0, "ANSWERED": 0}
    readiness = None
    open_gaps = 0
    if normalize_role(role) in {"Admin", "Reviewer", "Departing"}:
        conn = get_connection()
        try:
            for row in conn.execute(
                """
                SELECT q.status, COUNT(*) AS total FROM questions q
                JOIN gaps g ON g.id = q.gap_id
                WHERE g.project_id = ? AND q.assigned_user_id = 'USR-DEMO-DEPARTING'
                GROUP BY q.status
                """,
                (project_id,),
            ):
                question_status[row["status"]] = row["total"]
        finally:
            conn.close()
    if normalize_role(role) in {"Admin", "Reviewer"}:
        readiness = get_release_readiness(role, project_id)
        open_gaps = readiness["open_gaps"]
        interview_questions = question_status["DRAFT"] + question_status["SENT"]
    elif normalize_role(role) == "Departing":
        interview_questions = question_status["SENT"]
    else:
        interview_questions = 0
    released_claims = None
    if normalize_role(role) == "Incoming":
        conn = get_connection()
        try:
            release = conn.execute(
                """
                SELECT snapshot_json FROM handover_versions
                WHERE project_id = ? ORDER BY version DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            if release:
                snapshot_claims = json.loads(release["snapshot_json"]).get("claims", [])
                released_claims = len(snapshot_claims)
                released_sources = {
                    evidence["file_name"]
                    for claim in snapshot_claims
                    for evidence in claim.get("evidence", [])
                    if evidence.get("file_name")
                }
                released_evidence = {
                    evidence["evidence_id"]
                    for claim in snapshot_claims
                    for evidence in claim.get("evidence", [])
                }
                source_count_override = len(released_sources)
                evidence_count_override = len(released_evidence)
            else:
                released_claims = 0
                source_count_override = 0
                evidence_count_override = 0
        finally:
            conn.close()
        claims = []
    return {
        "sources": source_count_override if source_count_override is not None else len(sources),
        "public_sources": (
            0 if source_count_override is not None else
            sum(row["sensitivity"] == "public" for row in sources)
        ),
        "restricted_sources": (
            0 if source_count_override is not None else
            sum(row["sensitivity"] == "restricted" for row in sources)
        ),
        "evidence": evidence_count_override if evidence_count_override is not None else len(evidence),
        "claims": len(claims),
        "pending": sum(row["review_status"] == "PENDING" for row in claims),
        "approved": (
            released_claims
            if released_claims is not None
            else sum(row["review_status"] == "APPROVED" for row in claims)
        ),
        "hidden": 0 if normalize_role(role) == "Incoming" else count_hidden_claims(role, project_id),
        "open_gaps": open_gaps,
        "interview_questions": interview_questions,
        "unvalidated": sum(not row["validated_at"] for row in claims),
        "released": released_claims is not None and released_claims > 0,
        "draft_questions": question_status["DRAFT"],
        "sent_questions": question_status["SENT"],
        "answered_questions": question_status["ANSWERED"],
        "releasable": readiness["releasable"] if readiness else 0,
        "approved_excluded": readiness["approved_excluded"] if readiness else 0,
        "release_version": readiness["latest_version"] if readiness else 0,
        "release_acknowledged": bool(readiness and readiness["latest_acknowledged"]),
        "release_needed": bool(readiness and readiness["has_unreleased_changes"]),
    }


def _ai_mode() -> str:
    last_method = st.session_state.get("last_extraction_method")
    if last_method:
        return str(last_method)
    if os.environ.get("HANDOVERTRAIL_DISABLE_PROVIDERS", "").casefold() in {"1", "true", "yes"}:
        return "Local rule-based extraction (providers disabled)"
    try:
        gemini_key = st.secrets.get("GEMINI_API_KEY")
        openrouter_key = st.secrets.get("OPENROUTER_API_KEY")
    except StreamlitSecretNotFoundError:
        gemini_key = openrouter_key = None
    if gemini_key:
        return "Live Gemini available"
    if openrouter_key:
        return "OpenRouter fallback available"
    return "Local fallback; cached claims available"


def sidebar_identity() -> str:
    role = render_role_selector()
    role = st.session_state.get("user_role", role or "Admin")
    project_id = get_active_project_id()
    with st.sidebar:
        if project_id == DEMO_PROJECT_ID:
            st.markdown("### Synthetic demo")
            st.caption("Demo Project · Team Techtones")
        else:
            st.markdown("### Upload workspace")
            st.caption(f"Workspace {project_id[-6:]}")
        st.markdown(badge_html(role, variant="primary"), unsafe_allow_html=True)
        st.caption(_ROLE_DESCRIPTIONS.get(role, "Demo role."))
        if project_id == DEMO_PROJECT_ID:
            st.caption("Shared synthetic project · uploads go to a separate workspace")
        else:
            st.caption("Separate from demo data · workspace follows this URL")
        st.caption(f"AI mode · {_ai_mode()}")
        st.divider()
        sidebar_navigation(role)
    return role


def sidebar_navigation(role: str) -> None:
    """Role-aware page links that keep the workspace and role in the URL."""
    normalized_role = normalize_role(role)
    query_params = dict(st.query_params)
    st.markdown("**Pages**")
    for page, label, allowed_roles in _NAVIGATION:
        if normalized_role in allowed_roles:
            st.page_link(page, label=label, query_params=query_params)
    if normalized_role not in _REVIEW_ROLES:
        st.caption("Other workflow pages are available to Admin and Reviewer.")


def _rail_labels(counts: dict[str, int]) -> tuple[str, ...]:
    return (
        f"{counts['sources']} sources",
        f"{counts['evidence']} excerpts",
        f"{counts['claims']} claims",
        f"{counts['open_gaps']} open gaps",
        f"{counts['interview_questions']} interview questions",
        f"{counts['approved']} approved",
    )


def workflow_rail(current_step: int, counts: dict[str, int], role: str) -> None:
    normalized_role = normalize_role(role)
    if normalized_role == "Incoming":
        visible_steps = (("Handover", "pages/3_Handover_View.py"),)
        labels = (f"{counts['approved']} released claims",)
    elif normalized_role == "Departing":
        visible_steps = (("Interview", "pages/4_Exit_Interview.py"),)
        labels = (f"{counts['interview_questions']} assigned questions",)
    else:
        visible_steps = _WORKFLOW
        labels = _rail_labels(counts)
    query_params = dict(st.query_params)
    with st.container(key="workflow-rail-desktop"):
        columns = st.columns(len(visible_steps))
        if current_step == 0:
            current_visible_step = 0  # the guided tour is not a workflow stage
        else:
            current_visible_step = (
                1 if normalized_role in {"Incoming", "Departing"} else current_step
            )
        for index, (column, (name, page), count) in enumerate(
            zip(columns, visible_steps, labels),
            start=1,
        ):
            with column:
                key = (
                    "workflow-step-current"
                    if index == current_visible_step
                    else f"workflow-step-{index}"
                )
                with st.container(key=key):
                    st.page_link(page, label=name, query_params=query_params)
                    st.caption(count)
    with st.container(key="workflow-rail-mobile"):
        if current_step == 0:
            st.caption("Guided tour")
            return
        if normalized_role == "Incoming":
            label = "Handover"
            step = 1
            total = 1
        elif normalized_role == "Departing":
            label = "Interview"
            step = 1
            total = 1
        else:
            label = _WORKFLOW[current_step - 1][0]
            step = current_step
            total = len(_WORKFLOW)
        st.caption(f"Step {step} of {total} · {label}")


def next_step(counts: dict[str, int], role: str) -> dict:
    """Derive the single most useful next action from stored workspace state.

    Returns ``kind`` (info/success/warning), ``message``, a ``primary``
    ``(label, page)`` link, and an optional ``secondary`` link.
    """
    upload_page = "pages/1_Upload_Sources.py"
    review_page = "pages/2_Review_Claims.py"
    interview_page = "pages/4_Exit_Interview.py"
    handover_page = "pages/3_Handover_View.py"
    normalized_role = normalize_role(role)

    def step(kind: str, message: str, primary, secondary=None) -> dict:
        return {"kind": kind, "message": message, "primary": primary, "secondary": secondary}

    if normalized_role == "Incoming":
        if counts["released"]:
            return step(
                "success",
                f"The latest reviewer-released snapshot contains {counts['approved']} claims.",
                ("Open released handover", handover_page),
            )
        return step(
            "info",
            "No handover has been released yet. Ask a Reviewer to publish one.",
            ("Open released handover", handover_page),
        )
    if normalized_role == "Departing":
        if counts["interview_questions"]:
            message = (
                f"{counts['interview_questions']} question(s) are waiting for your answer."
            )
        elif counts["answered_questions"]:
            message = (
                "You have answered every question sent to you. "
                "A Reviewer will check your answers."
            )
        else:
            message = "No questions have been sent to you yet. A Reviewer prepares them first."
        return step("info", message, ("Open your exit interview", interview_page))

    release_link = (
        ("Release handover", handover_page) if counts["release_needed"] else None
    )
    if counts["sources"] == 0:
        return step(
            "info",
            "No sources are available in this workspace.",
            ("Connect sources", upload_page),
        )
    if counts["evidence"] == 0:
        return step(
            "info",
            f"{counts['sources']} sources are ready to parse.",
            ("Parse sources", upload_page),
        )
    if counts["claims"] == 0:
        return step(
            "info",
            f"{counts['evidence']} evidence excerpts are ready for extraction.",
            ("Extract claims", review_page),
        )
    if counts["unvalidated"]:
        return step(
            "info",
            f"{counts['unvalidated']} claims still need evidence validation.",
            ("Validate claims", review_page),
        )
    if counts["pending"]:
        message = f"{counts['pending']} claims are waiting for human review."
        if release_link:
            message += (
                f" {counts['releasable']} approved claim(s) can already be released."
            )
        return step("info", message, ("Review claims", review_page), release_link)
    if counts["draft_questions"]:
        return step(
            "info",
            f"{counts['draft_questions']} draft interview question(s) are ready to send "
            "to Departing.",
            ("Continue exit interview", interview_page),
            release_link,
        )
    interview_started = (
        counts["draft_questions"] + counts["sent_questions"] + counts["answered_questions"]
    ) > 0
    if counts["open_gaps"] and not interview_started:
        message = (
            f"{counts['open_gaps']} evidence gaps can be turned into exit-interview questions."
        )
        if release_link:
            message += " The interview is optional; approved claims can be released now."
        return step("info", message, ("Prepare exit interview", interview_page), release_link)
    waiting = (
        f" {counts['sent_questions']} interview question(s) are still with Departing."
        if counts["sent_questions"]
        else ""
    )
    if release_link:
        if counts["release_version"]:
            message = (
                f"Approved claims changed since version {counts['release_version']}. "
                f"{counts['releasable']} claim(s) are ready for a new release."
            )
        else:
            message = f"{counts['releasable']} approved claims are ready for a handover release."
        return step("info", message + waiting, release_link)
    interview_link = (
        ("Open exit interview", interview_page) if counts["sent_questions"] else None
    )
    if counts["release_version"]:
        acknowledgement = (
            "Incoming has acknowledged it."
            if counts["release_acknowledged"]
            else "Incoming has not acknowledged it yet; switch the demo role to Incoming to do so."
        )
        return step(
            "success",
            f"Handover version {counts['release_version']} is released and up to date. "
            f"{acknowledgement}{waiting}",
            ("View released handover", handover_page),
            interview_link,
        )
    if interview_link:
        return step(
            "info",
            f"{counts['sent_questions']} interview question(s) are waiting for Departing. "
            "Switch the demo role to Departing to answer them.",
            interview_link,
        )
    if counts["approved"]:
        return step(
            "warning",
            f"{counts['approved']} approved claim(s) rely on restricted sources or lack "
            "evidence, so nothing can be released to Incoming yet.",
            ("Review claims", review_page),
        )
    return step(
        "info",
        "No claims are approved yet. Approve claims before releasing a handover.",
        ("Review claims", review_page),
    )


def next_step_banner(counts: dict[str, int], role: str) -> None:
    query_params = dict(st.query_params)
    guidance = next_step(counts, role)
    {"success": st.success, "warning": st.warning}.get(guidance["kind"], st.info)(
        guidance["message"]
    )
    links = [link for link in (guidance["primary"], guidance["secondary"]) if link]
    for column, (label, page) in zip(st.columns(len(links) + 2), links):
        with column:
            st.page_link(page, label=f"{label} →", query_params=query_params)


def page_shell(
    step: int,
    title: str,
    subtitle: str,
    *,
    auto_stage: bool = False,
) -> tuple[str, dict[str, int]]:
    """Render the shared shell. ``auto_stage`` lets the claims page highlight
    Reconstruct, Verify, or Review according to what the workspace still needs."""
    apply_theme()
    role = sidebar_identity()
    counts = _dashboard_counts(role)
    if auto_stage:
        if counts["claims"] == 0:
            step = 2
        elif counts["unvalidated"]:
            step = 3
        else:
            step = 4
    workflow_rail(step, counts, role)
    st.title(title)
    st.markdown(subtitle)
    st.markdown(f"Current role: {badge_html(role, variant='primary')}", unsafe_allow_html=True)
    next_step_banner(counts, role)
    glossary_popover()
    return role, counts


def claim_headline_html(claim_type: str, text: str) -> str:
    return (
        f'<div class="ht-claim-type">{html.escape(str(claim_type))}</div>'
        f'<div class="ht-claim-text">{html.escape(str(text))}</div>'
    )


def quote_html(source: str, excerpt: str, limit: int | None = 320) -> str:
    """A cited excerpt, escaped and optionally shortened for inline preview."""
    shown = str(excerpt)
    source = str(source)
    if limit and len(shown) > limit:
        shown = shown[:limit].rstrip() + "…"
    return (
        '<div class="ht-quote">'
        f'<div class="ht-quote__source">{html.escape(str(source))}</div>'
        f'<div class="ht-quote__text">{html.escape(shown)}</div></div>'
    )


def step_html(number: int, verb: str, text: str, detail: str) -> str:
    return (
        '<div class="ht-step">'
        f'<div class="ht-step__num" aria-hidden="true">{number}</div>'
        '<div class="ht-step__body">'
        f'<div class="ht-step__verb">{html.escape(verb)}</div>'
        f"<div>{html.escape(text)}</div>"
        f'<div class="ht-why">{html.escape(detail)}</div></div></div>'
    )


def page_navigation(
    previous: tuple[str, str] | None = None,
    following: tuple[tuple[str, str], ...] = (),
) -> None:
    """Back/next links at the foot of a page so the journey never dead-ends."""
    if not previous and not following:
        return
    query_params = dict(st.query_params)
    st.divider()
    columns = st.columns(1 + max(len(following), 1))
    if previous:
        with columns[0]:
            st.page_link(previous[1], label=f"← {previous[0]}", query_params=query_params)
    for column, (label, page) in zip(columns[1:], following):
        with column:
            st.page_link(page, label=f"{label} →", query_params=query_params)


def badge_html(label: object, variant: str = "neutral", icon: str | None = None) -> str:
    safe_variant = variant if variant in _BADGE_VARIANTS else "neutral"
    badge_icon = _BADGE_VARIANTS[safe_variant] if icon is None else icon
    return (
        f'<span class="ht-badge ht-badge--{safe_variant}">'
        f'<span class="ht-badge__icon" aria-hidden="true">{html.escape(str(badge_icon))}</span>'
        f"<span>{html.escape(str(label))}</span></span>"
    )


def trust_badge(status: str) -> str:
    labels = {
        "VERIFIED": ("Corroborated — statements agree", "success"),
        "SINGLE_SOURCE": ("Single source", "warning"),
        "MISSING_EVIDENCE": ("Missing evidence", "danger"),
        "CONFLICTING": ("Conflicting", "conflict"),
    }
    label, variant = labels.get(status, ("Trust status unavailable", "neutral"))
    return badge_html(label, variant)


def review_badge(status: str) -> str:
    labels = {
        "PENDING": ("Pending review", "warning"),
        "APPROVED": ("Approved", "success"),
        "REJECTED": ("Rejected", "danger"),
        "EDITED_PENDING_REVIEW": ("Edited — pending review", "warning"),
    }
    label, variant = labels.get(status, ("Review status unavailable", "neutral"))
    return badge_html(label, variant)


def sensitivity_badge(sensitivity: str) -> str:
    label = sensitivity.title() if sensitivity in {"public", "restricted"} else "Unknown sensitivity"
    variant = sensitivity if sensitivity in {"public", "restricted"} else "neutral"
    return badge_html(label, variant)


def validation_badge(validated_at: str | None) -> str:
    if validated_at:
        return badge_html("Evidence checked", "success")
    return badge_html("Not validated", "warning")


def origin_badge(origin: str) -> str:
    labels = {
        "cached_demo": ("Cached demo", "primary"),
        "generated": ("AI / local extraction", "neutral"),
        "Gemini API": ("AI-extracted · Gemini", "primary"),
        "OpenRouter API": ("AI-extracted · OpenRouter", "primary"),
        "Universal Keyword Fallback": ("Computed · local fallback", "neutral"),
    }
    label, variant = labels.get(origin, (origin, "neutral"))
    return badge_html(label, variant)


def role_badge(role: str) -> str:
    return badge_html(role, "primary")


def empty_state(message: str, detail: str | None = None) -> None:
    st.info(message)
    if detail:
        st.caption(detail)


def stat_row(items: list[tuple[str, int]]) -> None:
    columns = st.columns(len(items))
    for column, (label, value) in zip(columns, items):
        column.metric(label, value)


def glossary_popover() -> None:
    with st.popover("Glossary"):
        st.markdown(
            """
            - **Corroborated:** comparable claim slots agree across different sources after normalization.
            - **Single source:** supported by one file.
            - **Missing evidence:** no readable evidence is linked.
            - **Conflicting:** the same subject and attribute have incompatible values.
            - **Possible conflict:** similar subjects have different values and need a human check.
            - **Public:** visible to the Incoming demo role.
            - **Restricted:** visible only to Admin and Reviewer demo roles.
            """
        )


@functools.lru_cache(maxsize=1)
def _app_version() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            check=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


def footer() -> None:
    version = _app_version()
    st.divider()
    st.caption(
        f"HandoverTrail · {version} · Synthetic demo data only · "
        "[Setup and limitations](README.md)"
    )


def render_stats_for_role(role: str, counts: dict[str, int]) -> None:
    if role == "Incoming":
        stat_row(
            [
                ("Available sources", counts["sources"]),
                ("Released evidence excerpts", counts["evidence"]),
                ("Claims in latest release", counts["approved"]),
            ]
        )
    else:
        stat_row(
            [
                ("Sources", counts["sources"]),
                ("Public", counts["public_sources"]),
                ("Restricted", counts["restricted_sources"]),
                ("Evidence excerpts", counts["evidence"]),
            ]
        )


def latest_extraction_method(method: str) -> None:
    st.session_state["last_extraction_method"] = method


def show_flash_toast() -> None:
    message = st.session_state.pop("ui_flash_toast", None)
    if message:
        st.toast(message)
