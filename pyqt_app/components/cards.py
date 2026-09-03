from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from PyQt6.QtCore import Qt


class MetricCard(QFrame):
    """Clean, compact, and perfectly proportioned metric card."""

    def __init__(self, title: str, value: str, subtext: str = "", icon: str = "📊", parent=None):
        super().__init__(parent)
        self.setProperty("class", "simple-card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(98)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        # Top row: Title + Icon
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        lbl_title = QLabel(title.upper())
        lbl_title.setObjectName("metricTitle")

        lbl_icon = QLabel(icon)
        lbl_icon.setStyleSheet("font-size: 15px;")

        top_row.addWidget(lbl_title)
        top_row.addStretch()
        top_row.addWidget(lbl_icon)
        layout.addLayout(top_row)

        # Value
        self.lbl_value = QLabel(str(value))
        self.lbl_value.setObjectName("metricValue")
        layout.addWidget(self.lbl_value)

        # Subtext
        if subtext:
            lbl_sub = QLabel(subtext)
            lbl_sub.setObjectName("metricSubtext")
            layout.addWidget(lbl_sub)

    def set_value(self, value: str):
        self.lbl_value.setText(str(value))


class StatusBadge(QLabel):
    """Clean colored status badge with proper padding."""

    def __init__(self, text: str, variant: str = "routine", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(24)
        self.setMinimumWidth(80)

        v = variant.lower()
        if "bacterial" in v or "pneumonia" in v or "stat" in v or "emergency" in v or "critical" in v or "danger" in v:
            self.setStyleSheet("background-color: #FEE2E2; color: #DC2626; font-weight: 700; font-size: 11px; padding: 2px 8px; border-radius: 4px; border: 1px solid #FCA5A5;")
        elif "viral" in v or "urgent" in v or "warn" in v or "review" in v or "elective" in v or "on-call" in v or "call" in v:
            self.setStyleSheet("background-color: #FEF3C7; color: #D97706; font-weight: 700; font-size: 11px; padding: 2px 8px; border-radius: 4px; border: 1px solid #FDE68A;")
        elif "normal" in v or "clear" in v or "complete" in v or "success" in v or "checkup" in v or "active" in v or "transmitted" in v:
            self.setStyleSheet("background-color: #DCFCE7; color: #16A34A; font-weight: 700; font-size: 11px; padding: 2px 8px; border-radius: 4px; border: 1px solid #86EFAC;")
        else:
            self.setStyleSheet("background-color: #E0F2FE; color: #0284C7; font-weight: 700; font-size: 11px; padding: 2px 8px; border-radius: 4px; border: 1px solid #BAE6FD;")
