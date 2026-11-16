import os
import sys
import math

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import DEMO_PROJECT_ID, bootstrap, get_connection
from conflict_detection import (
    get_conflict_records,
    get_gap_records,
    resolve_conflict,
)
from claim_history import edit_claim, get_claim_history
from extractor import extract_claims_from_evidence, get_latest_extraction_run
from permissions import can_review, perform_claim_review
from retrieval import get_claim_evidence, get_visible_claims, get_visible_sources
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
    validation_badge,
)
from validator import validate_project_claims
from workspace import get_active_project_id


def _render_conflict_gap_panel(role: str, project_id: str) -> None:
    with st.expander("Conflicts and gaps", expanded=False):
        st.caption(
            "Rule-based comparisons show conflicting values or corroboration only when "
            "normalized statements agree. Evidence gaps remain visible until addressed."
        )
        conflicts = get_conflict_records(role, project_id)
        if conflicts:
            statuses = sorted({row["status"] for row in conflicts})
            selected_status = st.selectbox(
                "Conflict status",
                ["All statuses", *statuses],
                key=f"conflict_status_{project_id}",
            )
            if selected_status != "All statuses":
                conflicts = [row for row in conflicts if row["status"] == selected_status]
            conflict_pages = max(1, math.ceil(len(conflicts) / 5))
            conflict_page = st.selectbox(
                "Conflict page",
                range(1, conflict_pages + 1),
                key=f"conflict_page_{project_id}_{selected_status}_{len(conflicts)}",
            )
            st.caption(f"{len(conflicts)} comparison(s); showing up to 5 per page.")
            start = (conflict_page - 1) * 5
            for conflict in conflicts[start : start + 5]:
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
                            st.markdown(claim_text)
                            for evidence in get_claim_evidence(role, claim_id):
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
                                        resolve_conflict(role, conflict["conflict_id"], resolution)
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
            conn = get_connection()
            try:
                status = conn.execute(
                    """
                    SELECT COUNT(*) AS total,
                           SUM(CASE WHEN validated_at IS NOT NULL THEN 1 ELSE 0 END) AS checked
                    FROM claims WHERE project_id = ?
                    """,
                    (project_id,),
                ).fetchone()
            finally:
                conn.close()
            if status["total"] and status["checked"] < status["total"]:
                empty_state(
                    "Conflict checks are not current.",
                    "Use Validate evidence links to recompute conflicts and gaps for this workspace.",
                )
            else:
                empty_state("No conflict comparisons are currently detected.")

        st.markdown("**Open evidence gaps**")
        gaps = get_gap_records(role, project_id)
        if not gaps:
            empty_state("No open evidence gaps are currently detected.")
            return
        gap_types = sorted({gap["gap_type"] for gap in gaps})
        selected_gap_type = st.selectbox(
            "Gap type",
            ["All gap types", *gap_types],
            key=f"gap_type_{project_id}",
        )
        if selected_gap_type != "All gap types":
            gaps = [gap for gap in gaps if gap["gap_type"] == selected_gap_type]
        gap_pages = max(1, math.ceil(len(gaps) / 5))
        gap_page = st.selectbox(
            "Gap page",
            range(1, gap_pages + 1),
            key=f"gap_page_{project_id}_{selected_gap_type}_{len(gaps)}",
        )
        st.caption(f"{len(gaps)} open gap(s); showing up to 5 per page.")
        start = (gap_page - 1) * 5
        for gap in gaps[start : start + 5]:
            with st.container(border=True):
                st.markdown(f"**{gap['gap_type'].replace('_', ' ').title()}**")
                st.write(gap["claim_text"] or gap["subject"] or "Related claim unavailable.")
                if gap["related_claim_id"]:
                    for evidence in get_claim_evidence(role, gap["related_claim_id"]):
                        st.caption(
                            f"{evidence['file_name']} · "
                            f"{evidence['reference_location'] or 'Source location unavailable'}"
                        )
                        st.write(evidence["excerpt"])


configure_page("Review claims · HandoverTrail")
bootstrap()
PROJECT_ID = get_active_project_id()

user_role, counts = page_shell(
    4,
    "Review claims",
    "Inspect source evidence, check what is supported, and record a human review decision.",
)
show_flash_toast()
if PROJECT_ID == DEMO_PROJECT_ID:
    st.info(
        "Active workspace: Demo project. The sources and claims below are not your "
        "separate upload workspace. Open Upload Sources and save files there; the "
        "workspace link keeps that project selected."
    )
