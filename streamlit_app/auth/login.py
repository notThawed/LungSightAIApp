from pathlib import Path
import base64

import streamlit as st

from auth.auth_manager import authenticate
from backend import audit
from shared.assets import load_css, image_path


LOGO_FILE = "LungSight_Logo-nobg.png"
HOSPITAL_IMAGE_FILE = "Hospital-bg01.png"


# ============================================================
# HELPERS
# ============================================================




@st.cache_data(show_spinner=False)
def image_as_base64(path):
    """Local image -> base64 data URL. Cached, so it is encoded once
    instead of on every rerun (every click on the page)."""
    try:
        path = Path(path)

        if not path.exists():
            return None

        encoded = base64.b64encode(path.read_bytes()).decode("utf-8")

        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(path.suffix.lower(), "image/png")

        return f"data:{mime};base64,{encoded}"

    except Exception:
        return None


# ============================================================
# SHOWCASE PANEL (Split Screen - Left Side)
# ============================================================

def show_showcase_panel():

    image_data = image_as_base64(image_path(HOSPITAL_IMAGE_FILE))

    background = (
        f" style=\"background-image:linear-gradient(155deg, rgba(6, 20, 32, 0.94) 0%, rgba(9, 32, 48, 0.90) 50%, rgba(11, 74, 88, 0.86) 100%), url('{image_data}');\""
        if image_data
        else ""
    )

    logo = image_path(LOGO_FILE)
    logo_data = image_as_base64(logo)
    logo_tag = (
        f"<img src='{logo_data}' class='ls-showcase-logo-img' alt='LungSight Logo'/>"
        if logo_data
        else "<span class='ls-showcase-logo-fallback'>LungSight</span>"
    )

    items_html = (
        "<div class='ls-showcase-items'>"
        "<div class='ls-showcase-item'>"
        "<div class='ls-showcase-icon'><span class='material-symbols-rounded'>radiology</span></div>"
        "<div class='ls-showcase-item-text'><b>Chest X-Ray AI Analysis</b><p>Automated pulmonary triage with high-accuracy lesion localization.</p></div>"
        "</div>"
        "<div class='ls-showcase-item'>"
        "<div class='ls-showcase-icon'><span class='material-symbols-rounded'>verified</span></div>"
        "<div class='ls-showcase-item-text'><b>ResNet-50 Diagnostic Engine</b><p>Clinical deep-learning model calibrated for diagnostic support.</p></div>"
        "</div>"
        "<div class='ls-showcase-item'>"
        "<div class='ls-showcase-icon'><span class='material-symbols-rounded'>task_alt</span></div>"
        "<div class='ls-showcase-item-text'><b>Physician-Validated Review</b><p>Collaborative radiologist review workflows and digital sign-offs.</p></div>"
        "</div>"
        "<div class='ls-showcase-item'>"
        "<div class='ls-showcase-icon'><span class='material-symbols-rounded'>event_available</span></div>"
        "<div class='ls-showcase-item-text'><b>Patient Follow-Up Tracker</b><p>Continuous clinical monitoring and scheduled care plans.</p></div>"
        "</div>"
        "</div>"
    )

    showcase_html = (
        f"<div class='ls-showcase-panel'{background}>"
        "<div class='ls-showcase-header'>"
        f"{logo_tag}"
        "<div class='ls-showcase-kicker'>"
        "<span class='material-symbols-rounded ls-kicker-icon'>radiology</span>"
        "<span>LUNGSIGHT HEALTHCARE</span>"
        "</div>"
        "</div>"
        "<h1 class='ls-showcase-title'>Smarter Chest X-Ray Screening</h1>"
        "<p class='ls-showcase-desc'>AI-assisted pulmonary triage and clinical decision support engineered for hospital imaging teams.</p>"
        f"{items_html}"
        "<div class='ls-showcase-footer'>"
        "<span class='material-symbols-rounded ls-footer-icon'>verified_user</span>"
        "<span>Institutional Grade &bull; 256-Bit SSL &bull; RLS Privacy Protected</span>"
        "</div>"
        "</div>"
    )

    st.markdown(showcase_html, unsafe_allow_html=True)


# ============================================================
# LOGIN
# ============================================================

def check_login(email, password):

    if not email or not password:
        st.error("Enter your email and password.")
        return

    try:
        user = authenticate(email.strip(), password)

        if user:
            st.session_state.logged_in = True
            st.session_state.user = user
            audit.record_login_once(user)
            st.rerun()
        else:
            st.error("Email or password is incorrect.")

    except ValueError as e:
        st.error(str(e))

    except Exception:
        st.error(
            "Unable to sign in right now. "
            "Please try again later."
        )


def show_login_form():

    with st.container(key="login_card"):

        header_html = (
            "<div class='ls-status-pill'>"
            "<span class='material-symbols-rounded ls-status-icon'>verified_user</span>"
            "<span>All Clinical Systems Online &bull; 256-Bit SSL Encrypted</span>"
            "</div>"
            "<div class='ls-login-heading'>"
            "<h2 class='ls-login-title'>Clinical Sign In</h2>"
            "<p class='ls-login-subtitle'>Access your hospital's LungSight workspace.</p>"
            "</div>"
        )
        st.markdown(header_html, unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False, border=False):

            email = st.text_input(
                "Email address",
                placeholder="physician@hospital.org",
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your account password",
            )

            submitted = st.form_submit_button("Sign in to Workspace", type="primary")

        if submitted:
            with st.spinner("Authenticating and loading workspace..."):
                check_login(email, password)

        footer_html = (
            "<p class='ls-login-help'>Need assistance? Contact your Hospital Administrator.</p>"
            "<div class='ls-trust-badges'>"
            "<div class='ls-trust-badge'><span class='material-symbols-rounded'>lock</span><span>256-Bit SSL</span></div>"
            "<div class='ls-trust-badge'><span class='material-symbols-rounded'>shield</span><span>RLS Protected</span></div>"
            "<div class='ls-trust-badge'><span class='material-symbols-rounded'>biotech</span><span>AI Advisory</span></div>"
            "</div>"
        )
        st.markdown(footer_html, unsafe_allow_html=True)


# ============================================================
# PAGE
# ============================================================

def show_login():

    load_css("login.css")

    # Top return navigation
    top_col, _ = st.columns([2.5, 6])
    with top_col:
        if st.button("\u2190 Back to Homepage", key="back_to_home_btn"):
            st.session_state["public_page"] = "home"
            st.rerun()

    with st.container(key="split_layout_shell"):

        left_col, right_col = st.columns(
            [1.1, 0.9],
            gap="large",
            vertical_alignment="top",
        )

        with left_col:
            show_showcase_panel()

        with right_col:
            show_login_form()
