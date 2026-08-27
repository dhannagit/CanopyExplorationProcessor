"""Background-friendly dataset loading for the desktop workbench."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..dxpx import DXPXRun, load_dxpx
from ..analysis import analyze_runs
from ..config import AnalysisConfig, PlotConfig
from ..plot_data import build_plot_data
from ..results import build_grid, join_sweep_variables
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


def analyze_loaded_dataset(
	loaded: LoadedDataset,
	config: AnalysisConfig,
	discovered_variables: tuple[object, ...],
	progress: Callable[[str, int, int], None] | None = None,
) -> AnalysisOutput:
	"""Reduce loaded runs and prepare plot data from the GUI configuration."""

	if not loaded.runs:
		raise ValueError("No loaded runs are available for analysis")
	metric_name = config.metrics[0] if config.metrics else next(iter(loaded.metrics), None)
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
	plot = _plot_config_from_roles(config, metric_name)
	if progress:
		progress("Building plot data", 3, 3)
	return AnalysisOutput(
		rows=tuple(rows),
		grid=grid,
		plot_data=build_plot_data(grid, plot),
		metric_name=metric_name,
	)


def _plot_config_from_roles(config: AnalysisConfig, metric_name: str) -> PlotConfig:
	"""Create the active plot configuration from selected variable roles."""

	roles = {variable.role: variable.path for variable in config.sweep_variables}
	x_variable = roles.get("x")
	y_variable = roles.get("y")
	facets = tuple(variable.path for variable in config.sweep_variables if variable.role == "facet")
	color_variable = roles.get("color")
	plot_type = config.plot.plot_type
	if plot_type == "line" and not x_variable:
		raise ValueError("Assign one selected sweep variable to the x role")
	if plot_type in {"heatmap", "faceted_heatmap"} and (not x_variable or not y_variable):
		raise ValueError("Heatmaps require selected x and y sweep variables")
	return PlotConfig(
		plot_type=plot_type,
		x_variable=x_variable,
		y_variable=y_variable,
		facet_variables=facets,
		color_variable=color_variable,
		annotate=config.plot.annotate,
	)


def load_dataset(
	discovery: DiscoveryResult,
	is_cancelled: Callable[[], bool] = lambda: False,
	progress: Callable[[str, int, int], None] | None = None,
) -> LoadedDataset:
	"""Load discovered DXPX runs and prepare missing turn-zone masks."""

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
			if not run.turn_zone_names and discovery.circuit_workbook is not None:
				run = add_turn_zones(run, discovery.circuit_workbook)
			runs.append(run)
		except Exception as error:
			diagnostics.append(f"Run {path.parent.name} could not be loaded: {error}")
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