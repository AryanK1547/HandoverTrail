import os
import sys

import streamlit as st

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from database import bootstrap
from retrieval import get_claim_evidence, get_visible_claims
from ui import (
    configure_page,
    empty_state,
    footer,
    origin_badge,
    page_shell,
    review_badge,
    trust_badge,
)

configure_page("Handover · HandoverTrail")
bootstrap()

PROJECT_ID = "PROJ-DEMO-001"
user_role, _counts = page_shell(
    6,
    "Project handover",
    "Continue the work using human-approved claims and their source evidence.",
)
approved_claims = [
    claim
    for claim in get_visible_claims(user_role, PROJECT_ID)
    if claim["review_status"] == "APPROVED"
]

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
                    for evidence in get_claim_evidence(user_role, claim["claim_id"]):
                        st.markdown(f"**{evidence['file_name']}**")
                        st.caption(evidence["reference_location"] or "Source location unavailable")
                        st.write(evidence["excerpt"])

footer()
