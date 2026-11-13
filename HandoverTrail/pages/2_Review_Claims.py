import os
import sys

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import bootstrap
from conflict_detection import (
    detect_project_conflicts,
    get_conflict_records,
    get_gap_records,
    resolve_conflict,
)
from extractor import extract_claims_from_evidence
from permissions import can_review, perform_claim_review
from retrieval import get_claim_evidence, get_visible_claims
from ui import (
    configure_page,
    empty_state,
    footer,
    latest_extraction_method,
    origin_badge,
    page_shell,
    review_badge,
    show_flash_toast,
    trust_badge,
)
from validator import validate_project_claims

configure_page("Review claims · HandoverTrail")
bootstrap()

PROJECT_ID = "PROJ-DEMO-001"
user_role, counts = page_shell(
    4,
    "Review claims",
    "Inspect source evidence, check what is supported, and record a human review decision.",
)
if can_review(user_role):
    detect_project_conflicts(user_role, PROJECT_ID)
show_flash_toast()
extraction_notice = st.session_state.pop("ui_extraction_notice", None)
if extraction_notice:
    st.warning(extraction_notice)

try:
    api_key_secret = st.secrets.get("GEMINI_API_KEY")
    openrouter_api_key_secret = st.secrets.get("OPENROUTER_API_KEY")
except StreamlitSecretNotFoundError:
    api_key_secret = None
    openrouter_api_key_secret = None

if "ai_extraction_runs" not in st.session_state:
    st.session_state["ai_extraction_runs"] = 0
MAX_AI_EXTRACTION_RUNS = 3

with st.container(border=True):
    st.subheader("Reconstruct and validate")
    st.caption(
        "Only public-source excerpts are sent through the provider gateway. Restricted-source "
        "excerpts use the local heuristic."
    )
    extraction_col, validation_col = st.columns(2)
    with extraction_col:
        limit_reached = st.session_state["ai_extraction_runs"] >= MAX_AI_EXTRACTION_RUNS
        if limit_reached:
            st.info("This session reached its three-run limit. Cached demo claims remain available.")
        if st.button(
            "Extract claims",
            type="primary",
            disabled=not can_review(user_role) or limit_reached,
        ):
            st.session_state["ai_extraction_runs"] += 1
            with st.status("Preparing permitted evidence...", expanded=True) as progress:
                def update_extraction_progress(_value: int, message: str) -> None:
                    progress.update(label=message, state="running")

                result = extract_claims_from_evidence(
                    PROJECT_ID,
                    api_key=api_key_secret,
                    openrouter_api_key=openrouter_api_key_secret,
                    progress_callback=update_extraction_progress,
                )
                if result.get("status") == "success":
                    method = result["method"]
                    latest_extraction_method(method)
                    progress.update(
                        label=f"Extraction saved using {method}.",
                        state="complete",
                    )
                    st.session_state["ui_flash_toast"] = (
                        f"Created {result['claims_created']} claims; "
                        f"{result.get('masked_values', 0)} values masked before provider calls."
                    )
                    if result.get("fallback_reason"):
                        st.session_state["ui_extraction_notice"] = result["fallback_reason"]
                    st.rerun()
                else:
                    progress.update(
                        label="Extraction did not complete. Existing claims remain available.",
                        state="error",
                    )
                    st.error(result.get("message", "Extraction failed."))

    with validation_col:
        if st.button(
            "Validate evidence links",
            disabled=not can_review(user_role),
        ):
            try:
                validated_count = validate_project_claims(user_role, PROJECT_ID)
            except PermissionError as exc:
                st.error(f"Validation not permitted: {exc}")
            else:
                st.session_state["ui_flash_toast"] = (
                    f"Validated {validated_count} claims against linked evidence."
                )
                st.rerun()

if not can_review(user_role):
    st.info("Select Admin or Reviewer to extract, validate, approve, or reject claims.")

claims = get_visible_claims(user_role, PROJECT_ID)
if any(claim["claim_source"] == "cached_demo" for claim in claims):
    st.info("Cached synthetic demo claims are available to review without an API call.")

