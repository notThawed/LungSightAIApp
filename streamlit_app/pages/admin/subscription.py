import streamlit as st

from backend.subscriptions import (
    get_all_subscription_plans,
    create_subscription,
    edit_subscription,
    deactivate_subscription,
    activate_subscription
)


# ==========================================
# RENDER SUBSCRIPTIONS TABLE
# ==========================================

def render_subscriptions_table():

    plans = get_all_subscription_plans()

    if not plans:

        st.info(
            "No subscription plans found."
        )

        return

    st.subheader("Subscription Plans")

    for plan in plans:

        plan_id = plan["plan_id"]
        plan_name = plan["plan_name"]
        description = plan["description"] or ""

        price_monthly = plan["price_monthly"] or 0
        price_yearly = plan["price_yearly"] or 0

        max_users = plan["max_users"]
        max_patients = plan["max_patients"]
        max_xrays = plan["max_xrays_per_month"]

        is_active = plan["is_active"]

        # ==================================
        # PLAN CONTAINER
        # ==================================

        with st.container(border=True):

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

                if is_active:

                    st.success(
                        "ACTIVE"
                    )

                else:

                    st.error(
                        "INACTIVE"
                    )

            st.divider()

            # ==================================
            # PLAN INFORMATION
            # ==================================

            col1, col2, col3, col4 = st.columns(4)

            with col1:

                st.metric(
                    "Monthly",
                    f"₱{price_monthly:,.2f}"
                )

            with col2:

                st.metric(
                    "Yearly",
                    f"₱{price_yearly:,.2f}"
                )

            with col3:

                st.metric(
                    "Max Users",
                    max_users if max_users is not None else "Unlimited"
                )

            with col4:

                st.metric(
                    "Max Patients",
                    max_patients if max_patients is not None else "Unlimited"
                )

            st.write(
                f"**Maximum X-rays / Month:** "
                f"{max_xrays if max_xrays is not None else 'Unlimited'}"
            )

            st.divider()

            # ==================================
            # ACTIONS
            # ==================================

            edit_col, status_col = st.columns(
                2
            )

            with edit_col:

                if st.button(
                    "Edit Plan",
                    key=f"edit_{plan_id}",
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
                        key=f"deactivate_{plan_id}",
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
                        key=f"activate_{plan_id}",
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


# ==========================================
# ADD SUBSCRIPTION PLAN
# ==========================================

def render_add_subscription_form():

    st.subheader(
        "Add Subscription Plan"
    )

    with st.form(
        "add_subscription_form",
        clear_on_submit=True
    ):

        plan_name = st.text_input(
            "Plan Name",
            placeholder="e.g. Professional"
        )

        description = st.text_area(
            "Description",
            placeholder="Describe what this plan offers."
        )

        col1, col2 = st.columns(2)

        with col1:

            price_monthly = st.number_input(
                "Monthly Price (₱)",
                min_value=0.00,
                step=500.00,
                format="%.2f"
            )

        with col2:

            price_yearly = st.number_input(
                "Yearly Price (₱)",
                min_value=0.00,
                step=1000.00,
                format="%.2f"
            )

        st.markdown(
            "### Plan Limits"
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            max_users = st.number_input(
                "Maximum Users",
                min_value=0,
                step=1
            )

        with col2:

            max_patients = st.number_input(
                "Maximum Patients",
                min_value=0,
                step=100
            )

        with col3:

            max_xrays = st.number_input(
                "Maximum X-rays / Month",
                min_value=0,
                step=100
            )

        submitted = st.form_submit_button(
            "Create Subscription Plan",
            use_container_width=True
        )

        if submitted:

            if not plan_name.strip():

                st.error(
                    "Plan name is required."
                )

                return

            result = create_subscription(
                plan_name=plan_name.strip(),
                description=description.strip(),
                price_monthly=price_monthly,
                price_yearly=price_yearly,
                max_users=max_users,
                max_xrays_per_month=max_xrays,
                max_patients=max_patients
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


# ==========================================
# EDIT SUBSCRIPTION PLAN
# ==========================================

def render_edit_subscription_form(plan):

    st.subheader(
        f"Edit Subscription Plan: {plan['plan_name']}"
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
            value=plan["description"] or ""
        )

        col1, col2 = st.columns(2)

        with col1:

            price_monthly = st.number_input(
                "Monthly Price (₱)",
                min_value=0.00,
                value=float(
                    plan["price_monthly"] or 0
                ),
                step=500.00,
                format="%.2f"
            )

        with col2:

            price_yearly = st.number_input(
                "Yearly Price (₱)",
                min_value=0.00,
                value=float(
                    plan["price_yearly"] or 0
                ),
                step=1000.00,
                format="%.2f"
            )

        st.markdown(
            "### Plan Limits"
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            max_users = st.number_input(
                "Maximum Users",
                min_value=0,
                value=int(
                    plan["max_users"] or 0
                ),
                step=1
            )

        with col2:

            max_patients = st.number_input(
                "Maximum Patients",
                min_value=0,
                value=int(
                    plan["max_patients"] or 0
                ),
                step=100
            )

        with col3:

            max_xrays = st.number_input(
                "Maximum X-rays / Month",
                min_value=0,
                value=int(
                    plan["max_xrays_per_month"] or 0
                ),
                step=100
            )

        col1, col2 = st.columns(2)

        with col1:

            save = st.form_submit_button(
                "Save Changes",
                use_container_width=True
            )

        with col2:

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
                max_users=max_users,
                max_xrays_per_month=max_xrays,
                max_patients=max_patients
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


# ==========================================
# MAIN PAGE
# ==========================================

def show():

    st.title(
        "Manage Subscription"
    )

    st.caption(
        "Create, edit, activate, and deactivate "
        "LungSight subscription plans."
    )

    # ==========================================
    # CHECK IF EDITING
    # ==========================================

    editing_plan_id = (
        st.session_state.get(
            "editing_plan_id"
        )
    )

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

        else:

            st.session_state.pop(
                "editing_plan_id",
                None
            )

    # ==========================================
    # TABS
    # ==========================================

    tab1, tab2 = st.tabs(
        [
            "Subscription Plans",
            "Add New Plan"
        ]
    )

    with tab1:

        render_subscriptions_table()

    with tab2:

        render_add_subscription_form()