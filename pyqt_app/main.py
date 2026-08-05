from PyQt6.QtWidgets import QApplication,QLabel
import sys
app=QApplication(sys.argv)
label=QLabel('LungSightApp Desktop')
label.show()
sys.exit(app.exec())
