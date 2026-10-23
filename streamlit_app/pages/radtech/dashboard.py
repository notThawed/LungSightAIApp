from streamlit_app.components.role_dashboard import show_role_dashboard


def show():

    show_role_dashboard(
        "Radiologic technologist dashboard",
        "Imaging requests and AI analysis status for your hospital.",
        [
            ("X-ray queue", "X-ray Queue", "pending_actions"),
            ("Analyze X-ray", "Analyze X-Ray", "radiology"),
            ("Patient records", "Patient Records", "folder_shared"),
        ],
    )