else:
    st.caption(f"Active workspace: Upload workspace {PROJECT_ID[-6:]}.")
if not can_review(user_role):
    if user_role == "Incoming":
        st.info("Incoming does not review candidate claims. Only a released snapshot is shown.")
        destination = "pages/3_Handover_View.py"
        label = "Open the released handover"
    else:
        st.info("Candidate claims are available to Admin or Reviewer.")
        destination = "pages/4_Exit_Interview.py"
        label = "Open your assigned interview"
    st.page_link(destination, label=label, query_params=dict(st.query_params))
    footer()
    st.stop()

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
        "excerpts use local rule-based extraction. New uploads default to Restricted; choose "
        "Public only when the content is safe to send to configured AI providers. Demo evidence "
        "is never included in an upload workspace."
    )
    available_sources = get_visible_sources(user_role, PROJECT_ID)
    if not counts["evidence"]:
        st.info("Parse this workspace's sources before extracting claims.")
    source_ids_by_name = {
        f"{source['file_name']} · {source['source_id']}": source["source_id"]
        for source in available_sources
    }
    selected_source_names = st.multiselect(
        "Sources to include in this extraction",
        options=list(source_ids_by_name),
        default=list(source_ids_by_name),
        key=f"extraction_sources_{PROJECT_ID}",
        help="Choose fewer files for a focused run. Claims cite only excerpts from these files.",
    )
    selected_source_ids = [
        source_ids_by_name[name] for name in selected_source_names
    ]
    extraction_col, validation_col = st.columns(2)
    with extraction_col:
        limit_reached = st.session_state["ai_extraction_runs"] >= MAX_AI_EXTRACTION_RUNS
        if limit_reached:
            st.info("This session reached its three-run limit. Existing claims remain available.")
        if st.button(
            "Extract claims",
            type="primary",
            disabled=not selected_source_ids or not counts["evidence"] or limit_reached,
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
                    source_ids=selected_source_ids,
                )
                if result.get("status") == "success":
                    method = result["method"]
                    latest_extraction_method(method)
                    progress.update(
                        label=(
                            f"Extraction finished with {method}; "
                            f"{result['claims_created']} new claim(s)."
                        ),
                        state="complete",
                    )
                    st.rerun()
                else:
                    progress.update(
                        label="Extraction did not complete. Existing claims remain available.",
                        state="error",
                    )

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

last_extraction = get_latest_extraction_run(PROJECT_ID)
if last_extraction and last_extraction.get("project_id") == PROJECT_ID:
    if last_extraction.get("status") == "success":
        st.success(
            f"Extraction complete · {last_extraction['method']} · "
            f"{last_extraction['claims_created']} new claim(s) · "
            f"{last_extraction.get('masked_values', 0)} values masked before provider calls. "
            f"Completed {last_extraction['completed_at']}."
        )
        if last_extraction.get("fallback_reason"):
            st.warning(last_extraction["fallback_reason"])
    else:
        st.error(
            last_extraction.get("message")
            or last_extraction.get("fallback_reason")
            or "Extraction failed."
        )

claims = get_visible_claims(user_role, PROJECT_ID)
if PROJECT_ID == DEMO_PROJECT_ID and any(
    claim["claim_source"] == "cached_demo" for claim in claims
):
    st.info("Cached synthetic demo claims are available to review without an API call.")

_render_conflict_gap_panel(user_role, PROJECT_ID)

st.subheader("Candidate claims")
st.caption(
    "Search and filter the review queue. Evidence-checked means the validator "
    "examined the claim's source links; corroboration is a separate trust result."
)
if not claims:
    empty_state(
        "No claims are available in this workspace yet.",
        "Connect and parse sources, then extract claims from this workspace.",
    )
