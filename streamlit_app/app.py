import streamlit as st

from auth.login import show_login

from layouts.physician_layout import show_physician_layout
from layouts.radtech_layout import show_radtech_layout
from layouts.system_admin_layout import show_system_admin_layout
from layouts.staff_layout import show_staff_layout
from layouts.hospital_admin_layout import show_hospital_admin_layout

from backend.hospital_utils import (
    is_hospital_setup_completed
)

from backend.subscription_utils import (
    get_subscription_context,
)

from pages.hospital_administrator import (
    setup_wizard
)


st.set_page_config(
    page_title="LungSight",
    page_icon=":microscope:",
    layout="wide",
)

# ==================================================
# INVITE / SET PASSWORD ROUTE
# ==================================================

# Supabase puts the invite token in the URL fragment
# (#access_token=...). Streamlit can't read fragments,
# so this JS snippet reloads the page with the token
# moved into query params (?access_token=...).

if st.query_params.get("access_token"):
    from screens.set_password import show as show_set_password
    show_set_password()
    st.stop()

# ==================================================
# SUBSCRIPTION CONTEXT (CACHED)
# ==================================================

def get_cached_subscription_context(user):
    """
    Returns the subscription context for the current user.

    Cached in st.session_state, keyed by hospital_id.
    Re-fetches only when the hospital_id changes.
    """

    if not user:

        return None

    hospital_id = user.get("hospital_id")

    if not hospital_id:

        return None

    cached = st.session_state.get("subscription_context")

    if cached and cached.get("hospital_id") == hospital_id:

        return cached

    context = get_subscription_context(hospital_id)

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

    st.session_state.pop("subscription_context", None)

    st.session_state.pop("grace_info", None)

    show_login()

    st.stop()


# ==================================================
# LOGGED-IN USER
# ==================================================

user = st.session_state.user

role = user.get("role")


# ==================================================
# SUBSCRIPTION GATE
# ==================================================
# Only applies to hospital-bound users.
# Superadmins (hospital_id = None) skip this entirely.

subscription_context = get_cached_subscription_context(user)

if subscription_context:

    sub_state = subscription_context.get("state")

    # --------------------------------------------------
    # Expired or no subscription → block
    # --------------------------------------------------

    if sub_state in ("expired", "none", "cancelled"):

        from pages.hospital_administrator import subscription_gate

        can_renew = (role == "Hospital Admin")

        if sub_state == "none":

            subscription_gate.show_expired_screen(
                hospital_name=subscription_context.get("hospital_name"),
                plan_name=None,
                end_date=None,
                can_renew=can_renew,
            )

            st.caption(
                "No active subscription was found for this hospital. "
                "Please contact support or renew your subscription."
            )

        else:

            subscription_gate.show_expired_screen(
                hospital_name=subscription_context.get("hospital_name"),
                plan_name=subscription_context.get("plan_name"),
                end_date=subscription_context.get("end_date"),
                can_renew=can_renew,
            )

        st.stop()

    # --------------------------------------------------
    # Grace → set the flag, allow through
    # --------------------------------------------------

    if sub_state == "grace":

        st.session_state.grace_info = {

            "days_left": subscription_context.get("days_left"),

            "end_date":  subscription_context.get("end_date"),
        }

    else:

        # Clear any stale grace flag
        st.session_state.pop("grace_info", None)


# ==================================================
# ROLE-BASED DASHBOARD
# ==================================================

if role == "Radiologist":

    show_physician_layout()


elif role == "Radiologic Technologist":

    show_radtech_layout()


elif role == "Hospital Admin":

    hospital_id = user.get(
        "hospital_id"
    )

    setup_completed = is_hospital_setup_completed(hospital_id)

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