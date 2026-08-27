"""Initial PySide6 workbench shell for one analysis session."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
	QCheckBox,
	QComboBox,
	QAbstractItemView,
	QDockWidget,
	QFileDialog,
	QFormLayout,
	QGroupBox,
	QHBoxLayout,
	QLabel,
	QListWidget,
	QListWidgetItem,
	QMainWindow,
	QProgressBar,
	QPushButton,
	QSplitter,
	QTabWidget,
	QTableWidget,
	QTableWidgetItem,
	QTextEdit,
	QVBoxLayout,
	QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

from ..config import DatasetConfig, FilterConfig, SweepVariableConfig
from .discovery import DiscoveryResult, discover_dataset
from .pipeline import AnalysisOutput, LoadedDataset, analyze_loaded_dataset, load_dataset
from ..plotting import render_plot_data
from .session import AnalysisSession, SessionState
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

	def __init__(self) -> None:
		super().__init__()
		self.session = AnalysisSession()
		self._thread = None
		self._worker: Worker | None = None
		self.setWindowTitle("Canopy Exploration Processor")
		self.resize(1400, 850)
		self.setStyleSheet(STYLE)
		self._build_ui()

	def _build_ui(self) -> None:
		root = QWidget()
		layout = QHBoxLayout(root)
		layout.setContentsMargins(14, 14, 14, 14)
		layout.addWidget(self._build_controls(), 0)
		layout.addWidget(self._build_results(), 1)
		self.setCentralWidget(root)
		self._build_status_dock()

	def _build_controls(self) -> QWidget:
		panel = QWidget()
		panel.setMinimumWidth(300)
		layout = QVBoxLayout(panel)

		title = QLabel("CANOPY / EXPLORATION")
		title.setObjectName("title")
		layout.addWidget(title)
		intro = QLabel("Configure a sweep, then apply it to the loaded source data.")
		intro.setObjectName("muted")
		intro.setWordWrap(True)
		layout.addWidget(intro)

		dataset = QGroupBox("Dataset")
		dataset_form = QFormLayout(dataset)
		self.root_label = QLabel("No root selected")
		self.root_label.setObjectName("muted")
		self.raw_label = QLabel("Not detected")
		self.raw_label.setObjectName("muted")
		self.dxpx_label = QLabel("Not detected")
		self.dxpx_label.setObjectName("muted")
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
		layout.addWidget(dataset)

		variables = QGroupBox("Sweep variables")
		variables_layout = QVBoxLayout(variables)
		self.variable_list = QTableWidget(0, 2)
		self.variable_list.setHorizontalHeaderLabels(["Variable", "Role"])
		self.variable_list.setSelectionBehavior(QAbstractItemView.SelectRows)
		self.variable_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
		self.variable_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
		self.variable_list.setMinimumHeight(130)
		variables_layout.addWidget(self.variable_list)
		self.confirm_button = QPushButton("Confirm variables")
		self.confirm_button.setEnabled(False)
		self.confirm_button.clicked.connect(self._confirm_variables)
		variables_layout.addWidget(self.confirm_button)
		layout.addWidget(variables)

		analysis = QGroupBox("Analysis")
		analysis_form = QFormLayout(analysis)
		self.metric_combo = QComboBox()
		self.metric_combo.addItem("Select metric")
		self.plot_combo = QComboBox()
		for label, value in (("Suggested plot", "suggested"), ("Line", "line"), ("Scatter", "scatter"), ("Heatmap", "heatmap"), ("Faceted heatmap", "faceted_heatmap"), ("Parallel coordinates", "parallel_coordinates")):
			self.plot_combo.addItem(label, value)
		self.baseline_combo = QComboBox()
		self.baseline_combo.addItems(["No baseline", "Loaded run", "External study"])
		self.phase_list = QListWidget()
		self.phase_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
		self.phase_list.setMaximumHeight(70)
		self.zone_list = QListWidget()
		self.zone_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
		self.zone_list.setMaximumHeight(70)
		self.phase_operator = QComboBox()
		self.phase_operator.addItems(["or", "and"])
		self.zone_operator = QComboBox()
		self.zone_operator.addItems(["or", "and"])
		self.category_operator = QComboBox()
		self.category_operator.addItems(["and", "or"])
		analysis_form.addRow("Metric:", self.metric_combo)
		analysis_form.addRow("Plot:", self.plot_combo)
		analysis_form.addRow("Baseline:", self.baseline_combo)
		analysis_form.addRow("Phases:", self.phase_list)
		analysis_form.addRow("Phase logic:", self.phase_operator)
		analysis_form.addRow("Turn zones:", self.zone_list)
		analysis_form.addRow("Zone logic:", self.zone_operator)
		analysis_form.addRow("Category logic:", self.category_operator)
		layout.addWidget(analysis)

		apply_button = QPushButton("Apply / Analyze")
		apply_button.setObjectName("applyButton")
		apply_button.clicked.connect(self._begin_analysis)
		layout.addWidget(apply_button)
		layout.addStretch()
		return panel

	def _build_results(self) -> QWidget:
		panel = QWidget()
		layout = QVBoxLayout(panel)
		tabs = QTabWidget()
		results = QWidget()
		results_layout = QVBoxLayout(results)
		self.results_label = QLabel("Results canvas is ready for the first analysis.")
		results_layout.addWidget(self.results_label)
		self.figure_canvas = FigureCanvasQTAgg()
		self.figure_canvas.setMinimumHeight(300)
		results_layout.addWidget(self.figure_canvas, 1)
		self.results_table = QTableWidget(0, 0)
		self.results_table.setMinimumHeight(180)
		results_layout.addWidget(self.results_table)
		tabs.addTab(results, "Results")
		comparison = QTextEdit("Baseline comparison will use the active metric, filters, and plot selections.")
		comparison.setReadOnly(True)
		tabs.addTab(comparison, "Comparison")
		layout.addWidget(tabs)
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
			self.session.begin_discovery()
			self.variable_list.clear()
			self.variable_list.setRowCount(0)
			self.raw_label.setText("Not detected")
			self.dxpx_label.setText("Not detected")
			self.choose_dxpx_button.setEnabled(False)
			self.confirm_button.setEnabled(False)
			self.status_label.setText("Discovering source data...")
			self._start_discovery(path)

	def _start_discovery(self, path: str) -> None:
		def operation(token: CancellationToken, progress: object) -> DiscoveryResult:
			progress("Scanning source folders", 1, 2)
			if token.cancelled:
				return None
			result = discover_dataset(path)
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
		self.raw_label.setText(str(result.raw_directory or "Not detected"))
		self.dxpx_label.setText(str(result.dxpx_directory or "Not detected"))
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
		self.status_label.setText("Manual DXPX path selected; review and confirm")

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
		self.session.publish_loaded_dataset(loaded)
		self.metric_combo.clear()
		self.metric_combo.addItem("Select metric")
		for name, metric in loaded.metrics.items():
			self.metric_combo.addItem(f"{metric.label} [{metric.units}]", name)
		self.phase_list.clear()
		self.zone_list.clear()
		if loaded.runs:
			phase_names = sorted(
				name for name in loaded.runs[0].data
				if name.startswith("is") and not name.startswith("isTurnZone")
			)
			for name in phase_names:
				self.phase_list.addItem(name)
			for name in loaded.runs[0].turn_zone_names:
				self.zone_list.addItem(name)
		if loaded.diagnostics:
			self.status_label.setText(f"Loaded {len(loaded.runs)} run(s) with {len(loaded.diagnostics)} diagnostic(s)")
		else:
			self.status_label.setText(f"Loaded {len(loaded.runs)} run(s); choose a metric and apply")

	def _operation_failed(self, message: str) -> None:
		self.session.fail(message)
		self.status_label.setText(f"Operation failed: {message}")

	def _operation_cancelled(self) -> None:
		self.session.complete_cancellation()
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
			phases=tuple(item.text() for item in self.phase_list.selectedItems()),
			turn_zones=tuple(item.text() for item in self.zone_list.selectedItems()),
			phase_operator=self.phase_operator.currentText(),
			turn_zone_operator=self.zone_operator.currentText(),
			category_operator=self.category_operator.currentText(),
		)
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