import os
from pathlib import Path
import pytest
import numpy as np
from openpyxl import Workbook

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFileDialog, QGroupBox, QHeaderView, QScrollArea, QMessageBox
from PySide6.QtCore import QPoint, Qt, QEventLoop, QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest

from canopy_processor.ui.main_window import MainWindow
from canopy_processor.ui.pipeline import LoadedDataset, analyze_loaded_dataset
from canopy_processor.ui.discovery import DiscoveryResult
from canopy_processor import AnalysisConfig, BaselineConfig, DatasetConfig, FilterConfig, PlotConfig, SweepVariable, SweepVariableConfig
from canopy_processor.ui.settings import RESOURCE_DIRECTORY_KEY
from canopy_processor.ui.session import SessionState
from canopy_processor.dxpx import DXPXRun
from canopy_processor.metric import source_metric
from PySide6.QtCore import QSettings


REPOSITORY_ROOT = os.path.dirname(os.path.dirname(__file__))


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
	export_row = window.workspace_tabs.widget(1).layout().itemAt(3).layout()
	assert export_row.itemAt(1).widget().text() == "Choose export folder"
	assert export_row.itemAt(2).widget() is window.export_aspect
	assert export_row.itemAt(3).widget() is window.export_svg
	assert export_row.itemAt(4).widget() is window.export_png
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


@pytest.mark.parametrize("render_tab", [0, 1])
def test_repeated_figures_fit_canvas_without_window_resize(tmp_path: Path, render_tab: int) -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()
	config = AnalysisConfig(
		dataset=DatasetConfig(tmp_path, tmp_path), metric="grip",
		sweep_variables=[SweepVariableConfig("pressure", role="x")],
	)
	window.session.config = config
	run = DXPXRun(tmp_path / "0" / "run.dxpx", {}, {
		"sLap": np.array([0., 1.]), "grip": np.array([1., 2.]),
	})
	loaded = LoadedDataset((run,), {"grip": source_metric("grip", "Grip", "grip", "g")}, ())
	output = analyze_loaded_dataset(loaded, config, (SweepVariable("pressure", "bar", (1.,)),))
	window.resize(1400, 1000)
	window.workspace_tabs.setCurrentIndex(render_tab)
	window.show()
	application.processEvents()
	for _ in range(2):
		window.workspace_tabs.setCurrentIndex(render_tab)
		application.processEvents()
		window._analysis_succeeded(output)
		window.workspace_tabs.setCurrentIndex(1)
		application.processEvents()
		canvas = window.figure_canvas
		pixel_width, pixel_height = canvas.figure.get_size_inches() * canvas.figure.dpi
		assert pixel_width == pytest.approx(canvas.width() * canvas.device_pixel_ratio, abs=1)
		assert pixel_height == pytest.approx(canvas.height() * canvas.device_pixel_ratio, abs=1)
	window.resize(1600, 1100)
	application.processEvents()
	canvas = window.figure_canvas
	assert canvas.figure.bbox.width == pytest.approx(canvas.width() * canvas.device_pixel_ratio, abs=1)
	assert canvas.figure.bbox.height == pytest.approx(canvas.height() * canvas.device_pixel_ratio, abs=1)
	window.close()
	application.processEvents()


def test_variable_columns_are_adjustable_and_keep_scaling() -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()
	window.resize(1920, 1200)
	window.show()
	application.processEvents()
	table = window.variable_list
	header = table.horizontalHeader()
	assert all(header.sectionResizeMode(index) == QHeaderView.Interactive for index in range(4))
	width = table.columnWidth(2) + 60
	header.resizeSection(2, width)
	application.processEvents()
	assert table.columnWidth(2) == width
	window.resize(2560, 1440)
	application.processEvents()
	assert table.columnWidth(2) > width
	assert sum(table.columnWidth(index) for index in range(4)) == pytest.approx(table.viewport().width(), abs=2)
	assert table.columnWidth(2) > table.columnWidth(1)
	window.close()
	application.processEvents()