else:
    review_options = ["All review states", "PENDING", "EDITED_PENDING_REVIEW", "APPROVED", "REJECTED"]
    trust_options = ["All evidence states", "VERIFIED", "SINGLE_SOURCE", "CONFLICTING", "MISSING_EVIDENCE"]
    validation_options = ["All validation states", "Validated", "Not validated"]
    filter_columns = st.columns(4)
    with filter_columns[0]:
        selected_review = st.selectbox("Review state", review_options)
    with filter_columns[1]:
        selected_trust = st.selectbox("Evidence state", trust_options)
    with filter_columns[2]:
        selected_validation = st.selectbox("Validation", validation_options)
    with filter_columns[3]:
        claim_search = st.text_input("Search claim text", placeholder="Type a keyword")

    filtered_claims = claims
    if selected_review != "All review states":
        filtered_claims = [
            claim for claim in filtered_claims
            if claim["review_status"] == selected_review
        ]
    if selected_trust != "All evidence states":
        filtered_claims = [
            claim for claim in filtered_claims
            if claim["trust_status"] == selected_trust
        ]
    if selected_validation == "Validated":
        filtered_claims = [claim for claim in filtered_claims if claim["validated_at"]]
    elif selected_validation == "Not validated":
        filtered_claims = [claim for claim in filtered_claims if not claim["validated_at"]]
    if claim_search.strip():
        query = claim_search.casefold().strip()
        filtered_claims = [
            claim for claim in filtered_claims
            if query in claim["claim_text"].casefold()
            or query in claim["claim_type"].casefold()
        ]
    filtered_claims = sorted(
        filtered_claims,
        key=lambda claim: claim["created_at"],
        reverse=True,
    )
    filtered_claims.sort(
        key=lambda claim: claim["review_status"]
        not in {"PENDING", "EDITED_PENDING_REVIEW"}
    )
    page_size = st.selectbox("Claims per page", [10, 25, 50], index=0)
    page_count = max(1, math.ceil(len(filtered_claims) / page_size))
    filter_signature = (
        selected_review,
        selected_trust,
        selected_validation,
        claim_search.casefold(),
        page_size,
        len(filtered_claims),
    )
    signature_key = f"claims_filter_signature_{PROJECT_ID}"
    page_key = f"claims_page_number_{PROJECT_ID}"
    if st.session_state.get(signature_key) != filter_signature:
        st.session_state[signature_key] = filter_signature
        st.session_state[page_key] = 1
    page_number = st.selectbox(
        "Claim page",
        range(1, page_count + 1),
        key=page_key,
    )
    start = (page_number - 1) * page_size
    if filtered_claims:
        st.caption(
            f"Showing claims {start + 1}–{min(start + page_size, len(filtered_claims))} "
            f"of {len(filtered_claims)} matching {len(claims)} total."
        )
    else:
        empty_state("No claims match these filters.", "Clear one or more filters to see more claims.")

    for claim in filtered_claims[start : start + page_size]:
        claim_id = claim["claim_id"]
        with st.container(border=True):
            st.markdown(
                f"{trust_badge(claim['trust_status'])} "
                f"{review_badge(claim['review_status'])} "
                f"{validation_badge(claim['validated_at'])} "
                f"{origin_badge(claim['claim_source'])}",
                unsafe_allow_html=True,
            )
            st.caption(f"{claim['claim_type']} · Claim ID {claim_id}")
            st.markdown(claim["claim_text"])

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

            if can_review(user_role):
                with st.expander("Edit claim"):
                    with st.form(f"edit_claim_{claim_id}"):
                        edited_claim_text = st.text_area(
                            "Claim text",
                            value=claim["claim_text"],
                            key=f"claim_text_{claim_id}",
                        )
                        edit_reason = st.text_input(
                            "Reason for edit",
                            key=f"edit_reason_{claim_id}",
                        )
                        edit_submitted = st.form_submit_button("Save claim edit")
                    if edit_submitted:
                        try:
                            edit_claim(
                                user_role,
                                claim_id,
                                edited_claim_text,
                                edit_reason,
                            )
                        except (PermissionError, ValueError) as exc:
                            st.error(f"Could not edit claim: {exc}")
                        else:
                            st.session_state["ui_flash_toast"] = (
                                "Claim edit saved and marked pending review."
                            )
                            st.rerun()

                with st.expander("History"):
                    history = get_claim_history(user_role, claim_id)
                    st.markdown(
                        f"{review_badge(history['review_status'])} **Current**",
                        unsafe_allow_html=True,
                    )
                    st.write(history["current_text"])
                    for version in history["versions"]:
                        st.markdown(f"**Previous version {version['version']}**")
                        st.write(version["text"])
                        st.caption(
                            f"Edited by {version['editor_name']} · {version['created_at']} · "
                            f"Reason: {version['reason']}"
                        )

            if can_review(user_role) and claim["review_status"] in {
                "PENDING",
                "EDITED_PENDING_REVIEW",
            }:
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
