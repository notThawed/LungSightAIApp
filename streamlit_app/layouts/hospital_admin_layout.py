from components.sidebar import show_hospital_admin_sidebar
from components.navbar import show_top_navbar

from pages.system_administrator import manage_user, manage_patients, manage_examinations

from pages.hospital_administrator import dashboard, subscription_gate, subscription_usage, hospital_info, subscription_settings
from pages import profile, audit_logs


def show_hospital_admin_layout():

    page = show_hospital_admin_sidebar()

    page_info = {
        "Dashboard": "Track your patient workload, case highlights, and current diagnostic activity.",
        "Audit Logs": "Review security and activity events recorded for your hospital.",
    }
    show_top_navbar(page_name=page, page_info=page_info.get(page, "Page information is not available."))

    subscription_gate.render_subscription_warnings(can_renew=True)

    if page == "Dashboard":
        dashboard.show()

    if page == "My Hospital":
        hospital_info.show()

    if page == "Manage Users":
        manage_user.show()

    if page == "Manage Patients":
        manage_patients.show()

    if page == "Manage Examinations":
        manage_examinations.show()

    if page == "Subscription Usage":
        subscription_usage.show()

    if page == "Subscription Settings":
        subscription_settings.show()

    if page == "Audit Logs":
        audit_logs.show()

    if page == "Profile":
        profile.show()
