from datetime import datetime
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel
)
from PyQt6.QtCore import Qt, QTimer


class TopNavbar(QFrame):
    """Clean and simple top navigation bar."""

    def __init__(self, user: dict, parent=None):
        super().__init__(parent)
        self.user = user or {}
        self.setObjectName("simpleNavbar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(54)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(14)

        # Current Page Title
        self.lbl_title = QLabel("Dashboard")
        self.lbl_title.setObjectName("pageTitle")
        layout.addWidget(self.lbl_title)

        layout.addStretch()

        # Clock / Date
        self.lbl_date = QLabel()
        self.lbl_date.setStyleSheet("color: #64748B; font-size: 12px; font-weight: 600;")
        self._update_date()
        layout.addWidget(self.lbl_date)

        timer = QTimer(self)
        timer.timeout.connect(self._update_date)
        timer.start(10000)

        # User Avatar & Name
        name = self.user.get("name", "User")
        role = self.user.get("role", "Radiologist")

        avatar = QLabel(self._get_initials(name))
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFixedSize(32, 32)
        avatar.setStyleSheet("background-color: #0284C7; color: #FFFFFF; font-weight: 800; font-size: 12px; border-radius: 16px;")
        layout.addWidget(avatar)

        user_info = QVBoxLayout()
        user_info.setSpacing(1)
        user_info.setContentsMargins(0, 8, 0, 8)

        lbl_name = QLabel(name)
        lbl_name.setObjectName("navUserName")

        lbl_role = QLabel(role)
        lbl_role.setObjectName("navUserRole")

        user_info.addWidget(lbl_name)
        user_info.addWidget(lbl_role)
        layout.addLayout(user_info)

    def set_page_title(self, title: str):
        self.lbl_title.setText(title)

    def _update_date(self):
        self.lbl_date.setText(datetime.now().strftime("%A, %B %d, %Y"))

    def _get_initials(self, name: str) -> str:
        parts = [p for p in name.strip().split() if p]
        if not parts:
            return "U"
        if len(parts) == 1:
            return parts[0][0].upper()
        return f"{parts[0][0]}{parts[-1][0]}".upper()
