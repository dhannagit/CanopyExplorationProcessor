"""Noninteractive installed-release check used before activation."""

import os
import platform
import sys
from tempfile import TemporaryDirectory
from pathlib import Path


def main() -> None:
	if sys.version_info[:2] != (3, 13) or platform.machine().lower() != "amd64":
		raise RuntimeError("Deployment requires Windows x64 Python 3.13")
	os.environ["QT_QPA_PLATFORM"] = "offscreen"
	import numpy as np
	from scipy.linalg import det
	from PySide6.QtCore import QSettings
	from PySide6.QtWidgets import QApplication
	from .main_window import MainWindow
	assert det(np.eye(2)) == 1.0
	application = QApplication.instance() or QApplication([])
	with TemporaryDirectory() as directory:
		settings = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
		window = MainWindow(settings)
		window.figure_canvas.draw()
		window.close()
		application.processEvents()


if __name__ == "__main__":
	main()