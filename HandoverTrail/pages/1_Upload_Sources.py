import streamlit as st
import os
import uuid
from datetime import datetime
import sys

# Ensure parent directory is in path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import get_connection, init_db

st.set_page_config(page_title="Upload Sources - HandoverTrail", page_icon="📁")

st.title("📁 Upload Project Sources")
st.markdown("Upload meeting notes, chat logs, git exports, or task CSVs to begin knowledge extraction.")

# Ensure database exists
init_db()

# Target project ID for MVP session
PROJECT_ID = "PROJ-DEMO-001"

# Guarantee default demo project exists in DB
conn = get_connection()
cursor = conn.cursor()
cursor.execute("SELECT project_id FROM projects WHERE project_id = ?", (PROJECT_ID,))
if not cursor.fetchone():
    cursor.execute(
        "INSERT INTO projects (project_id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (PROJECT_ID, "Demo Project (Team Techtones)", "HandoverTrail MVP Demonstration Project", datetime.now().isoformat(), datetime.now().isoformat())
    )
    conn.commit()
conn.close()

# --- DEMO DATA LOADER BUTTON ---
st.subheader("Option A: Load Demo Synthetic Dataset")
if st.button("🚀 Load Pre-packaged Demo Files"):
    demo_dir = os.path.join("data", "demo_project")
    if os.path.exists(demo_dir):
        loaded_count = 0
        conn = get_connection()
        cursor = conn.cursor()
        
        for file_name in os.listdir(demo_dir):
            file_path = os.path.join(demo_dir, file_name)
            if os.path.isfile(file_path):
                source_id = f"SRC-{uuid.uuid4().hex[:8].upper()}"
                file_type = file_name.split(".")[-1].upper()
                uploaded_at = datetime.now().isoformat()
                
                # Check if already loaded
                cursor.execute("SELECT source_id FROM sources WHERE project_id = ? AND file_name = ?", (PROJECT_ID, file_name))
                if not cursor.fetchone():
                    cursor.execute(
                        "INSERT INTO sources (source_id, project_id, file_name, file_type, uploaded_at) VALUES (?, ?, ?, ?, ?)",
                        (source_id, PROJECT_ID, file_name, file_type, uploaded_at)
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
uploaded_files = st.file_uploader(
    "Choose files (.txt, .csv)", 
    type=["txt", "csv"], 
    accept_multiple_files=True
)

if uploaded_files:
    conn = get_connection()
    cursor = conn.cursor()
    saved_count = 0
    
    for uploaded_file in uploaded_files:
        source_id = f"SRC-{uuid.uuid4().hex[:8].upper()}"
        file_name = uploaded_file.name
        file_type = file_name.split(".")[-1].upper()
        uploaded_at = datetime.now().isoformat()
        
        # Avoid duplicate filename records for demo stability
        cursor.execute("SELECT source_id FROM sources WHERE project_id = ? AND file_name = ?", (PROJECT_ID, file_name))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO sources (source_id, project_id, file_name, file_type, uploaded_at) VALUES (?, ?, ?, ?, ?)",
                (source_id, PROJECT_ID, file_name, file_type, uploaded_at)
            )
            saved_count += 1
            
    conn.commit()
    conn.close()
    if saved_count > 0:
        st.success(f"Successfully registered {saved_count} file(s) in database!")

st.divider()

# --- CURRENT SOURCES IN DB ---
st.subheader("📋 Currently Uploaded Sources")
conn = get_connection()
cursor = conn.cursor()
cursor.execute("SELECT source_id, file_name, file_type, uploaded_at FROM sources WHERE project_id = ?", (PROJECT_ID,))
rows = cursor.fetchall()
conn.close()

if rows:
    sources_data = [{"Source ID": r["source_id"], "File Name": r["file_name"], "Type": r["file_type"], "Uploaded At": r["uploaded_at"]} for r in rows]
    st.table(sources_data)
else:
    st.info("No sources registered yet. Load demo files or upload files above.")