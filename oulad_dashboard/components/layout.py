"""TrackWise shared application shell, login, ribbon controls and UI helpers."""

from __future__ import annotations

from html import escape
from pathlib import Path
from textwrap import dedent
import base64
import mimetypes

import streamlit as st

from config.demo_users import UserConfigurationError, authenticate_user
from services.data_service import DataUnavailable, load_student_info

ASSETS = Path(__file__).resolve().parents[1] / "assets"
LOGIN_BACKGROUND = ASSETS / "login-background.jpg"
SUBTITLE = "Behavioural Learning Analytics for Early Student Support"
ROLE_LABELS = {"student": "Student", "instructor": "Instructor", "admin": "Administrator"}
ROLE_SUBTITLES = {"student": "Learning Companion", "instructor": "Student Support Workspace", "admin": "Programme Intelligence"}


def _html(markup: str):
    st.html(dedent(markup).strip())


def initialise_session():
    defaults = {
        "user": None,
        "dark_mode": False,
        "login_role": "student",
        "student_plan": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_session(preserve_theme: bool = True):
    dark_mode = bool(st.session_state.get("dark_mode", False))
    for key in list(st.session_state):
        del st.session_state[key]
    st.session_state.user = None
    st.session_state.login_role = "student"
    st.session_state.dark_mode = dark_mode if preserve_theme else False
    st.session_state.student_plan = []
    st.query_params.clear()


def _theme_override() -> str:
    if st.session_state.get("dark_mode", False):
        return """
        <style>:root{--tw-bg:#0f172a;--tw-surface:#111c30;--tw-soft:#162238;--tw-text:#e5edf8;--tw-heading:#fff;--tw-muted:#a9b7cc;--tw-border:#2b3a52;--tw-primary:#60a5fa;--tw-primary-dark:#3b82f6;--tw-primary-soft:rgba(96,165,250,.13);--tw-success:#34d399;--tw-warning:#fbbf24;--tw-danger:#fb7185;--tw-shadow:0 12px 35px rgba(0,0,0,.18)}</style>
        """
    return """
    <style>:root{--tw-bg:#f5f7fb;--tw-surface:#fff;--tw-soft:#f7f9fc;--tw-text:#25324a;--tw-heading:#0f2445;--tw-muted:#66758d;--tw-border:#dce4ef;--tw-primary:#214f93;--tw-primary-dark:#173d78;--tw-primary-soft:#eaf1fb;--tw-success:#0f9f78;--tw-warning:#c78114;--tw-danger:#cf425b;--tw-shadow:0 10px 30px rgba(32,56,85,.08)}</style>
    """


def _login_background_css() -> str:
    if not LOGIN_BACKGROUND.is_file():
        return "<style>[data-testid='stAppViewContainer']{background:linear-gradient(135deg,#dce8fb,#f8fbff)!important}</style>"
    mime_type, _ = mimetypes.guess_type(LOGIN_BACKGROUND.name)
    encoded = base64.b64encode(LOGIN_BACKGROUND.read_bytes()).decode("utf-8")
    return f"""
    <style>[data-testid='stAppViewContainer']{{background-image:linear-gradient(rgba(8,28,58,.54),rgba(8,28,58,.54)),url('data:{mime_type or 'image/jpeg'};base64,{encoded}')!important;background-size:cover!important;background-position:center!important;background-attachment:fixed!important}}</style>
    """


def load_css(user=None):
    path = ASSETS / "styles.css"
    if path.is_file():
        st.markdown("<style>" + path.read_text(encoding="utf-8") + "</style>", unsafe_allow_html=True)
    st.markdown(_theme_override(), unsafe_allow_html=True)
    if user is None:
        st.markdown(_login_background_css(), unsafe_allow_html=True)


def render_theme_toggle(compact: bool = False):
    st.toggle("Dark" if compact else "🌙 Dark mode", key="dark_mode", help="Switch appearance")


def render_header(user):
    brand, account, theme, logout = st.columns([6.2, 1.7, .8, .9], vertical_alignment="center")
    with brand:
        _html(f"""
        <div class='tw-brand-row'>
          <div class='tw-brand'>TrackWise</div>
          <div class='tw-brand-copy'><strong>{ROLE_SUBTITLES.get(user.get('role'),'Workspace')}</strong><span>{SUBTITLE}</span></div>
        </div>""")
    with account:
        _html(f"<div class='tw-account'><span>{escape(user.get('display_name','User'))}</span><b>{ROLE_LABELS.get(user.get('role'),'User')}</b></div>")
    with theme:
        render_theme_toggle(compact=True)
    with logout:
        if st.button("Sign out", key="sign_out", use_container_width=True):
            clear_session(True)
            st.rerun()


def render_demo_banner():
    _html("""
    <div class='tw-demo-banner'><b>Research prototype</b><span>Historical anonymised OULAD data · No live student monitoring · Intervention actions are illustrative</span></div>
    """)


def render_page_heading(title: str, subtitle: str = ""):
    _html(f"<div class='tw-page-heading'><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>")


def ribbon_start(label: str | None = None):
    container = st.container(key=f"ribbon_{label or 'controls'}")
    if label:
        with container:
            _html(f"<div class='tw-ribbon-label'>{escape(label)}</div>")
    return container


def render_metric_card(label: str, value: str, note: str = "", tone: str = "neutral"):
    _html(f"""
    <div class='tw-metric-card tw-tone-{escape(tone)}'>
      <span>{escape(label)}</span><strong>{escape(str(value))}</strong><small>{escape(note)}</small>
    </div>""")


def render_status_banner(title: str, message: str, tone: str = "primary", eyebrow: str = "Your current picture"):
    _html(f"""
    <div class='tw-status tw-tone-{escape(tone)}'><div><small>{escape(eyebrow)}</small><h2>{escape(title)}</h2><p>{escape(message)}</p></div></div>
    """)


def render_empty_state(title: str, body: str):
    _html(f"<div class='tw-empty'><strong>{escape(title)}</strong><p>{escape(body)}</p></div>")


def render_login():
    _, theme_col = st.columns([8, 1])
    with theme_col:
        render_theme_toggle(compact=True)
    st.markdown("<div style='height:4vh'></div>", unsafe_allow_html=True)
    _, centre, _ = st.columns([1.2, 1.5, 1.2])
    with centre:
        with st.container(key="login_glass_panel"):
            _html(f"""
            <div class='login-brand'>TrackWise</div><div class='login-title'>Welcome</div>
            <div class='login-subtitle'>{SUBTITLE}</div>
            <div class='login-description'>Detect early. Understand behaviour. Support the next best action.</div>
            """)
            role_labels = {"Student": "student", "Instructor": "instructor", "Administrator": "admin"}
            selected_display = st.radio("Role", list(role_labels), horizontal=True, label_visibility="collapsed")
            selected_role = role_labels[selected_display]
            st.session_state.login_role = selected_role
            with st.form("trackwise_login"):
                username = st.text_input("Username", placeholder="Enter username")
                password = st.text_input("Password", type="password", placeholder="Enter password")
                submitted = st.form_submit_button("Sign in", use_container_width=True, type="primary")
            st.caption("Local conference prototype authentication — replace with institutional SSO for deployment.")
            if submitted:
                try:
                    info = load_student_info()
                    user = authenticate_user(username, password, info, expected_role=selected_role)
                except (DataUnavailable, UserConfigurationError) as exc:
                    st.error(str(exc))
                else:
                    if user is None:
                        st.error("Incorrect username, password, or role selection.")
                    else:
                        theme = st.session_state.get("dark_mode", False)
                        clear_session(True)
                        st.session_state.dark_mode = theme
                        st.session_state.user = user
                        st.rerun()

# Compatibility helpers retained for older imports. Navigation is now tab-based.
def render_sidebar(user):
    return "Overview"


def render_logout():
    return None
