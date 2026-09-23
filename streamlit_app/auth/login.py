from pathlib import Path

import streamlit as st

from auth.auth_manager import authenticate
from backend.backend_utils.subscription_utils import get_active_subscription_plans
from streamlit_app.auth.client_application import (
    show_client_application,
    clear_application,
)
from shared.assets import load_css, image_path


LOGO_FILE = "LungSight_Logo-nobg.png"


# ------------------------------------------------------------
# Small helpers (keep the layout code below easy to read)
# ------------------------------------------------------------

def peso(amount):
    """Format a number like 1500 -> ₱1,500.00"""
    return f"₱{float(amount or 0):,.2f}"


def limit_text(value):
    """None means no limit in the database."""
    if value is None:
        return "Unlimited"
    return f"{value:,}"


# ------------------------------------------------------------
# Login form (left side)
# ------------------------------------------------------------

def check_login(email, password):

    if not email or not password:
        st.error(
            "Enter your email and password."
        )
        return

    try:

        user = authenticate(
            email.strip(),
            password
        )

        if user:

            st.session_state.logged_in = True
            st.session_state.user = user

            st.rerun()

        else:

            st.error(
                "Email or password is incorrect."
            )

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
            "<p class='ls-login-title'>Sign in</p>"
            "<p class='ls-login-subtitle'>"
            "Access your hospital's LungSight workspace."
            "</p>",
            unsafe_allow_html=True,
        )

        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email", placeholder="you@hospital.org")
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
            )
            submitted = st.form_submit_button("Sign in")

        if submitted:
            check_login(email, password)


# ------------------------------------------------------------
# Logo panel (right side)
# ------------------------------------------------------------

def show_logo_panel():
    with st.container(key="logo_panel"):
        logo = image_path(LOGO_FILE)

        if Path(logo).exists():
            st.image(logo, width=360)
        else:
            st.warning("LungSight logo could not be found.")

        st.markdown(
            "<p class='ls-logo-tagline'>"
            "AI-assisted chest X-ray analysis for faster clinical decisions."
            "</p>",
            unsafe_allow_html=True,
        )


# ------------------------------------------------------------
# Subscription plans
# ------------------------------------------------------------

def show_plan_card(plan):
    plan_id = plan["plan_id"]
    description = plan.get("description") or "LungSight subscription plan."

    # One string, no line breaks or indentation, so Markdown
    # does not turn it into a code block.
    details = (
        "<ul class='ls-plan-features'>"
        f"<li><span>Users</span><b>{limit_text(plan.get('max_users'))}</b></li>"
        f"<li><span>Patients</span><b>{limit_text(plan.get('max_patients'))}</b></li>"
        f"<li><span>X-rays per month</span><b>{limit_text(plan.get('max_xrays_per_month'))}</b></li>"
        "</ul>"
    )

    with st.container(key=f"plan_card_{plan_id}"):
        st.markdown(
            f"<p class='ls-plan-name'>{plan['plan_name']}</p>"
            f"<p class='ls-plan-desc'>{description}</p>"
            f"<p class='ls-plan-price'>{peso(plan.get('price_monthly'))}"
            "<small> / month</small></p>"
            f"<p class='ls-plan-yearly'>or {peso(plan.get('price_yearly'))} per year</p>"
            f"{details}",
            unsafe_allow_html=True,
        )

        if st.button("Select plan", key=f"select_plan_{plan_id}"):
            clear_application()  # reset any old application first
            st.session_state["selected_plan_id"] = plan_id
            st.session_state["show_application_form"] = True
            st.rerun()


def show_plans(plans):
    with st.container(key="plans_section"):
        st.markdown(
            "<p class='ls-plans-title'>Choose a plan for your hospital</p>"
            "<p class='ls-plans-subtitle'>"
            "Every plan includes AI chest X-ray analysis. "
            "Pick the size that fits your team."
            "</p>",
            unsafe_allow_html=True,
        )

        if not plans:
            st.info("Subscription plans are currently unavailable.")
            return

        columns = st.columns(len(plans), gap="medium")

        for column, plan in zip(columns, plans):
            with column:
                show_plan_card(plan)


def show_application(plans):
    """Show the application form for the plan the user selected."""
    if not st.session_state.get("show_application_form"):
        return

    selected_id = st.session_state.get("selected_plan_id")

    for plan in plans:
        if plan["plan_id"] == selected_id:
            show_client_application(plan)
            return


# ------------------------------------------------------------
# The page
# ------------------------------------------------------------

def show_login():
    load_css("login.css")

    plans = get_active_subscription_plans()

    with st.container(key="login_shell"):
        form_col, logo_col = st.columns(
            2,
            gap="large",
            vertical_alignment="center",
        )

        with form_col:
            show_login_form()

        with logo_col:
            show_logo_panel()

    show_plans(plans)
    show_application(plans)