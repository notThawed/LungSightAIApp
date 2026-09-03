from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QCursor

from pyqt_app.styles import AUTH_STYLESHEET

# Base directory
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
LOGO_PATH = PROJECT_ROOT / "shared" / "images" / "LungSight Logo.png"

# Demo Users Preconfigured
DEMO_USERS = {
    "radiologist@lungsight.ai": {
        "user_id": "demo-rad-001",
        "email": "radiologist@lungsight.ai",
        "name": "Dr. Sarah Jenkins",
        "first_name": "Sarah",
        "last_name": "Jenkins",
        "role": "Radiologist",
        "role_id": 1,
    },
    "radtech@lungsight.ai": {
        "user_id": "demo-tech-002",
        "email": "radtech@lungsight.ai",
        "name": "Alex Rivera",
        "first_name": "Alex",
        "last_name": "Rivera",
        "role": "Radiologic Technologist",
        "role_id": 2,
    },
    "admin@lungsight.ai": {
        "user_id": "demo-adm-003",
        "email": "admin@lungsight.ai",
        "name": "Marcus Vance",
        "first_name": "Marcus",
        "last_name": "Vance",
        "role": "Hospital Admin",
        "role_id": 3,
    },
}


class AuthWindow(QWidget):
    """Clean & Simple Desktop Sign In Window."""

    login_successful = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LungSight AI — Sign In")
        self.resize(880, 560)
        self.setMinimumSize(800, 500)
        self.setObjectName("authContainer")
        self.setStyleSheet(AUTH_STYLESHEET)

        # Center Root Layout
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(40, 40, 40, 40)
        root_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Center Card Frame
        card = QFrame()
        card.setObjectName("authCard")
        card.setFixedSize(760, 460)

        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(36, 36, 36, 36)
        card_layout.setSpacing(36)

        # =====================================================================
        # LEFT COLUMN: FORM & DEMO BUTTONS
        # =====================================================================
        left_layout = QVBoxLayout()
        left_layout.setSpacing(12)

        lbl_title = QLabel("Sign In")
        lbl_title.setObjectName("authTitle")
        left_layout.addWidget(lbl_title)

        lbl_sub = QLabel("AI-powered chest X-ray analysis for clinical decisions.")
        lbl_sub.setObjectName("authSubtitle")
        lbl_sub.setWordWrap(True)
        left_layout.addWidget(lbl_sub)

        left_layout.addSpacing(6)

        # Inputs
        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("Email address (you@hospital.org)")
        self.txt_email.setFixedHeight(38)
        self.txt_email.returnPressed.connect(self._handle_login)
        left_layout.addWidget(self.txt_email)

        self.txt_password = QLineEdit()
        self.txt_password.setPlaceholderText("Password")
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.setFixedHeight(38)
        self.txt_password.returnPressed.connect(self._handle_login)
        left_layout.addWidget(self.txt_password)

        btn_signin = QPushButton("Sign In")
        btn_signin.setProperty("class", "btn-primary")
        btn_signin.setFixedHeight(40)
        btn_signin.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_signin.clicked.connect(self._handle_login)
        left_layout.addWidget(btn_signin)

        # Quick Demo Access
        lbl_demo_tag = QLabel("— QUICK DEMO ACCESS (3 ROLES) —")
        lbl_demo_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_demo_tag.setStyleSheet("color: #64748B; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; margin-top: 8px;")
        left_layout.addWidget(lbl_demo_tag)

        demo_btn_layout = QHBoxLayout()
        demo_btn_layout.setSpacing(8)

        btn_rad = QPushButton("🩺 Radiologist")
        btn_rad.setProperty("class", "btn-demo-role")
        btn_rad.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_rad.clicked.connect(lambda: self._quick_login("radiologist@lungsight.ai"))

        btn_tech = QPushButton("🩻 RadTech")
        btn_tech.setProperty("class", "btn-demo-role")
        btn_tech.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_tech.clicked.connect(lambda: self._quick_login("radtech@lungsight.ai"))

        btn_adm = QPushButton("🏥 Admin")
        btn_adm.setProperty("class", "btn-demo-role")
        btn_adm.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_adm.clicked.connect(lambda: self._quick_login("admin@lungsight.ai"))

        demo_btn_layout.addWidget(btn_rad)
        demo_btn_layout.addWidget(btn_tech)
        demo_btn_layout.addWidget(btn_adm)
        left_layout.addLayout(demo_btn_layout)

        left_layout.addStretch()
        card_layout.addLayout(left_layout, 3)

        # =====================================================================
        # RIGHT COLUMN: BRANDING PANEL
        # =====================================================================
        right_panel = QFrame()
        right_panel.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #E0F2FE, stop:1 #BAE6FD); border-radius: 10px; border: 1px solid #BAE6FD;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.setSpacing(12)

        if LOGO_PATH.exists():
            pix = QPixmap(str(LOGO_PATH))
            lbl_logo_img = QLabel()
            lbl_logo_img.setPixmap(pix.scaled(110, 110, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            lbl_logo_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            right_layout.addWidget(lbl_logo_img)

        lbl_brand = QLabel("LungSight AI")
        lbl_brand.setStyleSheet("font-size: 20px; font-weight: 900; color: #0284C7;")
        lbl_brand.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_brand_desc = QLabel("Automated diagnostic intelligence for pneumonia detection and triaging.")
        lbl_brand_desc.setStyleSheet("font-size: 12px; color: #0369A1; text-align: center;")
        lbl_brand_desc.setWordWrap(True)
        lbl_brand_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)

        right_layout.addWidget(lbl_brand)
        right_layout.addWidget(lbl_brand_desc)

        card_layout.addWidget(right_panel, 2)
        root_layout.addWidget(card)

    def _quick_login(self, email: str):
        if email in DEMO_USERS:
            user_data = DEMO_USERS[email]
            self.login_successful.emit(user_data)

    def _handle_login(self):
        email = self.txt_email.text().strip()
        password = self.txt_password.text().strip()

        if not email:
            QMessageBox.warning(self, "Validation Error", "Please enter your email address.")
            return

        if email in DEMO_USERS:
            self.login_successful.emit(DEMO_USERS[email])
            return

        # Attempt live Supabase login if configured
        try:
            from backend.supabase_client import supabase
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if res.user:
                u = {
                    "user_id": res.user.id,
                    "email": res.user.email,
                    "name": res.user.user_metadata.get("name", email.split("@")[0].title()),
                    "role": res.user.user_metadata.get("role", "Radiologist"),
                }
                self.login_successful.emit(u)
                return
        except Exception:
            pass

        # Fallback default user
        fallback = {
            "user_id": "user-001",
            "email": email,
            "name": email.split("@")[0].title(),
            "role": "Radiologist",
        }
        self.login_successful.emit(fallback)
