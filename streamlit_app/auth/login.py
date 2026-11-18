from pathlib import Path
import base64

import streamlit as st

from auth.auth_manager import authenticate
from backend import audit
from shared.assets import load_css, image_path


LOGO_FILE = "Futuristic Medical LungSight Logo.png"
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
            st.error("Incorrect email or password. Please try again.")

    except ValueError as e:
        # Business-level errors from backend/auth.py:
        # inactive accounts, missing profiles, invalid roles, etc.
        st.error(str(e))

    except Exception as e:
        # Supabase Auth errors expose a structured error code.
        error_code = str(
            getattr(e, "code", "") or ""
        ).lower()

        status = getattr(e, "status", None)

        if error_code == "invalid_credentials":
            st.error(
                "Incorrect email or password. Please try again."
            )

        elif error_code == "email_not_confirmed":
            st.warning(
                "Your email address has not been verified. "
                "Please check your inbox or contact your administrator."
            )

        elif error_code in (
            "over_request_rate_limit",
            "over_email_send_rate_limit",
            "too_many_requests",
        ) or status == 429:
            st.warning(
                "Too many attempts. Please wait a few minutes "
                "before trying again."
            )

        elif error_code in (
            "request_timeout",
            "unexpected_failure",
        ) or status in (500, 502, 503, 504):
            st.error(
                "The authentication service is temporarily "
                "unavailable. Please try again later."
            )

        else:
            st.error(
                "Unable to complete sign-in. "
                "Please try again or contact your administrator."
            )





def show_forgot_password_form():
    """Public recovery request UI: identical response regardless of account existence."""
    from backend.backend_utils.account_recovery import request_recovery_email
    with st.container(key="login_card"):
        st.markdown(
            '<div class="ls-recovery-intro"><h2 class="ls-recovery-title">Forgot your password?</h2>'
            '<p class="ls-recovery-copy">Enter your registered work email. '
            'We will send instructions if it is associated with a LungSightAI account. '
            'This also works when your initial setup link has expired.</p></div>',
            unsafe_allow_html=True,
        )
        if st.session_state.get("ls_recovery_sent"):
            st.success("If an account exists for that email, a recovery link will arrive shortly. Check your inbox and spam folder.")
            if st.button("Send another email", key="ls_resend_recovery", icon=":material/refresh:"):
                st.session_state.pop("ls_recovery_sent", None)
                st.rerun()
        else:
            with st.form("ls_forgot_password_form", border=False):
                email = st.text_input("Email address", key="ls_recovery_email",
                                      placeholder="you@hospital.org")
                submitted = st.form_submit_button("Email me a recovery link", type="primary", use_container_width=True)
            if submitted:
                import re
                if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", (email or "").strip()):
                    st.error("Enter a valid email address.")
                else:
                    try:
                        request_recovery_email(email)
                    except Exception:
                        # Deliberately avoid exposing whether a user exists.
                        pass
                    st.session_state["ls_recovery_sent"] = True
                    st.rerun()
        if st.button("Back to Sign In", key="ls_forgot_back_btn", icon=":material/arrow_back:"):
            st.session_state["ls_auth_view"] = "login"
            st.session_state.pop("ls_recovery_sent", None)
            st.rerun()


def show_login_form():

    if st.session_state.get("ls_auth_view") == "forgot":
        show_forgot_password_form()
        return

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

        if st.button("Forgot Password?", key="ls_forgot_password_link", icon=":material/lock_reset:"):
            st.session_state["ls_auth_view"] = "forgot"
            st.session_state.pop("ls_recovery_sent", None)
            st.rerun()

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
