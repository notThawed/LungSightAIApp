# windows/login_window.py
from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QDialog, QMessageBox
from .base_window import UiLoader
from backend.auth import login_user
from .super_admin.super_admin_window import Superadmin_Window

class LoginWindow(QDialog, UiLoader):
    def __init__(self):
        super().__init__()
        self.load_ui("login.ui")

        self.login_button.clicked.connect(self.login_function)

    def login_function(self):
        email = self.email.text()
        password = self.password.text()

        try:
            user = login_user(email, password)
            

            if user.get("role") == "Superadmin":
                self.superadmin_window = Superadmin_Window(user)
                self.superadmin_window.show()
                self.close()
                return

            

        except Exception as e:
            QMessageBox.critical(
                self,
                "Login Failed",
                str(e)
            )
