from components.sidebar import show_admin_sidebar
from components.navbar import show_top_navbar

from pages.system_administrator import dashboard, manage_user, configure_system_settings, reports, manage_subscriptions, training_data_review
from streamlit_app.pages.system_administrator import manage_applications, manage_patients, manage_examinations, manage_medical_records, manage_hospital
from streamlit_app.pages import profile
from pages import audit_logs, notification_history

def show_system_admin_layout():

    page = show_admin_sidebar()

    page_info = {
        "Dashboard": "Admin dashboard for managing users and system settings.",
        "User Management": "Manage user accounts, roles, and permissions.",
        "System Settings": "Configure system-wide settings and preferences.",
        "Reports": "Generate and view system reports and analytics.",
        "Manage Patients": "Manage Patient informations",
        "Manage Examinations": "Manage Patient Examinations",
        "Audit Logs": "Review security and activity events across all hospitals.",
        "Email Notifications": "Delivery history of LungSight emails, with retry for failed ones.",
        "Profile": "Update your profile and admin-specific account preferences.",
    }
    show_top_navbar(page_name=page, page_info=page_info.get(page, "Page information is not available."))

    if page == "Dashboard":
        dashboard.show()

    elif page == "User Management":
        manage_user.show()

    elif page == "System Settings":
        configure_system_settings.show()

    elif page == "Reports":
        reports.show()

    elif page == "Audit Logs":
        audit_logs.show()

    elif page == "Email Notifications":
        notification_history.show()

    elif page == "Training":
        training_data_review.show()

    elif page == "Manage Patients":
        manage_patients.show()

    elif page == "Manage Examinations":
        manage_examinations.show()

    elif page == "Manage Subscriptions":
        manage_subscriptions.show()

    elif page == "Manage Client Applications":
        manage_applications.show()

    elif page == "Medical Records":
        manage_medical_records.show()

    elif page == "Manage Hospitals":
        manage_hospital.show()

    elif page == "Profile":
        profile.show()

        