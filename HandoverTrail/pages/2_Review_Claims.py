import streamlit as st
import os
import sys

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import bootstrap
from extractor import extract_claims_from_evidence
from permissions import can_review, perform_claim_review
from retrieval import get_claim_evidence, get_visible_claims
from validator import validate_project_claims

bootstrap()

st.set_page_config(page_title="Review Claims - HandoverTrail", page_icon="⚖️")

st.sidebar.selectbox(
    "Demo role",
    ["Admin", "Reviewer", "Incoming"],
    key="user_role",
    help="Role switching is simulated for this demo.",
)

st.title("⚖️ Candidate Claims & Verification Engine")
st.markdown("Extract structured claims from evidence, inspect linked sources, and perform human reviews.")

PROJECT_ID = "PROJ-DEMO-001"
user_role = st.session_state["user_role"]

# --- EXTRACTION & VALIDATION CONTROLS ---
st.subheader("⚡ Action Controls")

# API keys stay in Streamlit secrets and are never displayed in the UI.
api_key_secret = st.secrets.get("GEMINI_API_KEY", None)
openrouter_api_key_secret = st.secrets.get("OPENROUTER_API_KEY", None)
openrouter_model = st.secrets.get("OPENROUTER_MODEL", "openrouter/auto")

col1, col2 = st.columns(2)

with col1:
    if st.button("🤖 1. Extract Claims", width="stretch", disabled=not can_review(user_role)):
        progress_bar = st.progress(0, text="Starting claim extraction...")

        def update_extraction_progress(value, message):
            progress_bar.progress(value, text=message)

        res = extract_claims_from_evidence(
            PROJECT_ID,
            api_key=api_key_secret,
            openrouter_api_key=openrouter_api_key_secret,
            openrouter_model=openrouter_model,
            progress_callback=update_extraction_progress,
        )
        if res.get("status") == "success":
            st.success(f"Generated {res['claims_created']} claims using [{res['method']}]!")
            if res.get("fallback_reason"):
                if res["method"] == "Universal Keyword Fallback":
                    st.warning(f"AI providers unavailable. {res['fallback_reason']}")
                else:
                    st.info(res["fallback_reason"])
        else:
            st.error(res.get("message"))

with col2:
    if st.button("🔍 2. Validate Evidence", width="stretch", disabled=not can_review(user_role)):
        try:
            count = validate_project_claims(user_role, PROJECT_ID)
        except PermissionError as exc:
            st.error(f"Validation not permitted: {exc}")
        else:
            st.success(f"Validated {count} claims based on database evidence links!")

if not can_review(user_role):
    st.info("Select Admin or Reviewer to extract, validate, or review claims.")

st.divider()

# --- CLAIMS & EVIDENCE INSPECTION QUEUE ---
st.subheader("📋 Candidate Claims Queue")
claims = get_visible_claims(user_role, PROJECT_ID)

if claims:
    for c in claims:
        claim_id = c["claim_id"]
        
        # Determine badge color based on trust status
        trust_color = "🟢" if c["trust_status"] == "VERIFIED" else "🟡" if c["trust_status"] == "SINGLE_SOURCE" else "🔴"
        review_icon = "⏳" if c["review_status"] == "PENDING" else "✅" if c["review_status"] == "APPROVED" else "❌"
        
        with st.expander(f"{review_icon} {trust_color} [{c['trust_status']}] [{c['claim_type']}] {c['claim_text'][:80]}..."):
            st.write("**Full Claim Text:**", c["claim_text"])
            st.write(f"**Claim ID:** `{claim_id}` | **Type:** `{c['claim_type']}` | **Review Status:** `{c['review_status']}`")

            # Fetch linked evidence chunks for this claim
            evd_list = get_claim_evidence(user_role, claim_id)

            if evd_list:
                st.markdown("#### 🔗 Linked Evidence Sources")
                for ev in evd_list:
                    st.info(f"**Source:** {ev['file_name']} (`{ev['reference_location']}`)\n\n> {ev['excerpt']}")
            else:
                st.warning("⚠️ No evidence chunks linked to this claim!")
            
            # --- THE REVIEW BUTTONS ---
            if can_review(user_role) and c["review_status"] == "PENDING":
                st.markdown("#### ✍️ Human Review Action")
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if st.button("✅ Approve Claim", key=f"app_{claim_id}", width="stretch"):
                        try:
                            perform_claim_review(user_role, claim_id, "APPROVED")
                        except PermissionError as exc:
                            st.error(f"Review not permitted: {exc}")
                        else:
                            st.rerun()
                with btn_col2:
                    if st.button("❌ Reject Claim", key=f"rej_{claim_id}", width="stretch"):
                        try:
                            perform_claim_review(user_role, claim_id, "REJECTED")
                        except PermissionError as exc:
                            st.error(f"Review not permitted: {exc}")
                        else:
                            st.rerun()