@pytest.mark.parametrize("column", range(4))
def test_column_drag_cannot_push_other_columns_offscreen(column: int) -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()
	window.variable_list.setRowCount(60)
	window.show()
	application.processEvents()
	table = window.variable_list
	header = table.horizontalHeader()
	minimum = header.minimumSectionSize()
	for window_width in (1920, 1100, 2560, 900):
		window.resize(window_width, 1000)
		application.processEvents()
		for requested_width in (table.viewport().width() * 3, minimum):
			header.resizeSection(column, requested_width)
			application.processEvents()
			assert all(table.columnWidth(index) >= minimum for index in range(4))
			assert header.length() == pytest.approx(table.viewport().width(), abs=1)
			assert header.sectionViewportPosition(3) + table.columnWidth(3) <= table.viewport().width() + 1
			assert table.horizontalScrollBar().maximum() == 0
	window.close()
	application.processEvents()


def test_reconfirm_after_column_resize_preserves_loaded_analysis(monkeypatch, tmp_path: Path) -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()
	variables = (SweepVariable("front", "bar", (1.,)), SweepVariable("rear", "bar", (2.,)))
	discovery = DiscoveryResult(tmp_path, tmp_path, tmp_path, None, variables, None, ())
	window._discovery_succeeded(discovery)
	config = AnalysisConfig(
		dataset=DatasetConfig(tmp_path, tmp_path, track_name="CTMP", confirmed_header_track="CTMP"),
		sweep_variables=[SweepVariableConfig("front", role="y"), SweepVariableConfig("rear", role="x")],
	)
	window.session.config = config
	window.variable_list.cellWidget(0, 1).setCurrentText("y")
	window.variable_list.cellWidget(1, 1).setCurrentText("x")
	run = DXPXRun(tmp_path / "0" / "run.dxpx", {"TrackName": "CTMP"}, {
		"sLap": np.array([0., 1.]), "grip": np.array([1., 2.]),
		"isApex": np.array([1, 0]), "isTurnZone1": np.array([1, 1]),
	})
	loaded = LoadedDataset((run,), {"grip": source_metric("grip", "Grip", "grip", "g")}, ())
	window._loading_succeeded(loaded)
	window.metric_combo.setCurrentIndex(window.metric_combo.findData("grip"))
	window.plot_combo.setCurrentIndex(window.plot_combo.findData("heatmap"))
	window.phase_list.item(0).setCheckState(Qt.CheckState.Checked)
	window.zone_list.item(0).setCheckState(Qt.CheckState.Checked)
	window._begin_analysis()
	_wait_for_window_worker(window, application)
	assert window.session.state is SessionState.RESULTS_AVAILABLE
	dataset = window.session.config.dataset
	previous_result = window.session.result
	window.variable_list.horizontalHeader().resizeSection(2, 250)
	def unexpected_reload(*args):
		pytest.fail("Reconfirming unchanged sources must not reload the data")
	monkeypatch.setattr(window, "_start_loading", unexpected_reload)
	window.confirm_button.click()
	assert window.session.state is SessionState.READY
	assert window.session.loaded_dataset is loaded
	assert window.session.config.dataset is dataset
	assert window.session.config.dataset.confirmed_header_track == "CTMP"
	assert window.session.result is previous_result
	assert window._checked_names(window.phase_list) == ("isApex",)
	assert window._checked_names(window.zone_list) == ("isTurnZone1",)
	window._begin_analysis()
	_wait_for_window_worker(window, application)
	assert window.session.state is SessionState.RESULTS_AVAILABLE
	assert window.session.result.plot_data.values.shape == (1, 1)
	window.close()
	application.processEvents()


