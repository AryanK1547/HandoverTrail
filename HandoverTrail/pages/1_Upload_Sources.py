import streamlit as st
import os
import uuid
from datetime import datetime
from pathlib import Path
import sys

# Ensure parent directory is in path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import PROJECT_ROOT, bootstrap, get_connection
from source_parser import parse_and_store_sources, persist_uploaded_file, sanitize_upload_filename
from retrieval import get_visible_evidence_chunks, get_visible_sources
from ui_helpers import render_role_selector

bootstrap()

st.set_page_config(page_title="Upload Sources - HandoverTrail", page_icon="📁")

render_role_selector()

st.title("📁 Upload Project Sources")
st.markdown("Upload meeting notes, chat logs, git exports, or task CSVs to begin knowledge extraction.")

# Target project ID for MVP session
PROJECT_ID = "PROJ-DEMO-001"

# --- DEMO DATA LOADER BUTTON ---
st.subheader("Option A: Load Demo Synthetic Dataset")
if st.button("🚀 Load Pre-packaged Demo Files"):
    demo_dir = PROJECT_ROOT / "data" / "demo_project"
    if os.path.exists(demo_dir):
        loaded_count = 0
        conn = get_connection()
        cursor = conn.cursor()
        
        for file_name in os.listdir(demo_dir):
            file_path = os.path.join(demo_dir, file_name)
            if os.path.isfile(file_path):
                source_id = f"SRC-{uuid.uuid4().hex[:8].upper()}"
                file_type = file_name.split(".")[-1].upper()
                sensitivity = "restricted" if file_name == "restricted_demo.txt" else "public"
                uploaded_at = datetime.now().isoformat()
                
                # Check if already loaded
                cursor.execute("SELECT source_id FROM sources WHERE project_id = ? AND file_name = ?", (PROJECT_ID, file_name))
                existing_source = cursor.fetchone()
                if existing_source:
                    cursor.execute(
                        "UPDATE sources SET sensitivity = ? WHERE source_id = ?",
                        (sensitivity, existing_source["source_id"]),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO sources
                            (source_id, project_id, file_name, file_type, uploaded_at, sensitivity)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (source_id, PROJECT_ID, file_name, file_type, uploaded_at, sensitivity)
                    )
                    loaded_count += 1
        
        conn.commit()
        conn.close()
        
        if loaded_count > 0:
            st.success(f"Successfully loaded {loaded_count} demo files into the database!")
        else:
            st.info("Demo files have already been loaded into the database.")
    else:
        st.error(f"Demo directory `{demo_dir}` not found.")

st.divider()

# --- FILE UPLOADER UI ---
st.subheader("Option B: Upload Custom Source Files")
with st.form("source_upload_form"):
    uploaded_files = st.file_uploader(
        "Choose files (.txt, .csv; maximum 2 MB per file)",
        type=["txt", "csv"],
        accept_multiple_files=True,
    )
    sensitivity = st.selectbox(
        "Source sensitivity",
        ["restricted", "public"],
        index=0,
        format_func=str.title,
    )
    upload_submitted = st.form_submit_button("Save and process uploaded files")

if upload_submitted and uploaded_files:
    conn = get_connection()
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
            cursor.execute("""
                UPDATE sources
                SET file_type = ?, uploaded_at = ?, sensitivity = ?
                WHERE source_id = ?
            """, (Path(file_name).suffix.lstrip(".").upper(), datetime.now().isoformat(), sensitivity, source_id))
        else:
            source_id = f"SRC-{uuid.uuid4().hex[:8].upper()}"
            cursor.execute("""
                INSERT INTO sources
                    (source_id, project_id, file_name, file_type, uploaded_at, sensitivity)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                source_id,
                PROJECT_ID,
                file_name,
                Path(file_name).suffix.lstrip(".").upper(),
                datetime.now().isoformat(),
                sensitivity,
            ))
        changed_source_ids.append(source_id)
        saved_files.append((file_name, saved_path))
        if replaced:
            replaced_files.append(file_name)

    conn.commit()
    conn.close()

    for message in rejected_files:
        st.warning(message)
    if changed_source_ids:
        chunks_created = parse_and_store_sources(PROJECT_ID, source_ids=changed_source_ids)
        for file_name, _ in saved_files:
            st.success(f"Saved {file_name} ({sensitivity}) and parsed its updated evidence.")
        for file_name in replaced_files:
            st.info(f"Replaced existing file: {file_name}")
        st.success(f"Created {chunks_created} evidence chunks from updated uploads.")
elif upload_submitted:
    st.info("Choose at least one .txt or .csv file to upload.")

st.divider()

# --- CURRENT SOURCES IN DB ---
st.subheader("📋 Currently Uploaded Sources")
conn = get_connection()
cursor = conn.cursor()
conn.close()
rows = get_visible_sources(st.session_state["user_role"], PROJECT_ID)

if rows:
    sources_data = [{"Source ID": r["source_id"], "File Name": r["file_name"], "Type": r["file_type"], "Sensitivity": r["sensitivity"], "Uploaded At": r["uploaded_at"]} for r in rows]
    st.table(sources_data)
else:
    st.info("No sources registered yet. Load demo files or upload files above.")

# --- STEP 2: SOURCE PARSING UI ---
st.divider()
st.subheader("⚙️ Parse Sources into Evidence Chunks")

if st.button("🔨 Process & Chunk Uploaded Sources"):
    new_chunks = parse_and_store_sources(PROJECT_ID)
    if new_chunks > 0:
        st.success(f"Successfully created and stored {new_chunks} evidence chunks for unprocessed sources!")
    else:
        st.info("All registered sources already have evidence chunks.")

# --- INSPECT EVIDENCE CHUNKS ---
st.subheader("🔍 Generated Evidence Chunks")

evidence_rows = get_visible_evidence_chunks(st.session_state["user_role"], PROJECT_ID)

if evidence_rows:
    evd_data = [
        {
            "Evidence ID": r["evidence_id"],
            "Source File": r["file_name"],
            "Reference Location": r["reference_location"],
            "Excerpt": r["excerpt"]
        }
        for r in evidence_rows
    ]
    st.dataframe(evd_data, width="stretch")
    st.caption(f"Total Evidence Chunks stored: {len(evd_data)}")
else:
    st.info("No evidence chunks parsed yet. Click 'Process & Chunk Uploaded Sources' above.")