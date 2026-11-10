from pathlib import Path
import uuid
import streamlit as st

from database import bootstrap, get_connection

bootstrap()

st.set_page_config(page_title="HandoverTrail", page_icon="🤝", layout="wide")

st.sidebar.selectbox(
    "Demo role",
    ["Admin", "Reviewer", "Incoming"],
    key="user_role",
    help="Role switching is simulated for this demo.",
)

st.title("HandoverTrail")
st.markdown("Turn scattered project files into a clear, evidence-linked handover.")
st.markdown("Reviewers assess claims against evidence, while incoming teammates see approved project context.")
st.markdown("Load the demo to explore the workflow without uploading your own files.")

st.subheader("Five-step workflow")
st.markdown(
    "1. Connect sources  →  2. Reconstruct claims  →  3. Verify evidence"
    "  →  4. Review claims  →  5. Handover"
)

if st.button("🚀 Load demo project", type="primary"):
    project_id = "PROJ-DEMO-001"
    demo_dir = Path(__file__).resolve().parent / "data" / "demo_project"
    conn = get_connection()
    cursor = conn.cursor()
    added = 0
    for path in sorted(demo_dir.iterdir()):
        if not path.is_file():
            continue
        sensitivity = "restricted" if path.name == "restricted_demo.txt" else "public"
        cursor.execute(
            "SELECT source_id FROM sources WHERE project_id = ? AND file_name = ?",
            (project_id, path.name),
        )
        existing_source = cursor.fetchone()
        if existing_source:
            cursor.execute(
                "UPDATE sources SET sensitivity = ? WHERE source_id = ?",
                (sensitivity, existing_source["source_id"]),
            )
            continue
        cursor.execute(
            """
            INSERT INTO sources (source_id, project_id, file_name, file_type, uploaded_at, sensitivity)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            """,
            (
                f"SRC-{uuid.uuid4().hex[:8].upper()}",
                project_id,
                path.name,
                path.suffix.lstrip(".").upper(),
                sensitivity,
            ),
        )
        added += 1
    conn.commit()
    conn.close()

    from source_parser import parse_and_store_sources

    chunks = parse_and_store_sources(project_id)
    st.success(
        f"Demo project ready: {added} sources registered and {chunks} new evidence chunks loaded. "
        "Cached claims are available on the Review Claims page."
    )

st.info("Use the pages in the sidebar to upload sources, review claims, and view the handover.")
