import streamlit as st
import os
import sys

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import bootstrap
from retrieval import count_hidden_claims, get_claim_evidence, get_visible_claims
from ui_helpers import render_role_selector

bootstrap()

st.set_page_config(page_title="Handover View - HandoverTrail", page_icon="🤝")

render_role_selector()

st.title("🤝 Official Project Handover")
st.markdown("Welcome to the team! Below is the human-approved project knowledge you need to get up to speed.")
st.caption(
    "Means the same claim is supported by 2+ different files; it does not yet check that they agree. "
    "Conflict detection is planned."
)
st.divider()

PROJECT_ID = "PROJ-DEMO-001"
user_role = st.session_state["user_role"]

approved_claims = [
    claim for claim in get_visible_claims(user_role, PROJECT_ID)
    if claim["review_status"] == "APPROVED"
]
hidden_count = count_hidden_claims(user_role, PROJECT_ID)
if hidden_count:
    st.info(f"{hidden_count} items hidden: sources you are not authorised to view")

if approved_claims:
    # Group claims by type for a cleaner reading experience
    claims_by_type = {}
    for c in approved_claims:
        ctype = c["claim_type"]
        if ctype not in claims_by_type:
            claims_by_type[ctype] = []
        claims_by_type[ctype].append(c)

    # Render the grouped claims
    for ctype, claims in claims_by_type.items():
        st.subheader(f"📌 {ctype}s")
        for c in claims:
            trust_labels = {
                "VERIFIED": "Corroborated (2+ source files)",
                "SINGLE_SOURCE": "Single source",
                "MISSING_EVIDENCE": "Missing evidence",
                "CONFLICTING": "Conflicting",
            }
            trust_badge = trust_labels.get(c["trust_status"], "Unknown")
            
            with st.expander(f"{trust_badge} {c['claim_text'][:60]}..."):
                st.write(f"**{c['claim_text']}**")
                
                # Fetch evidence for transparency
                evidence = get_claim_evidence(user_role, c["claim_id"])
                
                if evidence:
                    st.markdown("---")
                    st.markdown("#### 🔗 Supporting Evidence")
                    for ev in evidence:
                        st.info(f"📄 **{ev['file_name']}** (`{ev['reference_location']}`)\n> {ev['excerpt']}")
else:
    st.info("No approved claims available for handover yet. A Reviewer needs to approve claims in the Review dashboard.")
