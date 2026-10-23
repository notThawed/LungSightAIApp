from streamlit_app.components.role_dashboard import show_role_dashboard


def show():

    show_role_dashboard(
        "Radiologist dashboard",
        "Your hospital's diagnostic workload at a glance.",
        [
            ("Patient queue", "Patient Queue", "groups"),
            ("Review patient", "Review Patient", "person_search"),
            ("Follow-ups", "Follow-Ups", "event_available"),
        ],
    )
