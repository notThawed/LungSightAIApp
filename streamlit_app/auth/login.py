from pathlib import Path
import base64

import streamlit as st

from auth.auth_manager import authenticate
from backend.backend_utils.subscription_utils import (
    get_active_subscription_plans,
)
from streamlit_app.auth.client_application import (
    show_client_application,
    clear_application,
)
from shared.assets import load_css, image_path


LOGO_FILE = "LungSight_Logo-nobg.png"
HOSPITAL_IMAGE_FILE = "Hospital-bg01.png"


# ============================================================
# ICONS (inline SVG, identical on every device)
# ============================================================

def _svg(paths):
    return (
        "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' "
        "stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round' "
        f"aria-hidden='true'>{paths}</svg>"
    )


ICON_SCAN = _svg(
    "<path d='M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2"
    "M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2'/>"
    "<path d='M4 12h16'/>"
)
ICON_CHECK = _svg("<path d='M20 6 9 17l-5-5'/>")
ICON_CALENDAR = _svg(
    "<rect x='3' y='4' width='18' height='18' rx='2'/>"
    "<path d='M16 2v4M8 2v4M3 10h18M9 16l2 2 4-4'/>"
)
ICON_LOCK = _svg(
    "<rect x='3' y='11' width='18' height='11' rx='2'/>"
    "<path d='M7 11V7a5 5 0 0 1 10 0v4'/>"
)
ICON_LAYERS = _svg(
    "<path d='m12 2 10 5-10 5L2 7z'/>"
    "<path d='m2 17 10 5 10-5M2 12l10 5 10-5'/>"
)


# ============================================================
# HELPERS
# ============================================================

def peso(amount):
    return f"₱{float(amount or 0):,.2f}"


def limit_text(value):
    return "Unlimited" if value is None else f"{value:,}"


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
# HERO
# ============================================================

