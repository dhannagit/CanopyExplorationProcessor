"""Background-friendly dataset loading for the desktop workbench."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..dxpx import DXPXRun, load_dxpx
from ..analysis import analyze_runs
from ..config import AnalysisConfig
from ..plot_data import build_plot_data, resolve_plot
from ..results import (
	ComparedRow,
	analyze_baseline,
	build_grid,
	compare_rows_to_baseline,
	join_sweep_variables,
	resolve_baseline_laps,
)
from ..metric import Metric, default_metrics
from ..turn_zones import add_turn_zones
from .discovery import DiscoveryResult


@dataclass(frozen=True)
class LoadedDataset:
	"""Loaded runs, compatible metrics, and non-fatal loading diagnostics."""

	runs: tuple[DXPXRun, ...]
	metrics: dict[str, Metric]
	diagnostics: tuple[str, ...]


@dataclass(frozen=True)
class AnalysisOutput:
	"""Reduced rows and renderer-independent plot data for one analysis."""

	rows: tuple[object, ...]
	grid: object
	plot_data: object
	metric_name: str
	compared_rows: tuple[ComparedRow, ...] = ()


def analyze_loaded_dataset(
	loaded: LoadedDataset,
	config: AnalysisConfig,
	discovered_variables: tuple[object, ...],
	progress: Callable[[str, int, int], None] | None = None,
) -> AnalysisOutput:
	"""Reduce loaded runs and prepare plot data from the GUI configuration."""

	if not loaded.runs:
		raise ValueError("No loaded runs are available for analysis")
	config.validate_ready()
	metric_name = config.metric
	if not metric_name or metric_name not in loaded.metrics:
		raise ValueError("Select a compatible metric before analysis")
	selected_paths = {variable.path for variable in config.sweep_variables}
	variables = tuple(variable for variable in discovered_variables if variable.path in selected_paths)
	if not variables:
		raise ValueError("Select at least one sweep variable before analysis")
	if progress:
		progress("Reducing metric values", 1, 3)
	results = analyze_runs(loaded.runs, loaded.metrics[metric_name], config.filters)
	if progress:
		progress("Joining sweep coordinates", 2, 3)
	rows = join_sweep_variables(loaded.runs, results, variables)
	grid = build_grid(rows, variable_paths=[variable.path for variable in variables])
	compared_rows: tuple[ComparedRow, ...] = ()
	if config.baseline.mode != "none":
		baseline_laps = resolve_baseline_laps(config.baseline, sweep_runs=loaded.runs)
		if config.filters.turn_zones:
			if any(not lap.turn_zone_names for lap in baseline_laps):
				if config.dataset is None or config.dataset.circuit_workbook is None:
					raise ValueError("A circuit workbook is required to prepare baseline turn zones")
				if not config.dataset.track_name:
					raise ValueError("Confirm a circuit before generating baseline turn zones")
				if any(
					lap.track_name != config.dataset.confirmed_header_track
					for lap in baseline_laps if not lap.turn_zone_names
				):
					raise ValueError("Baseline track does not match the confirmed track; verify the baseline source")
				baseline_laps = [
					add_turn_zones(
						lap,
						config.dataset.circuit_workbook,
						track_name=config.dataset.track_name,
					)
					if not lap.turn_zone_names
					else lap
					for lap in baseline_laps
				]
		baseline = analyze_baseline(
			baseline_laps,
			loaded.metrics[metric_name],
			config.filters,
		)
		compared_rows = tuple(
			compare_rows_to_baseline(rows, baseline, config.baseline.delta_mode)
		)
	plot = resolve_plot(config.plot, config.sweep_variables)
	if progress:
		progress("Building plot data", 3, 3)
	return AnalysisOutput(
		rows=tuple(rows),
		grid=grid,
		plot_data=build_plot_data(grid, plot),
		metric_name=metric_name,
		compared_rows=compared_rows,
	)


def load_dataset(
	discovery: DiscoveryResult,
	is_cancelled: Callable[[], bool] = lambda: False,
	progress: Callable[[str, int, int], None] | None = None,
) -> LoadedDataset:
	"""Load discovered DXPX runs without generating turn-zone masks."""

	if discovery.dxpx_directory is None:
		raise FileNotFoundError("No DXPX directory was discovered")
	files = sorted(
		(path for path in discovery.dxpx_directory.rglob("*.dXpx") if path.parent.name.isdigit()),
		key=lambda path: (int(path.parent.name), str(path)),
	)
	if not files:
		raise FileNotFoundError(f"No numbered .dXpx files found below {discovery.dxpx_directory}")

	diagnostics = list(discovery.diagnostics)
	runs: list[DXPXRun] = []
	for index, path in enumerate(files, start=1):
		if is_cancelled():
			return LoadedDataset(tuple(runs), {}, tuple(diagnostics + ["Loading cancelled"]))
		if progress:
			progress("Loading simulation runs", index - 1, len(files))
		try:
			run = load_dxpx(path)
		except Exception as error:
			diagnostics.append(f"Run {path.parent.name} could not be loaded: {error}")
			continue
		runs.append(run)
	if progress:
		progress("Checking available metrics", len(files), len(files))

	metrics: dict[str, Metric] = {}
	if runs:
		for name, metric in default_metrics().items():
			try:
				metric.evaluate(runs[0])
			except (KeyError, ValueError, TypeError):
				continue
			metrics[name] = metric
		if not metrics:
			diagnostics.append("No default metrics are compatible with the loaded runs")
	else:
		diagnostics.append("No simulation runs were loaded")
	return LoadedDataset(tuple(runs), metrics, tuple(diagnostics))


def prepare_turn_zones(
	loaded: LoadedDataset,
	workbook_path: Path,
	track_name: str,
) -> LoadedDataset:
	"""Add missing zone masks using the circuit explicitly confirmed by the user."""

	diagnostics = list(loaded.diagnostics)
	runs: list[DXPXRun] = []
	for run in loaded.runs:
		if run.turn_zone_names:
			runs.append(run)
			continue
		try:
			runs.append(add_turn_zones(run, workbook_path, track_name=track_name))
		except Exception as error:
			diagnostics.append(f"Run {run.path.parent.name} turn zones could not be prepared: {error}")
			runs.append(run)
	return LoadedDataset(tuple(runs), loaded.metrics, tuple(diagnostics))