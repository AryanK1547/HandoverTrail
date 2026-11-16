import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import DEMO_PROJECT_ID, bootstrap, get_connection
from permissions import can_review
from retrieval import get_visible_evidence_chunks, get_visible_sources
from source_parser import (
    count_unparsed_sources,
    parse_and_store_sources,
    persist_uploaded_file,
    register_demo_sources,
    sanitize_upload_filename,
)
from ui import (
    configure_page,
    empty_state,
    footer,
    page_navigation,
    page_shell,
    render_stats_for_role,
    sensitivity_badge,
    show_flash_toast,
)
from workspace import (
    activate_demo_workspace,
    activate_upload_workspace,
    get_active_project_id,
)

configure_page("Connect sources · HandoverTrail")
bootstrap()
PROJECT_ID = get_active_project_id()

role, counts = page_shell(
    1,
    "Connect sources",
    "Add meeting notes, chat exports, repository records, and task files.",
)
show_flash_toast()
if PROJECT_ID == DEMO_PROJECT_ID:
    st.info(
        "Active workspace: Demo project. Saving uploaded files creates a separate "
        "upload workspace; demo sources stay in the demo project."
    )
else:
    st.caption(
        f"Active workspace: Upload workspace {PROJECT_ID[-6:]}. It stays separate from "
        "the demo and is restored by its workspace link."
    )
if not can_review(role):
    st.info("Only Admin or Reviewer can add or parse sources.")
    if role == "Departing":
        st.page_link(
            "pages/4_Exit_Interview.py",
            label="Open your assigned interview",
            query_params=dict(st.query_params),
        )
    else:
        st.page_link(
            "pages/3_Handover_View.py",
            label="Go to the released handover",
            query_params=dict(st.query_params),
        )
    footer()
    st.stop()
upload_success = st.session_state.pop("ui_upload_success", None)
if upload_success:
    st.success(upload_success)
    st.page_link(
        "pages/2_Review_Claims.py",
        label="Continue: extract claims from these sources →",
        query_params=dict(st.query_params),
    )
for upload_warning in st.session_state.pop("ui_upload_warnings", []):
    st.warning(upload_warning)
render_stats_for_role(role, counts)

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
            PROJECT_ID = activate_demo_workspace()
            try:
                loaded_count = register_demo_sources(PROJECT_ID)
                parsed_chunks = parse_and_store_sources(PROJECT_ID, prefer_demo=True)
            except (OSError, ValueError) as exc:
                st.error(
                    f"The demo files could not be loaded: {exc} "
                    "No claims were changed; you can retry."
                )
            else:
                if loaded_count or parsed_chunks:
                    st.session_state["ui_flash_toast"] = (
                        f"Registered {loaded_count} synthetic source file(s) and parsed "
                        f"{parsed_chunks} evidence excerpt(s)."
                    )
                else:
                    st.session_state["ui_flash_toast"] = (
                        "The synthetic demo files are already registered and parsed."
                    )
                st.rerun()

