import os
import sys

import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import bootstrap
from handover_release import (
    acknowledge_latest_release,
    get_latest_release,
    release_handover,
)
from permissions import can_review, normalize_role
from retrieval import get_claim_evidence, get_visible_claims
from ui import (
    configure_page,
    empty_state,
    footer,
    origin_badge,
    page_shell,
    review_badge,
    sensitivity_badge,
    show_flash_toast,
    trust_badge,
)
from workspace import get_active_project_id

configure_page("Handover · HandoverTrail")
bootstrap()
PROJECT_ID = get_active_project_id()

user_role, _counts = page_shell(
    6,
    "Project handover",
    "Reviewers release a fixed, cited snapshot. Incoming sees the latest released version and records receipt.",
)
show_flash_toast()

approved_claims = (
    []
    if normalize_role(user_role) == "Incoming"
    else [
        claim
        for claim in get_visible_claims(user_role, PROJECT_ID)
        if claim["review_status"] == "APPROVED"
    ]
)
release = get_latest_release(user_role, PROJECT_ID)

if can_review(user_role):
    with st.container(border=True):
        st.subheader("Handover release")
        if release:
            st.success(
                f"Latest release: version {release['version']} · {release['released_at']} · "
                f"{len(release['snapshot']['claims'])} approved claim(s)."
            )
            if release["acknowledgements"]:
                for acknowledgement in release["acknowledgements"]:
                    st.info(
                        f"Acknowledged by {acknowledgement['user_name']} at "
                        f"{acknowledgement['acknowledged_at']}."
                    )
            else:
                st.caption("Incoming has not acknowledged this version.")
        else:
            st.caption("No release exists yet. Incoming cannot see live handover content.")
        if st.button("Release current approved handover", type="primary"):
            try:
                created_release = release_handover(user_role, PROJECT_ID)
            except (PermissionError, ValueError) as exc:
                st.error(f"Could not release handover: {exc}")
            else:
                st.session_state["ui_flash_toast"] = (
                    f"Handover version {created_release['version']} released."
                )
                st.rerun()

if normalize_role(user_role) == "Incoming":
    if not release:
        empty_state(
            "No handover has been released yet.",
            "A Reviewer or Admin must release an approved snapshot before it appears here.",
        )
        footer()
        st.stop()
    st.subheader(f"Released handover · Version {release['version']}")
    st.info(
        "This is the latest fixed snapshot a Reviewer approved for release. "
        "Unreleased candidate claims and later edits are not shown here."
    )
    st.caption(
        f"Released {release['released_at']}. This is a fixed snapshot; later claim edits "
        "appear only in a newer release."
    )
    acknowledgement = next(
        (
            item
            for item in release["acknowledgements"]
            if item["user_id"] == "USR-DEMO-INCOMING"
        ),
        None,
    )
    if acknowledgement:
        st.success(
            f"You acknowledged version {release['version']} at "
            f"{acknowledgement['acknowledged_at']}."
        )
    elif st.button(
        f"Acknowledge receipt of version {release['version']}",
        type="primary",
    ):
        try:
            acknowledge_latest_release(user_role, PROJECT_ID)
        except (PermissionError, ValueError) as exc:
            st.error(f"Could not save acknowledgement: {exc}")
        else:
            st.session_state["ui_flash_toast"] = (
                f"Receipt of handover version {release['version']} recorded."
            )
            st.rerun()
    claims_for_display = release["snapshot"]["claims"]
else:
    claims_for_display = approved_claims

if not claims_for_display:
    empty_state(
        "No approved claims are available for this handover.",
        "Approve claims supported only by public sources, then release a new version.",
    )
else:
    claim_types = sorted({claim["claim_type"] for claim in claims_for_display})
    filter_columns = st.columns(2)
    with filter_columns[0]:
        selected_type = st.selectbox("Claim type", ["All types", *claim_types])
    with filter_columns[1]:
        claim_search = st.text_input("Search released claims", placeholder="Type a keyword")
    filtered_claims = claims_for_display
    if selected_type != "All types":
        filtered_claims = [
            claim for claim in filtered_claims if claim["claim_type"] == selected_type
        ]
    if claim_search.strip():
        query = claim_search.casefold().strip()
        filtered_claims = [
            claim
            for claim in filtered_claims
            if query in claim["claim_text"].casefold()
            or query in claim["claim_type"].casefold()
        ]
    page_size = st.selectbox("Claims per page", [10, 25, 50], index=0)
    page_count = max(1, (len(filtered_claims) + page_size - 1) // page_size)
    page_signature = (
        selected_type,
        claim_search.casefold(),
        page_size,
        len(filtered_claims),
    )
    signature_key = f"handover_filter_signature_{PROJECT_ID}"
    page_key = f"handover_page_number_{PROJECT_ID}"
    if st.session_state.get(signature_key) != page_signature:
        st.session_state[signature_key] = page_signature
        st.session_state[page_key] = 1
    page_number = st.selectbox(
        "Handover page",
        range(1, page_count + 1),
        key=page_key,
    )
    start = (page_number - 1) * page_size
    if not filtered_claims:
        empty_state("No released claims match these filters.")
    else:
        st.caption(
            f"Showing claims {start + 1}–{min(start + page_size, len(filtered_claims))} "
            f"of {len(filtered_claims)}."
        )
    for claim in filtered_claims[start : start + page_size]:
        with st.container(border=True):
            st.caption(claim["claim_type"])
            st.markdown(
                f"{trust_badge(claim['trust_status'])} "
                f"{review_badge(claim['review_status'])} "
                f"{origin_badge(claim['claim_source'])}",
                unsafe_allow_html=True,
            )
            st.markdown(claim["claim_text"])
            with st.expander("Source evidence"):
                evidence_list = (
                    claim["evidence"]
                    if normalize_role(user_role) == "Incoming"
                    else get_claim_evidence(user_role, claim["claim_id"])
                )
                if not evidence_list:
                    empty_state("No readable source evidence is available for this claim.")
                for evidence in evidence_list:
                    st.markdown(f"**{evidence['file_name']}**")
                    st.markdown(
                        sensitivity_badge(evidence["sensitivity"]),
                        unsafe_allow_html=True,
                    )
                    st.caption(
                        evidence["reference_location"] or "Source location unavailable"
                    )
                    st.write(evidence["excerpt"])

footer()
