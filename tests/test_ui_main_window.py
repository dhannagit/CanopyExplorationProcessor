import os
from pathlib import Path
import pytest
import numpy as np
from openpyxl import Workbook

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFileDialog, QGroupBox, QScrollArea, QMessageBox
from PySide6.QtCore import QPoint, Qt, QEventLoop, QTimer
from PySide6.QtTest import QTest

from canopy_processor.ui.main_window import MainWindow
from canopy_processor.ui.pipeline import LoadedDataset
from canopy_processor.ui.discovery import DiscoveryResult
from canopy_processor import AnalysisConfig, BaselineConfig, DatasetConfig, FilterConfig, PlotConfig, SweepVariable, SweepVariableConfig
from canopy_processor.ui.settings import RESOURCE_DIRECTORY_KEY
from canopy_processor.dxpx import DXPXRun
from canopy_processor.metric import source_metric
from PySide6.QtCore import QSettings


REPOSITORY_ROOT = os.path.dirname(os.path.dirname(__file__))
SAMPLE_RAW_STUDY = os.path.join(REPOSITORY_ROOT, "DATA_Raw", "MOS_COR_TyrePressureExploration")


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
	settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
	settings.setValue(RESOURCE_DIRECTORY_KEY, REPOSITORY_ROOT)
	monkeypatch.setattr("canopy_processor.ui.main_window.create_settings", lambda: settings)
	monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Discard)
	monkeypatch.setattr(QMessageBox, "information", lambda *args: QMessageBox.StandardButton.Ok)


def test_main_window_builds_workbench() -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()

	assert window.windowTitle() == "Canopy Exploration Processor"
	assert window.session.state.value == "empty"
	assert window.root_label.text() == "No root selected"
	assert window.metric_combo.count() == 1
	assert window.minimumSize().width() == 900
	window.resize(1920, 1200)
	window.show()
	application.processEvents()
	assert not isinstance(window.workspace_tabs.widget(0), QScrollArea)
	assert window.workspace_tabs.count() == 3
	assert [window.workspace_tabs.tabText(index) for index in range(3)] == [
		"Analysis", "Results", "Comparison"
	]
	for object_name in (
		"datasetGroup",
		"sweepVariablesGroup",
		"phaseFiltersGroup",
		"turnZonesGroup",
		"analysisSettingsGroup",
	):
		assert window.findChild(QGroupBox, object_name) is not None
	assert window.variable_list.height() > 100
	assert window.phase_list.height() > 80
	assert window.zone_list.height() > 100
	variable_width_at_1920 = window.variable_list.width()
	zone_height_at_1920 = window.zone_list.height()
	window.resize(2560, 1440)
	application.processEvents()
	assert window.variable_list.width() > variable_width_at_1920
	assert window.zone_list.height() > zone_height_at_1920
	long_path = Path("C:/") / "/".join(["long-study-folder"] * 8)
	window._set_path_label(window.raw_label, long_path)
	assert window.raw_label.text() == str(long_path)

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


def test_save_and_open_unapplied_draft(monkeypatch, tmp_path: Path) -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()
	path = tmp_path / "draft.json"
	monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(path), ""))
	window.analysis_name.setText("Unapplied study")
	window.baseline_combo.setCurrentIndex(window.baseline_combo.findData("external_study"))
	window.external_laps_edit.setText("0, 2")
	window._external_baseline_path = tmp_path / "inactive.dxpx"
	window.baseline_combo.setCurrentIndex(window.baseline_combo.findData("none"))
	window.annotate_checkbox.setChecked(False)
	window.export_svg.setChecked(False)
	assert window._save_analysis()
	saved = AnalysisConfig.load(path)
	assert saved.name == "Unapplied study"
	assert saved.dataset is None
	assert saved.baseline.mode == "none"
	assert saved.baseline.external_path == tmp_path / "inactive.dxpx"
	assert saved.baseline.lap_indices == (0, 2)
	assert saved.plot.plot_type == "suggested"
	assert not saved.plot.annotate
	assert saved.export.formats == ("png",)
	window.analysis_name.setText("Unsaved edit")
	monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(path), ""))
	window._open_analysis()
	assert window.analysis_name.text() == "Unapplied study"
	assert window._snapshot_config() == saved
	assert window.session.result is None
	window.close()
	application.processEvents()


