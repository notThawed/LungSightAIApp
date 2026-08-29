import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6 import uic

from backend.supabase_client import supabase


# Folder where main.py is located
BASE_DIR = Path(__file__).resolve().parent


app = QApplication(sys.argv)


# Load Sign-In window
window = uic.loadUi(
    str(BASE_DIR / "mainwindow.ui")
)


dashboard = None


def login():
    email = window.txt_email.text().strip()
    password = window.txt_password.text()

    if not email or not password:
        QMessageBox.warning(
            window,
            "Missing Information",
            "Please enter your email and password."
        )
        return

    try:
        response = supabase.auth.sign_in_with_password(
            {
                "email": email,
                "password": password
            }
        )

        if response.user:
            open_dashboard()

        else:
            QMessageBox.warning(
                window,
                "Login Failed",
                "Invalid email or password."
            )

    except Exception as error:
        QMessageBox.critical(
            window,
            "Login Failed",
            str(error)
        )


def open_dashboard():
    global dashboard

    dashboard = uic.loadUi(
        str(BASE_DIR / "dashboard.ui")
    )

    dashboard.btn_signout.clicked.connect(sign_out)

    dashboard.show()
    window.close()


def sign_out():
    global dashboard

    try:
        supabase.auth.sign_out()

        dashboard.close()

        window.txt_email.clear()
        window.txt_password.clear()

        window.show()

    except Exception as error:
        QMessageBox.critical(
            dashboard,
            "Logout Failed",
            str(error)
        )


window.btn_signin.clicked.connect(login)


window.show()

sys.exit(app.exec())