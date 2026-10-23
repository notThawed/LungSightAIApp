from components.sidebar import show_staff_sidebar
from components.navbar import show_top_navbar

from pages.staff import dashboard, followups
from pages.system_administrator import manage_patients, manage_examinations, manage_medical_records

from pages.hospital_administrator import subscription_gate
from pages import profile

def show_staff_layout():

    page = show_staff_sidebar()

    page_info = {
        "Dashboard": "Follow-ups and registrations for your hospital at a glance.",
        "Register Patient": "Register new patients and update patient details.",
        "Patient Records": "Browse patient medical records and examination history.",
        "Examinations": "Create and track patient examinations.",
        "Follow-Ups": "Today's follow-up appointments and their status.",
        "Profile": "Update your profile, password and preferences.",
    }
    show_top_navbar(page_name=page, page_info=page_info.get(page, "Page information is not available."))
    subscription_gate.render_subscription_warnings(can_renew=False)

    if page == "Dashboard":

        dashboard.show()

    if page == "Register Patient":
        manage_patients.show()

    if page == "Examinations":
        manage_examinations.show()

    if page == "Patient Records":
        manage_medical_records.show()

    if page == "Follow-Ups":
        followups.show()

    if page == "Profile":
        profile.show()