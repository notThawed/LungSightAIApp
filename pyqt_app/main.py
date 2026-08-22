from PyQt6.QtWidgets import QApplication
from PyQt6 import uic
import sys

app = QApplication(sys.argv)

window = uic.loadUi("mainwindow.ui")
window.show()

sys.exit(app.exec())
