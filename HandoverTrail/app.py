from pathlib import Path
import uuid

import streamlit as st

from database import bootstrap, get_connection
from permissions import can_review
from source_parser import parse_and_store_sources
from ui import configure_page, footer, page_shell
from workspace import activate_demo_workspace

configure_page("HandoverTrail")
bootstrap()

role, _counts = page_shell(
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
    st.caption(
        "Synthetic demo data is available. Custom uploads run in a separate workspace "
        "identified by its link."
    )

    if can_review(role) and st.button("Load demo project", type="primary"):
        project_id = activate_demo_workspace()
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
    elif not can_review(role):
        st.caption("Admin or Reviewer can load the synthetic demo workspace.")

with st.container(border=True):
    if role == "Incoming":
        st.subheader("Your next step")
        st.write("Open the latest snapshot released by the Reviewer.")
        st.page_link(
            "pages/3_Handover_View.py",
            label="Open released handover",
            query_params=dict(st.query_params),
        )
    elif role == "Departing":
        st.subheader("Your next step")
        st.write("Answer only the exit-interview questions assigned to you.")
        st.page_link(
            "pages/4_Exit_Interview.py",
            label="Open assigned interview",
            query_params=dict(st.query_params),
        )
    else:
        st.subheader("Try it in 2 minutes")
        steps = st.columns(3)
        for column, number, instruction in zip(
            steps,
            ("1", "2", "3"),
            (
                "Choose the synthetic demo or create a separate upload workspace.",
                "Extract, validate, and review evidence-linked claims.",
                "Release a fixed handover snapshot for Incoming.",
            ),
        ):
            with column:
                st.markdown(f"**{number}.** {instruction}")

st.caption(
    "Every claim links to source evidence. Restricted sources stay hidden from Incoming. "
    "A human reviewer makes approval decisions."
)
footer()