def show_hero():

    image_data = image_as_base64(image_path(HOSPITAL_IMAGE_FILE))

    # If the image is missing the hero falls back to a navy gradient
    # (see login.css) instead of showing a warning on the login page.
    background = (
        f" style=\"background-image:url('{image_data}');\""
        if image_data
        else ""
    )

    st.markdown(
        f"<div class='ls-hero'{background}>"
        "<div class='ls-hero-overlay'></div>"
        "<div class='ls-hero-content'>"
        "<p class='ls-hero-kicker'>LUNGSIGHT HEALTHCARE</p>"
        "<p class='ls-hero-title'>Smarter Chest X-Ray</p>"
        "<p class='ls-hero-text'>"
        "AI-assisted screening for better clinical decisions."
        "</p>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


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

        st.markdown(
            "<div class='ls-login-heading'>"
            "<p class='ls-login-title'>Sign in</p>"
            "<p class='ls-login-subtitle'>"
            "Access your hospital's LungSight workspace."
            "</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        with st.form("login_form", clear_on_submit=False, border=False):

            email = st.text_input(
                "Email address",
                placeholder="you@hospital.org",
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
            )

            submitted = st.form_submit_button("Sign in", type="primary")

        if submitted:
            check_login(email, password)

        st.markdown(
            "<p class='ls-login-help'>"
            "Forgot your password? Contact your hospital administrator."
            "</p>"
            f"<div class='ls-secure-note'>{ICON_LOCK}"
            "<span>Authorized hospital personnel only.</span>"
            "</div>",
            unsafe_allow_html=True,
        )


# ============================================================
# LOGO PANEL
# ============================================================

def show_logo_panel():

    with st.container(key="logo_panel"):

        logo = image_path(LOGO_FILE)

        if Path(logo).exists():
            st.image(logo, width=340)
        else:
            st.warning("LungSight logo could not be found.")


# ============================================================
# CLINICAL DESCRIPTION (below the sign-in row)
# ============================================================

def show_clinical_description():

    features = "".join([
        f"<div class='ls-clinical-feature'><span>{ICON_SCAN}</span>"
        "<p>Chest X-ray analysis</p></div>",

        f"<div class='ls-clinical-feature'><span>{ICON_CHECK}</span>"
        "<p>Physician review</p></div>",

        f"<div class='ls-clinical-feature'><span>{ICON_CALENDAR}</span>"
        "<p>Patient follow-up</p></div>",
    ])

    st.markdown(
        "<div class='ls-clinical-description'>"
        "<p class='ls-clinical-kicker'>CLINICAL DECISION SUPPORT</p>"
        "<p class='ls-clinical-text'>"
        "AI-assisted chest X-ray analysis for faster clinical decisions."
        "</p>"
        f"<div class='ls-clinical-features'>{features}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# SUBSCRIPTION PLAN CARD
# ============================================================

def show_plan_card(plan):

    plan_id = plan["plan_id"]

    plan_name = plan.get("plan_name") or "LungSight Plan"
    description = plan.get("description") or "LungSight subscription plan."

    users = limit_text(plan.get("max_users"))
    patients = limit_text(plan.get("max_patients"))
    xrays = limit_text(plan.get("max_xrays_per_month"))

    monthly = peso(plan.get("price_monthly"))
    yearly = peso(plan.get("price_yearly"))

    # Keep the HTML as ONE continuous string, no indentation,
    # otherwise Markdown turns it into a code block.
    features = "".join([
        f"<div class='ls-plan-feature'><span>Users</span><b>{users}</b></div>",
        f"<div class='ls-plan-feature'><span>Patients</span><b>{patients}</b></div>",
        f"<div class='ls-plan-feature'><span>X-rays / month</span><b>{xrays}</b></div>",
    ])

    card_html = "".join([
        f"<div class='ls-plan-icon'>{ICON_LAYERS}</div>",
        f"<p class='ls-plan-name'>{plan_name}</p>",
        f"<p class='ls-plan-desc'>{description}</p>",
        "<div class='ls-plan-price-row'>",
        f"<p class='ls-plan-price'>{monthly}</p>",
        "<span>/ month</span>",
        "</div>",
        f"<p class='ls-plan-yearly'>or {yearly} per year</p>",
        "<div class='ls-plan-features'>",
        features,
        "</div>",
    ])

    with st.container(key=f"plan_card_{plan_id}"):

        st.markdown(card_html, unsafe_allow_html=True)

        if st.button(
            "Select plan",
            key=f"select_plan_{plan_id}",
            width="stretch",
        ):
            clear_application()

            st.session_state["selected_plan_id"] = plan_id
            st.session_state["show_application_form"] = True

            st.rerun()


# ============================================================
# SUBSCRIPTIONS
# ============================================================

def show_plans(plans):

    with st.container(key="subscriptions_section"):

        st.markdown(
            "<div class='ls-subscriptions-header'>"
            "<p class='ls-subscriptions-kicker'>SUBSCRIPTIONS</p>"
            "<p class='ls-subscriptions-title'>Choose a plan for your hospital</p>"
            "<p class='ls-subscriptions-subtitle'>"
            "Flexible plans for different hospital sizes."
            "</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        if not plans:
            st.info("Subscription plans are currently unavailable.")
            return

        columns = st.columns(
            len(plans),
            gap="medium",
        )

        for column, plan in zip(columns, plans):

            with column:
                show_plan_card(plan)


# ============================================================
# APPLICATION
# ============================================================

def show_application(plans):

    if not st.session_state.get("show_application_form"):
        return

    selected_id = st.session_state.get("selected_plan_id")

    for plan in plans:
        if plan["plan_id"] == selected_id:
            show_client_application(plan)
            return


# ============================================================
# ABOUT US LINK (bottom of the page)
# ============================================================

def open_about_page():
    """CONNECT THIS to however your app switches pages. Pick one:

    1) Multipage with a file:   st.switch_page("pages/about.py")
    2) Session-state router:    set whatever key your main app reads,
                                e.g. st.session_state["page"] = "about"
    """
    st.session_state["auth_page"] = "about"
    st.rerun()


def show_footer():

    st.markdown(
        "<div class='ls-section-divider ls-section-divider-tight'></div>",
        unsafe_allow_html=True,
    )

    with st.container(key="about_footer"):

        _, middle, _ = st.columns([2, 1, 2])

        with middle:
            if st.button(
                "About us",
                key="about_us_button",
                width="stretch",
            ):
                open_about_page()

        st.markdown(
            "<p class='ls-footer-text'>© LungSight Healthcare 2026</p>",
            unsafe_allow_html=True,
        )


# ============================================================
# PAGE
# ============================================================

def show_login():

    load_css("login.css")

    plans = get_active_subscription_plans()

    # HERO
    show_hero()

    # SIGN-IN ROW + CLINICAL DESCRIPTION
    with st.container(key="login_shell"):

        form_col, logo_col = st.columns(
            [1, 1],
            gap="large",
            vertical_alignment="top",
        )

        with form_col:
            show_login_form()

        with logo_col:
            show_logo_panel()

        show_clinical_description()

    # SEPARATOR
    st.markdown(
        "<div class='ls-section-divider'></div>",
        unsafe_allow_html=True,
    )

    show_plans(plans)

    # APPLICATION FORM (opens after "Select plan")
    show_application(plans)

    # ABOUT US
    show_footer()