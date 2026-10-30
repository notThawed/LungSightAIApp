try:
    from streamlit_app.pages import hospital_reports
except ImportError:
    from pages import hospital_reports


def show():
    hospital_reports.show()