def test_cancel_open_and_invalid_json_preserve_session(monkeypatch, tmp_path: Path) -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()
	window.analysis_name.setText("Keep me")
	previous = window.session
	monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Cancel)
	window._open_analysis()
	assert window.session is previous
	assert window.analysis_name.text() == "Keep me"
	monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Discard)
	path = tmp_path / "bad.json"
	path.write_text("not JSON", encoding="utf-8")
	monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(path), ""))
	window._open_analysis()
	assert window.session is previous
	assert "Could not open" in window.status_label.text()
	window.close()
	application.processEvents()


def _wait_for_window_worker(window: MainWindow, application: QApplication) -> None:
	thread = window._thread
	assert thread is not None
	loop = QEventLoop()
	thread.finished.connect(loop.quit)
	QTimer.singleShot(10000, loop.quit)
	loop.exec()
	application.processEvents()
	assert window._thread is None


@pytest.mark.parametrize("assign_y_after_confirmation", [False, True])
def test_assigned_axes_survive_single_row_highlight_and_save(
	monkeypatch, tmp_path: Path, assign_y_after_confirmation: bool,
) -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()
	front = SweepVariable("tyres.front.pressure", "bar", (1., 1., 2., 2.))
	rear = SweepVariable("tyres.rear.pressure", "bar", (1., 2., 1., 2.))
	discovery = DiscoveryResult(tmp_path, tmp_path, tmp_path, None, (front, rear), None, ())
	runs = tuple(DXPXRun(tmp_path / str(index) / "run.dxpx", {"TrackName": "CTMP"}, {
		"sLap": np.array([0., 1.]), "grip": np.array([1., 2. + index]),
	}) for index in range(4))
	loaded = LoadedDataset(runs, {"grip": source_metric("grip", "Grip", "grip", "g")}, ())
	window._discovery_succeeded(discovery)
	window.variable_list.cellWidget(0, 2).setText("Front pressure")
	window.variable_list.cellWidget(1, 2).setText("Rear pressure")
	window.variable_list.cellWidget(1, 1).setCurrentText("x")
	if not assign_y_after_confirmation:
		window.variable_list.cellWidget(0, 1).setCurrentText("y")
	window.variable_list.selectRow(1)
	monkeypatch.setattr(window, "_start_loading", lambda result: window._loading_succeeded(loaded))
	window._confirm_variables()
	if assign_y_after_confirmation:
		window.variable_list.cellWidget(0, 1).setCurrentText("y")
	window.metric_combo.setCurrentIndex(window.metric_combo.findData("grip"))
	window.plot_combo.setCurrentIndex(window.plot_combo.findData("heatmap"))
	window._document_path = tmp_path / "pressure.json"
	assert window._save_analysis()
	saved = AnalysisConfig.load(window._document_path)
	assert {variable.path: variable.role for variable in saved.sweep_variables} == {
		front.path: "y", rear.path: "x",
	}
	assert {variable.display_name for variable in saved.sweep_variables} == {"Front pressure", "Rear pressure"}
	window._begin_analysis()
	_wait_for_window_worker(window, application)
	assert window.session.result.plot_data.values.shape == (2, 2)
	assert window.figure_canvas.figure.axes[0].get_ylabel() == "Front pressure [bar]"
	window.close()
	application.processEvents()


