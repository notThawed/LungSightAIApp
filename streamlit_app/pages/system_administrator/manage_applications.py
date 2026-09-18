import streamlit as st

from backend.application_utils import (
    get_all_hospital_applications,
    get_hospital_application,
    approve_hospital_application,
    reject_hospital_application,
    delete_hospital_application,
)


# ============================================================
# APPLICATION DETAILS DIALOG
# ============================================================

@st.dialog(
    "Hospital Application Details",
    width="large"
)
def show_application_details(application_id):

    application = get_hospital_application(
        application_id
    )

    if not application:

        st.error(
            "Unable to load application details."
        )

        return

    # ========================================================
    # HEADER
    # ========================================================

    hospital_name = application.get(
        "hospital_name",
        "Unnamed Hospital"
    )

    application_status = application.get(
        "application_status",
        "Unknown"
    )

    st.markdown(
        f"## {hospital_name}"
    )

    if application_status == "Pending":

        st.warning(
            f"Application Status: {application_status}"
        )

    elif application_status == "Approved":

        st.success(
            f"Application Status: {application_status}"
        )

    elif application_status == "Rejected":

        st.error(
            f"Application Status: {application_status}"
        )

    else:

        st.info(
            f"Application Status: {application_status}"
        )

    st.divider()

    # ========================================================
    # HOSPITAL INFORMATION
    # ========================================================

    st.markdown(
        "### 1. Hospital Information"
    )

    col1, col2 = st.columns(2)

    with col1:

        st.write(
            f"**Hospital Name:** "
            f"{application.get('hospital_name', '-')}"
        )

        st.write(
            f"**Hospital Type:** "
            f"{application.get('hospital_type', '-')}"
        )

        st.write(
            f"**Hospital Email:** "
            f"{application.get('hospital_email', '-')}"
        )

        st.write(
            f"**Hospital Contact:** "
            f"{application.get('hospital_contact_number', '-')}"
        )

    with col2:

        st.write(
            f"**Complete Address:** "
            f"{application.get('hospital_address', '-')}"
        )

        st.write(
            f"**Hospital Website:** "
            f"{application.get('hospital_website') or '-'}"
        )

    st.divider()

    # ========================================================
    # AUTHORIZED REPRESENTATIVE
    # ========================================================

    st.markdown(
        "### 2. Authorized Representative"
    )

    representative_name = " ".join(
        filter(
            None,
            [
                application.get(
                    "applicant_first_name"
                ),
                application.get(
                    "applicant_middle_name"
                ),
                application.get(
                    "applicant_last_name"
                ),
            ]
        )
    )

    col1, col2 = st.columns(2)

    with col1:

        st.write(
            f"**Name:** "
            f"{representative_name or '-'}"
        )

        st.write(
            f"**Position / Designation:** "
            f"{application.get('applicant_position', '-')}"
        )

    with col2:

        st.write(
            f"**Email:** "
            f"{application.get('applicant_email', '-')}"
        )

        st.write(
            f"**Contact Number:** "
            f"{application.get('applicant_contact_number', '-')}"
        )

    st.divider()

    # ========================================================
    # SELECTED SUBSCRIPTION
    # ========================================================

    st.markdown(
        "### 3. Selected Subscription"
    )

    col1, col2 = st.columns(2)

    with col1:

        st.write(
            f"**Plan ID:** "
            f"{application.get('selected_plan_id', '-')}"
        )

        st.write(
            f"**Billing Cycle:** "
            f"{application.get('billing_cycle', '-')}"
        )

    with col2:

        st.write(
            f"**Application Status:** "
            f"{application.get('application_status', '-')}"
        )

    st.divider()

    # ========================================================
    # HOSPITAL ADMINISTRATOR
    # ========================================================

    st.markdown(
        "### 4. Hospital Administrator"
    )

    administrator_name = " ".join(
        filter(
            None,
            [
                application.get(
                    "admin_first_name"
                ),
                application.get(
                    "admin_middle_name"
                ),
                application.get(
                    "admin_last_name"
                ),
            ]
        )
    )

    col1, col2 = st.columns(2)

    with col1:

        st.write(
            f"**Name:** "
            f"{administrator_name or '-'}"
        )

        st.write(
            f"**Email:** "
            f"{application.get('admin_email', '-')}"
        )

    with col2:

        st.write(
            f"**Contact Number:** "
            f"{application.get('admin_contact_number', '-')}"
        )

    st.divider()

    # ========================================================
    # AGREEMENT
    # ========================================================

    st.markdown(
        "### 5. Agreement"
    )

    agreement_accepted = application.get(
        "agreement_accepted",
        False
    )

    if agreement_accepted:

        st.success(
            "Service agreement accepted."
        )

    else:

        st.warning(
            "Service agreement has not been accepted."
        )

    agreement_accepted_at = application.get(
        "agreement_accepted_at"
    )

    if agreement_accepted_at:

        st.caption(
            f"Accepted At: {agreement_accepted_at}"
        )

    st.divider()

    # ========================================================
    # APPLICATION INFORMATION
    # ========================================================

    st.markdown(
        "### 6. Application Information"
    )

    col1, col2 = st.columns(2)

    with col1:

        st.write(
            f"**Application ID:** "
            f"{application.get('application_id', '-')}"
        )

        st.write(
            f"**Created At:** "
            f"{application.get('created_at', '-')}"
        )

    with col2:

        st.write(
            f"**Updated At:** "
            f"{application.get('updated_at', '-')}"
        )

    st.divider()

    # ========================================================
    # CLOSE
    # ========================================================

    if st.button(
        "Close",
        use_container_width=True,
        key=f"close_application_{application_id}"
    ):

        st.rerun()


