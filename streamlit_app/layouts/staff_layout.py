from components.sidebar import show_staff_sidebar
from components.navbar import show_top_navbar

from pages.staff import dashboard
from pages.system_administrator import manage_patients, manage_examinations, manage_medical_records

from pages.hospital_administrator import subscription_gate

def show_staff_layout():

    page = show_staff_sidebar()

    page_info = {
        "Dashboard": "Track your patient workload, case highlights, and current diagnostic activity."
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