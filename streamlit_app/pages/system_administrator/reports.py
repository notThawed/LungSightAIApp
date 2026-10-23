from shared.assets import load_css
from streamlit_app.components.ui import not_available_page


def show():

    load_css()

    not_available_page(
        "Reports",
        "System-wide reports on examinations, AI findings and hospital activity.",
        "Reports are not available yet. Live system activity is on the Dashboard.",
    )
