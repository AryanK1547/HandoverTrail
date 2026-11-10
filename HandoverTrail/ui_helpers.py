import streamlit as st


_ROLE_OPTIONS = ("Admin", "Reviewer", "Incoming")


def render_role_selector():
    if "selected_user_role" not in st.session_state:
        st.session_state["selected_user_role"] = st.session_state.get("user_role", "Admin")
    if st.session_state["selected_user_role"] not in _ROLE_OPTIONS:
        st.session_state["selected_user_role"] = "Admin"
    if "user_role" not in st.session_state:
        st.session_state["user_role"] = st.session_state["selected_user_role"]

    def save_selected_role():
        st.session_state["selected_user_role"] = st.session_state["user_role"]

    st.sidebar.selectbox(
        "Demo role",
        _ROLE_OPTIONS,
        key="user_role",
        on_change=save_selected_role,
        help="Role switching is simulated for this demo.",
    )
