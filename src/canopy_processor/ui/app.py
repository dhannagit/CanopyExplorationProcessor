"""Desktop application entry point."""

from __future__ import annotations

import sys


def main() -> int:
	"""Launch the optional PySide6 desktop application."""

	try:
		from PySide6.QtWidgets import QApplication
	except ImportError as error:
		raise SystemExit("Install the GUI extra with: pip install .[gui]") from error

	from .main_window import MainWindow

	application = QApplication(sys.argv)
	application.setApplicationName("Canopy Exploration Processor")
	window = MainWindow()
	window.show()
	return application.exec()


if __name__ == "__main__":
	raise SystemExit(main())