import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QMessageBox
)
from PyQt6.QtCore import Qt

from pyqt_app.styles import MAIN_STYLESHEET
from pyqt_app.auth_window import AuthWindow
from pyqt_app.components.sidebar import Sidebar
from pyqt_app.components.navbar import TopNavbar
from pyqt_app.views.radiologist_view import RadiologistView
from pyqt_app.views.radtech_view import RadTechView
from pyqt_app.views.admin_view import AdminView


class DashboardWindow(QMainWindow):
    """Clean and Simple Desktop Workspace Window."""

    def __init__(self, user: dict, parent=None):
        super().__init__(parent)
        self.user = user or {}
        self.role = self.user.get("role", "Radiologist")

        self.setWindowTitle(f"LungSight AI — {self.role} Workspace")
        self.resize(1200, 750)
        self.setMinimumSize(1000, 650)

        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Sidebar Navigation
        self.sidebar = Sidebar(self.user, self)
        self.sidebar.page_changed.connect(self._on_page_changed)
        self.sidebar.logout_clicked.connect(self._handle_logout)
        root_layout.addWidget(self.sidebar)

        # 2. Right Content Area (Navbar + View)
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Top Navbar
        self.navbar = TopNavbar(self.user, self)
        right_layout.addWidget(self.navbar)

        # Role View
        self.role_view = self._create_role_view(self.role)
        right_layout.addWidget(self.role_view, 1)

        root_layout.addWidget(right_container, 1)

        # Initial Page
        self._on_page_changed("Dashboard")

    def _create_role_view(self, role: str) -> QWidget:
        if role == "Radiologist":
            return RadiologistView(self.user, self)
        elif role == "Radiologic Technologist":
            return RadTechView(self.user, self)
        else:  # Hospital Admin
            return AdminView(self.user, self)

    def _on_page_changed(self, page_name: str):
        self.navbar.set_page_title(page_name)
        self.sidebar.select_page(page_name)

        if hasattr(self.role_view, "navigate_to"):
            self.role_view.navigate_to(page_name)

    def _handle_logout(self):
        reply = QMessageBox.question(
            self,
            "Confirm Sign Out",
            "Are you sure you want to sign out of LungSight AI?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            global auth_win, dash_win
            dash_win.close()
            auth_win = AuthWindow()
            auth_win.login_successful.connect(launch_dashboard)
            auth_win.show()


auth_win = None
dash_win = None


def launch_dashboard(user: dict):
    global auth_win, dash_win
    if auth_win:
        auth_win.close()
    dash_win = DashboardWindow(user)
    dash_win.show()


def main():
    global auth_win
    app = QApplication(sys.argv)
    app.setStyleSheet(MAIN_STYLESHEET)

    auth_win = AuthWindow()
    auth_win.login_successful.connect(launch_dashboard)
    auth_win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()