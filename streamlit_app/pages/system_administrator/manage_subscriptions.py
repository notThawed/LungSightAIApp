import streamlit as st

from backend.backend_utils.subscription_utils import (
    get_all_subscription_plans,
    get_inactive_subscription_plans,
    create_subscription,
    edit_subscription,
    deactivate_subscription,
    activate_subscription,
    delete_subscription,
)

from streamlit_app.components.ui import (
    load_css,
    page_header,
    empty_state,
    section_title,
    note,
    show_rows,
    safe,
    peso,
    limit_text,
    pill,
    confirm_buttons,
    remember,
    show_flash_message,
)


# ============================================================
# SMALL HELPERS
# ============================================================

def run_action(action, plan_id):
    """Run activate / deactivate and show the result."""
    result = action(plan_id)

    if result["success"]:
        remember(result["message"])
        st.rerun()
    else:
        st.error(result["message"])


def limit_input(label, key, current=None, step=1):
    """'Unlimited' checkbox + number box. Returns None (unlimited) or a number.
    current=None starts as unlimited; a number starts as that number."""

    unlimited = st.checkbox(f"Unlimited {label.lower()}", value=current is None, key=f"{key}_unlimited")

    number = st.number_input(
        label,
        min_value=1,
        value=int(current) if current else 1,
        step=step,
        disabled=unlimited,
        key=f"{key}_value",
    )

    return None if unlimited else int(number)


def limits_html(plan):
    limits = [
        ("Users", plan.get("max_users")),
        ("Patients", plan.get("max_patients")),
        ("X-rays per month", plan.get("max_xrays_per_month")),
    ]

    items = "".join(
        f"<div class='sa-limit'><b>{limit_text(value)}</b><span>{label}</span></div>"
        for label, value in limits
    )

    return f"<div class='sa-limits'>{items}</div>"


# ============================================================
# PLAN CARDS
# ============================================================

def render_plan_card(plan, inactive=False):

    plan_id = plan["plan_id"]
    is_active = plan.get("is_active", not inactive)

    description = safe(plan.get("description")) if plan.get("description") else "No description."

    with st.container(key=f"sa_card_plan_{plan_id}"):

        st.markdown(
            "<div class='sa-plan-head'>"
            "<div>"
            f"<p class='sa-plan-name'>{safe(plan['plan_name'])}</p>"
            f"<p class='sa-plan-desc'>{description}</p>"
            "</div>"
            f"{pill('Active', 'green') if is_active else pill('Inactive', 'grey')}"
            "</div>"
            f"<p class='sa-plan-price'>{peso(plan.get('price_monthly'))}<small> / month</small></p>"
            f"<p class='sa-plan-yearly'>{peso(plan.get('price_yearly'))} per year</p>"
            f"{limits_html(plan)}",
            unsafe_allow_html=True,
        )

        first_col, second_col = st.columns(2)

        if inactive:

            if first_col.button("Activate", key=f"activate_inactive_{plan_id}", icon=":material/check:", width="stretch"):
                run_action(activate_subscription, plan_id)

            if second_col.button("Delete", key=f"delete_inactive_{plan_id}", icon=":material/delete:", width="stretch"):
                show_delete_plan_dialog(plan)

        else:

            if first_col.button("Edit plan", key=f"edit_plan_{plan_id}", icon=":material/edit:", width="stretch"):
                show_edit_plan_dialog(plan)

            if is_active:
                if second_col.button("Deactivate", key=f"deactivate_plan_{plan_id}", icon=":material/block:", width="stretch"):
                    run_action(deactivate_subscription, plan_id)
            else:
                if second_col.button("Activate", key=f"activate_plan_{plan_id}", icon=":material/check:", width="stretch"):
                    run_action(activate_subscription, plan_id)


def render_plan_grid(plans, inactive=False):
    """Two cards per row."""
    for start in range(0, len(plans), 2):
        for column, plan in zip(st.columns(2, gap="medium"), plans[start:start + 2]):
            with column:
                render_plan_card(plan, inactive)


# ============================================================
# EDIT PLAN
# ============================================================

@st.dialog("Edit subscription plan", width="medium")
def show_edit_plan_dialog(plan):

    plan_id = plan["plan_id"]

    with st.container(key="sa_dialog"):

        errors = st.container()

        plan_name = st.text_input("Plan name *", value=plan["plan_name"], key=f"edit_{plan_id}_name")
        description = st.text_area(
            "Description", value=plan.get("description") or "", height=80, key=f"edit_{plan_id}_desc"
        )

        monthly_col, yearly_col = st.columns(2)

        price_monthly = monthly_col.number_input(
            "Monthly price (₱)", min_value=0.0, value=float(plan.get("price_monthly") or 0),
            step=500.0, format="%.2f", key=f"edit_{plan_id}_monthly",
        )

        price_yearly = yearly_col.number_input(
            "Yearly price (₱)", min_value=0.0, value=float(plan.get("price_yearly") or 0),
            step=1000.0, format="%.2f", key=f"edit_{plan_id}_yearly",
        )

        users_col, patients_col, xrays_col = st.columns(3)

        with users_col:
            max_users = limit_input("Users", f"edit_{plan_id}_users", plan.get("max_users"), 1)

        with patients_col:
            max_patients = limit_input("Patients", f"edit_{plan_id}_patients", plan.get("max_patients"), 100)

        with xrays_col:
            max_xrays = limit_input("X-rays / month", f"edit_{plan_id}_xrays", plan.get("max_xrays_per_month"), 100)

        cancel_col, save_col = st.columns(2)

        if cancel_col.button("Cancel", key=f"cancel_edit_{plan_id}", width="stretch"):
            st.rerun()

        if save_col.button("Save changes", key=f"save_edit_{plan_id}", type="primary", width="stretch"):

            if not plan_name.strip():
                errors.error("Plan name is required.")
                return

            result = edit_subscription(
                plan_id=plan_id,
                plan_name=plan_name.strip(),
                description=description.strip(),
                price_monthly=price_monthly,
                price_yearly=price_yearly,
                max_users=max_users,
                max_patients=max_patients,
                max_xrays_per_month=max_xrays,
            )

            if result["success"]:
                remember(result["message"])
                st.rerun()
            else:
                errors.error(result["message"])


