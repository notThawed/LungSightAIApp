from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QFileDialog,
    QStackedWidget, QScrollArea, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QPainter, QColor, QBrush, QPen, QPixmap

from pyqt_app.components.cards import MetricCard, StatusBadge


class RadTechView(QWidget):
    """Clean & Simple Radiologic Technologist Workspace."""

    def __init__(self, user: dict, parent=None):
        super().__init__(parent)
        self.user = user or {}

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        self.stacked_widget = QStackedWidget(self)
        main_layout.addWidget(self.stacked_widget)

        # Build pages
        self.page_dashboard = self._create_dashboard_page()
        self.page_analyze = self._create_analyze_page()
        self.page_records = self._create_records_page()
        self.page_reports = self._create_reports_page()
        self.page_geospatial = self._create_geospatial_page()
        self.page_profile = self._create_profile_page()

        self.stacked_widget.addWidget(self.page_dashboard)   # 0
        self.stacked_widget.addWidget(self.page_analyze)     # 1
        self.stacked_widget.addWidget(self.page_records)     # 2
        self.stacked_widget.addWidget(self.page_reports)     # 3
        self.stacked_widget.addWidget(self.page_geospatial)  # 4
        self.stacked_widget.addWidget(self.page_profile)     # 5

        self.page_map = {
            "Dashboard": 0,
            "Analyze X-Ray": 1,
            "Patient Records": 2,
            "Reports": 3,
            "Geospatial Map": 4,
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

        c1 = MetricCard("Acquisitions Today", "34", "+8 in morning shift", "🩻")
        c2 = MetricCard("AI Screened", "34", "100% Pre-screened", "⚡")
        c3 = MetricCard("Pneumonia Detected", "9", "Auto-flagged for Doctor", "🚨")
        c4 = MetricCard("Normal Scans", "25", "Clear radiographs", "✅")

        metrics_layout.addWidget(c1)
        metrics_layout.addWidget(c2)
        metrics_layout.addWidget(c3)
        metrics_layout.addWidget(c4)
        layout.addLayout(metrics_layout)

        # Recent Acquisitions Card
        card = QFrame()
        card.setProperty("class", "simple-card")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(12)

        top_row = QHBoxLayout()
        lbl_title = QLabel("Recent Chest Radiographs Acquired")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #0F172A;")

        btn_new = QPushButton("➕ Start New Acquisition")
        btn_new.setProperty("class", "btn-primary")
        btn_new.clicked.connect(lambda: self.navigate_to("Analyze X-Ray"))

        top_row.addWidget(lbl_title)
        top_row.addStretch()
        top_row.addWidget(btn_new)
        c_layout.addLayout(top_row)

        table = QTableWidget(4, 5)
        table.setHorizontalHeaderLabels(["MRN", "Patient Name", "Time", "AI CAD Screening", "Status"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(40)
        table.setMinimumHeight(210)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        data = [
            ("849-20412", "Robert Vance", "10:45 AM", "High Pneumonia Probability (89.4%)", "Queued for MD"),
            ("849-20409", "Elena Rostova", "10:22 AM", "Moderate Infiltration (76.2%)", "Queued for MD"),
            ("849-20371", "David Chen", "09:40 AM", "Normal Chest (97.8%)", "Transmitted"),
            ("849-20364", "Maria Santos", "09:15 AM", "Normal Chest (94.2%)", "Transmitted"),
        ]

        for r, (mrn, name, tm, ai, st) in enumerate(data):
            table.setItem(r, 0, QTableWidgetItem(mrn))
            table.setItem(r, 1, QTableWidgetItem(name))
            table.setItem(r, 2, QTableWidgetItem(tm))
            table.setItem(r, 3, QTableWidgetItem(ai))
            table.setCellWidget(r, 4, StatusBadge(st, variant="normal" if "Transmitted" in st else "urgent"))

        c_layout.addWidget(table)
        layout.addWidget(card)
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    # =========================================================================
    # 2. ANALYZE X-RAY
    # =========================================================================
    def _create_analyze_page(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # Left Column: Image Canvas
        left_card = QFrame()
        left_card.setProperty("class", "simple-card")
        left_card.setStyleSheet("background-color: #0F172A; border-radius: 10px;")
        l_lay = QVBoxLayout(left_card)
        l_lay.setContentsMargins(14, 14, 14, 14)
        l_lay.setSpacing(10)

        lbl = QLabel("Chest Radiograph Acquisition & AI Screening")
        lbl.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: 700;")
        l_lay.addWidget(lbl)

        self.canvas = QLabel()
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas.setMinimumHeight(400)
        self._draw_scan(False)
        l_lay.addWidget(self.canvas, 1)

        btn_row = QHBoxLayout()
        btn_import = QPushButton("📁 Import Image")
        btn_import.setProperty("class", "btn-secondary")
        btn_import.clicked.connect(self._browse)

        self.btn_run = QPushButton("⚡ Execute AI Screening")
        self.btn_run.setProperty("class", "btn-primary")
        self.btn_run.clicked.connect(self._run_cad)

        btn_row.addWidget(btn_import)
        btn_row.addWidget(self.btn_run)
        l_lay.addLayout(btn_row)

        layout.addWidget(left_card, 3)

        # Right Column: Controls
        right_card = QFrame()
        right_card.setProperty("class", "simple-card")
        r_lay = QVBoxLayout(right_card)
        r_lay.setSpacing(12)

        lbl_r = QLabel("Acquisition Parameters")
        lbl_r.setStyleSheet("font-size: 16px; font-weight: 800; color: #0F172A;")
        r_lay.addWidget(lbl_r)

        for l_txt, v_txt in [
            ("Voltage (kVp):", "120 kVp"),
            ("Current (mA):", "250 mA"),
            ("Exposure Time:", "12 ms"),
            ("Calculated Dose:", "14.2 mGy·cm²"),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"<b>{l_txt}</b>"))
            row.addStretch()
            row.addWidget(QLabel(v_txt))
            r_lay.addLayout(row)

        self.lbl_cad_result = QLabel("AI Screening: Ready to analyze")
        self.lbl_cad_result.setStyleSheet("color: #64748B; font-weight: 700; font-size: 12px; margin-top: 10px;")
        r_lay.addWidget(self.lbl_cad_result)

        btn_commit = QPushButton("📤 Push to Radiologist Queue")
        btn_commit.setProperty("class", "btn-primary")
        btn_commit.clicked.connect(lambda: QMessageBox.information(self, "Transmitted", "Study committed and pushed to Dr. Sarah Jenkins."))
        r_lay.addWidget(btn_commit)

        r_lay.addStretch()
        layout.addWidget(right_card, 2)
        return container

    def _draw_scan(self, ai_on: bool):
        pixmap = QPixmap(540, 390)
        pixmap.fill(QColor("#0F172A"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(QPen(QColor("#38BDF8")))
        painter.drawText(20, 35, "[ R ]")
        painter.drawText(490, 35, "[ L ]")

        painter.setPen(QPen(QColor("#334155"), 2))
        painter.drawRoundedRect(110, 50, 130, 260, 35, 35)
        painter.drawRoundedRect(290, 50, 130, 260, 35, 35)

        if ai_on:
            painter.setPen(QPen(QColor("#EF4444"), 2, Qt.PenStyle.DashLine))
            painter.drawRect(310, 185, 95, 95)
            painter.setPen(QPen(QColor("#EF4444")))
            painter.drawText(315, 180, "Pneumonia 91.2%")

        painter.end()
        self.canvas.setPixmap(pixmap)

    def _browse(self):
        QFileDialog.getOpenFileName(self, "Select Radiograph", "", "Images (*.png *.jpg *.dcm)")
        self._draw_scan(False)

    def _run_cad(self):
        self._draw_scan(True)
        self.lbl_cad_result.setText("🚨 High Pneumonia Probability (91.2%)\nAuto-flagged for Radiologist.")
        self.lbl_cad_result.setStyleSheet("color: #DC2626; font-weight: 800;")

    # =========================================================================
    # 3. RECORDS
    # =========================================================================
    def _create_records_page(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        card = QFrame()
        card.setProperty("class", "simple-card")
        c_lay = QVBoxLayout(card)
        c_lay.addWidget(QLabel("Acquisition Archives & Logs"))
        layout.addWidget(card)
        return container

    # =========================================================================
    # 4. REPORTS
    # =========================================================================
    def _create_reports_page(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        card = QFrame()
        card.setProperty("class", "simple-card")
        c_lay = QVBoxLayout(card)
        c_lay.addWidget(QLabel("Radiation Dose & Quality Assurance Reports"))
        layout.addWidget(card)
        return container

    # =========================================================================
    # 5. GEOSPATIAL MAP
    # =========================================================================
    def _create_geospatial_page(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        card = QFrame()
        card.setProperty("class", "simple-card")
        c_lay = QVBoxLayout(card)
        c_lay.addWidget(QLabel("Regional Screening Outreach Map"))
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
        c_lay.addWidget(QLabel("Technologist Credentials & Settings"))
        layout.addWidget(card)
        return container
