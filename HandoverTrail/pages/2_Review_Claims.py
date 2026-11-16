import html
import math
import os
import sys

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
from claim_insights import get_claim_insights, summarize_insights
from extractor import extract_claims_from_evidence, get_latest_extraction_run
from permissions import can_review, perform_claim_review
from retrieval import get_claim_evidence, get_visible_claims, get_visible_sources
from ui import (
    badge_html,
    claim_headline_html,
    configure_page,
    empty_state,
    footer,
    latest_extraction_method,
    origin_badge,
    page_navigation,
    page_shell,
    quote_html,
    review_badge,
    show_flash_toast,
    stat_row,
    trust_badge,
)
from validator import validate_project_claims
from workspace import get_active_project_id


def _render_conflict_gap_panel(role: str, project_id: str) -> None:
    conflicts = get_conflict_records(role, project_id)
    unresolved = sum(
        row["status"] != "CORROBORATED" and row["resolution"] == "UNRESOLVED"
        for row in conflicts
    )
    open_gap_count = len(get_gap_records(role, project_id))
    with st.expander(
        f"Conflicts and gaps · {unresolved} unresolved conflict(s) · "
        f"{open_gap_count} open gap(s)",
        expanded=False,
    ):
        st.caption(
            "Rule-based comparisons show conflicting values or corroboration only when "
            "normalized statements agree. Evidence gaps remain visible until addressed."
        )
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
                        st.caption(
                            "Record which version the team should rely on. This is an "
                            "audited note; approve or reject each claim separately below."
                        )
                        resolution_columns = st.columns(3)
                        for column, resolution, label in zip(
                            resolution_columns,
                            ("KEEP_A", "KEEP_B", "KEEP_BOTH"),
                            ("Keep A", "Keep B", "Keep both as context"),
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
                        if st.button(
                            "Reopen this conflict",
                            key=f"resolve_{conflict['conflict_id']}_UNRESOLVED",
                        ):
                            try:
                                resolve_conflict(role, conflict["conflict_id"], "UNRESOLVED")
                            except (PermissionError, ValueError) as exc:
                                st.error(f"Could not reopen the conflict: {exc}")
                            else:
                                st.session_state["ui_flash_toast"] = (
                                    "Conflict reopened; the change was audited."
                                )
                                st.rerun()
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
        st.page_link(
            "pages/4_Exit_Interview.py",
            label="Turn open gaps into exit-interview questions →",
            query_params=dict(st.query_params),
        )
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


def source_label(evidence: dict) -> str:
    """File name plus location, without repeating the file name."""
    location = evidence["reference_location"] or ""
    if location.startswith(evidence["file_name"]):
        return location
    return f"{evidence['file_name']} · {location or 'Source excerpt'}"


configure_page("Review claims · HandoverTrail")
bootstrap()
PROJECT_ID = get_active_project_id()

user_role, counts = page_shell(
    4,
    "Review claims",
    "Extract claims from your sources, verify them against their evidence, then record a human decision.",
    auto_stage=True,
)
show_flash_toast()
query_params = dict(st.query_params)
if PROJECT_ID == DEMO_PROJECT_ID:
    st.caption(
        "Active workspace: Demo project (shared synthetic data). Files you upload go to a "
        "separate workspace, not here."
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
    st.page_link(destination, label=label, query_params=query_params)
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

claims = get_visible_claims(user_role, PROJECT_ID)
insights = get_claim_insights(user_role, PROJECT_ID)
summary = summarize_insights(claims, insights)
available_sources = get_visible_sources(user_role, PROJECT_ID)
PENDING_STATES = {"PENDING", "EDITED_PENDING_REVIEW"}
pending_count = sum(claim["review_status"] in PENDING_STATES for claim in claims)
approved_count = sum(claim["review_status"] == "APPROVED" for claim in claims)
rejected_count = sum(claim["review_status"] == "REJECTED" for claim in claims)

# ---------------------------------------------------------------- stage tracker
stage_done = (
    bool(claims),
    bool(claims) and summary["unvalidated"] == 0,
    bool(claims) and pending_count == 0,
)
if claims:
    stage_detail = (
        f"{len(claims)} claim(s) from {len(available_sources)} source(s)",
        f"{len(claims) - summary['unvalidated']} checked · {summary['attention']} need attention",
        f"{approved_count} approved · {pending_count} pending · {rejected_count} rejected",
    )
else:
    stage_detail = (
        "No claims yet. Extract them from your sources."
        if available_sources
        else "No sources yet. Connect sources first.",
        "Starts once claims exist.",
        "Starts once claims exist.",
    )
current_stage = next((index for index, done in enumerate(stage_done) if not done), None)
for column, index, title in zip(st.columns(3), range(3), ("Reconstruct", "Verify", "Review")):
    with column, st.container(border=True):
        st.markdown(f"**{index + 1}. {title}**")
        if stage_done[index]:
            st.markdown(badge_html("Done", "success"), unsafe_allow_html=True)
        elif index == current_stage:
            st.markdown(badge_html("Do this now", "primary"), unsafe_allow_html=True)
        else:
            st.markdown(badge_html("Waiting", "neutral"), unsafe_allow_html=True)
        st.caption(stage_detail[index])

# ---------------------------------------------------------------- 1 reconstruct
st.subheader("1 · Reconstruct: extract claims from sources")
last_extraction = get_latest_extraction_run(PROJECT_ID)
if last_extraction and last_extraction.get("project_id") == PROJECT_ID:
    if last_extraction.get("status") == "success":
        st.caption(
            f"Extraction complete · {last_extraction['method']} · "
            f"{last_extraction['claims_created']} new claim(s) · "
            f"{last_extraction.get('masked_values', 0)} values masked before provider calls · "
            f"{last_extraction['completed_at']}"
        )
        if last_extraction.get("fallback_reason"):
            st.caption(f"Method note: {last_extraction['fallback_reason']}")
    else:
        st.error(
            last_extraction.get("message")
            or last_extraction.get("fallback_reason")
            or "Extraction failed."
        )
if PROJECT_ID == DEMO_PROJECT_ID and any(
    claim["claim_source"] == "cached_demo" for claim in claims
):
    st.caption("Cached synthetic demo claims are ready to review without an API call.")

with st.expander(
    "Extraction settings and run" if claims else "Run extraction",
    expanded=not claims,
):
    st.caption(
        "Only public-source excerpts go to AI providers. Restricted sources use local "
        "rule-based extraction. New uploads default to Restricted."
    )
    if not available_sources:
        st.info("This workspace has no sources yet. Connect sources before extracting claims.")
        st.page_link(
            "pages/1_Upload_Sources.py",
            label="Connect sources →",
            query_params=query_params,
        )
    elif not counts["evidence"]:
        st.info("Parse this workspace's sources before extracting claims.")
        st.page_link(
            "pages/1_Upload_Sources.py",
            label="Parse sources →",
            query_params=query_params,
        )
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
    selected_source_ids = [source_ids_by_name[name] for name in selected_source_names]
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

            try:
                result = extract_claims_from_evidence(
                    PROJECT_ID,
                    api_key=api_key_secret,
                    openrouter_api_key=openrouter_api_key_secret,
                    progress_callback=update_extraction_progress,
                    source_ids=selected_source_ids,
                )
            except Exception as exc:  # database or storage failure
                result = {
                    "status": "error",
                    "message": f"Extraction stopped ({type(exc).__name__}).",
                }
            if result.get("status") == "success":
                method = result["method"]
                latest_extraction_method(method)
                progress.update(label="Checking evidence links...", state="running")
                try:
                    validated_count = validate_project_claims(user_role, PROJECT_ID)
                except Exception:  # claims are saved; validation can be retried
                    validated_count = None
                progress.update(
                    label=(
                        f"Extraction finished with {method}; "
                        f"{result['claims_created']} new claim(s)."
                    ),
                    state="complete",
                )
                if validated_count is None:
                    st.session_state["ui_flash_toast"] = (
                        f"{result['claims_created']} new claim(s) saved. Verification "
                        "did not finish; use Validate evidence links."
                    )
                else:
                    st.session_state["ui_flash_toast"] = (
                        f"{result['claims_created']} new claim(s) saved and "
                        f"{validated_count} claim(s) verified against their evidence."
                    )
                st.rerun()
            else:
                progress.update(
                    label="Extraction did not complete. Existing claims remain available.",
                    state="error",
                )
                st.error(
                    f"{result.get('message', 'Extraction failed.')} Sources and existing "
                    "claims are unchanged, and it is safe to retry."
                )

# ---------------------------------------------------------------- 2 verify
st.subheader("2 · Verify: what the evidence supports")
if not claims:
    st.caption("Verification starts once claims exist.")
else:
    stat_row(
        [
            ("Corroborated", summary["VERIFIED"]),
            ("Single source", summary["SINGLE_SOURCE"]),
            ("Conflicting", summary["CONFLICTING"]),
            ("Missing evidence", summary["MISSING_EVIDENCE"]),
            ("Weak evidence match", summary["weak_match"]),
        ]
    )
    st.caption(
        "Verification compares claims across sources, checks that each claim's key words and "
        "numbers appear in the excerpts it cites, and lists evidence gaps. It finds claims "
        "that need a closer look; it does not prove a claim is true."
    )
    verify_message, verify_action = st.columns([3, 1])
    with verify_message:
        if summary["unvalidated"]:
            st.warning(
                f"{summary['unvalidated']} claim(s) have not been verified yet. "
                "Run verification before relying on their labels."
            )
        elif summary["attention"]:
            st.info(
                f"{summary['attention']} claim(s) need attention. Open the "
                "“Needs attention” view in step 3."
            )
        else:
            st.success("No conflicts, missing evidence, or weak matches were found.")
        if summary["last_validated"]:
            st.caption(f"Last verified {summary['last_validated']}.")
    with verify_action:
        if st.button(
            "Validate evidence links",
            disabled=not can_review(user_role),
            help=(
                "Re-checks every claim's evidence links and recomputes conflicts and gaps. "
                "Runs automatically after extraction."
            ),
        ):
            try:
                validated_count = validate_project_claims(user_role, PROJECT_ID)
            except PermissionError as exc:
                st.error(f"Validation not permitted: {exc}")
            else:
                st.session_state["ui_flash_toast"] = (
                    f"Verified {validated_count} claims against their linked evidence."
                )
                st.rerun()
    _render_conflict_gap_panel(user_role, PROJECT_ID)

# ---------------------------------------------------------------- 3 review
st.subheader("3 · Review: approve or reject each claim")
st.caption(
    "Approved claims become Incoming's start plan: blockers and next actions first, each "
    "with its source. Check the quoted evidence before approving."
)
if not claims:
    empty_state(
        "No claims are available in this workspace yet.",
        "Connect and parse sources, then extract claims from this workspace.",
    )
else:
    if not pending_count:
        st.success(
            "The review queue is clear: every claim has a decision. "
            f"{approved_count} approved, {rejected_count} rejected."
        )
        if approved_count:
            st.page_link(
                "pages/3_Handover_View.py",
                label="Continue: release the handover →",
                query_params=query_params,
            )

    attention_count = sum(
        insights[claim["claim_id"]]["attention"] and claim["review_status"] != "REJECTED"
        for claim in claims
    )
    view_counts = {
        "Needs review": pending_count,
        "Needs attention": attention_count,
        "Approved": approved_count,
        "Rejected": rejected_count,
        "All": len(claims),
    }
    view_key = f"claims_view_{PROJECT_ID}"
    if view_key not in st.session_state:
        st.session_state[view_key] = "Needs review" if pending_count else "All"
    selected_view = st.radio(
        "Show",
        list(view_counts),
        key=view_key,
        horizontal=True,
        format_func=lambda name: f"{name} ({view_counts[name]})",
    )
    type_options = ["All types", *sorted({claim["claim_type"] for claim in claims})]
    trust_options = ["All evidence states", "VERIFIED", "SINGLE_SOURCE", "CONFLICTING", "MISSING_EVIDENCE"]
    filter_columns = st.columns(3)
    with filter_columns[0]:
        selected_type = st.selectbox("Claim type", type_options)
    with filter_columns[1]:
        selected_trust = st.selectbox(
            "Evidence state",
            trust_options,
            format_func=lambda value: (
                value if value == "All evidence states" else value.replace("_", " ").capitalize()
            ),
        )
    with filter_columns[2]:
        claim_search = st.text_input("Search claim text", placeholder="Type a keyword")

    filtered_claims = claims
    if selected_view == "Needs review":
        filtered_claims = [c for c in filtered_claims if c["review_status"] in PENDING_STATES]
    elif selected_view == "Needs attention":
        filtered_claims = [
            c for c in filtered_claims
            if insights[c["claim_id"]]["attention"] and c["review_status"] != "REJECTED"
        ]
    elif selected_view == "Approved":
        filtered_claims = [c for c in filtered_claims if c["review_status"] == "APPROVED"]
    elif selected_view == "Rejected":
        filtered_claims = [c for c in filtered_claims if c["review_status"] == "REJECTED"]
    if selected_type != "All types":
        filtered_claims = [c for c in filtered_claims if c["claim_type"] == selected_type]
    if selected_trust != "All evidence states":
        filtered_claims = [c for c in filtered_claims if c["trust_status"] == selected_trust]
    if claim_search.strip():
        query = claim_search.casefold().strip()
        filtered_claims = [
            c for c in filtered_claims
            if query in c["claim_text"].casefold() or query in c["claim_type"].casefold()
        ]
    filtered_claims = sorted(filtered_claims, key=lambda c: c["created_at"], reverse=True)
    filtered_claims.sort(key=lambda c: not insights[c["claim_id"]]["attention"])

    size_column, page_column = st.columns(2)
    with size_column:
        page_size = st.selectbox("Claims per page", [10, 25, 50], index=0)
    page_count = max(1, math.ceil(len(filtered_claims) / page_size))
    filter_signature = (
        selected_view,
        selected_type,
        selected_trust,
        claim_search.casefold(),
        page_size,
        len(filtered_claims),
    )
    signature_key = f"claims_filter_signature_{PROJECT_ID}"
    page_key = f"claims_page_number_{PROJECT_ID}"
    if st.session_state.get(signature_key) != filter_signature:
        st.session_state[signature_key] = filter_signature
        st.session_state[page_key] = 1
    with page_column:
        page_number = st.selectbox("Claim page", range(1, page_count + 1), key=page_key)
    start = (page_number - 1) * page_size
    if filtered_claims:
        st.caption(
            f"Showing claims {start + 1}–{min(start + page_size, len(filtered_claims))} "
            f"of {len(filtered_claims)} matching {len(claims)} total. "
            "Claims that need attention are listed first."
        )
    else:
        empty_state(
            "No claims match this view.",
            "Choose another view above or clear a filter.",
        )

    for claim in filtered_claims[start : start + page_size]:
        claim_id = claim["claim_id"]
        info = insights[claim_id]
        evidence_list = info["evidence"]
        with st.container(border=True):
            st.markdown(
                claim_headline_html(claim["claim_type"], claim["claim_text"]),
                unsafe_allow_html=True,
            )
            badges = [trust_badge(claim["trust_status"]), review_badge(claim["review_status"])]
            badges += [badge_html(label, variant) for variant, label in info["flags"]]
            st.markdown(" ".join(badges), unsafe_allow_html=True)
            st.markdown(
                f'<div class="ht-why">{html.escape(info["reason"])}</div>',
                unsafe_allow_html=True,
            )
            for conflict in info["open_conflicts"][:2]:
                st.warning(
                    f"Conflicts with: “{conflict['other_text']}”"
                    + (
                        f" ({', '.join(conflict['other_sources'])})"
                        if conflict["other_sources"]
                        else ""
                    )
                )
            if evidence_list:
                first = evidence_list[0]
                st.markdown(
                    quote_html(source_label(first), first["excerpt"]),
                    unsafe_allow_html=True,
                )
                if info["match"]["weak"]:
                    st.caption(
                        "Not found in the cited evidence: "
                        + ", ".join(info["match"]["missing"][:8])
                    )
                if len(evidence_list) > 1:
                    with st.expander(f"All cited evidence ({len(evidence_list)} excerpts)"):
                        for evidence in evidence_list:
                            st.markdown(
                                quote_html(
                                    source_label(evidence), evidence["excerpt"], limit=None
                                ),
                                unsafe_allow_html=True,
                            )
            else:
                empty_state("No readable evidence excerpts are linked to this claim.")

            if claim["review_status"] in PENDING_STATES:
                approve_col, reject_col, _spacer = st.columns([1, 1, 2])
                with approve_col:
                    if st.button("Approve claim", key=f"approve_{claim_id}", type="primary"):
                        try:
                            perform_claim_review(user_role, claim_id, "APPROVED")
                        except (PermissionError, ValueError) as exc:
                            st.error(f"The approval was not saved: {exc}")
                        else:
                            st.session_state["ui_flash_toast"] = (
                                "Claim approved and saved. It is now eligible for handover."
                            )
                            st.rerun()
                with reject_col:
                    if st.button("Reject claim", key=f"reject_{claim_id}"):
                        st.session_state["pending_rejection_id"] = claim_id
                        st.rerun()

            with st.expander("Edit, history and details"):
                edit_tab, history_tab, details_tab = st.tabs(["Edit", "History", "Details"])
                with edit_tab:
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
                            edit_claim(user_role, claim_id, edited_claim_text, edit_reason)
                        except (PermissionError, ValueError) as exc:
                            st.error(f"Could not edit claim: {exc}")
                        else:
                            st.session_state["ui_flash_toast"] = (
                                "Claim edit saved and marked pending review."
                            )
                            st.rerun()
                with history_tab:
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
                with details_tab:
                    st.markdown(origin_badge(claim["claim_source"]), unsafe_allow_html=True)
                    st.caption(f"Claim ID {claim_id}")
                    st.caption(
                        "Cited sources: "
                        + (", ".join(info["sources"]) if info["sources"] else "none")
                    )
                    match = info["match"]
                    if match["assessed"]:
                        st.caption(
                            f"Evidence match: {round(match['ratio'] * 100)}% of the claim's key "
                            "words and numbers appear in the cited excerpts."
                        )
                    else:
                        st.caption("Evidence match: too little text to assess.")
                    if info["gaps"]:
                        st.caption(
                            "Open gaps: " + ", ".join(gap.replace("_", " ") for gap in info["gaps"])
                        )


@st.dialog("Confirm claim rejection")
def confirm_rejection(claim_id: str) -> None:
    st.write("Reject this claim? The decision will be saved to the review and audit history.")
    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button("Confirm rejection", type="primary"):
            try:
                perform_claim_review(user_role, claim_id, "REJECTED")
            except (PermissionError, ValueError) as exc:
                st.error(f"The rejection was not saved: {exc}")
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

page_navigation(
    previous=("Connect sources", "pages/1_Upload_Sources.py"),
    following=(
        ("Exit interview (optional)", "pages/4_Exit_Interview.py"),
        ("Release handover", "pages/3_Handover_View.py"),
    ),
)
footer()
