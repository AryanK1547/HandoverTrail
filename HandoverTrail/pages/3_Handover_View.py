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

configure_page("Handover · HandoverTrail")
bootstrap()

PROJECT_ID = "PROJ-DEMO-001"
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
    claims_by_type: dict[str, list] = {}
    for claim in claims_for_display:
        claims_by_type.setdefault(claim["claim_type"], []).append(claim)

    for claim_type, claims in claims_by_type.items():
        st.subheader(claim_type)
        for claim in claims:
            with st.container(border=True):
                st.markdown(
                    f"{trust_badge(claim['trust_status'])} "
                    f"{review_badge(claim['review_status'])} "
                    f"{origin_badge(claim['claim_source'])}",
                    unsafe_allow_html=True,
                )
                st.write(claim["claim_text"])
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
