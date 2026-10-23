"""Desktop application entry point."""

from __future__ import annotations

import sys
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path


def configure_logging() -> Path:
	"""Keep console-free application failures visible and diagnosable."""
	directory = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CanopyExplorationProcessor" / "logs"
	directory.mkdir(parents=True, exist_ok=True)
	path = directory / "application.log"
	handler = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
	handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
	logger = logging.getLogger("canopy_processor")
	logger.setLevel(logging.INFO)
	logger.addHandler(handler)
	return path


def main() -> int:
	"""Launch the optional PySide6 desktop application."""

	try:
		from PySide6.QtWidgets import QApplication
	except ImportError as error:
		raise SystemExit("Install the GUI extra with: pip install .[gui]") from error

	application = QApplication(sys.argv)
	application.setApplicationName("Canopy Exploration Processor")
	from PySide6.QtWidgets import QMessageBox
	log_path = configure_logging()

	def report_exception(error_type: type, error: BaseException, traceback: object) -> None:
		logging.getLogger("canopy_processor").error("Unhandled GUI exception", exc_info=(error_type, error, traceback))
		QMessageBox.critical(None, "Canopy Exploration Processor", f"An unexpected error occurred.\nDetails: {log_path}")

	sys.excepthook = report_exception
	try:
		from .main_window import MainWindow
		window = MainWindow()
		window.show()
		return application.exec()
	except Exception:
		report_exception(*sys.exc_info())
		return 1


if __name__ == "__main__":
	raise SystemExit(main())