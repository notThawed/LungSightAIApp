from components.sidebar import show_physician_sidebar
from components.navbar import show_top_navbar

from pages.physician import dashboard, patient_queue, review_patient, records, profile

def show_physician_layout():

    page = show_physician_sidebar()

    page_info = {
        "Dashboard": "Track your patient workload, case highlights, and current diagnostic activity.",
        "Patient Queue": "Review incoming patients awaiting analysis, interpretation, or follow-up.",
        "Review Patient": "Open detailed clinical context and imaging to assess individual patient cases.",
        "Patient Records": "Access longitudinal records, notes, and prior imaging history.",
        "Profile": "Update your profile and physician-specific account preferences.",
    }
    show_top_navbar(page_name=page, page_info=page_info.get(page, "Page information is not available."))

    if page == "Dashboard":

        dashboard.show()

    elif page == "Patient Queue":

        patient_queue.show()

    elif page == "Review Patient":

        review_patient.show()

    elif page == "Patient Records":

        records.show()

    elif page == "Profile":

        profile.show()