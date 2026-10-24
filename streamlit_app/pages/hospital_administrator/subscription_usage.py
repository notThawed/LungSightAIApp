import streamlit as st

from backend.backend_utils.subscription_usage import (
    get_hospital_subscription,
    get_remaining_usage,
)

from streamlit_app.components.ui import (
    page_header,
    metric_card,
    show_rows,
    pill,
    show_flash_message,
)

from shared.assets import load_css



# ============================================================
# HELPERS
# ============================================================

def get_current_user():
    return st.session_state.get("user") or {}


def get_current_hospital_id():
    user = get_current_user()
    return user.get("hospital_id")


def format_limit(value, unlimited=False):
    if unlimited or value is None:
        return "Unlimited"

    return f"{int(value):,}"


def format_remaining(value, unlimited=False):
    if unlimited or value is None:
        return "Unlimited"

    return f"{int(value):,}"


def get_usage_percentage(used, limit, unlimited=False):
    if unlimited or limit is None:
        return 0

    try:
        limit = int(limit)
        used = int(used or 0)

        if limit <= 0:
            return 0

        return min(used / limit, 1.0)

    except (TypeError, ValueError):
        return 0


def get_usage_tone(used, limit, unlimited=False):
    if unlimited or limit is None:
        return "green"

    try:
        used = int(used or 0)
        limit = int(limit)

        if limit <= 0:
            return "red"

        percentage = used / limit

        if percentage >= 1:
            return "red"

        if percentage >= 0.8:
            return "amber"

        return "green"

    except (TypeError, ValueError):
        return "green"


# ============================================================
# SUBSCRIPTION DETAILS
# ============================================================

def render_subscription_details(subscription):
    if not subscription:
        st.warning(
            "No active subscription was found for your hospital."
        )
        return

    plan = subscription.get("plan") or {}

    plan_name = plan.get("plan_name") or "Unknown plan"
    description = plan.get("description") or "No description available."

    billing_cycle = (
        subscription.get("billing_cycle")
        or "—"
    )

    start_date = (
        subscription.get("start_date")
        or "—"
    )

    end_date = (
        subscription.get("end_date")
        or "—"
    )

    price = None

    if billing_cycle.lower() == "monthly":
        price = plan.get("price_monthly")
    elif billing_cycle.lower() == "yearly":
        price = plan.get("price_yearly")

    if price is not None:
        try:
            price_text = f"₱{float(price):,.2f}"
        except (TypeError, ValueError):
            price_text = "—"
    else:
        price_text = "—"

    st.subheader(plan_name)

    st.caption(description)

    details_col1, details_col2, details_col3 = st.columns(3)

    with details_col1:
        show_rows(
            [
                ("Billing cycle", billing_cycle),
                ("Price", price_text),
            ]
        )

    with details_col2:
        show_rows(
            [
                ("Start date", start_date),
                ("End date", end_date),
            ]
        )

    with details_col3:
        show_rows(
            [
                (
                    "User limit",
                    format_limit(
                        plan.get("max_users")
                    ),
                ),
                (
                    "Patient limit",
                    format_limit(
                        plan.get("max_patients")
                    ),
                ),
                (
                    "Monthly X-ray limit",
                    format_limit(
                        plan.get("max_xrays_per_month")
                    ),
                ),
            ]
        )


# ============================================================
# USAGE ITEM
# ============================================================

def render_usage_item(
    title,
    icon,
    data,
):
    data = data or {}

    used = data.get("used", 0)
    limit = data.get("limit")
    remaining = data.get("remaining")
    unlimited = data.get("unlimited", False)

    percentage = get_usage_percentage(
        used,
        limit,
        unlimited,
    )

    tone = get_usage_tone(
        used,
        limit,
        unlimited,
    )

    limit_text = format_limit(
        limit,
        unlimited,
    )

    remaining_text = format_remaining(
        remaining,
        unlimited,
    )

    st.markdown(
        f"### :material/{icon}: {title}"
    )

    value_col, status_col = st.columns(
        [2, 1]
    )

    with value_col:
        st.metric(
            label="Used",
            value=f"{int(used):,}",
            delta=f"of {limit_text}",
            delta_color="off",
        )

    with status_col:
        if unlimited:
            pill(
                "Unlimited",
                "green",
            )
        elif remaining <= 0:
            pill(
                "Limit reached",
                "red",
            )
        elif tone == "amber":
            pill(
                "Near limit",
                "amber",
            )
        else:
            pill(
                "Available",
                "green",
            )

    st.progress(
        percentage
    )

    st.caption(
        f"{remaining_text} remaining"
    )