# ============================================================
# APPROVE APPLICATION DIALOG
# ============================================================

@st.dialog(
    "Approve Hospital Application",
    width="small"
)
def show_approve_dialog(application_id):

    application = get_hospital_application(
        application_id
    )

    if not application:

        st.error(
            "Application could not be found."
        )

        return

    hospital_name = application.get(
        "hospital_name",
        "this hospital"
    )

    st.markdown(
        f"### Approve Application?"
    )

    st.write(
        f"Are you sure you want to approve the "
        f"application for **{hospital_name}**?"
    )

    st.info(
        "The application status will be changed to "
        "**Approved**."
    )

    st.warning(
        "Please make sure you have reviewed the "
        "application information before approving it."
    )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "Cancel",
            use_container_width=True,
            key=f"cancel_approve_{application_id}"
        ):

            st.rerun()

    with col2:

        if st.button(
            "Approve",
            type="primary",
            use_container_width=True,
            key=f"confirm_approve_{application_id}"
        ):

            result = approve_hospital_application(
                application_id
            )

            if result["success"]:

                st.success(
                    "Application approved successfully."
                )

                st.rerun()

            else:

                st.error(
                    f"Unable to approve application: "
                    f"{result['message']}"
                )


# ============================================================
# REJECT APPLICATION DIALOG
# ============================================================

@st.dialog(
    "Reject Hospital Application",
    width="small"
)
def show_reject_dialog(application_id):

    application = get_hospital_application(
        application_id
    )

    if not application:

        st.error(
            "Application could not be found."
        )

        return

    hospital_name = application.get(
        "hospital_name",
        "this hospital"
    )

    st.markdown(
        "### Reject Application?"
    )

    st.write(
        f"Are you sure you want to reject the "
        f"application for **{hospital_name}**?"
    )

    st.warning(
        "The application will be marked as **Rejected**."
    )

    st.caption(
        "Rejected applications can be reviewed later "
        "and permanently deleted from the Rejected Applications tab."
    )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "Cancel",
            use_container_width=True,
            key=f"cancel_reject_{application_id}"
        ):

            st.rerun()

    with col2:

        if st.button(
            "Reject",
            use_container_width=True,
            key=f"confirm_reject_{application_id}"
        ):

            result = reject_hospital_application(
                application_id
            )

            if result["success"]:

                st.success(
                    "Application rejected successfully."
                )

                st.rerun()

            else:

                st.error(
                    f"Unable to reject application: "
                    f"{result['message']}"
                )


# ============================================================
# DELETE REJECTED APPLICATION DIALOG
# ============================================================

@st.dialog(
    "Delete Rejected Application",
    width="small"
)
def show_delete_dialog(application_id):

    application = get_hospital_application(
        application_id
    )

    if not application:

        st.error(
            "Application could not be found."
        )

        return

    hospital_name = application.get(
        "hospital_name",
        "this hospital"
    )

    application_status = application.get(
        "application_status"
    )

    # --------------------------------------------------------
    # SAFETY CHECK
    # --------------------------------------------------------

    if application_status != "Rejected":

        st.error(
            "Only rejected applications can be deleted."
        )

        return

    # ========================================================
    # WARNING
    # ========================================================

    st.markdown(
        "### Permanently Delete Application?"
    )

    st.write(
        f"You are about to permanently delete the "
        f"application for **{hospital_name}**."
    )

    st.error(
        "This action cannot be undone."
    )

    st.warning(
        "All application information stored in this "
        "application record will be permanently removed."
    )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "Cancel",
            use_container_width=True,
            key=f"cancel_delete_{application_id}"
        ):

            st.rerun()

    with col2:

        if st.button(
            "Delete Permanently",
            use_container_width=True,
            key=f"confirm_delete_{application_id}"
        ):

            result = delete_hospital_application(
                application_id
            )

            if result["success"]:

                st.success(
                    "Rejected application deleted successfully."
                )

                st.rerun()

            else:

                st.error(
                    f"Unable to delete application: "
                    f"{result['message']}"
                )


# ============================================================
# APPLICATION CARD
# ============================================================

