from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

from database import DEMO_PROJECT_ID, get_connection

WORKSPACE_QUERY_PARAM = "workspace"
ACTIVE_WORKSPACE_SESSION_KEY = "active_upload_workspace_token"
DEMO_WORKSPACE_TOKEN = "demo"
_WORKSPACE_TOKEN_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def project_id_for_token(token: str | None) -> str:
    if token in (None, "", DEMO_WORKSPACE_TOKEN):
        return DEMO_PROJECT_ID
    if not isinstance(token, str) or not _WORKSPACE_TOKEN_PATTERN.fullmatch(token):
        raise ValueError("This workspace link is invalid. Start a new upload workspace.")
    return f"PROJ-UPLOAD-{token.upper()}"


def ensure_upload_workspace(
    token: str,
    db_path: str | Path | None = None,
) -> str:
    project_id = project_id_for_token(token)
    if project_id == DEMO_PROJECT_ID:
        raise ValueError("The synthetic demo is not an upload workspace.")

    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO projects
                (project_id, name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                project_id,
                f"Upload workspace {token[-6:].upper()}",
                "Isolated uploaded-source workspace; the URL identifies this demo workspace.",
                datetime.now().isoformat(),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        return project_id
    finally:
        conn.close()


def create_upload_workspace(db_path: str | Path | None = None) -> tuple[str, str]:
    token = uuid.uuid4().hex
    return token, ensure_upload_workspace(token, db_path)


def get_active_project_id() -> str:
    token = st.query_params.get(WORKSPACE_QUERY_PARAM)
    if token in (None, ""):
        token = st.session_state.get(ACTIVE_WORKSPACE_SESSION_KEY)
        if token:
            st.query_params[WORKSPACE_QUERY_PARAM] = token
        else:
            return DEMO_PROJECT_ID
    if token == DEMO_WORKSPACE_TOKEN:
        st.session_state.pop(ACTIVE_WORKSPACE_SESSION_KEY, None)
        return DEMO_PROJECT_ID
    try:
        project_id = project_id_for_token(token)
    except ValueError as exc:
        st.error(str(exc))
        st.query_params.pop(WORKSPACE_QUERY_PARAM, None)
        st.session_state.pop(ACTIVE_WORKSPACE_SESSION_KEY, None)
        st.session_state.pop("last_extraction_result", None)
        return DEMO_PROJECT_ID
    if project_id != DEMO_PROJECT_ID:
        st.session_state[ACTIVE_WORKSPACE_SESSION_KEY] = token
        ensure_upload_workspace(token)
    return project_id


def activate_demo_workspace() -> str:
    st.query_params.pop(WORKSPACE_QUERY_PARAM, None)
    st.session_state.pop(ACTIVE_WORKSPACE_SESSION_KEY, None)
    st.session_state.pop("last_extraction_result", None)
    st.session_state.pop("last_extraction_method", None)
    return DEMO_PROJECT_ID


def activate_upload_workspace(*, new_workspace: bool = False) -> str:
    token = None if new_workspace else st.query_params.get(WORKSPACE_QUERY_PARAM)
    if token is None or token == DEMO_WORKSPACE_TOKEN:
        token, project_id = create_upload_workspace()
    else:
        project_id = ensure_upload_workspace(token)
    st.query_params[WORKSPACE_QUERY_PARAM] = token
    st.session_state[ACTIVE_WORKSPACE_SESSION_KEY] = token
    st.session_state.pop("last_extraction_result", None)
    st.session_state.pop("last_extraction_method", None)
    return project_id
