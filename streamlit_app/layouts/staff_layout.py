from components.sidebar import show_staff_sidebar
from components.navbar import show_top_navbar

from pages.staff import dashboard

def show_staff_layout():

    page = show_staff_sidebar()

    page_info = {
        "Dashboard": "Track your patient workload, case highlights, and current diagnostic activity."
    }
    show_top_navbar(page_name=page, page_info=page_info.get(page, "Page information is not available."))

    if page == "Dashboard":

        dashboard.show()