# ============================================================
# USAGE SECTION
# ============================================================

def render_usage_section(usage):
    users = usage.get("users") or {}
    patients = usage.get("patients") or {}
    xrays = usage.get("xrays") or {}

    st.subheader("Subscription usage")

    st.caption(
        "Monitor your hospital's current usage against the limits of your subscription plan."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        render_usage_item(
            title="Users",
            icon="group",
            data=users,
        )

    with col2:
        render_usage_item(
            title="Patients",
            icon="personal_injury",
            data=patients,
        )

    with col3:
        render_usage_item(
            title="X-rays this month",
            icon="radiology",
            data=xrays,
        )


# ============================================================
# SUMMARY METRICS
# ============================================================

def render_summary_metrics(usage):
    users = usage.get("users") or {}
    patients = usage.get("patients") or {}
    xrays = usage.get("xrays") or {}

    user_remaining = (
        "Unlimited"
        if users.get("unlimited")
        else users.get("remaining", 0)
    )

    patient_remaining = (
        "Unlimited"
        if patients.get("unlimited")
        else patients.get("remaining", 0)
    )

    xray_remaining = (
        "Unlimited"
        if xrays.get("unlimited")
        else xrays.get("remaining", 0)
    )

    st.subheader("Remaining capacity")

    col1, col2, col3 = st.columns(3)

    with col1:
        metric_card(
            "Users remaining",
            user_remaining,
            "group",
            "blue",
        )

    with col2:
        metric_card(
            "Patients remaining",
            patient_remaining,
            "personal_injury",
            "green",
        )

    with col3:
        metric_card(
            "X-rays remaining",
            xray_remaining,
            "radiology",
            "amber",
        )


# ============================================================
# INFORMATION
# ============================================================

def render_usage_information():
    st.subheader("About subscription usage")

    st.info(
        "User and patient usage represents the current number of "
        "records associated with your hospital. X-ray usage represents "
        "X-ray images uploaded during the current month."
    )

    st.caption(
        "A limit shown as Unlimited means that the subscription "
        "does not impose a limit for that resource."
    )


# ============================================================
# PAGE
# ============================================================

def show():
    load_css(
        "subscription_usage.css"
    )

    show_flash_message()

    hospital_id = get_current_hospital_id()

    with st.container(
        key="sa_page"
    ):

        page_header(
            "Subscription & Usage",
            "View your hospital's current subscription plan and resource usage.",
        )

        if not hospital_id:
            st.error(
                "Your account is not assigned to a hospital. "
                "Please contact your Superadmin."
            )
            return

        try:
            subscription = get_hospital_subscription(
                hospital_id
            )

            usage = get_remaining_usage(
                hospital_id
            )

        except Exception as error:
            st.error(
                f"Failed to load subscription usage: {error}"
            )
            return

        # ====================================================
        # CURRENT SUBSCRIPTION
        # ====================================================

        st.subheader("Current subscription")

        st.caption(
            "Details of your hospital's active subscription plan."
        )

        render_subscription_details(
            subscription
        )

        st.divider()

        # ====================================================
        # USAGE
        # ====================================================

        render_usage_section(
            usage
        )

        st.divider()

        # ====================================================
        # REMAINING CAPACITY
        # ====================================================

        render_summary_metrics(
            usage
        )

        st.divider()

        # ====================================================
        # INFORMATION
        # ====================================================

        render_usage_information()