import os
import sys

import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import DEMO_PROJECT_ID, bootstrap
from judge_tour import build_tour, get_tour_state
from ui import (
    badge_html,
    configure_page,
    footer,
    page_shell,
    show_flash_toast,
)
from workspace import create_demo_copy, get_active_project_id

configure_page("Guided tour · HandoverTrail")
bootstrap()
PROJECT_ID = get_active_project_id()

role, _counts = page_shell(
    0,
    "Guided tour",
    "Walk the whole handover in about ten minutes: sources, conflicts, exit interview, "
    "release, and pick-up. Each step opens the right page as the right role.",
)
show_flash_toast()

# ------------------------------------------------------------ workspace choice
with st.container(border=True):
    if PROJECT_ID == DEMO_PROJECT_ID:
        st.subheader("Start with your own copy")
        st.write(
            "You are in the shared demo project. Other visitors may already have approved "
            "claims or released a version here, which would change what you see. A private "
            "copy has the same synthetic sources and claims, untouched, and is yours alone."
        )
        if st.button("Start my private demo copy", type="primary"):
            try:
                token, _project_id = create_demo_copy()
            except (OSError, ValueError) as exc:
                st.error(
                    f"The private copy could not be created: {exc} Nothing was changed; "
                    "you can retry or continue in the shared demo."
                )
            else:
                st.session_state["active_upload_workspace_token"] = token
                st.query_params["workspace"] = token
                st.query_params["role"] = "Reviewer"
                st.session_state["ui_flash_toast"] = (
                    "Private demo copy ready: 8 sources, 13 claims, 3 conflicts. "
                    "Follow the steps below."
                )
                st.rerun()
        st.caption("Or continue in the shared demo; the steps below track it the same way.")
    else:
        st.subheader("Your workspace")
        st.write(
            f"Workspace {PROJECT_ID[-6:]}. Bookmark this page's address to come back to it. "
            "Anyone with the link can open it, so use synthetic data only."
        )
        st.caption(
            "Role links below keep this workspace. To start over, create a new private copy."
        )
        if st.button("Start a fresh private copy"):
            try:
                token, _project_id = create_demo_copy()
            except (OSError, ValueError) as exc:
                st.error(f"The new copy could not be created: {exc} Your current workspace is unchanged.")
            else:
                st.session_state["active_upload_workspace_token"] = token
                st.query_params["workspace"] = token
                st.query_params["role"] = "Reviewer"
                st.session_state["ui_flash_toast"] = "A fresh private demo copy is ready."
                st.rerun()

tour = build_tour(get_tour_state(PROJECT_ID))
base_params = {
    key: value for key, value in st.query_params.items() if key not in {"role"}
}

# ------------------------------------------------------------ progress
st.progress(
    tour["done_required"] / tour["total_required"],
    text=f"{tour['done_required']} of {tour['total_required']} steps complete",
)
current = next((step for step in tour["steps"] if step["key"] == tour["current"]), None)
if tour["complete"]:
    st.success(
        "You have completed the whole handover: evidence, conflicts, exit interview, release, "
        "and acknowledgement. Start a fresh private copy to run it again."
    )
elif current:
    st.info(
        f"Next: **{current['title']}** as **{current['role']}**. "
        "The step below has a link that opens the right page with that role selected."
    )

# ------------------------------------------------------------ steps
for number, step in enumerate(tour["steps"], start=1):
    is_current = step["key"] == tour["current"]
    with st.container(border=True):
        heading, status = st.columns([4, 1])
        with heading:
            st.markdown(f"**{number}. {step['title']}**")
            st.markdown(
                badge_html(step["tag"], "primary" if step["tag"] != "Core" else "neutral")
                + " "
                + badge_html(f"Role: {step['role']}", "restricted")
                + (" " + badge_html("Optional", "neutral") if step["optional"] else ""),
                unsafe_allow_html=True,
            )
        with status:
            if step["done"]:
                st.markdown(badge_html("Done", "success"), unsafe_allow_html=True)
            elif is_current:
                st.markdown(badge_html("Do this now", "primary"), unsafe_allow_html=True)
            else:
                st.markdown(badge_html("Not yet", "neutral"), unsafe_allow_html=True)
        st.write(step["todo"])
        st.caption(f"You should see: {step['expect']}")
        st.page_link(
            step["page"],
            label=f"Open as {step['role']} →",
            query_params={**base_params, "role": step["role"]},
        )

# ------------------------------------------------------------ safety checks
with st.expander("Checks worth making along the way"):
    st.markdown(
        """
        - **Restricted data stays restricted.** Switch to Incoming and look at the source
          list and the released claims: `restricted_demo.txt` and any claim that cites it
          never appear. Approving such a claim as Reviewer still does not release it.
        - **Nothing is sent to an AI provider from restricted sources.** Before a provider
          call, only public excerpts are included and emails, phone numbers, tokens, and
          long ID numbers are masked. The Review page reports how many values were masked.
        - **No claim reaches Incoming without a human approval,** and a released version
          cannot be edited. Later edits only appear in a newer version.
        - **Source agreement is checked, not assumed.** “Corroborated” appears only when
          matching statements actually agree across sources.
        - **Roles are a demo selector, not a login.** Do not enter real data.
        """
    )

st.caption(
    "Stuck? Each page's banner shows the next step, and the pages in the sidebar follow the "
    "same order as this tour."
)
footer()
