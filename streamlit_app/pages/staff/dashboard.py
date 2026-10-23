from streamlit_app.components.role_dashboard import show_role_dashboard


def show():

    show_role_dashboard(
        "Staff dashboard",
        "Follow-up appointments and patient registrations for your hospital.",
        [
            ("Register patient", "Register Patient", "person_add"),
            ("Follow-ups", "Follow-Ups", "event_available"),
            ("Examinations", "Examinations", "assignment"),
        ],
        show_ai_note=False,
    )
