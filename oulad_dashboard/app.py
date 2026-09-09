"""TrackWise — single Streamlit entry point."""

import streamlit as st

from auth.permissions import ROLES
from components.layout import initialise_session, load_css, render_demo_banner, render_header, render_login
from services.data_service import DataUnavailable


def _render_session():
    user = st.session_state.user
    if user is None:
        render_login()
        return
    if not isinstance(user, dict) or user.get("role") not in ROLES:
        st.error("Your TrackWise session is unavailable. Please sign in again.")
        return

    render_header(user)
    render_demo_banner()

    try:
        if user["role"] == "student":
            from pages.student_home import render_student_dashboard
            render_student_dashboard(user)
        elif user["role"] == "instructor":
            from pages.instructor_home import render_instructor_dashboard
            render_instructor_dashboard(user)
        else:
            from pages.admin_home import render_admin_dashboard
            render_admin_dashboard(user)
    except DataUnavailable as exc:
        st.info(str(exc))


def main():
    st.set_page_config(
        page_title="TrackWise",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    initialise_session()
    load_css(st.session_state.user)
    page = st.navigation([st.Page(_render_session, title="TrackWise", default=True)], position="hidden")
    page.run()


if __name__ == "__main__":
    main()
