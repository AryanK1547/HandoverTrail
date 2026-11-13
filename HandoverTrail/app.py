from pathlib import Path
import uuid

import streamlit as st

from database import bootstrap, get_connection
from source_parser import parse_and_store_sources
from ui import configure_page, footer, page_shell

configure_page("HandoverTrail")
bootstrap()

page_shell(
    1,
    "HandoverTrail",
    "Turn scattered project files into a clear, evidence-linked handover.",
)

with st.container(border=True):
    st.subheader("A safer way to pass project knowledge")
    st.write(
        "Reviewers assess claims against source evidence. Incoming teammates see "
        "approved context supported only by sources they can access."
    )
    st.caption("Synthetic demo data is available so you can explore without uploading project files.")

    if st.button("Load demo project", type="primary"):
        project_id = "PROJ-DEMO-001"
        demo_dir = Path(__file__).resolve().parent / "data" / "demo_project"
        conn = get_connection()
        try:
            cursor = conn.cursor()
            added = 0
            for path in sorted(demo_dir.iterdir()):
                if not path.is_file():
                    continue
                sensitivity = "restricted" if path.name == "restricted_demo.txt" else "public"
                existing_source = cursor.execute(
                    "SELECT source_id FROM sources WHERE project_id = ? AND file_name = ?",
                    (project_id, path.name),
                ).fetchone()
                if existing_source:
                    cursor.execute(
                        "UPDATE sources SET sensitivity = ? WHERE source_id = ?",
                        (sensitivity, existing_source["source_id"]),
                    )
                    continue
                cursor.execute(
                    """
                    INSERT INTO sources
                        (source_id, project_id, file_name, file_type, uploaded_at, sensitivity)
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
        finally:
            conn.close()

        chunks = parse_and_store_sources(project_id)
        st.success(
            f"Demo project ready: {added} sources registered and {chunks} new evidence "
            "excerpts loaded. Cached claims are available in Review Claims."
        )

with st.container(border=True):
    st.subheader("Try it in 2 minutes")
    steps = st.columns(3)
    for column, number, instruction in zip(
        steps,
        ("1", "2", "3"),
        (
            "Connect synthetic or custom sources.",
            "Inspect evidence-linked claims and review them.",
            "Switch to Incoming and view permitted handover context.",
        ),
    ):
        with column:
            st.markdown(f"**{number}.** {instruction}")

st.caption(
    "Every claim links to source evidence. Restricted sources stay hidden from Incoming. "
    "A human reviewer makes approval decisions."
)
footer()
