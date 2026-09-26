import sys
from pathlib import Path

import streamlit as st


# ==================================================
# PROJECT ROOT
# ==================================================
#
# Project structure:
#
# LungSightApp/
# ├── backend/
# ├── shared/
# └── streamlit_app/
#     └── app.py
#
# app.py is inside streamlit_app/, so:
# parent       = streamlit_app
# parent.parent = LungSightApp
#
# Adding the project root to sys.path allows imports
# such as:
#
#     from backend.backend_utils.hospital_utils import ...
#     from shared.theme.streamlit_theme import ...
#
# to work correctly on Streamlit Cloud.
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ==================================================
# APPLICATION IMPORTS
# ==================================================

from auth.login import show_login

from shared.theme.streamlit_theme import (
    set_theme,
    apply_theme,
)

from layouts.physician_layout import show_physician_layout
from layouts.radtech_layout import show_radtech_layout
from layouts.system_admin_layout import show_system_admin_layout
from layouts.staff_layout import show_staff_layout
from layouts.hospital_admin_layout import show_hospital_admin_layout

from backend.backend_utils.hospital_utils import (
    is_hospital_setup_completed,
    is_hospital_active,
)

from backend.backend_utils.subscription_utils import (
    get_subscription_context,
)

from pages.hospital_administrator import (
    setup_wizard,
)


# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="LungSight",
    page_icon=":microscope:",
    layout="wide",
)


# ==================================================
# INVITE / SET PASSWORD ROUTE
# ==================================================
#
# Supabase puts the invite token in the URL fragment
# (#access_token=...).
#
# Streamlit cannot directly read URL fragments, so the
# login flow moves the token into query parameters.
# ==================================================

if st.query_params.get("access_token"):

    from screens.set_password import show as show_set_password

    show_set_password()

    st.stop()


# ==================================================
# SUBSCRIPTION CONTEXT
# ==================================================

def get_cached_subscription_context(user):
    """
    Return the subscription context for the current user.

    The context is cached in session state and refreshed
    when the hospital_id changes.
    """

    if not user:
        return None

    hospital_id = user.get("hospital_id")

    if not hospital_id:
        return None

    cached = st.session_state.get(
        "subscription_context"
    )

    if (
        cached
        and cached.get("hospital_id") == hospital_id
    ):
        return cached

    context = get_subscription_context(
        hospital_id
    )

    st.session_state.subscription_context = context

    return context


# ==================================================
# SESSION STATE
# ==================================================

if "current_page" not in st.session_state:
    st.session_state.current_page = "Dashboard"

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user" not in st.session_state:
    st.session_state.user = None


# ==================================================
# LOGIN
# ==================================================

if not st.session_state.logged_in:

    # Clear hospital-specific cached information
    # whenever the user is not authenticated.

    st.session_state.pop(
        "subscription_context",
        None,
    )

    st.session_state.pop(
        "grace_info",
        None,
    )

    show_login()

    st.stop()


# ==================================================
# LOGGED-IN USER
# ==================================================

user = st.session_state.user


# --------------------------------------------------
# Safety check
# --------------------------------------------------

if not user:

    st.session_state.logged_in = False

    st.stop()


# --------------------------------------------------
# Theme
# --------------------------------------------------

user_theme = user.get(
    "theme_preference",
    "light",
)

set_theme(user_theme)
apply_theme()


# --------------------------------------------------
# Role
# --------------------------------------------------

role = user.get("role")


# ==================================================
# HOSPITAL ACTIVE STATUS GATE
# ==================================================
#
# Hospital-bound users must belong to an active
# hospital.
#
# If the System Administrator deactivates a hospital,
# all users belonging to that hospital are prevented
# from accessing the LungSight workspace.
#
# Superadmin accounts normally have no hospital_id,
# so they skip this check.
# ==================================================

hospital_id = user.get(
    "hospital_id"
)


