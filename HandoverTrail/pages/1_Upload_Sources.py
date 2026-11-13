import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import PROJECT_ROOT, bootstrap, get_connection
from retrieval import get_visible_evidence_chunks, get_visible_sources
from source_parser import (
    parse_and_store_sources,
    persist_uploaded_file,
    sanitize_upload_filename,
)
from ui import (
    configure_page,
    empty_state,
    footer,
    page_shell,
    render_stats_for_role,
    sensitivity_badge,
    show_flash_toast,
)

configure_page("Connect sources · HandoverTrail")
bootstrap()

role, counts = page_shell(
    1,
    "Connect sources",
    "Add meeting notes, chat exports, repository records, and task files.",
)
show_flash_toast()
for upload_warning in st.session_state.pop("ui_upload_warnings", []):
    st.warning(upload_warning)
render_stats_for_role(role, counts)

PROJECT_ID = "PROJ-DEMO-001"

demo_tab, upload_tab = st.tabs(["Load demo", "Upload files"])

with demo_tab:
    with st.container(border=True):
        st.subheader("Synthetic project data")
        st.write(
            "Use the packaged example files to try the workflow. The sample data is synthetic."
        )
        if st.button(
            "Load pre-packaged demo files",
            type="primary",
        ):
            demo_dir = PROJECT_ROOT / "data" / "demo_project"
            conn = get_connection()
            try:
                cursor = conn.cursor()
                loaded_count = 0
                for path in sorted(demo_dir.iterdir()):
                    if not path.is_file():
                        continue
                    file_name = path.name
                    sensitivity = "restricted" if file_name == "restricted_demo.txt" else "public"
                    existing = cursor.execute(
                        "SELECT source_id FROM sources WHERE project_id = ? AND file_name = ?",
                        (PROJECT_ID, file_name),
                    ).fetchone()
                    if existing:
                        cursor.execute(
                            "UPDATE sources SET sensitivity = ? WHERE source_id = ?",
                            (sensitivity, existing["source_id"]),
                        )
                    else:
                        cursor.execute(
                            """
                            INSERT INTO sources
                                (source_id, project_id, file_name, file_type, uploaded_at, sensitivity)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                f"SRC-{uuid.uuid4().hex[:8].upper()}",
                                PROJECT_ID,
                                file_name,
                                path.suffix.lstrip(".").upper(),
                                datetime.now().isoformat(),
                                sensitivity,
                            ),
                        )
                        loaded_count += 1
                conn.commit()
            finally:
                conn.close()
            if loaded_count:
                st.session_state["ui_flash_toast"] = (
                    f"Registered {loaded_count} synthetic source files."
                )
            else:
                st.session_state["ui_flash_toast"] = (
                    "The synthetic demo files are already registered."
                )
            st.rerun()

with upload_tab:
    with st.container(border=True):
        st.subheader("Upload custom files")
        st.caption("Accepted formats: .txt and .csv. Maximum size: 2 MB per file.")
        with st.form("source_upload_form"):
            uploaded_files = st.file_uploader(
                "Choose source files",
                type=["txt", "csv"],
                accept_multiple_files=True,
            )
            sensitivity = st.selectbox(
                "Source sensitivity",
                ["restricted", "public"],
                index=0,
                format_func=str.title,
            )
            upload_submitted = st.form_submit_button(
                "Save and process uploaded files",
                type="primary",
            )

        if upload_submitted and uploaded_files:
            conn = get_connection()
            try:
                cursor = conn.cursor()
                changed_source_ids = []
                saved_files = []
                replaced_files = []
                rejected_files = []

                for uploaded_file in uploaded_files:
                    try:
                        file_name = sanitize_upload_filename(uploaded_file.name)
                        saved_path, path_replaced = persist_uploaded_file(
                            PROJECT_ID,
                            file_name,
                            uploaded_file.getvalue(),
                        )
                    except ValueError as exc:
                        rejected_files.append(f"{uploaded_file.name}: {exc}")
                        continue

                    existing = cursor.execute(
                        "SELECT source_id FROM sources WHERE project_id = ? AND file_name = ?",
                        (PROJECT_ID, file_name),
                    ).fetchone()
                    replaced = path_replaced or existing is not None
                    if existing:
                        source_id = existing["source_id"]
                        cursor.execute(
                            """
                            UPDATE sources
                            SET file_type = ?, uploaded_at = ?, sensitivity = ?
                            WHERE source_id = ?
                            """,
                            (
                                Path(file_name).suffix.lstrip(".").upper(),
                                datetime.now().isoformat(),
                                sensitivity,
                                source_id,
                            ),
                        )
                    else:
                        source_id = f"SRC-{uuid.uuid4().hex[:8].upper()}"
                        cursor.execute(
                            """
                            INSERT INTO sources
                                (source_id, project_id, file_name, file_type, uploaded_at, sensitivity)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                source_id,
                                PROJECT_ID,
                                file_name,
                                Path(file_name).suffix.lstrip(".").upper(),
                                datetime.now().isoformat(),
                                sensitivity,
                            ),
                        )
                    changed_source_ids.append(source_id)
                    saved_files.append((file_name, saved_path))
                    if replaced:
                        replaced_files.append(file_name)
                conn.commit()
            finally:
                conn.close()

            if changed_source_ids:
                chunks_created = parse_and_store_sources(
                    PROJECT_ID,
                    source_ids=changed_source_ids,
                )
                summary = (
                    f"Saved {len(saved_files)} file(s), created {chunks_created} evidence "
                    "excerpts, and replaced "
                    f"{len(replaced_files)} existing file(s)."
                )
                st.session_state["ui_flash_toast"] = summary
                st.session_state["ui_upload_warnings"] = rejected_files
                st.rerun()
            for message in rejected_files:
                st.warning(message)
        elif upload_submitted:
            st.info("Choose at least one .txt or .csv file to upload.")

st.subheader("Current sources")
sources = get_visible_sources(role, PROJECT_ID)
if sources:
    for source in sources:
        with st.container(border=True):
            st.markdown(sensitivity_badge(source["sensitivity"]), unsafe_allow_html=True)
            st.write(source["file_name"])
            st.caption(f"{source['file_type']} · Added {source['uploaded_at']}")
else:
    empty_state(
        "No sources are available for this role yet.",
        "Load the synthetic demo or upload a .txt or .csv file.",
    )

with st.container(border=True):
    st.subheader("Parse source files")
    st.write("Create searchable evidence excerpts from registered sources.")
    if st.button("Parse unprocessed sources"):
        new_chunks = parse_and_store_sources(PROJECT_ID)
        if new_chunks:
            st.success(f"Created {new_chunks} evidence excerpts.")
        else:
            st.info("All registered sources already have evidence excerpts.")

st.subheader("Evidence excerpts")
evidence_rows = get_visible_evidence_chunks(role, PROJECT_ID)
if evidence_rows:
    for evidence in evidence_rows:
        with st.expander(
            f"{evidence['file_name']} · {evidence['reference_location'] or 'Source excerpt'}"
        ):
            st.write(evidence["excerpt"])
            st.caption(f"Evidence ID: {evidence['evidence_id']}")
else:
    empty_state(
        "No evidence excerpts are available for this role.",
        "Parse registered sources to create excerpts that can support claims.",
    )

footer()
