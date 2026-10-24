import streamlit as st

from components.sidebar import show_physician_sidebar
from components.navbar import show_top_navbar

from pages.physician import dashboard, patient_queue, review_patient, physician_patient_records, profile, followups, inpatient_dashboard
from pages.hospital_administrator import subscription_gate
from pages.system_administrator import manage_medical_records

def show_physician_layout():

    page = show_physician_sidebar()

    last_page = st.session_state.get("_physician_last_page")

    if last_page != page:
        for key in (
            "physician_selected_patient",
            "physician_selected_category",
            "physician_selected_examination",
            "pr_external_record",
            "pr_external_displayed",
            "pf_fu_selected_patient_id",
            "follow_up_details_id",
            "reschedule_follow_up_id",
            "cancel_follow_up_id",
            "missed_follow_up_id",
            "physician_parent_view",
            "physician_prev_fu_view",
            "pf_fu_page",
            "pf_fu_query",
            "pf_fu_status_filter",
        ):
            st.session_state.pop(key, None)


    st.session_state["_physician_last_page"] = page


    page_info = {
        "Dashboard": "Track your patient workload, case highlights, and current diagnostic activity.",
        "Patient Queue": "Review incoming patients awaiting analysis, interpretation, or follow-up.",
        "Review Patient": "Open detailed clinical context and imaging to assess individual patient cases.",
        "Patient Records": "Access longitudinal records, notes, and prior imaging history.",
        "Profile": "Update your profile and physician-specific account preferences.",
    }
    show_top_navbar(page_name=page, page_info=page_info.get(page, "Page information is not available."))

    subscription_gate.render_subscription_warnings(can_renew=False)

    if page == "Dashboard":

        dashboard.show()

    elif page == "Patient Queue":

        patient_queue.show()

    elif page == "Review Patient":

        review_patient.show()

    elif page == "Patient Records":
        physician_patient_records.show()

    elif page == "Inpatient Dashboard":

        inpatient_dashboard.show()

    elif page == "Follow-Ups":

        followups.show()

    elif page == "Profile":

        profile.show()