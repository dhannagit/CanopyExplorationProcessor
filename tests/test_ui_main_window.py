import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

from canopy_processor.ui.main_window import MainWindow


REPOSITORY_ROOT = os.path.dirname(os.path.dirname(__file__))
SAMPLE_RAW_STUDY = os.path.join(REPOSITORY_ROOT, "DATA_Raw", "MOS_COR_TyrePressureExploration")


def test_main_window_builds_workbench() -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()

	assert window.windowTitle() == "Canopy Exploration Processor"
	assert window.session.state.value == "empty"
	assert window.root_label.text() == "No root selected"
	assert window.metric_combo.count() == 1

	window.close()
	application.processEvents()
	del window
	application.processEvents()


def test_main_window_populates_discovered_variables() -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()
	window._start_discovery(SAMPLE_RAW_STUDY)
	loop = QEventLoop()
	thread = window._thread
	assert thread is not None
	thread.finished.connect(loop.quit)
	QTimer.singleShot(5000, loop.quit)
	loop.exec()
	application.processEvents()

	assert window.session.discovery_result is not None
	assert window.dxpx_label.text().endswith("DATA_dXpx\\MOS_COR_TyrePressureExploration")
	assert window.variable_list.rowCount() == 2
	assert window.variable_list.selectionMode().name == "ExtendedSelection"
	assert window.confirm_button.isEnabled()
	window.variable_list.selectRow(0)
	window.variable_list.cellWidget(0, 1).setCurrentText("x")
	window._confirm_variables()
	assert [variable.path for variable in window.session.config.sweep_variables] == [
		window.session.discovered_variables[0].path
	]
	assert window.session.config.sweep_variables[0].role == "x"

	window.close()
	application.processEvents()
	del window
	application.processEvents()


def test_main_window_persists_multiple_selected_variables() -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()
	window._start_discovery(SAMPLE_RAW_STUDY)
	loop = QEventLoop()
	thread = window._thread
	assert thread is not None
	thread.finished.connect(loop.quit)
	QTimer.singleShot(5000, loop.quit)
	loop.exec()
	application.processEvents()

	window.variable_list.selectAll()
	window.variable_list.cellWidget(0, 1).setCurrentText("x")
	window.variable_list.cellWidget(1, 1).setCurrentText("y")
	window._confirm_variables()
	loop = QEventLoop()
	loading_thread = window._thread
	assert loading_thread is not None
	loading_thread.finished.connect(loop.quit)
	QTimer.singleShot(60000, loop.quit)
	loop.exec()
	application.processEvents()

	assert [variable.path for variable in window.session.config.sweep_variables] == [
		variable.path for variable in window.session.discovered_variables
	]
	assert window.session.loaded_dataset is not None
	assert len(window.session.loaded_dataset.runs) == 25
	assert window.metric_combo.count() > 1

	window.close()
	application.processEvents()
	del window
	application.processEvents()