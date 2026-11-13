import streamlit as st

from database import bootstrap
from retrieval import count_hidden_claims, get_claim_evidence, get_visible_claims
from ui_helpers import render_role_selector

bootstrap()

st.set_page_config(page_title="Handover View - HandoverTrail", page_icon="🤝")

render_role_selector()

st.title("🤝 Official Project Handover")
st.markdown(
    "Welcome to the team! Below is the human-approved project knowledge you need to get up to speed."
)
st.caption(
    "Means the same claim is supported by 2+ different files; it does not yet check that they agree. "
    "Conflict detection is planned."
)

project_id = "PROJ-DEMO-001"
user_role = st.session_state["user_role"]
approved_claims = [
    claim for claim in get_visible_claims(user_role, project_id)
    if claim["review_status"] == "APPROVED"
]
hidden_count = count_hidden_claims(user_role, project_id)
if hidden_count:
    st.info(f"{hidden_count} items hidden: sources you are not authorised to view")

if approved_claims:
    claims_by_type = {}
    for claim in approved_claims:
        claims_by_type.setdefault(claim["claim_type"], []).append(claim)

    for claim_type, claims in claims_by_type.items():
        st.subheader(f"📌 {claim_type}s")
        for claim in claims:
            trust_labels = {
                "VERIFIED": "Corroborated (2+ source files)",
                "SINGLE_SOURCE": "Single source",
                "MISSING_EVIDENCE": "Missing evidence",
                "CONFLICTING": "Conflicting",
            }
            trust_badge = trust_labels.get(claim["trust_status"], "Unknown")
            with st.expander(f"{claim['claim_text'][:60]}..."):
                st.write(claim["claim_text"])
                st.caption(f"Trust Level: {trust_badge}")
                evidence = get_claim_evidence(user_role, claim["claim_id"])
                if evidence:
                    st.markdown("**Supporting Evidence:**")
                    for item in evidence:
                        st.info(
                            f"📄 {item['file_name']} (`{item['reference_location']}`)\n"
                            f"> {item['excerpt']}"
                        )
else:
    st.info(
        "No approved claims available for handover yet. "
        "A Reviewer needs to approve claims in the Review dashboard."
    )
