from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor


class Sidebar(QFrame):
    """Clean and simple sidebar navigation."""

    page_changed = pyqtSignal(str)
    logout_clicked = pyqtSignal()

    def __init__(self, user: dict, parent=None):
        super().__init__(parent)
        self.user = user or {}
        self.role = self.user.get("role", "Radiologist")
        self.setObjectName("simpleSidebar")
        self.setFixedWidth(220)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 16, 10, 16)
        layout.setSpacing(4)

        # 1. Logo Box
        logo_box = QVBoxLayout()
        logo_box.setContentsMargins(10, 0, 10, 14)
        logo_box.setSpacing(2)

        lbl_title = QLabel("🫁 LungSight AI")
        lbl_title.setObjectName("sidebarLogoTitle")

        lbl_sub = QLabel("Chest X-Ray Diagnostics")
        lbl_sub.setObjectName("sidebarLogoSub")

        logo_box.addWidget(lbl_title)
        logo_box.addWidget(lbl_sub)
        layout.addLayout(logo_box)

        # 2. Navigation Items
        self.nav_items = self._get_nav_items(self.role)
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        self.buttons = {}

        for page_name, icon in self.nav_items:
            btn = QPushButton(f" {icon}  {page_name}")
            btn.setProperty("class", "nav-btn")
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda checked, name=page_name: self._on_btn_clicked(name))

            self.btn_group.addButton(btn)
            layout.addWidget(btn)
            self.buttons[page_name] = btn

        if self.nav_items:
            self.buttons[self.nav_items[0][0]].setChecked(True)

        layout.addStretch()

        # 3. Log Out
        btn_logout = QPushButton(" 🚪  Sign Out")
        btn_logout.setProperty("class", "logout-btn")
        btn_logout.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_logout.clicked.connect(self.logout_clicked.emit)
        layout.addWidget(btn_logout)

    def _get_nav_items(self, role: str) -> list[tuple[str, str]]:
        if role == "Radiologist":
            return [
                ("Dashboard", "📊"),
                ("Patient Queue", "👥"),
                ("Analyze X-Ray", "🔬"),
                ("Patient Records", "📁"),
                ("Profile", "👤"),
            ]
        elif role == "Radiologic Technologist":
            return [
                ("Dashboard", "📊"),
                ("Analyze X-Ray", "🩻"),
                ("Patient Records", "📁"),
                ("Reports", "📑"),
                ("Geospatial Map", "🗺️"),
                ("Profile", "👤"),
            ]
        else:  # Admin
            return [
                ("Dashboard", "📊"),
                ("User Management", "👥"),
                ("Manage Clients", "🏥"),
                ("Subscription", "💳"),
                ("System Settings", "⚙️"),
                ("Profile", "👤"),
            ]

    def _on_btn_clicked(self, page_name: str):
        self.page_changed.emit(page_name)

    def select_page(self, page_name: str):
        if page_name in self.buttons:
            self.buttons[page_name].setChecked(True)
