import streamlit as st

from backend.subscription_utils import (
    get_all_subscription_plans,
    get_inactive_subscription_plans,
    create_subscription,
    edit_subscription,
    deactivate_subscription,
    activate_subscription,
    delete_subscription
)


# ==========================================
# FORMAT LIMIT
# ==========================================

def format_limit(value):

    if value is None:

        return "Unlimited"

    return f"{value:,}"


# ==========================================
# RENDER SUBSCRIPTIONS TABLE
# ==========================================

def render_subscriptions_table():

    plans = get_all_subscription_plans()

    if not plans:

        st.info(
            "No subscription plans have been created yet."
        )

        return

    st.subheader("Subscription Plans")

    for plan in plans:

        plan_id = plan["plan_id"]

        plan_name = plan["plan_name"]

        description = (
            plan.get("description")
            or ""
        )

        price_monthly = (
            plan.get("price_monthly")
            or 0
        )

        price_yearly = (
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

        is_active = plan.get(
            "is_active",
            False
        )

        with st.container(border=True):

            # ==================================
            # HEADER
            # ==================================

            header_col, status_col = st.columns(
                [4, 1]
            )

            with header_col:

                st.markdown(
                    f"### {plan_name}"
                )

                if description:

                    st.caption(
                        description
                    )

            with status_col:

                if is_active:

                    st.success(
                        "ACTIVE"
                    )

                else:

                    st.warning(
                        "INACTIVE"
                    )

            st.divider()

            # ==================================
            # PRICING
            # ==================================

            price_col1, price_col2 = st.columns(2)

            with price_col1:

                st.metric(
                    "Monthly",
                    f"₱{float(price_monthly):,.2f}"
                )

            with price_col2:

                st.metric(
                    "Yearly",
                    f"₱{float(price_yearly):,.2f}"
                )

            st.markdown(
                "#### Plan Limits"
            )

            limit_col1, limit_col2, limit_col3 = st.columns(3)

            with limit_col1:

                st.write("**Users**")
                st.write(
                    format_limit(max_users)
                )

            with limit_col2:

                st.write("**Patients**")
                st.write(
                    format_limit(max_patients)
                )

            with limit_col3:

                st.write("**X-rays / Month**")
                st.write(
                    format_limit(max_xrays)
                )

            st.divider()

            # ==================================
            # ACTIONS
            # ==================================

            edit_col, status_col = st.columns(2)

            with edit_col:

                if st.button(
                    "Edit Plan",
                    key=f"edit_plan_{plan_id}",
                    use_container_width=True
                ):

                    st.session_state[
                        "editing_plan_id"
                    ] = plan_id

                    st.rerun()

            with status_col:

                if is_active:

                    if st.button(
                        "Deactivate",
                        key=f"deactivate_plan_{plan_id}",
                        use_container_width=True
                    ):

                        result = (
                            deactivate_subscription(
                                plan_id
                            )
                        )

                        if result["success"]:

                            st.success(
                                result["message"]
                            )

                            st.rerun()

                        else:

                            st.error(
                                result["message"]
                            )

                else:

                    if st.button(
                        "Activate",
                        key=f"activate_plan_{plan_id}",
                        use_container_width=True
                    ):

                        result = (
                            activate_subscription(
                                plan_id
                            )
                        )

                        if result["success"]:

                            st.success(
                                result["message"]
                            )

                            st.rerun()

                        else:

                            st.error(
                                result["message"]
                            )

@st.dialog("Confirm Subscription Plan")
def render_subscription_confirmation():

    plan = st.session_state.get(
        "pending_subscription_plan"
    )

    if not plan:
        return

    st.divider()

    st.subheader(
        "Confirm Subscription Plan"
    )

    st.warning(
        "Please review the subscription plan "
        "before creating it."
    )

    # ==========================================
    # PLAN INFORMATION
    # ==========================================

    with st.container(border=True):

        st.markdown(
            f"### {plan['plan_name']}"
        )

        if plan["description"]:

            st.write(
                plan["description"]
            )

        st.divider()

        # ======================================
        # PRICING
        # ======================================

        col1, col2 = st.columns(2)

        with col1:

            st.metric(
                "Monthly Price",
                f"₱{plan['price_monthly']:,.2f}"
            )

        with col2:

            st.metric(
                "Yearly Price",
                f"₱{plan['price_yearly']:,.2f}"
            )

        st.caption(
            "Yearly price is automatically calculated "
            "as Monthly Price × 12."
        )

        st.divider()

        # ======================================
        # LIMITS
        # ======================================

        st.markdown(
            "#### Plan Limits"
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            st.write("**Maximum Users**")

            st.write(
                plan["max_users"]
                if plan["max_users"] is not None
                else "Unlimited"
            )

        with col2:

            st.write("**Maximum Patients**")

            st.write(
                plan["max_patients"]
                if plan["max_patients"] is not None
                else "Unlimited"
            )

        with col3:

            st.write("**X-rays / Month**")

            st.write(
                plan["max_xrays_per_month"]
                if plan["max_xrays_per_month"] is not None
                else "Unlimited"
            )

    st.write("")

    # ==========================================
    # CONFIRMATION BUTTONS
    # ==========================================

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "Cancel",
            use_container_width=True
        ):

            st.session_state.pop(
                "pending_subscription_plan",
                None
            )

            st.session_state.pop(
                "show_subscription_confirmation",
                None
            )

            st.rerun()

    with col2:

        if st.button(
            "Confirm & Create Plan",
            type="primary",
            use_container_width=True
        ):

            result = create_subscription(
                plan_name=plan["plan_name"],
                description=plan["description"],
                price_monthly=plan["price_monthly"],
                price_yearly=plan["price_yearly"],
                max_users=plan["max_users"],
                max_xrays_per_month=plan[
                    "max_xrays_per_month"
                ],
                max_patients=plan["max_patients"]
            )

            if result["success"]:

                st.session_state.pop(
                    "pending_subscription_plan",
                    None
                )

                st.session_state.pop(
                    "show_subscription_confirmation",
                    None
                )

                st.success(
                    result["message"]
                )

                st.rerun()

            else:

                st.error(
                    result["message"]
                )

# ==========================================
# ADD SUBSCRIPTION PLAN
# ==========================================

def render_add_subscription_form():

    st.subheader(
        "Add Subscription Plan"
    )

    with st.form(
        "add_subscription_form",
        clear_on_submit=False
    ):

        # ==========================================
        # PLAN INFORMATION
        # ==========================================

        plan_name = st.text_input(
            "Plan Name",
            placeholder="e.g. Professional"
        )

        description = st.text_area(
            "Description",
            placeholder="Describe what this plan offers."
        )

        # ==========================================
        # PRICING
        # ==========================================

        st.markdown("### Pricing")

        price_monthly = st.number_input(
            "Monthly Price (₱)",
            min_value=0.00,
            step=500.00,
            format="%.2f"
        )

        st.caption(
            "Yearly price will be automatically "
            "calculated as monthly price × 12."
        )

        # ==========================================
        # PLAN LIMITS
        # ==========================================

        st.markdown("### Plan Limits")

        # ------------------------------------------
        # MAX USERS
        # ------------------------------------------

        unlimited_users = st.checkbox(
            "Unlimited Users",
            key="add_unlimited_users"
        )

        if unlimited_users:

            max_users = None

        else:

            max_users = st.number_input(
                "Maximum Users",
                min_value=1,
                step=1,
                key="add_max_users"
            )


        # ------------------------------------------
        # MAX PATIENTS
        # ------------------------------------------

        unlimited_patients = st.checkbox(
            "Unlimited Patients",
            key="add_unlimited_patients"
        )

        if unlimited_patients:

            max_patients = None

        else:

            max_patients = st.number_input(
                "Maximum Patients",
                min_value=1,
                step=100,
                key="add_max_patients"
            )


        # ------------------------------------------
        # MAX X-RAYS
        # ------------------------------------------

        unlimited_xrays = st.checkbox(
            "Unlimited X-rays / Month",
            key="add_unlimited_xrays"
        )

        if unlimited_xrays:

            max_xrays = None

        else:

            max_xrays = st.number_input(
                "Maximum X-rays / Month",
                min_value=1,
                step=100,
                key="add_max_xrays"
            )

        # ==========================================
        # CREATE
        # ==========================================

        submitted = st.form_submit_button(
            "Create Subscription Plan",
            type="primary",
            use_container_width=True
        )

    # ==========================================
    # OPEN CONFIRMATION DIALOG
    # ==========================================

    if submitted:

        if not plan_name.strip():

            st.error(
                "Plan name is required."
            )

            return

        # Calculate yearly price
        price_yearly = price_monthly * 12

        # Store pending plan
        st.session_state[
            "pending_subscription_plan"
        ] = {

            "plan_name":
                plan_name.strip(),

            "description":
                description.strip(),

            "price_monthly":
                price_monthly,

            "price_yearly":
                price_yearly,

            "max_users":
                max_users,

            "max_patients":
                max_patients,

            "max_xrays_per_month":
                max_xrays
        }

        # Open dialog
        render_subscription_confirmation()


# ==========================================
# EDIT SUBSCRIPTION PLAN
# ==========================================

def render_edit_subscription_form(plan):

    st.subheader(
        f"Edit Subscription Plan: "
        f"{plan['plan_name']}"
    )

    with st.form(
        f"edit_subscription_{plan['plan_id']}"
    ):

        plan_name = st.text_input(
            "Plan Name",
            value=plan["plan_name"]
        )

        description = st.text_area(
            "Description",
            value=plan.get("description") or ""
        )

        st.markdown(
            "### Pricing"
        )

        col1, col2 = st.columns(2)

        with col1:

            price_monthly = st.number_input(
                "Monthly Price (₱)",
                min_value=0.00,
                value=float(
                    plan.get("price_monthly") or 0
                ),
                step=500.00,
                format="%.2f"
            )

        with col2:

            price_yearly = st.number_input(
                "Yearly Price (₱)",
                min_value=0.00,
                value=float(
                    plan.get("price_yearly") or 0
                ),
                step=1000.00,
                format="%.2f"
            )

        st.markdown(
            "### Plan Limits"
        )

        # ==================================
        # USERS
        # ==================================

        current_users = plan.get(
            "max_users"
        )

        unlimited_users = st.checkbox(
            "Unlimited Users",
            value=current_users is None,
            key=f"edit_unlimited_users_{plan['plan_id']}"
        )

        max_users = st.number_input(
            "Maximum Users",
            min_value=1,
            value=(
                int(current_users)
                if current_users is not None
                else 1
            ),
            step=1,
            disabled=unlimited_users
        )

        # ==================================
        # PATIENTS
        # ==================================

        current_patients = plan.get(
            "max_patients"
        )

        unlimited_patients = st.checkbox(
            "Unlimited Patients",
            value=current_patients is None,
            key=f"edit_unlimited_patients_{plan['plan_id']}"
        )

        max_patients = st.number_input(
            "Maximum Patients",
            min_value=1,
            value=(
                int(current_patients)
                if current_patients is not None
                else 1
            ),
            step=100,
            disabled=unlimited_patients
        )

        # ==================================
        # XRAYS
        # ==================================

        current_xrays = plan.get(
            "max_xrays_per_month"
        )

        unlimited_xrays = st.checkbox(
            "Unlimited X-rays",
            value=current_xrays is None,
            key=f"edit_unlimited_xrays_{plan['plan_id']}"
        )

        max_xrays = st.number_input(
            "Maximum X-rays / Month",
            min_value=1,
            value=(
                int(current_xrays)
                if current_xrays is not None
                else 1
            ),
            step=100,
            disabled=unlimited_xrays
        )

        st.divider()

        save_col, cancel_col = st.columns(2)

        with save_col:

            save = st.form_submit_button(
                "Save Changes",
                use_container_width=True
            )

        with cancel_col:

            cancel = st.form_submit_button(
                "Cancel",
                use_container_width=True
            )

        if cancel:

            st.session_state.pop(
                "editing_plan_id",
                None
            )

            st.rerun()

        if save:

            if not plan_name.strip():

                st.error(
                    "Plan name is required."
                )

                return

            result = edit_subscription(

                plan_id=plan["plan_id"],

                plan_name=plan_name.strip(),

                description=description.strip(),

                price_monthly=price_monthly,

                price_yearly=price_yearly,

                max_users=(
                    None
                    if unlimited_users
                    else max_users
                ),

                max_patients=(
                    None
                    if unlimited_patients
                    else max_patients
                ),

                max_xrays_per_month=(
                    None
                    if unlimited_xrays
                    else max_xrays
                )
            )

            if result["success"]:

                st.session_state.pop(
                    "editing_plan_id",
                    None
                )

                st.success(
                    result["message"]
                )

                st.rerun()

            else:

                st.error(
                    result["message"]
                )

def render_inactive_subscriptions():

    plans = get_inactive_subscription_plans()

    if not plans:

        st.info(
            "There are currently no inactive subscription plans."
        )

        return

    st.subheader("Inactive Subscription Plans")

    st.caption(
        "These subscription plans are no longer available "
        "for new hospital subscriptions."
    )

    for plan in plans:

        plan_id = plan["plan_id"]

        plan_name = plan["plan_name"]

        description = (
            plan["description"]
            or ""
        )

        price_monthly = (
            plan["price_monthly"]
            or 0
        )

        price_yearly = (
            plan["price_yearly"]
            or 0
        )

        max_users = plan["max_users"]

        max_patients = plan["max_patients"]

        max_xrays = plan["max_xrays_per_month"]

        with st.container(border=True):

            # ==================================
            # HEADER
            # ==================================

            header_col, status_col = st.columns(
                [4, 1]
            )

            with header_col:

                st.markdown(
                    f"### {plan_name}"
                )

                if description:

                    st.write(
                        description
                    )

            with status_col:

                st.warning(
                    "INACTIVE"
                )

            st.divider()

            # ==================================
            # PRICING
            # ==================================

            col1, col2 = st.columns(2)

            with col1:

                st.metric(
                    "Monthly",
                    f"₱{float(price_monthly):,.2f}"
                )

            with col2:

                st.metric(
                    "Yearly",
                    f"₱{float(price_yearly):,.2f}"
                )

            st.divider()

            # ==================================
            # LIMITS
            # ==================================

            col1, col2, col3 = st.columns(3)

            with col1:

                st.write("**Maximum Users**")

                st.write(
                    max_users
                    if max_users is not None
                    else "Unlimited"
                )

            with col2:

                st.write("**Maximum Patients**")

                st.write(
                    max_patients
                    if max_patients is not None
                    else "Unlimited"
                )

            with col3:

                st.write("**X-rays / Month**")

                st.write(
                    max_xrays
                    if max_xrays is not None
                    else "Unlimited"
                )

            st.divider()

            # ==================================
            # ACTIONS
            # ==================================

            col1, col2 = st.columns(2)

            with col1:

                if st.button(
                    "Activate",
                    key=f"activate_inactive_{plan_id}",
                    use_container_width=True
                ):

                    result = activate_subscription(
                        plan_id
                    )

                    if result["success"]:

                        st.success(
                            "Subscription plan activated successfully."
                        )

                        st.rerun()

                    else:

                        st.error(
                            result["message"]
                        )

            with col2:

                if st.button(
                    "Delete",
                    key=f"delete_inactive_{plan_id}",
                    use_container_width=True
                ):

                    st.session_state[
                        "delete_subscription_id"
                    ] = plan_id

                    st.rerun()

@st.dialog("Delete Subscription Plan")
def confirm_delete_subscription():

    plan_id = st.session_state.get(
        "delete_subscription_id"
    )

    if not plan_id:

        st.error(
            "No subscription plan selected."
        )

        return

    plans = get_inactive_subscription_plans()

    plan = next(
        (
            p
            for p in plans
            if p["plan_id"] == plan_id
        ),
        None
    )

    if not plan:

        st.error(
            "Subscription plan could not be found."
        )

        return

    st.warning(
        "This action cannot be undone."
    )

    st.write(
        "You are about to permanently delete:"
    )

    st.markdown(
        f"### {plan['plan_name']}"
    )

    if plan["description"]:

        st.write(
            plan["description"]
        )

    st.write(
        f"**Monthly Price:** "
        f"₱{float(plan['price_monthly'] or 0):,.2f}"
    )

    st.write(
        f"**Yearly Price:** "
        f"₱{float(plan['price_yearly'] or 0):,.2f}"
    )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "Cancel",
            use_container_width=True
        ):

            st.session_state.pop(
                "delete_subscription_id",
                None
            )

            st.rerun()

    with col2:

        if st.button(
            "Delete Permanently",
            type="primary",
            use_container_width=True
        ):

            result = delete_subscription(
                plan_id
            )

            if result["success"]:

                st.session_state.pop(
                    "delete_subscription_id",
                    None
                )

                st.success(
                    result["message"]
                )

                st.rerun()

            else:

                st.error(
                    result["message"]
                )


# ==========================================
# MAIN PAGE
# ==========================================

def show():

    st.title(
        "Manage Subscription"
    )

    st.caption(
        "Create and manage LungSight subscription plans."
    )

    editing_plan_id = (
        st.session_state.get(
            "editing_plan_id"
        )
    )

    delete_subscription_id = (
            st.session_state.get(
                "delete_subscription_id"
            )
        )

    if delete_subscription_id:

        confirm_delete_subscription()

    if editing_plan_id:

        plans = get_all_subscription_plans()

        selected_plan = next(
            (
                plan
                for plan in plans
                if plan["plan_id"] == editing_plan_id
            ),
            None
        )

        if selected_plan:

            render_edit_subscription_form(
                selected_plan
            )

    

            st.divider()

    tab1, tab2, tab3 = st.tabs(
    [
        "Subscription Plans",
        "Add New Subscription Plan",
        "Manage Inactive Plans"
    ]
)

    with tab1:

        render_subscriptions_table()

    with tab2:

        render_add_subscription_form()

    with tab3:

        render_inactive_subscriptions()