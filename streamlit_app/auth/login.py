from pathlib import Path

import streamlit as st

from auth.auth_manager import authenticate

from backend.subscription_utils import (
    get_active_subscription_plans
)

from streamlit_app.auth.client_application import ( 
    show_client_application, clear_application
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOGIN_CSS_PATH = (
    PROJECT_ROOT
    / "shared"
    / "theme"
    / "css_content"
    / "login.css"
)

LOGO_PATH = (
    PROJECT_ROOT
    / "shared"
    / "images"
    / "LungSight_Logo-nobg.png"
)


def _load_login_css() -> None:
    if LOGIN_CSS_PATH.exists():
        st.markdown(
            f"<style>{LOGIN_CSS_PATH.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )


def render_subscription_cards():

    plans = get_active_subscription_plans()

    if not plans:

        st.info(
            "Subscription plans are currently unavailable."
        )

        return

    st.markdown(
        """
        <div style="text-align:center;">
            <h2>Find Your Perfect Plan</h2>
            <p>
                Choose the LungSight subscription plan
                that best fits your hospital.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ==========================================
    # CREATE COLUMNS
    # ==========================================

    columns = st.columns(
        len(plans)
    )

    for column, plan in zip(
        columns,
        plans
    ):

        with column:

            plan_id = plan["plan_id"]

            plan_name = plan["plan_name"]

            description = (
                plan.get("description")
                or "LungSight subscription plan."
            )

            monthly = (
                plan.get("price_monthly")
                or 0
            )

            yearly = (
                plan.get("price_yearly")
                or 0
            )

            max_users = plan.get(
                "max_users"
            )

            max_patients = plan.get(
                "max_patients"
            )

            max_xrays = plan.get(
                "max_xrays_per_month"
            )

            # ======================================
            # CARD
            # ======================================

            with st.container(
                border=True
            ):

                st.markdown(
                    f"## {plan_name}"
                )

                st.caption(
                    description
                )

                st.divider()

                st.markdown(
                    f"### ₱{float(monthly):,.2f} /month"
                )

                st.markdown(
                    f"""
                    **₱{float(yearly):,.2f} / year**
                    """
                )

                st.divider()

                users_text = (
                    "Unlimited"
                    if max_users is None
                    else f"{max_users:,}"
                )

                patients_text = (
                    "Unlimited"
                    if max_patients is None
                    else f"{max_patients:,}"
                )

                xrays_text = (
                    "Unlimited"
                    if max_xrays is None
                    else f"{max_xrays:,}"
                )

                st.write(
                    f"👥 **Users:** {users_text}"
                )

                st.write(
                    f"👤 **Patients:** {patients_text}"
                )

                st.write(
                    f"🩻 **X-rays/month:** {xrays_text}"
                )

                st.divider()

                if st.button(
                    "Select Plan",
                    key=f"select_plan_{plan_id}",
                    use_container_width=True
                ):

                    st.session_state["selected_plan_id"] = plan_id
                    st.session_state["show_application_form"] = True
                    clear_application()

                    st.session_state["selected_plan_id"] = plan_id
                    st.session_state["show_application_form"] = True

                    st.rerun()

def show_login():

    _load_login_css()

    with st.container(key="login_shell"):

        form_col, logo_col = st.columns(
            [1, 1.05],
            gap="large"
        )

        # ============================================
        # LOGIN FORM
        # ============================================

        with form_col:

            with st.container(key="login_card"):

                st.markdown(
                    """
                    <p class="ls-login-title">SIGN-IN</p>
                    """,
                    unsafe_allow_html=True,
                )

                with st.form(
                    "login_form",
                    clear_on_submit=False
                ):

                    email = st.text_input(
                        "Email",
                        placeholder="you@hospital.org"
                    )

                    password = st.text_input(
                        "Password",
                        type="password",
                        placeholder="Enter your password"
                    )

                    submitted = st.form_submit_button(
                        "Sign in"
                    )

                st.markdown(
                    """
                    <p class="ls-login-subheader">
                        AI-powered chest X-ray analysis
                        for faster clinical decisions
                    </p>
                    """,
                    unsafe_allow_html=True,
                )

                # ====================================
                # AUTHENTICATION
                # ====================================

                if submitted:

                    if not email or not password:

                        st.error(
                            "Please enter your email and password."
                        )

                    else:

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
                                "Invalid email or password."
                            )

        # ============================================
        # LOGO
        # ============================================

        with logo_col:

            with st.container(key="logo_panel"):

                if LOGO_PATH.exists():

                    st.image(
                        str(LOGO_PATH),
                        width=440
                    )

                else:

                    st.warning(
                        "LungSight logo could not be found."
                    )

    st.divider()

    render_subscription_cards()

    if st.session_state.get(
        "show_application_form", False
    ):
        selected_plan_id = st.session_state.get(
            "selected_plan_id"
        )

        if selected_plan_id:
            plans = get_active_subscription_plans()

            selected_plan = next (
                (
                    plan
                    for plan in plans
                    if plan["plan_id"] == selected_plan_id
                ),
                None
            )

            if selected_plan:
                show_client_application(
                    selected_plan
                )