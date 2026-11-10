import streamlit as st
import os
import sys

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import bootstrap, get_connection

bootstrap()

st.set_page_config(page_title="Handover View - HandoverTrail", page_icon="🤝")

st.sidebar.selectbox(
    "Demo role",
    ["Admin", "Reviewer", "Incoming"],
    key="user_role",
    help="Role switching is simulated for this demo.",
)

st.title("🤝 Official Project Handover")
st.markdown("Welcome to the team! Below is the verified, human-approved knowledge you need to get up to speed.")
st.divider()

PROJECT_ID = "PROJ-DEMO-001"

# --- FETCH ONLY APPROVED CLAIMS ---
conn = get_connection()
cursor = conn.cursor()

# STRICT FILTERING: We only query claims where review_status is 'APPROVED'
cursor.execute("""
    SELECT claim_id, claim_text, claim_type, trust_status
    FROM claims
    WHERE project_id = ? AND review_status = 'APPROVED'
    ORDER BY claim_type ASC
""", (PROJECT_ID,))
approved_claims = cursor.fetchall()

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
            trust_badge = "🟢 [VERIFIED]" if c["trust_status"] == "VERIFIED" else "🟡 [SINGLE SOURCE]"
            
            with st.expander(f"{trust_badge} {c['claim_text'][:60]}..."):
                st.write(f"**{c['claim_text']}**")
                
                # Fetch evidence for transparency
                cursor.execute("""
                    SELECT s.file_name, e.reference_location, e.excerpt
                    FROM claim_evidence ce
                    JOIN evidence_chunks e ON ce.evidence_id = e.evidence_id
                    JOIN sources s ON e.source_id = s.source_id
                    WHERE ce.claim_id = ?
                """, (c["claim_id"],))
                evidence = cursor.fetchall()
                
                if evidence:
                    st.markdown("---")
                    st.markdown("#### 🔗 Supporting Evidence")
                    for ev in evidence:
                        st.info(f"📄 **{ev['file_name']}** (`{ev['reference_location']}`)\n> {ev['excerpt']}")
else:
    st.info("No approved claims available for handover yet. A Reviewer needs to approve claims in the Review dashboard.")

conn.close()