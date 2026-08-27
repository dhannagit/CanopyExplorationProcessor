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
	assert window.variable_list.selectionMode().name == "ExtendedSelection"
	assert window.confirm_button.isEnabled()
	window.variable_list.item(0).setSelected(True)
	window._confirm_variables()
	assert [variable.path for variable in window.session.config.sweep_variables] == [
		window.session.discovered_variables[0].path
	]

	window.close()
	application.processEvents()


def test_main_window_persists_multiple_selected_variables() -> None:
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

	window.variable_list.selectAll()
	window._confirm_variables()

	assert [variable.path for variable in window.session.config.sweep_variables] == [
		variable.path for variable in window.session.discovered_variables
	]

	window.close()
	application.processEvents()