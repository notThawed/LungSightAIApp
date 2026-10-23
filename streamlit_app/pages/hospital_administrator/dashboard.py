from streamlit_app.components.role_dashboard import show_role_dashboard


def show():

    show_role_dashboard(
        "Hospital dashboard",
        "Examination activity across your hospital.",
        [
            ("Manage users", "Manage Users", "manage_accounts"),
            ("Manage patients", "Manage Patients", "group"),
            ("Subscription usage", "Subscription Usage", "data_usage"),
        ],
        show_ai_note=False,
    )
