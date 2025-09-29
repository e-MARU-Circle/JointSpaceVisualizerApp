import sys
from pathlib import Path

if __package__ is None or __package__ == '':
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.env_utils import prepare_runtime_dirs

prepare_runtime_dirs()

from PyQt5 import QtWidgets

from app.logging_config import configure_logging
from app.ui import JointSpaceVisualizerApp

configure_logging()


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    window = JointSpaceVisualizerApp()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
