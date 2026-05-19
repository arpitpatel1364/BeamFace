"""
BeamFace application entry point.

Launches the PyQt5 event loop and shows the main window.
This file is intentionally minimal; all application logic lives in
the core, vision, and ui packages.
"""

import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from ui.main_window import MainWindow
from utils.logger import setup_logger

logger = setup_logger("beamface.main")


def main():
    """Initialize the Qt application, show the main window, and enter the event loop."""
    logger.info("Starting BeamFace v1.0.0")

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    app.setApplicationName("BeamFace")
    app.setApplicationVersion("1.0.0")

    window = MainWindow()
    window.show()

    logger.info("Main window displayed")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