def test_file_menu_has_room_for_labels_and_shortcuts(tmp_path: Path) -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()
	window.show()
	menu = window.file_menu
	font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeui.ttf"
	if font_path.is_file():
		font_id = QFontDatabase.addApplicationFont(str(font_path))
		families = QFontDatabase.applicationFontFamilies(font_id)
		if families:
			menu.setFont(QFont(families[0], 10))
	menu.popup(window.mapToGlobal(QPoint(10, 30)))
	application.processEvents()
	metrics = menu.fontMetrics()
	for action in (window.open_action, window.save_action, window.save_as_action):
		label_width = metrics.horizontalAdvance(action.text())
		shortcut_width = metrics.horizontalAdvance(action.shortcut().toString())
		assert menu.actionGeometry(action).width() >= label_width + shortcut_width + 24
	assert menu.grab().save(str(tmp_path / "file-menu.png"))
	menu.close()
	window.close()
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
	window.export_aspect.setCurrentIndex(window.export_aspect.findData("16:9"))
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
	assert saved.export.aspect_ratio == "16:9"
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
		window.export_aspect.setCurrentIndex(window.export_aspect.findData("4:3"))
		original_size = tuple(window.figure_canvas.figure.get_size_inches())
		window._export_figure()
		assert tuple(window.figure_canvas.figure.get_size_inches()) == original_size
		assert (tmp_path / "exports/study.svg").is_file()
		assert (tmp_path / "exports/study.png").is_file()
		exported_svg = (tmp_path / "exports/study.svg").read_text(encoding="utf-8")
		assert "isApex" in exported_svg
		assert "isTurnZone1" in exported_svg
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


@pytest.mark.local_data
def test_main_window_populates_discovered_variables(sample_exploration) -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()
	window._start_discovery(sample_exploration.raw_directory)
	loop = QEventLoop()
	thread = window._thread
	assert thread is not None
	thread.finished.connect(loop.quit)
	QTimer.singleShot(5000, loop.quit)
	loop.exec()
	application.processEvents()

	assert window.session.discovery_result is not None
	assert window.dxpx_label.text().endswith(str(sample_exploration.dxpx_directory))
	assert window.variable_list.rowCount() == len(window.session.discovered_variables)
	assert window.variable_list.rowCount() >= 2
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


@pytest.mark.local_data
def test_main_window_persists_multiple_selected_variables(sample_exploration) -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()
	window._start_discovery(sample_exploration.raw_directory)
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
	assert len(window.session.loaded_dataset.runs) > 0
	assert window.metric_combo.count() > 1
	assert window.detected_track_label.text().endswith(sample_exploration.track_name)
	assert window.turn_zone_track_combo.currentData() == sample_exploration.track_name
	window.prepare_turn_zones_button.click()
	loop = QEventLoop()
	zone_thread = window._thread
	assert zone_thread is not None
	zone_thread.finished.connect(loop.quit)
	QTimer.singleShot(30000, loop.quit)
	loop.exec()
	application.processEvents()
	assert len(window.session.loaded_dataset.runs[0].turn_zone_names) > 0
	assert window.detected_track_label.text() == (
		f"DXPX Header.TrackName: {sample_exploration.track_name}; zones use: {sample_exploration.track_name}"
	)
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
	assert {"x", "y"}.issubset({variable.role for variable in window.session.config.sweep_variables})
	assert window.session.config.filters.phases
	assert window.session.config.filters.turn_zones
	assert all(
		row.metric_result.selected_samples < row.metric_result.available_samples
		for row in window.session.result.rows
	)
	assert window.results_table.rowCount() == len(window.session.result.rows)
	assert len(window.figure_canvas.figure.axes) >= 1

	window.close()
	application.processEvents()


@pytest.mark.local_data
def test_manual_dxpx_override_is_used_for_loading(monkeypatch, sample_exploration) -> None:
	application = QApplication.instance() or QApplication([])
	window = MainWindow()
	window._start_discovery(sample_exploration.raw_directory)
	loop = QEventLoop()
	thread = window._thread
	assert thread is not None
	thread.finished.connect(loop.quit)
	QTimer.singleShot(5000, loop.quit)
	loop.exec()
	application.processEvents()

	override = sample_exploration.raw_directory.parent / "manual-dxpx-study"
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