if hospital_id:

    hospital_active = is_hospital_active(
        hospital_id
    )

    if not hospital_active:

        # Clear cached subscription information so
        # an old subscription state cannot remain
        # available while the hospital is inactive.

        st.session_state.pop(
            "subscription_context",
            None,
        )

        st.session_state.pop(
            "grace_info",
            None,
        )

        # --------------------------------------------------
        # Deactivated hospital screen
        # --------------------------------------------------

        st.markdown(
            """
            <div style="
                max-width: 720px;
                margin: 120px auto 0 auto;
                text-align: center;
            ">

                <div style="
                    font-size: 48px;
                    margin-bottom: 16px;
                ">
                    ⚠️
                </div>

                <h1>
                    Hospital Access Temporarily Unavailable
                </h1>

                <p style="
                    font-size: 17px;
                    line-height: 1.6;
                    color: #666;
                ">
                    The hospital associated with your
                    LungSight account is currently
                    deactivated in the system.
                </p>

                <p style="
                    font-size: 16px;
                    line-height: 1.6;
                    color: #666;
                ">
                    You cannot access the LungSight
                    workspace while your hospital account
                    is inactive.
                </p>

                <p style="
                    font-size: 15px;
                    line-height: 1.6;
                    color: #777;
                    margin-top: 24px;
                ">
                    Please contact your hospital administrator
                    or the LungSight System Administrator
                    for assistance.
                </p>

            </div>
            """,
            unsafe_allow_html=True,
        )

        # --------------------------------------------------
        # Logout
        # --------------------------------------------------

        st.markdown(
            "<div style='text-align: center; margin-top: 30px;'>"
            "</div>",
            unsafe_allow_html=True,
        )

        if st.button(
            "Logout",
            icon=":material/logout:",
            width="content",
        ):

            from auth.auth_manager import logout

            logout()

            st.rerun()

        st.stop()


# ==================================================
# SUBSCRIPTION GATE
# ==================================================
#
# Only applies to hospital-bound users.
#
# Superadmins have no hospital_id and therefore skip
# the subscription system.
# ==================================================

subscription_context = get_cached_subscription_context(
    user
)


if subscription_context:

    sub_state = subscription_context.get(
        "state"
    )

    # --------------------------------------------------
    # EXPIRED / NO SUBSCRIPTION
    # --------------------------------------------------

    if sub_state in (
        "expired",
        "none",
        "cancelled",
    ):

        from pages.hospital_administrator import (
            subscription_gate,
        )

        can_renew = (
            role == "Hospital Admin"
        )

        # --------------------------------------------------
        # No subscription
        # --------------------------------------------------

        if sub_state == "none":

            subscription_gate.show_expired_screen(
                hospital_name=(
                    subscription_context.get(
                        "hospital_name"
                    )
                ),
                plan_name=None,
                end_date=None,
                can_renew=can_renew,
            )

            st.caption(
                "No active subscription was found "
                "for this hospital. Please contact "
                "support or renew your subscription."
            )

        # --------------------------------------------------
        # Expired / Cancelled
        # --------------------------------------------------

        else:

            subscription_gate.show_expired_screen(
                hospital_name=(
                    subscription_context.get(
                        "hospital_name"
                    )
                ),
                plan_name=(
                    subscription_context.get(
                        "plan_name"
                    )
                ),
                end_date=(
                    subscription_context.get(
                        "end_date"
                    )
                ),
                can_renew=can_renew,
            )

        st.stop()

    # --------------------------------------------------
    # GRACE PERIOD
    # --------------------------------------------------

    if sub_state == "grace":

        st.session_state.grace_info = {

            "days_left": (
                subscription_context.get(
                    "days_left"
                )
            ),

            "end_date": (
                subscription_context.get(
                    "end_date"
                )
            ),
        }

    else:

        # Remove stale grace-period information.

        st.session_state.pop(
            "grace_info",
            None,
        )


# ==================================================
# ROLE-BASED DASHBOARD
# ==================================================

if role == "Radiologist":

    show_physician_layout()


elif role == "Radiologic Technologist":

    show_radtech_layout()


elif role == "Hospital Admin":

    # --------------------------------------------------
    # Hospital setup check
    # --------------------------------------------------

    hospital_id = user.get(
        "hospital_id"
    )

    setup_completed = (
        is_hospital_setup_completed(
            hospital_id
        )
    )

    if not setup_completed:

        setup_wizard.show()

        st.stop()

    show_hospital_admin_layout()


elif role == "Superadmin":

    show_system_admin_layout()


elif role == "Staff":

    show_staff_layout()


else:

    st.error(
        "Invalid user role. "
        "Please contact the administrator."
    )