@pytest.mark.parametrize("confirmed,header", [(False, "CTMP"), (True, "CTMP"), (True, "Watkins-Glen")])
def test_open_reloads_override_and_restores_track_safely(monkeypatch, tmp_path: Path, confirmed: bool, header: str) -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()
	raw = tmp_path / "raw"
	dxpx = tmp_path / "manual-dxpx"
	raw.mkdir()
	dxpx.mkdir()
	book = Workbook()
	book.active.title = "Turns"
	book.active.append(["Circuit", "T1_in", "T1_out"])
	book.active.append(["CTMP", 0, 1])
	workbook = tmp_path / "CircuitsData_Canopy_Hypercar.xlsx"
	book.save(workbook)
	book.close()
	window.settings.setValue(RESOURCE_DIRECTORY_KEY, str(tmp_path))
	variable = SweepVariable("setup.pressure", "bar", (1.0,))
	discovery = DiscoveryResult(raw, tmp_path / "auto-dxpx", raw, workbook, (variable,), None, ())
	run = DXPXRun(dxpx / "0" / "run.dXpx", {"TrackName": header}, {
		"sLap": np.array([0., 1., 2.]), "grip": np.array([1., 2., 3.]),
		"isApex": np.array([0, 1, 0]),
	})
	loaded = LoadedDataset((run,), {"grip": source_metric("grip", "Grip", "grip", "g")}, ())
	config = AnalysisConfig(
		name="Restored recipe", dataset=DatasetConfig(dxpx, raw, workbook, "CTMP"),
		sweep_variables=[SweepVariableConfig(variable.path, "Pressure", "bar", "x")], metric="grip",
		filters=FilterConfig(phases=("isApex",), turn_zones=("isTurnZone1",)),
		plot=PlotConfig("suggested", False),
	)
	if confirmed:
		config.dataset.confirmed_header_track = "CTMP"
		config.dataset.confirmed_workbook_digest = window._workbook_digest(workbook)
	path = tmp_path / "study.json"
	config.save(path)
	monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(path), ""))
	monkeypatch.setattr("canopy_processor.ui.main_window.discover_dataset", lambda *args: discovery)
	seen = []
	monkeypatch.setattr("canopy_processor.ui.main_window.load_dataset", lambda candidate, *args: seen.append(candidate) or loaded)
	previous = window.session
	window._open_analysis()
	assert window.session is previous
	_wait_for_window_worker(window, application)
	assert seen[0].dxpx_directory == dxpx
	assert window.session is not previous
	assert window.session.result is None
	assert window.metric_combo.currentData() == "grip"
	assert window.variable_list.cellWidget(0, 2).text() == "Pressure"
	assert window._checked_names(window.phase_list) == ("isApex",)
	assert window._checked_names(window.zone_list) == ("isTurnZone1",)
	assert bool(window.session.loaded_dataset.runs[0].turn_zone_names) == (confirmed and header == "CTMP")
	if not confirmed or header != "CTMP":
		assert window.session.config.dataset.confirmed_header_track is None
	assert window._snapshot_config().plot.plot_type == "suggested"
	if confirmed and header == "CTMP":
		window._begin_analysis()
		_wait_for_window_worker(window, application)
		assert window.session.result is not None
		assert window.figure_canvas.figure.axes[0].get_xlabel() == "Pressure [bar]"
		window.export_directory.setText(str(tmp_path / "exports"))
		window._export_figure()
		assert (tmp_path / "exports/study.svg").is_file()
		assert (tmp_path / "exports/study.png").is_file()
	window.close()
	application.processEvents()


def test_failed_source_open_preserves_session_and_results(monkeypatch, tmp_path: Path) -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()
	window.session.result = "previous result"
	previous = window.session
	config = AnalysisConfig(dataset=DatasetConfig(tmp_path, tmp_path))
	path = tmp_path / "broken-study.json"
	config.save(path)
	monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(path), ""))
	def fail(*args):
		raise ValueError("source unavailable")
	monkeypatch.setattr("canopy_processor.ui.main_window.discover_dataset", fail)
	window._open_analysis()
	_wait_for_window_worker(window, application)
	assert window.session is previous
	assert window.session.result == "previous result"
	assert "source unavailable" in window.status_label.text()
	window.close()
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

	def fake_discovery(path: str, circuit_workbook: Path | None = None) -> DiscoveryResult:
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