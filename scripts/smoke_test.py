import os
import sys

# Ensure offscreen platform for headless environments
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtWidgets, QtCore

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from app.main import JointSpaceVisualizerApp
except Exception as e:
    print(f"IMPORT_ERROR: {e}")
    sys.exit(2)

app = QtWidgets.QApplication(sys.argv)
window = JointSpaceVisualizerApp()
window.show()

# Quit after a short delay to validate startup
QtCore.QTimer.singleShot(1500, app.quit)

try:
    rc = app.exec_()
    print("SMOKE_OK")
    sys.exit(0)
except Exception as e:
    print(f"RUNTIME_ERROR: {e}")
    sys.exit(3)

