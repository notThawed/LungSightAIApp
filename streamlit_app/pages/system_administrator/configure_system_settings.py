from shared.assets import load_css
from streamlit_app.components.ui import not_available_page


def show():

    load_css()

    not_available_page(
        "System settings",
        "System-wide configuration for LungSightAI.",
        "System settings are not available yet.",
    )
