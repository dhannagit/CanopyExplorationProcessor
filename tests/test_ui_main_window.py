import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFileDialog, QScrollArea
from PySide6.QtCore import QPoint, Qt, QEventLoop, QTimer
from PySide6.QtTest import QTest
from PySide6.QtCore import QEventLoop, QTimer

from canopy_processor.ui.main_window import MainWindow
from canopy_processor.ui.pipeline import LoadedDataset
from canopy_processor.ui.discovery import DiscoveryResult
from canopy_processor import SweepVariable


REPOSITORY_ROOT = os.path.dirname(os.path.dirname(__file__))
SAMPLE_RAW_STUDY = os.path.join(REPOSITORY_ROOT, "DATA_Raw", "MOS_COR_TyrePressureExploration")


def test_main_window_builds_workbench() -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()

	assert window.windowTitle() == "Canopy Exploration Processor"
	assert window.session.state.value == "empty"
	assert window.root_label.text() == "No root selected"
	assert window.metric_combo.count() == 1
	assert window.minimumSize().width() == 900
	controls_scroll = window.findChild(QScrollArea, "controlsScroll")
	assert controls_scroll is not None
	assert controls_scroll.maximumWidth() == 360

	window.close()
	application.processEvents()
	del window
	application.processEvents()


def test_baseline_dropdown_configures_both_sources(monkeypatch, tmp_path: Path) -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()
	window.baseline_run_combo.addItem("Run 4", 4)
	window.baseline_combo.setCurrentIndex(window.baseline_combo.findData("loaded_run"))
	assert not window.baseline_run_combo.isHidden()
	assert window._baseline_config().run_index == 4

	external_path = tmp_path / "baseline.dXpx"
	monkeypatch.setattr(
		QFileDialog,
		"getOpenFileName",
		lambda *args: (str(external_path), "DXPX files (*.dXpx *.DXPX)"),
	)
	window.baseline_combo.setCurrentIndex(window.baseline_combo.findData("external_study"))
	assert not window.external_baseline_button.isHidden()
	window._choose_external_baseline()
	window.external_laps_edit.setText("0, 2")
	baseline = window._baseline_config()
	assert baseline.external_path == external_path
	assert baseline.lap_indices == (0, 2)
	assert baseline.delta_mode == "percent"

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
	window.variable_list.cellWidget(0, 1).setCurrentText("y")
	assert window.session.config.sweep_variables[0].role == "y"

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
	assert all(not run.turn_zone_names for run in window.session.loaded_dataset.runs)
	assert window.detected_track_label.text().endswith("CTMP")
	assert window.turn_zone_track_combo.currentData() == "CTMP"
	assert window.zone_list.count() == 0
	window.prepare_turn_zones_button.click()
	loop = QEventLoop()
	zone_thread = window._thread
	assert zone_thread is not None
	zone_thread.finished.connect(loop.quit)
	QTimer.singleShot(30000, loop.quit)
	loop.exec()
	application.processEvents()
	assert len(window.session.loaded_dataset.runs[0].turn_zone_names) == 12
	assert window.detected_track_label.text() == "DXPX Header.TrackName: CTMP; zones use: CTMP"
	window.variable_list.cellWidget(0, 1).setCurrentText("x")
	window.variable_list.cellWidget(1, 1).setCurrentText("y")
	assert window.phase_list.count() > 0
	assert window.zone_list.count() > 0
	phase_item = window.phase_list.item(0)
	zone_item = window.zone_list.item(0)
	phase_item.setCheckState(Qt.CheckState.Checked)
	zone_item.setCheckState(Qt.CheckState.Checked)
	zone_rect = window.zone_list.visualItemRect(zone_item)
	QTest.mouseClick(
		window.zone_list.viewport(),
		Qt.MouseButton.LeftButton,
		pos=QPoint(zone_rect.left() + 8, zone_rect.center().y()),
	)
	assert zone_item.checkState() == Qt.CheckState.Unchecked
	QTest.mouseClick(
		window.zone_list.viewport(),
		Qt.MouseButton.LeftButton,
		pos=QPoint(zone_rect.left() + 8, zone_rect.center().y()),
	)
	assert zone_item.checkState() == Qt.CheckState.Checked
	window.phase_operator.setCurrentText("or")
	window.zone_operator.setCurrentText("or")
	window.category_operator.setCurrentText("and")
	window.session.config.sweep_variables = [window.session.config.sweep_variables[0]]
	window.metric_combo.setCurrentIndex(window.metric_combo.findData("gCarPotential"))
	window._begin_analysis()
	loop = QEventLoop()
	analysis_thread = window._thread
	assert analysis_thread is not None
	analysis_thread.finished.connect(loop.quit)
	QTimer.singleShot(15000, loop.quit)
	loop.exec()
	application.processEvents()
	assert window.session.result is not None
	assert {variable.role for variable in window.session.config.sweep_variables} == {"x", "y"}
	assert window.session.config.filters.phases
	assert window.session.config.filters.turn_zones
	assert all(
		row.metric_result.selected_samples < row.metric_result.available_samples
		for row in window.session.result.rows
	)
	assert window.results_table.rowCount() == 25
	assert len(window.figure_canvas.figure.axes) >= 1

	window.close()
	application.processEvents()


def test_manual_dxpx_override_is_used_for_loading(monkeypatch) -> None:
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

	override = Path(SAMPLE_RAW_STUDY).parent.parent / "manual-dxpx-study"
	result = window.session.discovery_result
	assert result is not None
	window.session.discovery_result = result.__class__(
		root=result.root,
		dxpx_directory=override,
		raw_directory=result.raw_directory,
		circuit_workbook=result.circuit_workbook,
		variables=result.variables,
		exploration=result.exploration,
		diagnostics=result.diagnostics,
		dxpx_candidates=result.dxpx_candidates,
	)
	window.variable_list.selectRow(0)
	captured = []
	monkeypatch.setattr(
		"canopy_processor.ui.main_window.load_dataset",
		lambda discovery, *args: captured.append(discovery) or LoadedDataset((), {}, ()),
	)
	window._start_loading(window.session.discovery_result)
	loop = QEventLoop()
	thread = window._thread
	assert thread is not None
	thread.finished.connect(loop.quit)
	QTimer.singleShot(5000, loop.quit)
	loop.exec()

	assert captured and captured[0].dxpx_directory == override
	window.close()
	application.processEvents()


def test_new_raw_study_selection_rediscoveries_variables(monkeypatch, tmp_path: Path) -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()
	first = tmp_path / "StudyA"
	second = tmp_path / "StudyB"
	first_variable = SweepVariable("setup.first", "bar", (1.0,))
	second_variable = SweepVariable("setup.second", "deg", (2.0,))

	def fake_discovery(path: str) -> DiscoveryResult:
		variable = first_variable if Path(path) == first else second_variable
		return DiscoveryResult(Path(path), Path(path) / "dxpx", Path(path), None, (variable,), None, ())

	monkeypatch.setattr("canopy_processor.ui.main_window.discover_dataset", fake_discovery)
	for path, expected in ((first, first_variable), (second, second_variable)):
		window._start_discovery(str(path))
		loop = QEventLoop()
		thread = window._thread
		assert thread is not None
		thread.finished.connect(loop.quit)
		QTimer.singleShot(5000, loop.quit)
		loop.exec()
		application.processEvents()
		assert window.session.discovery_result.root == path.resolve()
		assert window.session.discovered_variables == (expected,)

	window.close()
	application.processEvents()
	del window
	application.processEvents()