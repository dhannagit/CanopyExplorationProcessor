"""Prepare plotting data from deduplicated sweep results.

The functions here produce NumPy arrays and labels only. Rendering, colors,
annotations, and GUI concerns belong to a later plotting layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

from .config import PlotConfig
from .results import GridPoint, GridResult


@dataclass(frozen=True)
class LinePlotData:
	"""Ordered x/y values for a one-dimensional sweep plot."""

	x_variable: str
	y_label: str
	x_values: np.ndarray
	y_values: np.ndarray


@dataclass(frozen=True)
class HeatmapPlotData:
	"""A two-dimensional sweep matrix with sorted axis values."""

	x_variable: str
	y_variable: str
	metric_name: str
	x_values: np.ndarray
	y_values: np.ndarray
	values: np.ndarray


@dataclass(frozen=True)
class FacetedHeatmapData:
	"""Heatmap data grouped by one or more remaining sweep dimensions."""

	base: HeatmapPlotData
	facet_variables: tuple[str, ...]
	facets: dict[tuple[float, ...], HeatmapPlotData]


@dataclass(frozen=True)
class ParallelCoordinatesData:
	"""Rows of sweep variables and metric values for parallel coordinates."""

	variables: tuple[str, ...]
	metric_name: str
	values: np.ndarray
	metric_values: np.ndarray
	run_indices: np.ndarray


def build_plot_data(grid: GridResult, plot: PlotConfig):
	"""Build the data object required by the configured plot type."""

	if plot.plot_type in {"line", "scatter"}:
		return build_line_data(grid.points, plot.x_variable)
	if plot.plot_type == "heatmap":
		return build_heatmap_data(grid.points, plot.x_variable, plot.y_variable)
	if plot.plot_type == "faceted_heatmap":
		return build_faceted_heatmap_data(
			grid.points,
			plot.x_variable,
			plot.y_variable,
			plot.facet_variables,
		)
	if plot.plot_type == "parallel_coordinates":
		return build_parallel_coordinates_data(grid.points, plot.color_variable)
	raise ValueError(f"Unsupported plot type: {plot.plot_type}")


def build_line_data(points: Iterable[GridPoint], x_variable: str | None) -> LinePlotData:
	"""Build sorted x/y arrays for a line or scatter plot."""

	point_list = list(points)
	variable = _required_variable(x_variable, "x_variable")
	if not point_list:
		raise ValueError("Cannot build line data from an empty grid")
	metric_name = _metric_name(point_list)
	ordered = sorted(point_list, key=lambda point: point.sweep_values[variable])
	return LinePlotData(
		x_variable=variable,
		y_label=metric_name,
		x_values=np.asarray([point.sweep_values[variable] for point in ordered], dtype=float),
		y_values=np.asarray([point.metric_result.value for point in ordered], dtype=float),
	)


def build_heatmap_data(
	points: Iterable[GridPoint],
	x_variable: str | None,
	y_variable: str | None,
) -> HeatmapPlotData:
	"""Build a y-by-x matrix, leaving absent coordinate pairs as NaN."""

	point_list = list(points)
	x_name = _required_variable(x_variable, "x_variable")
	y_name = _required_variable(y_variable, "y_variable")
	if x_name == y_name:
		raise ValueError("Heatmap x_variable and y_variable must be different")
	if not point_list:
		raise ValueError("Cannot build heatmap data from an empty grid")

	x_values = np.array(sorted({point.sweep_values[x_name] for point in point_list}), dtype=float)
	y_values = np.array(sorted({point.sweep_values[y_name] for point in point_list}), dtype=float)
	value_matrix = np.full((len(y_values), len(x_values)), np.nan)
	for point in point_list:
		x_index = np.searchsorted(x_values, point.sweep_values[x_name])
		y_index = np.searchsorted(y_values, point.sweep_values[y_name])
		value_matrix[y_index, x_index] = point.metric_result.value

	return HeatmapPlotData(
		x_variable=x_name,
		y_variable=y_name,
		metric_name=_metric_name(point_list),
		x_values=x_values,
		y_values=y_values,
		values=value_matrix,
	)


def build_faceted_heatmap_data(
	points: Iterable[GridPoint],
	x_variable: str | None,
	y_variable: str | None,
	facet_variables: Iterable[str],
) -> FacetedHeatmapData:
	"""Build one heatmap per unique combination of facet variables."""

	point_list = list(points)
	facets = tuple(facet_variables)
	if not facets:
		raise ValueError("Faceted heatmaps require at least one facet variable")
	for facet in facets:
		if facet in {x_variable, y_variable}:
			raise ValueError("Facet variables must differ from heatmap axes")

	groups: dict[tuple[float, ...], list[GridPoint]] = {}
	for point in point_list:
		key = tuple(point.sweep_values[facet] for facet in facets)
		groups.setdefault(key, []).append(point)

	base = build_heatmap_data(point_list, x_variable, y_variable)
	facet_data = {
		key: build_heatmap_data(group, x_variable, y_variable)
		for key, group in sorted(groups.items())
	}
	return FacetedHeatmapData(base=base, facet_variables=facets, facets=facet_data)


def build_parallel_coordinates_data(
	points: Iterable[GridPoint],
	color_variable: str | None = None,
) -> ParallelCoordinatesData:
	"""Build a rectangular matrix for a parallel-coordinates plot."""

	point_list = list(points)
	if not point_list:
		raise ValueError("Cannot build parallel-coordinate data from an empty grid")
	variables = tuple(sorted(point_list[0].sweep_values))
	if color_variable and color_variable not in variables:
		raise ValueError(f"Unknown parallel-coordinate color variable: {color_variable}")
	return ParallelCoordinatesData(
		variables=variables,
		metric_name=_metric_name(point_list),
		values=np.asarray(
			[[point.sweep_values[variable] for variable in variables] for point in point_list],
			dtype=float,
		),
		metric_values=np.asarray([point.metric_result.value for point in point_list], dtype=float),
		run_indices=np.asarray([point.run_indices[0] for point in point_list], dtype=int),
	)


def _required_variable(variable: str | None, field_name: str) -> str:
	if not variable:
		raise ValueError(f"{field_name} is required for this plot")
	return variable


def _metric_name(points: list[GridPoint]) -> str:
	names = {point.metric_result.metric_name for point in points}
	if len(names) != 1:
		raise ValueError(f"Plot data contains multiple metrics: {names}")
	return next(iter(names))