"""Initial PySide6 workbench shell for one analysis session."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
	QComboBox,
	QAbstractItemView,
	QDockWidget,
	QDialog,
	QFileDialog,
	QFormLayout,
	QGroupBox,
	QHBoxLayout,
	QHeaderView,
	QLabel,
	QListWidget,
	QListWidgetItem,
	QLineEdit,
	QMainWindow,
	QProgressBar,
	QPushButton,
	QSizePolicy,
	QTabWidget,
	QTableWidget,
	QTableWidgetItem,
	QVBoxLayout,
	QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

from ..config import BaselineConfig, DatasetConfig, FilterConfig, SweepVariableConfig
from .discovery import DiscoveryResult, discover_dataset
from .pipeline import (
	AnalysisOutput,
	LoadedDataset,
	analyze_loaded_dataset,
	load_dataset,
	prepare_turn_zones,
)
from ..turn_zones import list_circuit_names
from ..plotting import render_plot_data
from .session import AnalysisSession, SessionState
from .settings import RESOURCE_DIRECTORY_KEY, circuit_workbook, create_settings
from .settings_dialog import SettingsDialog
from .worker import CancellationToken, Worker, start_worker


STYLE = """
QMainWindow, QWidget { background: #151a20; color: #d7e0e8; }
QGroupBox { border: 1px solid #303b45; margin-top: 12px; padding: 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #74d7e8; }
QPushButton { background: #24333b; border: 1px solid #42616b; padding: 7px 12px; }
QPushButton:hover { background: #2d4852; border-color: #74d7e8; }
QPushButton#applyButton { background: #187a8e; border-color: #74d7e8; font-weight: 700; }
QComboBox, QListWidget, QTableWidget, QTextEdit { background: #10151a; border: 1px solid #303b45; padding: 5px; }
QLabel#title { color: #74d7e8; font-size: 20px; font-weight: 700; }
QLabel#muted { color: #8c9aa5; }
QProgressBar { border: 1px solid #303b45; text-align: center; }
QProgressBar::chunk { background: #20a8bd; }
"""


class MainWindow(QMainWindow):
	"""Plotting workbench shell; numerical workers will attach to its session."""

	def __init__(self, settings: QSettings | None = None) -> None:
		super().__init__()
		self.settings = settings if settings is not None else create_settings()
		self.session = AnalysisSession()
		self._thread = None
		self._worker: Worker | None = None
		self._source_loaded_dataset: LoadedDataset | None = None
		self.setWindowTitle("Canopy Exploration Processor")
		self.setMinimumSize(900, 600)
		self.resize(1100, 700)
		self.setStyleSheet(STYLE)
		self._build_ui()
		file_menu = self.menuBar().addMenu("File")
		file_menu.addAction("Settings...", self._open_settings)

	def _open_settings(self) -> None:
		dialog = SettingsDialog(self.settings.value(RESOURCE_DIRECTORY_KEY, "", type=str), self)
		if dialog.exec() == QDialog.DialogCode.Accepted:
			self.settings.setValue(RESOURCE_DIRECTORY_KEY, dialog.resource_directory)
			self.settings.sync()
			self.status_label.setText("Settings saved; circuit folder changes apply to the next study load")

	def _build_ui(self) -> None:
		root = QWidget()
		layout = QVBoxLayout(root)
		layout.setContentsMargins(14, 14, 14, 14)
		self.workspace_tabs = QTabWidget()
		self.workspace_tabs.addTab(self._build_controls(), "Analysis")
		self.workspace_tabs.addTab(self._build_results(), "Results")
		self.workspace_tabs.addTab(self._build_comparison(), "Comparison")
		layout.addWidget(self.workspace_tabs)
		self.setCentralWidget(root)
		self._build_status_dock()

	def _build_controls(self) -> QWidget:
		panel = QWidget()
		layout = QVBoxLayout(panel)

		title = QLabel("EXPLORATION PROCESSOR")
		title.setObjectName("title")
		layout.addWidget(title)
		intro = QLabel("Configure a sweep, then apply it to the loaded source data.")
		intro.setObjectName("muted")
		intro.setWordWrap(True)
		layout.addWidget(intro)

		top_row = QHBoxLayout()
		dataset = QGroupBox("Dataset")
		dataset.setObjectName("datasetGroup")
		dataset.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
		dataset_form = QFormLayout(dataset)
		self.root_label = QLabel("No root selected")
		self.root_label.setObjectName("muted")
		self.root_label.setWordWrap(True)
		self.root_label.setToolTip("No root selected")
		self.raw_label = QLabel("Not detected")
		self.raw_label.setObjectName("muted")
		self.raw_label.setWordWrap(True)
		self.dxpx_label = QLabel("Not detected")
		self.dxpx_label.setObjectName("muted")
		self.dxpx_label.setWordWrap(True)
		select_root = QPushButton("Select raw study folder")
		select_root.clicked.connect(self._select_raw_study)
		dataset_form.addRow(select_root)
		dataset_form.addRow("Study:", self.root_label)
		dataset_form.addRow("Raw:", self.raw_label)
		dataset_form.addRow("DXPX:", self.dxpx_label)
		self.choose_dxpx_button = QPushButton("Choose DXPX folder")
		self.choose_dxpx_button.setEnabled(False)
		self.choose_dxpx_button.clicked.connect(self._choose_dxpx)
		dataset_form.addRow(self.choose_dxpx_button)
		top_row.addWidget(dataset, 1)

		variables = QGroupBox("Sweep variables")
		variables.setObjectName("sweepVariablesGroup")
		variables.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
		variables_layout = QVBoxLayout(variables)
		self.variable_list = QTableWidget(0, 2)
		self.variable_list.setHorizontalHeaderLabels(["Variable", "Role"])
		self.variable_list.setSelectionBehavior(QAbstractItemView.SelectRows)
		self.variable_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
		self.variable_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
		self.variable_list.setMinimumHeight(100)
		self.variable_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
		self.variable_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
		self.variable_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
		variables_layout.addWidget(self.variable_list)
		self.confirm_button = QPushButton("Confirm variables")
		self.confirm_button.setEnabled(False)
		self.confirm_button.clicked.connect(self._confirm_variables)
		variables_layout.addWidget(self.confirm_button)
		top_row.addWidget(variables, 1)
		layout.addLayout(top_row, 2)

		bottom_row = QHBoxLayout()
		phases = QGroupBox("Phases")
		phases.setObjectName("phaseFiltersGroup")
		phases.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
		phases_form = QFormLayout(phases)
		zones = QGroupBox("Turn zones")
		zones.setObjectName("turnZonesGroup")
		zones.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
		zones_form = QFormLayout(zones)
		self.turn_zone_form = zones_form
		analysis = QGroupBox("Analysis settings")
		analysis.setObjectName("analysisSettingsGroup")
		analysis.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
		analysis_layout = QVBoxLayout(analysis)
		analysis_form = QFormLayout()
		analysis_layout.addLayout(analysis_form)
		self.analysis_form = analysis_form
		self.metric_combo = QComboBox()
		self.metric_combo.addItem("Select metric")
		self.plot_combo = QComboBox()
		for label, value in (("Suggested plot", "suggested"), ("Line", "line"), ("Scatter", "scatter"), ("Heatmap", "heatmap"), ("Faceted heatmap", "faceted_heatmap"), ("Parallel coordinates", "parallel_coordinates")):
			self.plot_combo.addItem(label, value)
		self.baseline_combo = QComboBox()
		self.baseline_combo.addItem("No baseline", "none")
		self.baseline_combo.addItem("Loaded run", "loaded_run")
		self.baseline_combo.addItem("External study", "external_study")
		self.baseline_combo.currentIndexChanged.connect(self._baseline_mode_changed)
		self.baseline_run_combo = QComboBox()
		self.external_baseline_button = QPushButton("Choose baseline DXPX file")
		self.external_baseline_button.clicked.connect(self._choose_external_baseline)
		self.external_baseline_label = QLabel("No external baseline selected")
		self.external_baseline_label.setWordWrap(True)
		self.external_laps_edit = QLineEdit("0")
		self.external_laps_edit.setToolTip("Zero-based lap indices, comma-separated")
		self.baseline_delta_combo = QComboBox()
		for label, value in (("Absolute difference", "absolute"), ("Percent difference", "percent")):
			self.baseline_delta_combo.addItem(label, value)
		self.baseline_delta_combo.setCurrentIndex(1)
		self._external_baseline_path: Path | None = None
		self.phase_list = QListWidget()
		self.phase_list.setSelectionMode(QAbstractItemView.NoSelection)
		self.phase_list.setMinimumHeight(80)
		self.phase_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
		self.zone_list = QListWidget()
		self.zone_list.setSelectionMode(QAbstractItemView.NoSelection)
		self.zone_list.setMinimumHeight(100)
		self.zone_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
		self.phase_operator = QComboBox()
		self.phase_operator.addItems(["or", "and"])
		self.zone_operator = QComboBox()
		self.zone_operator.addItems(["or", "and"])
		self.category_operator = QComboBox()
		self.category_operator.addItems(["and", "or"])
		self.detected_track_label = QLabel("Track has not been inspected")
		self.detected_track_label.setWordWrap(True)
		self.turn_zone_track_combo = QComboBox()
		self.prepare_turn_zones_button = QPushButton("Confirm track and add zones")
		self.prepare_turn_zones_button.clicked.connect(self._prepare_turn_zones)
		analysis_form.addRow("Metric:", self.metric_combo)
		analysis_form.addRow("Plot:", self.plot_combo)
		analysis_form.addRow("Baseline:", self.baseline_combo)
		analysis_form.addRow("Baseline run:", self.baseline_run_combo)
		analysis_form.addRow("External file:", self.external_baseline_button)
		analysis_form.addRow("Selected file:", self.external_baseline_label)
		analysis_form.addRow("Lap indices (0-based):", self.external_laps_edit)
		analysis_form.addRow("Comparison:", self.baseline_delta_combo)
		phases_form.addRow("Select phases:", self.phase_list)
		phases_form.addRow("Phase logic:", self.phase_operator)
		zones_form.addRow("Detected track:", self.detected_track_label)
		zones_form.addRow("Track for zones:", self.turn_zone_track_combo)
		zones_form.addRow(self.prepare_turn_zones_button)
		zones_form.addRow("Select zones:", self.zone_list)
		zones_form.addRow("Zone logic:", self.zone_operator)
		analysis_form.addRow("Category logic:", self.category_operator)

		self.apply_button = QPushButton("Apply / Analyze")
		self.apply_button.setObjectName("applyButton")
		self.apply_button.clicked.connect(self._begin_analysis)
		analysis_layout.addWidget(self.apply_button)
		bottom_row.addWidget(phases, 1)
		bottom_row.addWidget(zones, 1)
		bottom_row.addWidget(analysis, 1)
		layout.addLayout(bottom_row, 3)
		self._baseline_mode_changed()
		self._set_track_controls_visible(False)
		return panel

	def _build_results(self) -> QWidget:
		panel = QWidget()
		layout = QVBoxLayout(panel)
		self.results_label = QLabel("Results canvas is ready for the first analysis.")
		layout.addWidget(self.results_label)
		self.figure_canvas = FigureCanvasQTAgg()
		self.figure_canvas.setMinimumHeight(300)
		layout.addWidget(self.figure_canvas, 1)
		self.results_table = QTableWidget(0, 0)
		self.results_table.setMinimumHeight(180)
		layout.addWidget(self.results_table)
		return panel

	def _build_comparison(self) -> QWidget:
		panel = QWidget()
		layout = QVBoxLayout(panel)
		self.comparison_table = QTableWidget(0, 0)
		layout.addWidget(self.comparison_table)
		return panel

	def _build_status_dock(self) -> None:
		dock = QDockWidget("Diagnostics", self)
		dock.setAllowedAreas(Qt.BottomDockWidgetArea)
		content = QWidget()
		layout = QHBoxLayout(content)
		self.status_label = QLabel("Ready for a dataset")
		self.progress = QProgressBar()
		self.progress.setRange(0, 0)
		self.progress.setVisible(False)
		self.cancel_button = QPushButton("Cancel")
		self.cancel_button.setVisible(False)
		self.cancel_button.clicked.connect(self._cancel_analysis)
		layout.addWidget(self.status_label, 1)
		layout.addWidget(self.progress)
		layout.addWidget(self.cancel_button)
		dock.setWidget(content)
		self.addDockWidget(Qt.BottomDockWidgetArea, dock)

	def _select_raw_study(self) -> None:
		path = QFileDialog.getExistingDirectory(self, "Select one raw StudyName folder")
		if path:
			self.root_label.setText(path)
			self.root_label.setToolTip(path)
			self.session.begin_discovery()
			self._source_loaded_dataset = None
			self._set_track_controls_visible(False)
			self.variable_list.clear()
			self.variable_list.setRowCount(0)
			self.raw_label.setText("Not detected")
			self.dxpx_label.setText("Not detected")
			self.choose_dxpx_button.setEnabled(False)
			self.confirm_button.setEnabled(False)
			self.status_label.setText("Discovering source data...")
			self._start_discovery(path)

	def _start_discovery(self, path: str) -> None:
		workbook = circuit_workbook(self.settings.value(RESOURCE_DIRECTORY_KEY, "", type=str))

		def operation(token: CancellationToken, progress: object) -> DiscoveryResult:
			progress("Scanning source folders", 1, 2)
			if token.cancelled:
				return None
			result = discover_dataset(path, workbook)
			progress("Reading sweep metadata", 2, 2)
			return result

		self._thread, self._worker = start_worker(operation, start=False)
		self._worker.progress.connect(self._show_progress)
		self._worker.result_ready.connect(self._discovery_succeeded)
		self._worker.failed.connect(self._operation_failed)
		self._worker.cancelled.connect(self._operation_cancelled)
		self._thread.finished.connect(self._worker_finished)
		self.progress.setRange(0, 2)
		self.progress.setValue(0)
		self.progress.setVisible(True)
		self.cancel_button.setVisible(True)
		self._thread.start()

	def _show_progress(self, stage: str, value: int, total: int) -> None:
		self.session.update_progress(stage, value, total)
		self.status_label.setText(stage)
		self.progress.setRange(0, total)
		self.progress.setValue(value)

	def _discovery_succeeded(self, result: DiscoveryResult) -> None:
		self.session.finish_discovery(result.variables, list(result.diagnostics), result)
		self._set_path_label(self.raw_label, result.raw_directory)
		self._set_path_label(self.dxpx_label, result.dxpx_directory)
		self.choose_dxpx_button.setEnabled(result.raw_directory is not None)
		self.variable_list.clear()
		self.variable_list.setColumnCount(2)
		self.variable_list.setHorizontalHeaderLabels(["Variable", "Role"])
		self.variable_list.setRowCount(len(result.variables))
		for row, variable in enumerate(result.variables):
			units = f" [{variable.units}]" if variable.units else ""
			self.variable_list.setItem(row, 0, QTableWidgetItem(f"{variable.path}{units} ({len(variable.values)} values)"))
			role = QComboBox()
			role.addItems(["unused", "x", "y", "facet", "color"])
			role.currentTextChanged.connect(lambda value, row=row: self._update_config_role(row, value))
			self.variable_list.setCellWidget(row, 1, role)
		if not result.variables:
			self.variable_list.setRowCount(1)
			self.variable_list.setItem(0, 0, QTableWidgetItem("No numeric sweep variables found"))
		self.confirm_button.setEnabled(bool(result.variables) and result.dxpx_directory is not None and result.raw_directory is not None)
		self.status_label.setText(self._discovery_status(result))
		self.status_label.setToolTip("\n".join(result.diagnostics))

	def _update_config_role(self, row: int, role: str) -> None:
		"""Keep visible role edits synchronized after variable confirmation."""

		if row >= len(self.session.discovered_variables):
			return
		path = self.session.discovered_variables[row].path
		for variable in self.session.config.sweep_variables:
			if variable.path == path:
				variable.role = role
				return

	def _choose_dxpx(self) -> None:
		path = QFileDialog.getExistingDirectory(self, "Select DXPX study folder")
		if not path:
			return
		result = self.session.discovery_result
		if not isinstance(result, DiscoveryResult):
			return
		updated = DiscoveryResult(
			root=result.root,
			dxpx_directory=Path(path),
			raw_directory=result.raw_directory,
			circuit_workbook=result.circuit_workbook,
			variables=result.variables,
			exploration=result.exploration,
			diagnostics=result.diagnostics,
			dxpx_candidates=result.dxpx_candidates,
		)
		self.session.discovery_result = updated
		self.dxpx_label.setText(path)
		self.dxpx_label.setToolTip(path)
		self.status_label.setText("Manual DXPX path selected; review and confirm")

	def _set_path_label(self, label: QLabel, path: Path | None) -> None:
		"""Show the complete path in the wrapping label and its tooltip."""

		text = str(path) if path else "Not detected"
		label.setText(text)
		label.setToolTip(text)

	def _discovery_status(self, result: DiscoveryResult) -> str:
		if result.diagnostics:
			return f"Discovery complete with {len(result.diagnostics)} diagnostic(s)"
		return f"Discovered {len(result.variables)} sweep variable(s); review and confirm"

	def _confirm_variables(self) -> None:
		result = self.session.discovery_result
		if not isinstance(result, DiscoveryResult) or result.dxpx_directory is None or result.raw_directory is None:
			return
		selected_rows = sorted({index.row() for index in self.variable_list.selectionModel().selectedRows()})
		if not selected_rows:
			self.status_label.setText("Select at least one sweep variable")
			return
		self.session.config.dataset = DatasetConfig(
			dxpx_directory=result.dxpx_directory,
			raw_directory=result.raw_directory,
			circuit_workbook=result.circuit_workbook,
		)
		self.session.config.sweep_variables = []
		for row in selected_rows:
			role_widget = self.variable_list.cellWidget(row, 1)
			role = role_widget.currentText() if isinstance(role_widget, QComboBox) else "unused"
			self.session.config.sweep_variables.append(
				SweepVariableConfig(path=result.variables[row].path, units=result.variables[row].units, role=role)
			)
		self.session.mark_ready()
		self.confirm_button.setEnabled(False)
		self.status_label.setText("Loading simulation runs...")
		self._start_loading(result)

	def _start_loading(self, discovery: DiscoveryResult) -> None:
		self.session.begin_loading()

		def operation(token: CancellationToken, progress: object) -> LoadedDataset:
			return load_dataset(discovery, lambda: token.cancelled, progress)

		self._thread, self._worker = start_worker(operation, start=False)
		self._worker.progress.connect(self._show_progress)
		self._worker.result_ready.connect(self._loading_succeeded)
		self._worker.failed.connect(self._operation_failed)
		self._worker.cancelled.connect(self._operation_cancelled)
		self._thread.finished.connect(self._worker_finished)
		self.progress.setVisible(True)
		self.cancel_button.setVisible(True)
		self._thread.start()

	def _loading_succeeded(self, loaded: LoadedDataset) -> None:
		self._source_loaded_dataset = loaded
		self.session.publish_loaded_dataset(loaded)
		self.metric_combo.clear()
		self.metric_combo.addItem("Select metric")
		for name, metric in loaded.metrics.items():
			self.metric_combo.addItem(f"{metric.label} [{metric.units}]", name)
		self.phase_list.clear()
		self.zone_list.clear()
		self.status_label.setToolTip("\n".join(loaded.diagnostics))
		self.zone_list.setEnabled(False)
		if loaded.runs:
			phase_names = sorted(
				name for name in loaded.runs[0].data
				if name.startswith("is") and not name.startswith("isTurnZone")
			)
			self._set_checkable_items(self.phase_list, phase_names)
			self._populate_zone_list(loaded)
			missing_zones = any(not run.turn_zone_names for run in loaded.runs)
			workbook = self.session.config.dataset.circuit_workbook if self.session.config.dataset else None
			if missing_zones and workbook is not None:
				try:
					tracks = list_circuit_names(workbook)
				except Exception as error:
					tracks = ()
					self.status_label.setToolTip(f"{self.status_label.toolTip()}\n{error}".strip())
				self.turn_zone_track_combo.clear()
				self.turn_zone_track_combo.addItem("Select track", None)
				for track in tracks:
					self.turn_zone_track_combo.addItem(track, track)
				detected_tracks = sorted({run.track_name for run in loaded.runs if run.track_name})
				if len(detected_tracks) == 1:
					detected = detected_tracks[0]
					self.detected_track_label.setText(f"DXPX Header.TrackName: {detected}")
					index = self.turn_zone_track_combo.findData(detected)
					if index >= 0:
						self.turn_zone_track_combo.setCurrentIndex(index)
				elif detected_tracks:
					self.detected_track_label.setText(
						"Multiple DXPX tracks: " + ", ".join(detected_tracks)
					)
				else:
					self.detected_track_label.setText("DXPX headers do not specify a track")
				self.prepare_turn_zones_button.setEnabled(bool(tracks))
				self.prepare_turn_zones_button.setText("Confirm track and add zones")
				self._set_track_controls_visible(True)
			else:
				self._set_track_controls_visible(False)
		self.zone_list.setEnabled(self.zone_list.count() > 0)
		if not self.zone_list.count():
			if self.session.config.dataset is None or self.session.config.dataset.circuit_workbook is None:
				self.zone_list.setToolTip("Configure the circuit folder in File > Settings, then reload the study")
			else:
				self.zone_list.setToolTip("Confirm a circuit above to generate turn-zone masks")
		self.baseline_run_combo.clear()
		for run in loaded.runs:
			self.baseline_run_combo.addItem(f"Run {run.path.parent.name}", int(run.path.parent.name))
		self._baseline_mode_changed()
		if loaded.diagnostics:
			self.status_label.setText(f"Loaded {len(loaded.runs)} run(s) with {len(loaded.diagnostics)} diagnostic(s)")
		else:
			self.status_label.setText(f"Loaded {len(loaded.runs)} run(s); choose a metric and apply")

	def _populate_zone_list(self, loaded: LoadedDataset) -> None:
		self.zone_list.clear()
		if not loaded.runs:
			return
		available_zones = set(loaded.runs[0].turn_zone_names)
		for run in loaded.runs[1:]:
			available_zones.intersection_update(run.turn_zone_names)
		for name in loaded.runs[0].turn_zone_names:
			if name in available_zones:
				self._add_checkable_item(self.zone_list, name)
		self.zone_list.setEnabled(self.zone_list.count() > 0)
		self.zone_list.setToolTip(
			"" if self.zone_list.count() else "No turn-zone mask is available on every loaded run"
		)

	def _set_checkable_items(self, widget: QListWidget, names: list[str]) -> None:
		widget.clear()
		for name in names:
			self._add_checkable_item(widget, name)

	def _add_checkable_item(self, widget: QListWidget, name: str) -> None:
		item = QListWidgetItem(name)
		item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
		item.setCheckState(Qt.CheckState.Unchecked)
		widget.addItem(item)

	def _set_track_controls_visible(self, visible: bool) -> None:
		for widget in (
			self.detected_track_label,
			self.turn_zone_track_combo,
			self.prepare_turn_zones_button,
		):
			widget.setVisible(visible)
			label = self.turn_zone_form.labelForField(widget)
			if label is not None:
				label.setVisible(visible)

	def _prepare_turn_zones(self) -> None:
		loaded = self._source_loaded_dataset
		track_name = self.turn_zone_track_combo.currentData()
		dataset = self.session.config.dataset
		if loaded is None or dataset is None or dataset.circuit_workbook is None:
			self.status_label.setText("The central circuit workbook is unavailable")
			return
		if not track_name:
			self.status_label.setText("Select and confirm a circuit before adding turn zones")
			return
		self.session.config.dataset.track_name = str(track_name)
		self.prepare_turn_zones_button.setEnabled(False)
		self.status_label.setText(f"Adding turn zones for {track_name}...")

		def operation(token: CancellationToken, progress: object) -> LoadedDataset:
			if token.cancelled:
				return None
			return prepare_turn_zones(loaded, dataset.circuit_workbook, str(track_name))

		self._thread, self._worker = start_worker(operation, start=False)
		self._worker.result_ready.connect(self._turn_zones_succeeded)
		self._worker.failed.connect(self._operation_failed)
		self._worker.cancelled.connect(self._operation_cancelled)
		self._thread.finished.connect(self._worker_finished)
		self.progress.setVisible(True)
		self.cancel_button.setVisible(True)
		self._thread.start()

	def _turn_zones_succeeded(self, loaded: LoadedDataset) -> None:
		self.session.publish_loaded_dataset(loaded)
		self._populate_zone_list(loaded)
		self.prepare_turn_zones_button.setEnabled(True)
		self.prepare_turn_zones_button.setText("Regenerate zones with selected track")
		track_name = self.session.config.dataset.track_name if self.session.config.dataset else ""
		detected_tracks = sorted(
			{run.track_name for run in self._source_loaded_dataset.runs if run.track_name}
		) if self._source_loaded_dataset else []
		detected_label = ", ".join(detected_tracks) if detected_tracks else "not specified"
		self.detected_track_label.setText(
			f"DXPX Header.TrackName: {detected_label}; zones use: {track_name}"
		)
		self.status_label.setText(
			f"Turn zones prepared for {track_name}: {self.zone_list.count()} shared zone(s)"
		)

	def _operation_failed(self, message: str) -> None:
		self.session.fail(message)
		self.prepare_turn_zones_button.setEnabled(self._source_loaded_dataset is not None)
		self.status_label.setText(f"Operation failed: {message}")

	def _operation_cancelled(self) -> None:
		self.session.complete_cancellation()
		self.prepare_turn_zones_button.setEnabled(self._source_loaded_dataset is not None)
		self.status_label.setText("Operation cancelled; previous results are preserved")

	def _worker_finished(self) -> None:
		self.progress.setVisible(False)
		self.cancel_button.setVisible(False)
		self._worker = None
		self._thread = None

	def closeEvent(self, event: QCloseEvent) -> None:
		"""Stop an active operation before the window and its Qt objects close."""

		if self._worker is not None and self._thread is not None:
			self._worker.request_cancel()
			self._thread.quit()
			self._thread.wait(2000)
		event.accept()

	def _begin_analysis(self) -> None:
		if self.session.state not in {SessionState.READY, SessionState.RESULTS_AVAILABLE}:
			self.status_label.setText("Review the discovered variables before applying analysis")
			return
		loaded = self.session.loaded_dataset
		if not isinstance(loaded, LoadedDataset):
			self.status_label.setText("Load the dataset before applying analysis")
			return
		metric_name = self.metric_combo.currentData()
		if not metric_name:
			self.status_label.setText("Select a metric before applying analysis")
			return
		self.session.config.metrics = [metric_name]
		self._sync_config_roles()
		self._ensure_roles_from_visible_controls()
		self.session.config.filters = FilterConfig(
			phases=tuple(
				self.phase_list.item(index).text()
				for index in range(self.phase_list.count())
				if self.phase_list.item(index).checkState() == Qt.CheckState.Checked
			),
			turn_zones=tuple(
				self.zone_list.item(index).text()
				for index in range(self.zone_list.count())
				if self.zone_list.item(index).checkState() == Qt.CheckState.Checked
			),
			phase_operator=self.phase_operator.currentText(),
			turn_zone_operator=self.zone_operator.currentText(),
			category_operator=self.category_operator.currentText(),
		)
		try:
			self.session.config.baseline = self._baseline_config()
		except ValueError as error:
			self.status_label.setText(str(error))
			return
		plot_type = self.plot_combo.currentData()
		if plot_type == "suggested":
			roles = {variable.role for variable in self.session.config.sweep_variables}
			plot_type = "heatmap" if {"x", "y"}.issubset(roles) else "line"
		self.session.config.plot.plot_type = plot_type
		self.session.begin_analysis()
		self.status_label.setText("Analyzing selected metric...")
		self._start_analysis(loaded)

	def _sync_config_roles(self) -> None:
		"""Copy current role controls into the confirmed configuration."""

		configured = {variable.path: variable for variable in self.session.config.sweep_variables}
		for row, discovered in enumerate(self.session.discovered_variables):
			variable = configured.get(discovered.path)
			role_widget = self.variable_list.cellWidget(row, 1)
			if variable is not None and isinstance(role_widget, QComboBox):
				variable.role = role_widget.currentText()

	def _ensure_roles_from_visible_controls(self) -> None:
		"""Recover role assignments if row selection was lost after confirmation."""

		roles = {
			self.session.discovered_variables[row].path: self.variable_list.cellWidget(row, 1).currentText()
			for row in range(self.variable_list.rowCount())
			if row < len(self.session.discovered_variables)
			and isinstance(self.variable_list.cellWidget(row, 1), QComboBox)
		}
		configured_roles = {variable.role for variable in self.session.config.sweep_variables}
		if "x" in roles.values() and "y" in roles.values() and not {"x", "y"}.issubset(configured_roles):
			self.session.config.sweep_variables = [
				SweepVariableConfig(
					path=variable.path,
					units=variable.units,
					role=roles[variable.path],
				)
				for variable in self.session.discovered_variables
				if roles.get(variable.path, "unused") != "unused"
			]

	def _start_analysis(self, loaded: LoadedDataset) -> None:
		config = self.session.config
		discovered_variables = self.session.discovered_variables

		def operation(token: CancellationToken, progress: object) -> AnalysisOutput:
			if token.cancelled:
				return None
			return analyze_loaded_dataset(loaded, config, discovered_variables, progress)

		self._thread, self._worker = start_worker(operation, start=False)
		self._worker.progress.connect(self._show_progress)
		self._worker.result_ready.connect(self._analysis_succeeded)
		self._worker.failed.connect(self._operation_failed)
		self._worker.cancelled.connect(self._operation_cancelled)
		self._thread.finished.connect(self._worker_finished)
		self.progress.setRange(0, 3)
		self.progress.setValue(0)
		self.progress.setVisible(True)
		self.cancel_button.setVisible(True)
		self._thread.start()

	def _analysis_succeeded(self, output: AnalysisOutput) -> None:
		self.session.publish_result(output)
		figure = render_plot_data(output.plot_data, scatter=self.session.config.plot.plot_type == "scatter")
		self.figure_canvas.figure = figure
		self.figure_canvas.draw()
		self.results_label.setText(f"{output.metric_name}: {len(output.rows)} analyzed run(s)")
		self._populate_results_table(output)
		self._populate_comparison_table(output)

	def _baseline_mode_changed(self, *_args: object) -> None:
		mode = self.baseline_combo.currentData()
		for widget, visible in (
			(self.baseline_run_combo, mode == "loaded_run"),
			(self.external_baseline_button, mode == "external_study"),
			(self.external_baseline_label, mode == "external_study"),
			(self.external_laps_edit, mode == "external_study"),
			(self.baseline_delta_combo, mode != "none"),
		):
			widget.setVisible(visible)
			label = self.analysis_form.labelForField(widget)
			if label is not None:
				label.setVisible(visible)

	def _choose_external_baseline(self) -> None:
		path, _ = QFileDialog.getOpenFileName(
			self,
			"Select external baseline DXPX file",
			"",
			"DXPX files (*.dXpx *.DXPX)",
		)
		if not path:
			return
		self._external_baseline_path = Path(path)
		self._set_path_label(self.external_baseline_label, self._external_baseline_path)

	def _baseline_config(self) -> BaselineConfig:
		mode = self.baseline_combo.currentData()
		if mode == "none":
			return BaselineConfig()
		delta_mode = self.baseline_delta_combo.currentData()
		if mode == "loaded_run":
			run_index = self.baseline_run_combo.currentData()
			if run_index is None:
				raise ValueError("Select a loaded run for the baseline")
			return BaselineConfig(mode=mode, run_index=int(run_index), delta_mode=delta_mode)
		if self._external_baseline_path is None:
			raise ValueError("Choose an external baseline DXPX file")
		try:
			lap_indices = tuple(int(value.strip()) for value in self.external_laps_edit.text().split(","))
		except ValueError as error:
			raise ValueError("Lap indices must be comma-separated zero-based integers") from error
		return BaselineConfig(
			mode=mode,
			external_path=self._external_baseline_path,
			lap_indices=lap_indices,
			delta_mode=delta_mode,
		)

	def _populate_comparison_table(self, output: AnalysisOutput) -> None:
		if not output.compared_rows:
			self.comparison_table.clear()
			self.comparison_table.setRowCount(0)
			self.comparison_table.setColumnCount(0)
			return
		paths = [variable.path for variable in self.session.config.sweep_variables]
		delta_header = "Delta (%)" if self.session.config.baseline.delta_mode == "percent" else "Delta"
		headers = paths + ["Run", "Metric", "Baseline", delta_header]
		self.comparison_table.setColumnCount(len(headers))
		self.comparison_table.setHorizontalHeaderLabels(headers)
		self.comparison_table.setRowCount(len(output.compared_rows))
		for row_index, compared in enumerate(output.compared_rows):
			row = compared.row
			for column, path in enumerate(paths):
				self.comparison_table.setItem(
					row_index, column, QTableWidgetItem(f"{row.sweep_values[path]:g}")
				)
			self.comparison_table.setItem(row_index, len(paths), QTableWidgetItem(str(row.run_index)))
			self.comparison_table.setItem(
				row_index, len(paths) + 1, QTableWidgetItem(f"{row.metric_result.value:.6g}")
			)
			self.comparison_table.setItem(
				row_index, len(paths) + 2, QTableWidgetItem(f"{compared.baseline.value:.6g}")
			)
			delta = f"{compared.delta:.6g}" if compared.baseline_valid else "Invalid"
			self.comparison_table.setItem(row_index, len(paths) + 3, QTableWidgetItem(delta))

	def _populate_results_table(self, output: AnalysisOutput) -> None:
		paths = [variable.path for variable in self.session.config.sweep_variables]
		self.results_table.setColumnCount(len(paths) + 3)
		self.results_table.setHorizontalHeaderLabels(paths + ["Run", "Value", "Samples"])
		self.results_table.setRowCount(len(output.rows))
		for row_index, row in enumerate(output.rows):
			for column, path in enumerate(paths):
				self.results_table.setItem(row_index, column, QTableWidgetItem(f"{row.sweep_values[path]:g}"))
			self.results_table.setItem(row_index, len(paths), QTableWidgetItem(str(row.run_index)))
			self.results_table.setItem(row_index, len(paths) + 1, QTableWidgetItem(f"{row.metric_result.value:.6g}"))
			self.results_table.setItem(row_index, len(paths) + 2, QTableWidgetItem(str(row.metric_result.selected_samples)))

	def _cancel_analysis(self) -> None:
		if self._worker is not None:
			self._worker.request_cancel()
		self.session.request_cancel()
		self.status_label.setText("Cancellation requested; finishing current operation")