import streamlit as st

from database import DEMO_PROJECT_ID, bootstrap
from permissions import can_review
from source_parser import parse_and_store_sources, register_demo_sources
from ui import configure_page, footer, page_shell, show_flash_toast
from validator import validate_project_claims
from workspace import activate_demo_workspace, get_active_project_id

configure_page("HandoverTrail")
bootstrap()

role, counts = page_shell(
    1,
    "HandoverTrail",
    "Turn scattered project files into a clear, evidence-linked handover.",
)
show_flash_toast()
query_params = dict(st.query_params)

with st.container(border=True):
    st.subheader("New here? Take the guided tour")
    st.write(
        "Ten steps, about ten minutes: verify evidence, resolve a conflict, run the exit "
        "interview, release a handover, and pick it up as the incoming teammate. Each step "
        "opens the right page as the right role, and it keeps your progress."
    )
    st.page_link(
        "pages/0_Guided_Tour.py",
        label="Start the guided tour →",
        query_params=query_params,
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

    if can_review(role):
        demo_column, upload_column = st.columns(2)
        with demo_column:
            if st.button("Load demo project", type="primary"):
                project_id = activate_demo_workspace()
                try:
                    added = register_demo_sources(project_id)
                    chunks = parse_and_store_sources(project_id, prefer_demo=True)
                    checked = validate_project_claims(role, project_id)
                except (OSError, ValueError, PermissionError) as exc:
                    st.error(
                        f"The demo project could not be loaded: {exc} "
                        "Nothing was changed; you can retry."
                    )
                else:
                    st.session_state["ui_flash_toast"] = (
                        f"Demo project ready: {added} new source(s) registered, "
                        f"{chunks} new evidence excerpt(s) parsed, and {checked} claim(s) "
                        "checked against their evidence."
                    )
                    st.switch_page("pages/2_Review_Claims.py")
            st.caption("Opens the synthetic project with cached claims ready to review.")
        with upload_column:
            st.page_link(
                "pages/1_Upload_Sources.py",
                label="Upload your own files →",
                query_params=query_params,
            )
            st.caption("Starts a separate workspace; demo claims are not included.")
    else:
        st.caption("Admin or Reviewer can load the synthetic demo workspace.")

with st.container(border=True):
    if role == "Incoming":
        st.subheader("Your next step")
        st.write("Open the latest snapshot released by the Reviewer.")
        st.page_link(
            "pages/3_Handover_View.py",
            label="Open released handover",
            query_params=query_params,
        )
    elif role == "Departing":
        st.subheader("Your next step")
        st.write("Answer only the exit-interview questions assigned to you.")
        st.page_link(
            "pages/4_Exit_Interview.py",
            label="Open assigned interview",
            query_params=query_params,
        )
    else:
        st.subheader("How a handover moves through HandoverTrail")
        workspace_label = (
            "the synthetic demo project"
            if get_active_project_id() == DEMO_PROJECT_ID
            else "your upload workspace"
        )
        st.caption(f"Progress shown for {workspace_label}.")
        journey = (
            (
                "Connect sources",
                f"{counts['sources']} source(s), {counts['evidence']} excerpt(s)",
                counts["evidence"] > 0,
            ),
            (
                "Extract and validate claims",
                f"{counts['claims']} claim(s), {counts['unvalidated']} not validated",
                counts["claims"] > 0 and not counts["unvalidated"],
            ),
            (
                "Review claims",
                f"{counts['pending']} pending, {counts['approved']} approved",
                counts["claims"] > 0 and not counts["pending"],
            ),
            (
                "Exit interview (optional)",
                f"{counts['open_gaps']} open gap(s), "
                f"{counts['answered_questions']} answer(s) recorded",
                counts["answered_questions"] > 0 and not counts["interview_questions"],
            ),
            (
                "Release handover",
                (
                    f"Version {counts['release_version']} released"
                    if counts["release_version"]
                    else "Not released yet"
                ),
                bool(counts["release_version"]) and not counts["release_needed"],
            ),
            (
                "Incoming acknowledges",
                "Acknowledged" if counts["release_acknowledged"] else "Not acknowledged yet",
                counts["release_acknowledged"],
            ),
        )
        for number, (name, detail, done) in enumerate(journey, start=1):
            status = "Done" if done else "To do"
            st.markdown(f"**{number}. {name}** — {status} · {detail}")

st.caption(
    "Every claim links to source evidence. Restricted sources stay hidden from Incoming. "
    "A human reviewer makes approval decisions."
)
footer()
