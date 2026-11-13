from __future__ import annotations

import html
import subprocess

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from database import PROJECT_ROOT, get_connection
from permissions import normalize_role
from retrieval import (
    count_hidden_claims,
    get_visible_claims,
    get_visible_evidence_chunks,
    get_visible_sources,
)
from ui_helpers import render_role_selector

PROJECT_ID = "PROJ-DEMO-001"

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
    "Admin": "Can inspect all sources and manage demo reviews.",
    "Reviewer": "Can inspect evidence and approve or reject claims.",
    "Incoming": "Can read approved claims supported only by public sources.",
    "Departing": "Can answer only interview questions assigned to the demo leaver.",
}

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
    sources = get_visible_sources(role, PROJECT_ID)
    evidence = get_visible_evidence_chunks(role, PROJECT_ID)
    claims = get_visible_claims(role, PROJECT_ID)
    if normalize_role(role) in {"Admin", "Reviewer"}:
        conn = get_connection()
        try:
            open_gaps = conn.execute(
                "SELECT COUNT(*) FROM gaps WHERE project_id = ? AND status = 'open'",
                (PROJECT_ID,),
            ).fetchone()[0]
            interview_questions = conn.execute(
                """
                SELECT COUNT(*) FROM questions q
                JOIN gaps g ON g.id = q.gap_id
                WHERE g.project_id = ? AND q.status IN ('DRAFT', 'SENT')
                """,
                (PROJECT_ID,),
            ).fetchone()[0]
        finally:
            conn.close()
    elif normalize_role(role) == "Departing":
        conn = get_connection()
        try:
            open_gaps = 0
            interview_questions = conn.execute(
                """
                SELECT COUNT(*) FROM questions
                WHERE assigned_user_id = 'USR-DEMO-DEPARTING' AND status = 'SENT'
                """
            ).fetchone()[0]
        finally:
            conn.close()
    else:
        open_gaps = interview_questions = 0
    return {
        "sources": len(sources),
        "public_sources": sum(row["sensitivity"] == "public" for row in sources),
        "restricted_sources": sum(row["sensitivity"] == "restricted" for row in sources),
        "evidence": len(evidence),
        "claims": len(claims),
        "pending": sum(row["review_status"] == "PENDING" for row in claims),
        "approved": sum(row["review_status"] == "APPROVED" for row in claims),
        "hidden": count_hidden_claims(role, PROJECT_ID),
        "open_gaps": open_gaps,
        "interview_questions": interview_questions,
    }


def _ai_mode() -> str:
    last_method = st.session_state.get("last_extraction_method")
    if last_method:
        return str(last_method)
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
    with st.sidebar:
        st.markdown("### Demo workspace")
        st.caption("Demo Project · Team Techtones")
        st.markdown(badge_html(role, variant="primary"), unsafe_allow_html=True)
        st.caption(_ROLE_DESCRIPTIONS.get(role, "Demo role."))
        st.caption("Data mode · Synthetic demo + local uploads")
        st.caption(f"AI mode · {_ai_mode()}")
    return role


def _rail_labels(counts: dict[str, int]) -> tuple[str, ...]:
    return (
        f"{counts['sources']} sources",
        f"{counts['evidence']} excerpts",
        f"{counts['claims']} claims",
        f"{counts['open_gaps']} open gaps",
        f"{counts['interview_questions']} interview questions",
        f"{counts['approved']} approved",
    )


def workflow_rail(current_step: int, counts: dict[str, int]) -> None:
    labels = _rail_labels(counts)
    with st.container(key="workflow-rail-desktop"):
        columns = st.columns(len(_WORKFLOW))
        for index, (column, (name, page), count) in enumerate(
            zip(columns, _WORKFLOW, labels),
            start=1,
        ):
            with column:
                key = "workflow-step-current" if index == current_step else f"workflow-step-{index}"
                with st.container(key=key):
                    st.page_link(page, label=name)
                    st.caption(count)
    with st.container(key="workflow-rail-mobile"):
        st.caption(f"Step {current_step} of {len(_WORKFLOW)} · {_WORKFLOW[current_step - 1][0]}")


def next_step_banner(counts: dict[str, int], role: str) -> None:
    if normalize_role(role) == "Departing":
        message = "Answer your assigned exit-interview questions; other project sources and claims stay hidden."
    elif counts["sources"] == 0:
        message = "No sources yet. Load the synthetic demo or add project files in Connect."
    elif counts["evidence"] == 0:
        message = f"{counts['sources']} sources are available. Parse them into evidence excerpts in Connect."
    elif counts["claims"] == 0:
        message = f"{counts['evidence']} evidence excerpts are ready. Reconstruct claims from Review Claims."
    elif role == "Incoming":
        if counts["approved"]:
            message = f"{counts['approved']} approved claims are available in Handover."
        else:
            message = "No approved claims are available yet. A Reviewer must approve claims before handover."
    elif counts["pending"]:
        message = f"{counts['pending']} claims are waiting for human review."
    elif counts["approved"]:
        message = f"{counts['approved']} approved claims are ready in Handover."
    else:
        message = "No claims are ready for handover. Review the claims and evidence."
    st.info(message)


def page_shell(step: int, title: str, subtitle: str) -> tuple[str, dict[str, int]]:
    apply_theme()
    role = sidebar_identity()
    counts = _dashboard_counts(role)
    workflow_rail(step, counts)
    st.title(title)
    st.markdown(subtitle)
    st.markdown(f"Current role: {badge_html(role, variant='primary')}", unsafe_allow_html=True)
    next_step_banner(counts, role)
    glossary_popover()
    return role, counts


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


def footer() -> None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            check=True,
            text=True,
            timeout=2,
        )
        version = result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        version = "unavailable"
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
                ("Visible excerpts", counts["evidence"]),
                ("Approved claims", counts["approved"]),
                ("Hidden approved items", counts["hidden"]),
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