with upload_tab:
    with st.container(border=True):
        st.subheader("Upload custom files")
        st.caption(
            "Accepted formats: .txt, .md, and .csv. Maximum size: 2 MB per file. "
            "Uploads use a separate workspace; demo claims and evidence are not included."
        )
        if st.button("Start a new upload workspace"):
            activate_upload_workspace(new_workspace=True)
            st.session_state["ui_flash_toast"] = "Started a separate, empty upload workspace."
            st.rerun()
        with st.form("source_upload_form", clear_on_submit=True):
            uploaded_files = st.file_uploader(
                "Choose source files",
                type=["txt", "md", "csv"],
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
            PROJECT_ID = activate_upload_workspace()
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
                            SET file_type = ?, uploaded_at = ?, sensitivity = ?,
                                source_type = 'upload'
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
                                (source_id, project_id, file_name, file_type, uploaded_at,
                                 sensitivity, source_type)
                            VALUES (?, ?, ?, ?, ?, ?, 'upload')
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

            rejected_messages = [
                f"Not saved — {message}" for message in rejected_files
            ]
            if changed_source_ids:
                try:
                    chunks_created = parse_and_store_sources(
                        PROJECT_ID,
                        source_ids=changed_source_ids,
                    )
                except (OSError, ValueError) as exc:
                    st.session_state["ui_upload_warnings"] = [
                        f"Saved {len(saved_files)} file(s), but parsing failed: {exc} "
                        "The files remain registered; use Parse unprocessed sources to retry.",
                        *rejected_messages,
                    ]
                else:
                    saved_names = ", ".join(name for name, _path in saved_files)
                    summary = (
                        f"Saved {len(saved_files)} of {len(uploaded_files)} file(s) "
                        f"({saved_names}), created {chunks_created} evidence "
                        "excerpts, and replaced "
                        f"{len(replaced_files)} existing file(s)."
                    )
                    st.session_state["ui_flash_toast"] = summary
                    st.session_state["ui_upload_success"] = summary
                    st.session_state["ui_upload_warnings"] = rejected_messages
                st.rerun()
            st.error("No file was saved. Fix the problems below and upload again.")
            for message in rejected_messages:
                st.warning(message)
        elif upload_submitted:
            st.info("Choose at least one .txt, .md, or .csv file to upload.")

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
        "Load the synthetic demo or upload a .txt, .md, or .csv file.",
    )

unparsed_sources = count_unparsed_sources(PROJECT_ID)
with st.container(border=True):
    st.subheader("Parse source files")
    if unparsed_sources:
        st.write(
            f"{unparsed_sources} registered source(s) have no evidence excerpts yet. "
            "Parsing creates the searchable excerpts that claims cite."
        )
    else:
        st.caption(
            "Uploads are parsed automatically when they are saved. Every registered "
            "source already has evidence excerpts."
        )
    if st.button("Parse unprocessed sources", disabled=not unparsed_sources):
        try:
            new_chunks = parse_and_store_sources(PROJECT_ID)
        except (OSError, ValueError) as exc:
            st.error(
                f"Parsing did not finish: {exc} Existing excerpts and claims are "
                "unchanged. Upload the file again, then retry."
            )
        else:
            st.session_state["ui_flash_toast"] = (
                f"Created {new_chunks} evidence excerpts."
                if new_chunks
                else "No readable content was found in the unprocessed sources."
            )
            st.rerun()
    if sources and not unparsed_sources:
        st.page_link(
            "pages/2_Review_Claims.py",
            label="Continue: extract and review claims →",
            query_params=dict(st.query_params),
        )

st.subheader("Evidence excerpts")
evidence_rows = get_visible_evidence_chunks(role, PROJECT_ID)
if evidence_rows:
    source_names = sorted({row["file_name"] for row in evidence_rows})
    source_filter = st.selectbox(
        "Evidence source",
        ["All sources", *source_names],
        key=f"evidence_source_{PROJECT_ID}",
    )
    if source_filter != "All sources":
        evidence_rows = [
            row for row in evidence_rows if row["file_name"] == source_filter
        ]
    page_size = st.selectbox(
        "Excerpts per page",
        [10, 25, 50],
        key=f"evidence_page_size_{PROJECT_ID}",
    )
    page_count = max(1, (len(evidence_rows) + page_size - 1) // page_size)
    page_number = st.selectbox(
        "Evidence page",
        range(1, page_count + 1),
        key=f"evidence_page_{PROJECT_ID}_{source_filter}_{page_size}_{len(evidence_rows)}",
    )
    start = (page_number - 1) * page_size
    st.caption(
        f"Showing {start + 1}–{min(start + page_size, len(evidence_rows))} "
        f"of {len(evidence_rows)} excerpts."
    )
    for evidence in evidence_rows[start : start + page_size]:
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

page_navigation(
    following=(("Extract and review claims", "pages/2_Review_Claims.py"),) if sources else (),
)
footer()
