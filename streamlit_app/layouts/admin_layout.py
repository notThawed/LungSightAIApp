import streamlit as st
from components.sidebar import show_admin_sidebar
from components.navbar import show_top_navbar

from pages.admin import dashboard, manage_user, configure_system_settings, manage_hospital, subscription, reports

def show_admin_layout():

    page = show_admin_sidebar()

    page_info = {
        "Dashboard": "Admin dashboard for managing users and system settings.",
        "User Management": "Manage user accounts, roles, and permissions.",
        "System Settings": "Configure system-wide settings and preferences.",
        "Reports": "Generate and view system reports and analytics.",
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

    elif page == "Manage Hospital":
        manage_hospital.show()

    elif page == "Subscription":
        subscription.show()
        