import streamlit as st


_ROLE_OPTIONS = ("Admin", "Reviewer", "Incoming", "Departing")


def render_role_selector():
    query_role = st.query_params.get("role")
    role_lookup = {role.casefold(): role for role in _ROLE_OPTIONS}
    selected_role = role_lookup.get(
        str(query_role).casefold(),
        st.session_state.get(
            "selected_user_role",
            st.session_state.get("user_role", "Admin"),
        ),
    )
    if selected_role not in _ROLE_OPTIONS:
        selected_role = "Admin"
    st.session_state["selected_user_role"] = selected_role
    st.session_state["user_role"] = selected_role

    def save_selected_role():
        st.session_state["selected_user_role"] = st.session_state["user_role"]
        st.query_params["role"] = st.session_state["user_role"]

    st.sidebar.selectbox(
        "Demo role",
        _ROLE_OPTIONS,
        key="user_role",
        on_change=save_selected_role,
        help="Role switching is simulated for this demo.",
    )
    if query_role != selected_role:
        st.query_params["role"] = selected_role
