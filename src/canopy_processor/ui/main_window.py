"""Initial PySide6 workbench shell for one analysis session."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
	QCheckBox,
	QComboBox,
	QDockWidget,
	QFileDialog,
	QFormLayout,
	QGroupBox,
	QHBoxLayout,
	QLabel,
	QListWidget,
	QMainWindow,
	QProgressBar,
	QPushButton,
	QSplitter,
	QTabWidget,
	QTableWidget,
	QTextEdit,
	QVBoxLayout,
	QWidget,
)

from ..config import DatasetConfig
from .discovery import DiscoveryResult, discover_dataset
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
		select_root = QPushButton("Select root folder")
		select_root.clicked.connect(self._select_root)
		dataset_form.addRow(select_root)
		dataset_form.addRow("Source:", self.root_label)
		layout.addWidget(dataset)

		variables = QGroupBox("Sweep variables")
		variables_layout = QVBoxLayout(variables)
		self.variable_list = QListWidget()
		self.variable_list.addItem("Review discovered variables after loading")
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
		self.plot_combo.addItems(["Suggested plot", "Line", "Scatter", "Heatmap", "Faceted heatmap", "Parallel coordinates"])
		self.baseline_combo = QComboBox()
		self.baseline_combo.addItems(["No baseline", "Loaded run", "External study"])
		self.turn_zone_check = QCheckBox("Use turn-zone masks")
		analysis_form.addRow("Metric:", self.metric_combo)
		analysis_form.addRow("Plot:", self.plot_combo)
		analysis_form.addRow("Baseline:", self.baseline_combo)
		analysis_form.addRow(self.turn_zone_check)
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
		results_layout.addWidget(QLabel("Results canvas is ready for the first analysis."))
		table = QTableWidget(0, 0)
		table.setMinimumHeight(180)
		results_layout.addWidget(table)
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

	def _select_root(self) -> None:
		path = QFileDialog.getExistingDirectory(self, "Select Canopy exploration root")
		if path:
			self.root_label.setText(path)
			self.session.begin_discovery()
			self.variable_list.clear()
			self.variable_list.addItem("Discovering source data...")
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

		self._thread, self._worker = start_worker(operation)
		self._worker.progress.connect(self._show_progress)
		self._worker.result_ready.connect(self._discovery_succeeded)
		self._worker.failed.connect(self._operation_failed)
		self._worker.cancelled.connect(self._operation_cancelled)
		self._worker.finished.connect(self._worker_finished)
		self.progress.setRange(0, 2)
		self.progress.setValue(0)
		self.progress.setVisible(True)
		self.cancel_button.setVisible(True)

	def _show_progress(self, stage: str, value: int, total: int) -> None:
		self.session.update_progress(stage, value, total)
		self.status_label.setText(stage)
		self.progress.setRange(0, total)
		self.progress.setValue(value)

	def _discovery_succeeded(self, result: DiscoveryResult) -> None:
		self.session.finish_discovery(result.variables, list(result.diagnostics), result)
		self.variable_list.clear()
		for variable in result.variables:
			units = f" [{variable.units}]" if variable.units else ""
			self.variable_list.addItem(f"{variable.path}{units} ({len(variable.values)} values)")
		if not result.variables:
			self.variable_list.addItem("No numeric sweep variables found")
		self.confirm_button.setEnabled(bool(result.variables) and result.dxpx_directory is not None and result.raw_directory is not None)
		self.status_label.setText(self._discovery_status(result))

	def _discovery_status(self, result: DiscoveryResult) -> str:
		if result.diagnostics:
			return f"Discovery complete with {len(result.diagnostics)} diagnostic(s)"
		return f"Discovered {len(result.variables)} sweep variable(s); review and confirm"

	def _confirm_variables(self) -> None:
		result = self.session.discovery_result
		if not isinstance(result, DiscoveryResult) or result.dxpx_directory is None or result.raw_directory is None:
			return
		self.session.config.dataset = DatasetConfig(
			dxpx_directory=result.dxpx_directory,
			raw_directory=result.raw_directory,
			circuit_workbook=result.circuit_workbook,
		)
		self.session.mark_ready()
		self.confirm_button.setEnabled(False)
		self.status_label.setText("Configuration ready; choose analysis settings and apply")

	def _operation_failed(self, message: str) -> None:
		self.session.fail(message)
		self.status_label.setText(f"Operation failed: {message}")

	def _operation_cancelled(self) -> None:
		self.status_label.setText("Operation cancelled; previous results are preserved")

	def _worker_finished(self) -> None:
		self.progress.setVisible(False)
		self.cancel_button.setVisible(False)
		self._worker = None
		self._thread = None

	def _begin_analysis(self) -> None:
		if self.session.state not in {SessionState.READY, SessionState.RESULTS_AVAILABLE}:
			self.status_label.setText("Review the discovered variables before applying analysis")
			return
		self.session.begin_analysis()
		self.progress.setVisible(True)
		self.cancel_button.setVisible(True)
		self.status_label.setText("Analysis queued")

	def _cancel_analysis(self) -> None:
		if self._worker is not None:
			self._worker.request_cancel()
		self.session.request_cancel()
		self.status_label.setText("Cancellation requested; finishing current operation")