from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QDialog,
    QStackedWidget, QScrollArea, QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt

from pyqt_app.components.cards import MetricCard, StatusBadge


class AddUserDialog(QDialog):
    """Dialog to register new clinical staff account."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Register Staff Account")
        self.setFixedWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        lbl = QLabel("Register Clinical Staff")
        lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #0F172A;")
        layout.addWidget(lbl)

        self.txt_first = QLineEdit()
        self.txt_first.setPlaceholderText("First Name")
        self.txt_last = QLineEdit()
        self.txt_last.setPlaceholderText("Last Name")
        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("Staff Email (@lungsight.ai)")

        self.cb_role = QComboBox()
        self.cb_role.addItems(["Radiologist", "Radiologic Technologist", "Hospital Admin"])

        layout.addWidget(self.txt_first)
        layout.addWidget(self.txt_last)
        layout.addWidget(self.txt_email)
        layout.addWidget(self.cb_role)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setProperty("class", "btn-secondary")
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Save Staff")
        btn_save.setProperty("class", "btn-primary")
        btn_save.clicked.connect(self.accept)

        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def get_data(self):
        return {
            "name": f"{self.txt_first.text().strip()} {self.txt_last.text().strip()}",
            "email": self.txt_email.text().strip(),
            "role": self.cb_role.currentText(),
        }


class AdminView(QWidget):
    """Clean & Simple Administrator Workspace."""

    def __init__(self, user: dict, parent=None):
        super().__init__(parent)
        self.user = user or {}

        self.staff_data = [
            {"id": "1", "name": "Dr. Sarah Jenkins", "email": "radiologist@lungsight.ai", "role": "Radiologist", "status": "Active"},
            {"id": "2", "name": "Alex Rivera", "email": "radtech@lungsight.ai", "role": "Radiologic Technologist", "status": "Active"},
            {"id": "3", "name": "Marcus Vance", "email": "admin@lungsight.ai", "role": "Hospital Admin", "status": "Active"},
            {"id": "4", "name": "Dr. Emily Wong", "email": "e.wong@lungsight.ai", "role": "Radiologist", "status": "On-Call"},
        ]

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        self.stacked_widget = QStackedWidget(self)
        main_layout.addWidget(self.stacked_widget)

        # Pages
        self.page_dashboard = self._create_dashboard_page()
        self.page_users = self._create_users_page()
        self.page_clients = self._create_clients_page()
        self.page_subscription = self._create_subscription_page()
        self.page_settings = self._create_settings_page()
        self.page_profile = self._create_profile_page()

        self.stacked_widget.addWidget(self.page_dashboard)     # 0
        self.stacked_widget.addWidget(self.page_users)         # 1
        self.stacked_widget.addWidget(self.page_clients)       # 2
        self.stacked_widget.addWidget(self.page_subscription)  # 3
        self.stacked_widget.addWidget(self.page_settings)      # 4
        self.stacked_widget.addWidget(self.page_profile)       # 5

        self.page_map = {
            "Dashboard": 0,
            "User Management": 1,
            "Manage Clients": 2,
            "Subscription": 3,
            "System Settings": 4,
            "Profile": 5,
        }

    def navigate_to(self, page_name: str):
        if page_name in self.page_map:
            self.stacked_widget.setCurrentIndex(self.page_map[page_name])

    # =========================================================================
    # 1. DASHBOARD
    # =========================================================================
    def _create_dashboard_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 16)
        layout.setSpacing(16)

        # 4 Metric Cards
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(12)

        c1 = MetricCard("Total Scans Today", "142", "+14% vs avg", "🩻")
        c2 = MetricCard("Pneumonia Cases", "38", "26.7% Detection rate", "🫁")
        c3 = MetricCard("Active Staff", "6", "On-duty today", "👥")
        c4 = MetricCard("System Uptime", "99.9%", "PACS Server Online", "📡")

        metrics_layout.addWidget(c1)
        metrics_layout.addWidget(c2)
        metrics_layout.addWidget(c3)
        metrics_layout.addWidget(c4)
        layout.addLayout(metrics_layout)

        # Staff Table Card
        card = QFrame()
        card.setProperty("class", "simple-card")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(12)

        top_row = QHBoxLayout()
        lbl_title = QLabel("Hospital Clinical Staff & Roles")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #0F172A;")

        btn_add = QPushButton("➕ Register New Staff")
        btn_add.setProperty("class", "btn-primary")
        btn_add.clicked.connect(lambda: self.navigate_to("User Management"))

        top_row.addWidget(lbl_title)
        top_row.addStretch()
        top_row.addWidget(btn_add)
        c_layout.addLayout(top_row)

        table = QTableWidget(4, 4)
        table.setHorizontalHeaderLabels(["ID", "Staff Name", "Role", "Status"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 50)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(3, 120)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(40)
        table.setMinimumHeight(210)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        for row, u in enumerate(self.staff_data):
            it_id = QTableWidgetItem(str(u["id"]))
            it_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 0, it_id)
            table.setItem(row, 1, QTableWidgetItem(u["name"]))
            table.setItem(row, 2, QTableWidgetItem(u["role"]))
            table.setCellWidget(row, 3, StatusBadge(u["status"], variant="normal" if u["status"] == "Active" else "urgent"))

        c_layout.addWidget(table)
        layout.addWidget(card)
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    # =========================================================================
    # 2. USER MANAGEMENT
    # =========================================================================
    def _create_users_page(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        card = QFrame()
        card.setProperty("class", "simple-card")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(12)

        top_row = QHBoxLayout()
        lbl = QLabel("Staff Accounts & Permissions")
        lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #0F172A;")

        btn_add = QPushButton("➕ Add Staff Member")
        btn_add.setProperty("class", "btn-primary")
        btn_add.clicked.connect(self._add_user)

        top_row.addWidget(lbl)
        top_row.addStretch()
        top_row.addWidget(btn_add)
        c_layout.addLayout(top_row)

        self.table = QTableWidget(len(self.staff_data), 4)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Email", "Role"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)

        self._populate_table()
        c_layout.addWidget(self.table)
        layout.addWidget(card)
        return container

    def _populate_table(self):
        self.table.setRowCount(len(self.staff_data))
        for row, u in enumerate(self.staff_data):
            self.table.setItem(row, 0, QTableWidgetItem(u["id"]))
            self.table.setItem(row, 1, QTableWidgetItem(u["name"]))
            self.table.setItem(row, 2, QTableWidgetItem(u["email"]))
            self.table.setItem(row, 3, QTableWidgetItem(u["role"]))

    def _add_user(self):
        dlg = AddUserDialog(self)
        if dlg.exec():
            d = dlg.get_data()
            self.staff_data.append({
                "id": str(len(self.staff_data) + 1),
                "name": d["name"],
                "email": d["email"],
                "role": d["role"],
                "status": "Active",
            })
            self._populate_table()

    # =========================================================================
    # 3. CLIENTS
    # =========================================================================
    def _create_clients_page(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        card = QFrame()
        card.setProperty("class", "simple-card")
        c_lay = QVBoxLayout(card)
        c_lay.addWidget(QLabel("Hospital Facility Directory & PACS Endpoints"))
        layout.addWidget(card)
        return container

    # =========================================================================
    # 4. SUBSCRIPTION
    # =========================================================================
    def _create_subscription_page(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        card = QFrame()
        card.setProperty("class", "simple-card")
        c_lay = QVBoxLayout(card)
        c_lay.addWidget(QLabel("Hospital Enterprise License & AI Quotas"))
        layout.addWidget(card)
        return container

    # =========================================================================
    # 5. SETTINGS
    # =========================================================================
    def _create_settings_page(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        card = QFrame()
        card.setProperty("class", "simple-card")
        c_lay = QVBoxLayout(card)
        c_lay.addWidget(QLabel("System Integrations & Security Settings"))
        layout.addWidget(card)
        return container

    # =========================================================================
    # 6. PROFILE
    # =========================================================================
    def _create_profile_page(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        card = QFrame()
        card.setProperty("class", "simple-card")
        c_lay = QVBoxLayout(card)
        c_lay.addWidget(QLabel("Administrator Profile & Credentials"))
        layout.addWidget(card)
        return container
