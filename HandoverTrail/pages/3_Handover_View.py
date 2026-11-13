import os
import sys

import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import bootstrap
from retrieval import count_hidden_claims, get_claim_evidence, get_visible_claims
from ui import (
    configure_page,
    empty_state,
    footer,
    origin_badge,
    page_shell,
    review_badge,
    sensitivity_badge,
    trust_badge,
)

configure_page("Handover · HandoverTrail")
bootstrap()

PROJECT_ID = "PROJ-DEMO-001"
user_role, _counts = page_shell(
    5,
    "Project handover",
    "Continue the work using human-approved claims and their source evidence.",
)

approved_claims = [
    claim
    for claim in get_visible_claims(user_role, PROJECT_ID)
    if claim["review_status"] == "APPROVED"
]
hidden_count = count_hidden_claims(user_role, PROJECT_ID)
if user_role == "Incoming":
    if hidden_count:
        st.info(
            f"{hidden_count} approved item(s) are hidden because at least one linked source "
            "is restricted or not readable for this role."
        )
    else:
        st.success("No approved items are hidden for this role.")

if not approved_claims:
    empty_state(
        "No approved claims are available for this handover yet.",
        "A Reviewer must approve claims before they appear here.",
    )
else:
    claims_by_type: dict[str, list] = {}
    for claim in approved_claims:
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
                    evidence_list = get_claim_evidence(user_role, claim["claim_id"])
                    if not evidence_list:
                        empty_state("No readable source evidence is available for this claim.")
                    for evidence in evidence_list:
                        st.markdown(f"**{evidence['file_name']}**")
                        st.markdown(
                            sensitivity_badge(evidence["sensitivity"]),
                            unsafe_allow_html=True,
                        )
                        st.caption(evidence["reference_location"] or "Source location unavailable")
                        st.write(evidence["excerpt"])

footer()
