import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

from canopy_processor.ui.main_window import MainWindow


REPOSITORY_ROOT = os.path.dirname(os.path.dirname(__file__))


def test_main_window_builds_workbench() -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()

	assert window.windowTitle() == "Canopy Exploration Processor"
	assert window.session.state.value == "empty"
	assert window.root_label.text() == "No root selected"
	assert window.metric_combo.count() == 1

	window.close()
	application.processEvents()


def test_main_window_populates_discovered_variables() -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()
	window._start_discovery(REPOSITORY_ROOT)
	loop = QEventLoop()
	worker = window._worker
	assert worker is not None
	worker.finished.connect(loop.quit)
	QTimer.singleShot(5000, loop.quit)
	loop.exec()
	application.processEvents()

	assert window.session.discovery_result is not None
	assert window.variable_list.count() == 2
	assert window.confirm_button.isEnabled()

	window.close()
	application.processEvents()