if can_review(user_role):
    st.subheader("Conflicts and gaps")
    st.caption(
        "Rule-based comparisons show conflicting values or corroboration only when "
        "normalized statements agree. Evidence gaps remain visible until addressed."
    )
    conflicts = get_conflict_records(user_role, PROJECT_ID)
    if conflicts:
        for conflict in conflicts:
            with st.container(border=True):
                st.markdown(
                    f"**{conflict['subject']} · {conflict['attribute']}** "
                    f"— {conflict['status'].replace('_', ' ').title()}"
                )
                version_a, version_b = st.columns(2)
                for column, claim_id, claim_text, label in (
                    (version_a, conflict["claim_a"], conflict["claim_a_text"], "Version A"),
                    (version_b, conflict["claim_b"], conflict["claim_b_text"], "Version B"),
                ):
                    with column:
                        st.markdown(f"**{label}**")
                        st.write(claim_text)
                        for evidence in get_claim_evidence(user_role, claim_id):
                            st.caption(
                                f"{evidence['file_name']} · "
                                f"{evidence['reference_location'] or 'Source location unavailable'}"
                            )
                            st.write(evidence["excerpt"])
                if conflict["status"] == "CORROBORATED":
                    st.success("The normalized values agree across separate sources.")
                elif conflict["resolution"] == "UNRESOLVED":
                    resolution_columns = st.columns(4)
                    for column, resolution, label in zip(
                        resolution_columns,
                        ("KEEP_A", "KEEP_B", "KEEP_BOTH", "UNRESOLVED"),
                        ("Keep A", "Keep B", "Keep both as context", "Mark unresolved"),
                    ):
                        with column:
                            if st.button(
                                label,
                                key=f"resolve_{conflict['conflict_id']}_{resolution}",
                            ):
                                try:
                                    resolve_conflict(user_role, conflict["conflict_id"], resolution)
                                except (PermissionError, ValueError) as exc:
                                    st.error(f"Could not save conflict resolution: {exc}")
                                else:
                                    st.session_state["ui_flash_toast"] = (
                                        "Conflict resolution and audit event saved."
                                    )
                                    st.rerun()
                else:
                    st.success(
                        f"Recorded resolution: {conflict['resolution'].replace('_', ' ').title()}."
                    )
    else:
        empty_state("No unresolved conflicts are currently detected.")

    gaps = get_gap_records(user_role, PROJECT_ID)
    if gaps:
        st.markdown("**Open evidence gaps**")
        for gap in gaps:
            with st.container(border=True):
                st.markdown(f"**{gap['gap_type'].replace('_', ' ').title()}**")
                st.write(gap["claim_text"] or gap["subject"] or "Related claim unavailable.")
                if gap["related_claim_id"]:
                    for evidence in get_claim_evidence(user_role, gap["related_claim_id"]):
                        st.caption(
                            f"{evidence['file_name']} · "
                            f"{evidence['reference_location'] or 'Source location unavailable'}"
                        )
                        st.write(evidence["excerpt"])
    else:
        empty_state("No open evidence gaps are currently detected.")

st.subheader("Candidate claims")
st.caption("Corroborated means comparable statements agree after normalization; source count alone is not proof.")
if not claims:
    empty_state(
        "No claims are available for this role yet.",
        "Connect and parse sources, then run claim extraction.",
    )
else:
    for claim in claims:
        claim_id = claim["claim_id"]
        with st.container(border=True):
            st.markdown(
                f"{trust_badge(claim['trust_status'])} "
                f"{review_badge(claim['review_status'])} "
                f"{origin_badge(claim['claim_source'])}",
                unsafe_allow_html=True,
            )
            st.caption(f"{claim['claim_type']} · Claim ID {claim_id}")
            st.write(claim["claim_text"])

            with st.expander("Evidence and provenance"):
                evidence_list = get_claim_evidence(user_role, claim_id)
                if evidence_list:
                    for evidence in evidence_list:
                        st.markdown(f"**{evidence['file_name']}**")
                        st.caption(evidence["reference_location"] or "Source location unavailable")
                        st.write(evidence["excerpt"])
                else:
                    empty_state("No readable evidence excerpts are linked to this claim.")
                st.markdown(
                    f"Origin: {origin_badge(claim['claim_source'])}",
                    unsafe_allow_html=True,
                )

            if can_review(user_role) and claim["review_status"] == "PENDING":
                approve_col, reject_col = st.columns(2)
                with approve_col:
                    if st.button(
                        "Approve claim",
                        key=f"approve_{claim_id}",
                        type="primary",
                    ):
                        try:
                            perform_claim_review(user_role, claim_id, "APPROVED")
                        except PermissionError as exc:
                            st.error(f"Review not permitted: {exc}")
                        else:
                            st.session_state["ui_flash_toast"] = (
                                "Claim approved and saved. It is now eligible for handover."
                            )
                            st.rerun()
                with reject_col:
                    if st.button(
                        "Reject claim",
                        key=f"reject_{claim_id}",
                    ):
                        st.session_state["pending_rejection_id"] = claim_id
                        st.rerun()

@st.dialog("Confirm claim rejection")
def confirm_rejection(claim_id: str) -> None:
    st.write("Reject this claim? The decision will be saved to the review and audit history.")
    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button("Confirm rejection", type="primary"):
            try:
                perform_claim_review(user_role, claim_id, "REJECTED")
            except PermissionError as exc:
                st.error(f"Review not permitted: {exc}")
            else:
                st.session_state.pop("pending_rejection_id", None)
                st.session_state["ui_flash_toast"] = "Claim rejection saved."
                st.rerun()
    with cancel_col:
        if st.button("Cancel"):
            st.session_state.pop("pending_rejection_id", None)
            st.rerun()

pending_rejection_id = st.session_state.get("pending_rejection_id")
if pending_rejection_id:
    pending_claim = next(
        (claim for claim in claims if claim["claim_id"] == pending_rejection_id),
        None,
    )
    if pending_claim:
        confirm_rejection(pending_rejection_id)
    else:
        st.session_state.pop("pending_rejection_id", None)

footer()
