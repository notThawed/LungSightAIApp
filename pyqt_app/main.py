import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6 import uic


app = QApplication(sys.argv)

BASE_DIR = Path(__file__).resolve().parent
ui_file = BASE_DIR / "mainwindow.ui"

window = uic.loadUi(str(ui_file))

window.show()

sys.exit(app.exec())