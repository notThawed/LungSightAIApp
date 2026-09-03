"""
LungSight AI — Clean, Simple & Modern Desktop Stylesheet (QSS)
Pixel-perfect typography, harmonious color palette, and rock-solid widget layouts.
"""

MAIN_STYLESHEET = """
/* Base Window & Canvas */
QMainWindow {
    background-color: #F8FAFC;
}

QWidget {
    font-family: 'Segoe UI', 'Inter', -apple-system, BlinkMacSystemFont, 'Roboto', 'Arial', sans-serif;
    font-size: 13px;
    color: #0F172A;
}

QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

/* =========================================================================
   1. CLEAN SIDEBAR
   ========================================================================= */
QFrame#simpleSidebar {
    background-color: #FFFFFF;
    border-right: 1px solid #E2E8F0;
    min-width: 220px;
    max-width: 240px;
}

#simpleSidebar QLabel {
    background: transparent;
}

#sidebarLogoTitle {
    font-size: 17px;
    font-weight: 800;
    color: #0284C7;
    letter-spacing: -0.3px;
}

#sidebarLogoSub {
    font-size: 11px;
    font-weight: 600;
    color: #64748B;
}

#simpleSidebar QPushButton.nav-btn {
    background-color: transparent;
    color: #475569;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 10px 14px;
    text-align: left;
    font-size: 13px;
    font-weight: 600;
    margin: 2px 8px;
}

#simpleSidebar QPushButton.nav-btn:hover {
    background-color: #F1F5F9;
    color: #0F172A;
}

#simpleSidebar QPushButton.nav-btn:checked {
    background-color: #E0F2FE;
    color: #0284C7;
    font-weight: 700;
    border-color: #BAE6FD;
}

#simpleSidebar QPushButton.logout-btn {
    background-color: transparent;
    color: #64748B;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 9px 14px;
    font-weight: 600;
    margin: 8px 8px;
    text-align: left;
    font-size: 12.5px;
}

#simpleSidebar QPushButton.logout-btn:hover {
    background-color: #FEE2E2;
    color: #DC2626;
    border-color: #FCA5A5;
}

/* =========================================================================
   2. CLEAN TOP NAVBAR
   ========================================================================= */
QFrame#simpleNavbar {
    background-color: #FFFFFF;
    border-bottom: 1px solid #E2E8F0;
    min-height: 56px;
    max-height: 56px;
}

#pageTitle {
    font-size: 18px;
    font-weight: 800;
    color: #0F172A;
}

#navUserName {
    font-size: 13px;
    font-weight: 700;
    color: #0F172A;
}

#navUserRole {
    font-size: 11.5px;
    color: #64748B;
    font-weight: 500;
}

/* =========================================================================
   3. CLEAN CARDS & CONTAINERS
   ========================================================================= */
QFrame.simple-card {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 16px;
}

QFrame.simple-card QLabel {
    background: transparent;
}

.card-title {
    font-size: 15px;
    font-weight: 800;
    color: #0F172A;
}

/* Metric Cards */
#metricTitle {
    font-size: 11px;
    font-weight: 700;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.4px;
}

#metricValue {
    font-size: 22px;
    font-weight: 800;
    color: #0F172A;
    min-height: 28px;
}

#metricSubtext {
    font-size: 11px;
    color: #059669;
    font-weight: 600;
}

/* =========================================================================
   4. BUTTONS & CONTROLS
   ========================================================================= */
QPushButton.btn-primary {
    background-color: #0284C7;
    color: #FFFFFF;
    border: 1px solid #0369A1;
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton.btn-primary:hover {
    background-color: #0369A1;
}

QPushButton.btn-primary:pressed {
    background-color: #075985;
}

QPushButton.btn-secondary {
    background-color: #FFFFFF;
    color: #334155;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 8px 14px;
    font-size: 12.5px;
    font-weight: 600;
}

QPushButton.btn-secondary:hover {
    background-color: #F8FAFC;
    border-color: #94A3B8;
    color: #0F172A;
}

QPushButton.btn-danger {
    background-color: #DC2626;
    color: #FFFFFF;
    border: 1px solid #B91C1C;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton.btn-danger:hover {
    background-color: #B91C1C;
}

/* =========================================================================
   5. TABLES
   ========================================================================= */
QTableWidget {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    gridline-color: #F1F5F9;
    color: #0F172A;
    font-size: 12.5px;
    selection-background-color: #E0F2FE;
    selection-color: #0369A1;
}

QHeaderView::section {
    background-color: #F8FAFC;
    color: #475569;
    padding: 10px 14px;
    font-weight: 700;
    font-size: 11.5px;
    border: none;
    border-bottom: 1px solid #E2E8F0;
    border-right: 1px solid #F1F5F9;
    text-transform: uppercase;
    letter-spacing: 0.3px;
}

QTableWidget::item {
    padding: 8px 14px;
    border-bottom: 1px solid #F1F5F9;
}

QTableWidget::item:selected {
    background-color: #E0F2FE;
    color: #0369A1;
    font-weight: 600;
}

/* =========================================================================
   6. INPUTS & FORM CONTROLS
   ========================================================================= */
QLineEdit, QTextEdit, QComboBox {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 8px 12px;
    color: #0F172A;
    font-size: 12.5px;
}

QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border-color: #0284C7;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #F1F5F9;
    width: 6px;
    margin: 0px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: #CBD5E1;
    min-height: 20px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: #94A3B8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

AUTH_STYLESHEET = """
QWidget#authContainer {
    background-color: #F8FAFC;
}

QFrame#authCard {
    background-color: #FFFFFF;
    border-radius: 12px;
    border: 1px solid #E2E8F0;
}

#authTitle {
    color: #0F172A;
    font-size: 22px;
    font-weight: 800;
    letter-spacing: -0.3px;
}

#authSubtitle {
    color: #64748B;
    font-size: 13px;
}

QPushButton.btn-primary {
    background-color: #0284C7;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 10px;
    font-weight: 700;
    font-size: 13px;
}

QPushButton.btn-primary:hover {
    background-color: #0369A1;
}

QPushButton.btn-demo-role {
    background-color: #F8FAFC;
    color: #334155;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 9px 12px;
    font-size: 12.5px;
    font-weight: 700;
    text-align: left;
}

QPushButton.btn-demo-role:hover {
    background-color: #E0F2FE;
    border-color: #0284C7;
    color: #0284C7;
}

QLineEdit {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
    color: #0F172A;
}

QLineEdit:focus {
    border-color: #0284C7;
}
"""