def render_application_card(
    application,
    show_actions=False,
    allow_delete=False
):

    application_id = application.get(
        "application_id"
    )

    hospital_name = application.get(
        "hospital_name",
        "Unnamed Hospital"
    )

    application_status = application.get(
        "application_status",
        "Unknown"
    )

    applicant_name = " ".join(
        filter(
            None,
            [
                application.get(
                    "applicant_first_name"
                ),
                application.get(
                    "applicant_last_name"
                ),
            ]
        )
    )

    created_at = application.get(
        "created_at",
        "-"
    )

    # ========================================================
    # CARD
    # ========================================================

    with st.container(
        border=True
    ):

        col1, col2, col3 = st.columns(
            [4, 3, 2]
        )

        # ----------------------------------------------------
        # HOSPITAL
        # ----------------------------------------------------

        with col1:

            st.markdown(
                f"### {hospital_name}"
            )

            st.caption(
                f"Applicant: "
                f"{applicant_name or '-'}"
            )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        with col2:

            if application_status == "Pending":

                st.warning(
                    f"Status: {application_status}"
                )

            elif application_status == "Approved":

                st.success(
                    f"Status: {application_status}"
                )

            elif application_status == "Rejected":

                st.error(
                    f"Status: {application_status}"
                )

            else:

                st.info(
                    f"Status: {application_status}"
                )

            st.caption(
                f"Submitted: {created_at}"
            )

        # ----------------------------------------------------
        # ACTIONS
        # ----------------------------------------------------

        with col3:

            if st.button(
                "View Details",
                use_container_width=True,
                key=f"view_{application_id}"
            ):

                show_application_details(
                    application_id
                )

            # ------------------------------------------------
            # PENDING ACTIONS
            # ------------------------------------------------

            if show_actions:

                if st.button(
                    "Approve",
                    type="primary",
                    use_container_width=True,
                    key=f"approve_{application_id}"
                ):

                    show_approve_dialog(
                        application_id
                    )

                if st.button(
                    "Reject",
                    use_container_width=True,
                    key=f"reject_{application_id}"
                ):

                    show_reject_dialog(
                        application_id
                    )

            # ------------------------------------------------
            # DELETE REJECTED APPLICATION
            # ------------------------------------------------

            if allow_delete:

                if st.button(
                    "Delete",
                    use_container_width=True,
                    key=f"delete_{application_id}"
                ):

                    show_delete_dialog(
                        application_id
                    )


# ============================================================
# MAIN PAGE
# ============================================================

def show():

    # ========================================================
    # PAGE HEADER
    # ========================================================

    st.title(
        "Hospital Applications"
    )

    st.caption(
        "Review and manage hospital subscription applications."
    )

    st.divider()

    # ========================================================
    # GET APPLICATIONS
    # ========================================================

    applications = get_all_hospital_applications()

    # ========================================================
    # FILTER APPLICATIONS
    # ========================================================

    pending_applications = [
        application
        for application in applications
        if application.get(
            "application_status"
        ) == "Pending"
    ]

    approved_applications = [
        application
        for application in applications
        if application.get(
            "application_status"
        ) == "Approved"
    ]

    rejected_applications = [
        application
        for application in applications
        if application.get(
            "application_status"
        ) == "Rejected"
    ]

    # ========================================================
    # SUMMARY
    # ========================================================

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Pending Applications",
            len(pending_applications)
        )

    with col2:

        st.metric(
            "Approved Applications",
            len(approved_applications)
        )

    with col3:

        st.metric(
            "Rejected Applications",
            len(rejected_applications)
        )

    st.divider()

    # ========================================================
    # TABS
    # ========================================================

    pending_tab, approved_tab, rejected_tab = st.tabs(
        [
            "View All Pending Applications",
            "View All Approved Applications",
            "View All Rejected Applications",
        ]
    )

    # ========================================================
    # PENDING TAB
    # ========================================================

    with pending_tab:

        st.markdown(
            "### Pending Applications"
        )

        st.caption(
            "Applications waiting for System Administrator review."
        )

        if not pending_applications:

            st.info(
                "There are no pending hospital applications."
            )

        else:

            for application in pending_applications:

                render_application_card(
                    application,
                    show_actions=True
                )

    # ========================================================
    # APPROVED TAB
    # ========================================================

    with approved_tab:

        st.markdown(
            "### Approved Applications"
        )

        st.caption(
            "Hospital applications that have been approved."
        )

        if not approved_applications:

            st.info(
                "There are no approved hospital applications."
            )

        else:

            for application in approved_applications:

                render_application_card(
                    application
                )

    # ========================================================
    # REJECTED TAB
    # ========================================================

    with rejected_tab:

        st.markdown(
            "### Rejected Applications"
        )

        st.caption(
            "Applications that were rejected by the System Administrator."
        )

        if not rejected_applications:

            st.info(
                "There are no rejected hospital applications."
            )

        else:

            st.warning(
                "Deleting a rejected application is permanent "
                "and cannot be undone."
            )

            for application in rejected_applications:

                render_application_card(
                    application,
                    allow_delete=True
                )