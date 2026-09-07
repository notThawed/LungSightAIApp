from pathlib import Path
from PyQt6.QtWidgets import QMessageBox
from PyQt6 import uic

class UiLoader:

    def load_ui(self, filename):
        ui_path = Path(__file__).parent.parent / "ui" / filename
        uic.loadUi(str(ui_path), self)

    def logout(self):
        reply = QMessageBox.question(
            self,
            "Logout",
            "Are you sure you want to logout?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            from .login_window import LoginWindow

            self.login_window = LoginWindow()
            self.login_window.show()
            self.close()