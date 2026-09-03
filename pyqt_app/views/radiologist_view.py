from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QTextEdit,
    QStackedWidget, QScrollArea, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QPainter, QColor, QBrush, QPen, QPixmap

from pyqt_app.components.cards import MetricCard, StatusBadge


class RadiologistView(QWidget):
    """Clean & Simple Radiologist Workspace."""

    def __init__(self, user: dict, parent=None):
        super().__init__(parent)
        self.user = user or {}

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        self.stacked_widget = QStackedWidget(self)
        main_layout.addWidget(self.stacked_widget)

        # Pages
        self.page_dashboard = self._create_dashboard_page()
        self.page_queue = self._create_queue_page()
        self.page_analyze = self._create_analyze_page()
        self.page_records = self._create_records_page()
        self.page_profile = self._create_profile_page()

        self.stacked_widget.addWidget(self.page_dashboard)  # 0
        self.stacked_widget.addWidget(self.page_queue)      # 1
        self.stacked_widget.addWidget(self.page_analyze)    # 2
        self.stacked_widget.addWidget(self.page_records)    # 3
        self.stacked_widget.addWidget(self.page_profile)    # 4

        self.page_map = {
            "Dashboard": 0,
            "Patient Queue": 1,
            "Analyze X-Ray": 2,
            "Patient Records": 3,
            "Profile": 4,
            # Aliases
            "Review Patient": 2,
            "In Patients": 1,
            "Appointments": 1,
            "Radiology": 2,
            "Patient Profile": 4,
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

        c1 = MetricCard("Total Scans Today", "48", "12 reviewed in shift", "🩻")
        c2 = MetricCard("Pneumonia Cases", "12", "8 Bacterial / 4 Viral", "🫁")
        c3 = MetricCard("Normal Scans", "36", "75% Normal rate", "✅")
        c4 = MetricCard("Pending Review", "4", "High priority triage", "⏳")

        metrics_layout.addWidget(c1)
        metrics_layout.addWidget(c2)
        metrics_layout.addWidget(c3)
        metrics_layout.addWidget(c4)
        layout.addLayout(metrics_layout)

        # Recent Patient Scans Card
        card = QFrame()
        card.setProperty("class", "simple-card")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(12)

        top_row = QHBoxLayout()
        lbl_title = QLabel("Recent Patient Scans & AI Predictions")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #0F172A;")

        btn_analyze = QPushButton("➕ Analyze New Scan")
        btn_analyze.setProperty("class", "btn-primary")
        btn_analyze.clicked.connect(lambda: self.navigate_to("Analyze X-Ray"))

        top_row.addWidget(lbl_title)
        top_row.addStretch()
        top_row.addWidget(btn_analyze)
        c_layout.addLayout(top_row)

        table = QTableWidget(5, 6)
        table.setHorizontalHeaderLabels(["MRN", "Patient Name", "Scan Date", "AI Prediction", "Confidence", "Action"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(40)
        table.setMinimumHeight(250)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        data = [
            ("849-20412", "Robert Vance (58/M)", "2026-08-30 10:45", "Bacterial Pneumonia", "89.4%"),
            ("849-20409", "Elena Rostova (42/F)", "2026-08-30 10:22", "Viral Pneumonia", "76.2%"),
            ("849-20398", "James Miller (67/M)", "2026-08-30 10:05", "Bacterial Pneumonia", "82.1%"),
            ("849-20371", "David Chen (29/M)", "2026-08-30 09:40", "Normal", "97.8%"),
            ("849-20364", "Maria Santos (51/F)", "2026-08-30 09:15", "Normal", "94.2%"),
        ]

        for row, (mrn, name, dt, pred, conf) in enumerate(data):
            table.setItem(row, 0, QTableWidgetItem(mrn))
            table.setItem(row, 1, QTableWidgetItem(name))
            table.setItem(row, 2, QTableWidgetItem(dt))
            table.setCellWidget(row, 3, StatusBadge(pred, variant=pred))
            table.setItem(row, 4, QTableWidgetItem(conf))

            btn_view = QPushButton("Inspect")
            btn_view.setProperty("class", "btn-secondary")
            btn_view.clicked.connect(lambda: self.navigate_to("Analyze X-Ray"))
            table.setCellWidget(row, 5, btn_view)

        c_layout.addWidget(table)
        layout.addWidget(card)
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    # =========================================================================
    # 2. PATIENT QUEUE
    # =========================================================================
    def _create_queue_page(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        card = QFrame()
        card.setProperty("class", "simple-card")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(12)

        top_row = QHBoxLayout()
        txt_search = QLineEdit()
        txt_search.setPlaceholderText("🔍 Search patient queue by MRN or name...")
        txt_search.setFixedHeight(36)
        top_row.addWidget(txt_search)
        c_layout.addLayout(top_row)

        table = QTableWidget(4, 5)
        table.setHorizontalHeaderLabels(["MRN", "Patient Name", "Priority", "AI Impression", "Action"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)

        queue_data = [
            ("849-20412", "Robert Vance", "STAT Emergency", "Bacterial Pneumonia (89.4%)"),
            ("849-20409", "Elena Rostova", "Urgent", "Viral Pneumonia (76.2%)"),
            ("849-20398", "James Miller", "Urgent", "Bacterial Pneumonia (82.1%)"),
            ("849-20385", "Linda Kim", "Routine", "Pending Review"),
        ]

        for r, (mrn, name, prio, imp) in enumerate(queue_data):
            table.setItem(r, 0, QTableWidgetItem(mrn))
            table.setItem(r, 1, QTableWidgetItem(name))
            table.setCellWidget(r, 2, StatusBadge(prio, variant=prio))
            table.setItem(r, 3, QTableWidgetItem(imp))

            btn_open = QPushButton("Open Scan")
            btn_open.setProperty("class", "btn-primary")
            btn_open.clicked.connect(lambda: self.navigate_to("Analyze X-Ray"))
            table.setCellWidget(r, 4, btn_open)

        c_layout.addWidget(table)
        layout.addWidget(card)
        return container

    # =========================================================================
    # 3. ANALYZE X-RAY
    # =========================================================================
    def _create_analyze_page(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # Left Column: Image Viewer
        left_card = QFrame()
        left_card.setProperty("class", "simple-card")
        left_card.setStyleSheet("background-color: #0F172A; border-radius: 10px;")
        l_lay = QVBoxLayout(left_card)
        l_lay.setContentsMargins(14, 14, 14, 14)
        l_lay.setSpacing(10)

        lbl_scan = QLabel("Chest X-Ray Viewer — Patient: Robert Vance (MRN: 849-20412)")
        lbl_scan.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: 700;")
        l_lay.addWidget(lbl_scan)

        self.canvas = QLabel()
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas.setMinimumHeight(400)
        self._draw_xray(True)
        l_lay.addWidget(self.canvas, 1)

        btn_bar = QHBoxLayout()
        self.btn_toggle_heat = QPushButton("🔥 Toggle AI Heatmap")
        self.btn_toggle_heat.setProperty("class", "btn-secondary")
        self.btn_toggle_heat.setCheckable(True)
        self.btn_toggle_heat.setChecked(True)
        self.btn_toggle_heat.clicked.connect(lambda: self._draw_xray(self.btn_toggle_heat.isChecked()))

        btn_load = QPushButton("📁 Load Other Image")
        btn_load.setProperty("class", "btn-secondary")
        btn_load.clicked.connect(self._load_image)

        btn_bar.addWidget(self.btn_toggle_heat)
        btn_bar.addWidget(btn_load)
        l_lay.addLayout(btn_bar)

        layout.addWidget(left_card, 3)

        # Right Column: Diagnosis & Report
        right_card = QFrame()
        right_card.setProperty("class", "simple-card")
        r_lay = QVBoxLayout(right_card)
        r_lay.setSpacing(12)

        lbl_r_title = QLabel("AI Diagnostic Findings")
        lbl_r_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #0F172A;")
        r_lay.addWidget(lbl_r_title)

        # AI Result Box
        res_box = QFrame()
        res_box.setStyleSheet("background-color: #FEF2F2; border: 1px solid #FCA5A5; border-radius: 8px; padding: 12px;")
        rb_lay = QVBoxLayout(res_box)
        rb_lay.setSpacing(4)

        lbl_cond = QLabel("Condition: <b>Bacterial Pneumonia</b>")
        lbl_cond.setStyleSheet("color: #DC2626; font-size: 14px; font-weight: 700;")
        lbl_prob = QLabel("Confidence: <b>89.4%</b>  |  Severity: <b>Moderate-High</b>")
        lbl_prob.setStyleSheet("color: #991B1B; font-size: 12px;")

        rb_lay.addWidget(lbl_cond)
        rb_lay.addWidget(lbl_prob)
        r_lay.addWidget(res_box)

        lbl_notes = QLabel("Radiologist Clinical Notes:")
        lbl_notes.setStyleSheet("font-weight: 700; color: #334155; font-size: 12.5px;")
        r_lay.addWidget(lbl_notes)

        self.txt_notes = QTextEdit()
        self.txt_notes.setText("Dense consolidation in right lower lung field consistent with acute bacterial pneumonia. Recommend targeted antibiotic therapy.")
        self.txt_notes.setFixedHeight(100)
        r_lay.addWidget(self.txt_notes)

        btn_save = QPushButton("💾 Save & Sign Diagnostic Report")
        btn_save.setProperty("class", "btn-primary")
        btn_save.clicked.connect(lambda: QMessageBox.information(self, "Report Saved", "Report signed and saved successfully."))
        r_lay.addWidget(btn_save)

        r_lay.addStretch()
        layout.addWidget(right_card, 2)
        return container

    def _draw_xray(self, show_heat: bool):
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

        if show_heat:
            painter.setBrush(QBrush(QColor(220, 38, 38, 150)))
            painter.setPen(QPen(QColor("#EF4444"), 2))
            painter.drawEllipse(310, 200, 90, 80)
            painter.setPen(QPen(QColor("#FFFFFF")))
            painter.drawText(315, 195, "Bacterial Pneumonia 89.4%")

        painter.end()
        self.canvas.setPixmap(pixmap)

    def _load_image(self):
        QFileDialog.getOpenFileName(self, "Select Chest Radiograph", "", "Images (*.png *.jpg *.dcm)")
        self._draw_xray(True)

    # =========================================================================
    # 4. PATIENT RECORDS
    # =========================================================================
    def _create_records_page(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        card = QFrame()
        card.setProperty("class", "simple-card")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(12)

        txt_search = QLineEdit()
        txt_search.setPlaceholderText("🔍 Search records by MRN, patient name, or date...")
        txt_search.setFixedHeight(36)
        c_layout.addWidget(txt_search)

        table = QTableWidget(5, 5)
        table.setHorizontalHeaderLabels(["MRN", "Patient Name", "Study Date", "Diagnosis", "Report"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)

        archives = [
            ("849-20412", "Robert Vance", "2026-08-30 10:45", "Bacterial Pneumonia", "📄 View"),
            ("849-20409", "Elena Rostova", "2026-08-30 10:22", "Viral Pneumonia", "📄 View"),
            ("849-20371", "David Chen", "2026-08-29 16:30", "Normal", "📄 View"),
            ("849-20364", "Maria Santos", "2026-08-29 14:15", "Normal", "📄 View"),
            ("849-20350", "Arthur Pendelton", "2026-08-28 09:00", "Bacterial Pneumonia", "📄 View"),
        ]

        for r, (mrn, name, dt, diag, rep) in enumerate(archives):
            table.setItem(r, 0, QTableWidgetItem(mrn))
            table.setItem(r, 1, QTableWidgetItem(name))
            table.setItem(r, 2, QTableWidgetItem(dt))
            table.setCellWidget(r, 3, StatusBadge(diag, variant=diag))

            btn_rep = QPushButton(rep)
            btn_rep.setProperty("class", "btn-secondary")
            btn_rep.clicked.connect(lambda: QMessageBox.information(self, "Report", "Displaying diagnostic report PDF."))
            table.setCellWidget(r, 4, btn_rep)

        c_layout.addWidget(table)
        layout.addWidget(card)
        return container

    # =========================================================================
    # 5. PROFILE
    # =========================================================================
    def _create_profile_page(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        card = QFrame()
        card.setProperty("class", "simple-card")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(14)

        lbl = QLabel("Physician Profile & Credentials")
        lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #0F172A;")
        c_layout.addWidget(lbl)

        for field, val in [
            ("Full Name", self.user.get("name", "Dr. Sarah Jenkins")),
            ("Email Address", self.user.get("email", "radiologist@lungsight.ai")),
            ("Medical License ID", "MD-9840219-PH"),
            ("Role", "Radiologist"),
        ]:
            row = QHBoxLayout()
            l = QLabel(f"<b>{field}:</b>")
            l.setFixedWidth(160)
            txt = QLineEdit(val)
            row.addWidget(l)
            row.addWidget(txt)
            c_layout.addLayout(row)

        btn_save = QPushButton("Save Changes")
        btn_save.setProperty("class", "btn-primary")
        btn_save.setFixedWidth(140)
        btn_save.clicked.connect(lambda: QMessageBox.information(self, "Saved", "Profile updated successfully."))
        c_layout.addWidget(btn_save)

        c_layout.addStretch()
        layout.addWidget(card)
        return container
