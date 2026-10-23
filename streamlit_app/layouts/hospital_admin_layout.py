from components.sidebar import show_hospital_admin_sidebar
from components.navbar import show_top_navbar

from pages.system_administrator import manage_user, manage_patients, manage_examinations

from pages.hospital_administrator import dashboard, subscription_gate, subscription_usage, hospital_info, subscription_settings
from pages import profile


def show_hospital_admin_layout():

    page = show_hospital_admin_sidebar()

    page_info = {
        "Dashboard": "Examination activity across your hospital.",
        "My Hospital": "Your hospital's details, address and logo.",
        "Manage Users": "Invite and manage hospital staff accounts and roles.",
        "Manage Patients": "Register and manage patients of your hospital.",
        "Manage Examinations": "Review examinations and their status.",
        "Subscription Usage": "Plan limits and how much of them your hospital has used.",
        "Subscription Settings": "Change, renew or cancel your hospital's subscription.",
        "Profile": "Update your profile, password and preferences.",
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

    if page == "Profile":
        profile.show()
