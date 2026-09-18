from components.sidebar import show_hospital_admin_sidebar
from components.navbar import show_top_navbar

from pages.hospital_administrator import dashboard

def show_hospital_admin_layout():

    page = show_hospital_admin_sidebar()

    page_info = {
        "Dashboard": "Track your patient workload, case highlights, and current diagnostic activity."
    }
    show_top_navbar(page_name=page, page_info=page_info.get(page, "Page information is not available."))

    if page == "Dashboard":

        dashboard.show()