# ============================================================
# ADD PLAN (form on the page + a confirmation dialog)
# ============================================================

@st.dialog("Confirm subscription plan", width="medium")
def show_confirm_plan_dialog(plan):

    with st.container(key="sa_dialog"):

        note("Please review the plan before creating it.", "amber")

        show_rows([
            ("Plan name", plan["plan_name"]),
            ("Description", plan["description"]),
            ("Monthly price", peso(plan["price_monthly"])),
            ("Yearly price", peso(plan["price_yearly"])),
        ])

        st.markdown(limits_html({
            "max_users": plan["max_users"],
            "max_patients": plan["max_patients"],
            "max_xrays_per_month": plan["max_xrays_per_month"],
        }), unsafe_allow_html=True)

        st.caption("The yearly price is calculated as the monthly price × 12.")

        if confirm_buttons("create_plan", "Confirm and create"):

            result = create_subscription(
                plan_name=plan["plan_name"],
                description=plan["description"],
                price_monthly=plan["price_monthly"],
                price_yearly=plan["price_yearly"],
                max_users=plan["max_users"],
                max_xrays_per_month=plan["max_xrays_per_month"],
                max_patients=plan["max_patients"],
            )

            if result["success"]:
                remember(result["message"])
                st.rerun()
            else:
                st.error(result["message"])


def render_add_plan_form():
    """Plain widgets (not an st.form) so the 'Unlimited' boxes react right away."""

    with st.container(key="sa_card_add_plan"):

        section_title("New subscription plan", "The yearly price is calculated as the monthly price × 12.")

        name_col, price_col = st.columns([2, 1])

        plan_name = name_col.text_input("Plan name *", placeholder="e.g. Professional", key="add_plan_name")
        price_monthly = price_col.number_input(
            "Monthly price (₱)", min_value=0.0, step=500.0, format="%.2f", key="add_plan_price"
        )

        description = st.text_area(
            "Description", placeholder="Describe what this plan offers.", height=80, key="add_plan_desc"
        )

        users_col, patients_col, xrays_col = st.columns(3)

        with users_col:
            max_users = limit_input("Users", "add_users", current=1, step=1)

        with patients_col:
            max_patients = limit_input("Patients", "add_patients", current=1, step=100)

        with xrays_col:
            max_xrays = limit_input("X-rays / month", "add_xrays", current=1, step=100)

        if st.button("Review plan", key="review_plan", type="primary", icon=":material/fact_check:"):

            if not plan_name.strip():
                st.error("Plan name is required.")
                return

            show_confirm_plan_dialog({
                "plan_name": plan_name.strip(),
                "description": description.strip(),
                "price_monthly": price_monthly,
                "price_yearly": price_monthly * 12,
                "max_users": max_users,
                "max_patients": max_patients,
                "max_xrays_per_month": max_xrays,
            })


# ============================================================
# DELETE AN INACTIVE PLAN
# ============================================================

@st.dialog("Delete subscription plan", width="small")
def show_delete_plan_dialog(plan):

    plan_id = plan["plan_id"]

    with st.container(key="sa_dialog"):

        st.markdown(
            f"<p class='sa-dialog-text'>Permanently delete <b>{safe(plan['plan_name'])}</b>?</p>",
            unsafe_allow_html=True,
        )

        note("This cannot be undone.", "red")

        show_rows([
            ("Monthly price", peso(plan.get("price_monthly"))),
            ("Yearly price", peso(plan.get("price_yearly"))),
        ])

        if confirm_buttons(f"delete_plan_{plan_id}", "Delete permanently"):

            result = delete_subscription(plan_id)

            if result["success"]:
                remember(result["message"])
                st.rerun()
            else:
                st.error(result["message"])


# ============================================================
# PAGE
# ============================================================

def show():

    load_css("manage_subscriptions.css")
    show_flash_message()

    with st.container(key="sa_page"):

        page_header("Manage subscriptions", "Create and manage LungSight subscription plans.")

        plans_tab, add_tab, inactive_tab = st.tabs(["Plans", "Add plan", "Inactive plans"])

        with plans_tab:
            plans = get_all_subscription_plans() or []

            if plans:
                render_plan_grid(plans)
            else:
                empty_state("No subscription plans have been created yet.")

        with add_tab:
            render_add_plan_form()

        with inactive_tab:
            inactive_plans = get_inactive_subscription_plans() or []

            if inactive_plans:
                st.caption("These plans are no longer offered for new hospital subscriptions.")
                render_plan_grid(inactive_plans, inactive=True)
            else:
                empty_state("There are no inactive subscription plans.")