# auth/login.py

from pathlib import Path

import streamlit as st

from auth.auth_manager import authenticate


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGIN_CSS_PATH = PROJECT_ROOT / "shared" / "theme" / "css_content" / "login.css"
LOGO_PATH = PROJECT_ROOT / "shared" / "images" / "LungSight Logo.png"


def _load_login_css() -> None:
    if LOGIN_CSS_PATH.exists():
        st.markdown(f"<style>{LOGIN_CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def show_login():
    _load_login_css()

    with st.container(key="login_shell"):
        form_col, logo_col = st.columns([1, 1.05], gap="large")

        with form_col:
            with st.container(key="login_card"):
                st.markdown(
                    """
                    <p class="ls-login-title">SIGN-IN</p>
                    """,
                    unsafe_allow_html=True,
                )

                with st.form("login_form", clear_on_submit=False):
                    email = st.text_input("Email", placeholder="you@hospital.org")
                    password = st.text_input("Password", type="password", placeholder="Enter your password")
                    submitted = st.form_submit_button("Sign in")

                st.markdown(
                    """
                    <p class="ls-login-subheader">AI-powered chest X-ray analysis for faster clinical decisions</p>
                    """,
                    unsafe_allow_html=True,
                )

                if submitted:
                    user = authenticate(email, password)

                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user = user
                        st.rerun()

                    else:
                        st.error("Invalid email or password.")

        with logo_col:
            with st.container(key="logo_panel"):
                if LOGO_PATH.exists():
                    st.image(str(LOGO_PATH), width=440)