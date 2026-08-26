"""Render prepared Canopy plot data with Matplotlib."""

from __future__ import annotations

from typing import Any

import numpy as np
from matplotlib.figure import Figure

from .plot_data import (
	FacetedHeatmapData,
	HeatmapPlotData,
	LinePlotData,
	ParallelCoordinatesData,
)


def render_line(data: LinePlotData, *, scatter: bool = False) -> Figure:
	"""Render one-dimensional line or scatter data and return its Figure."""

	figure = Figure()
	axis = figure.subplots()
	if scatter:
		axis.scatter(data.x_values, data.y_values)
	else:
		axis.plot(data.x_values, data.y_values, marker="o")
	axis.set_xlabel(data.x_variable)
	axis.set_ylabel(data.y_label)
	axis.set_title(data.y_label)
	axis.grid(True, alpha=0.3)
	figure.tight_layout()
	return figure


def render_heatmap(data: HeatmapPlotData) -> Figure:
	"""Render a two-dimensional heatmap and return its Figure."""

	figure = Figure()
	axis = figure.subplots()
	image = axis.imshow(
		data.values,
		origin="lower",
		aspect="auto",
		interpolation="none",
		extent=_heatmap_extent(data),
		cmap="jet",
	)
	axis.set_xticks(data.x_values)
	axis.set_yticks(data.y_values)
	_annotate_heatmap(axis, data)
	axis.set_xlabel(data.x_variable)
	axis.set_ylabel(data.y_variable)
	axis.set_title(data.metric_name)
	figure.colorbar(image, ax=axis, label=data.metric_name)
	figure.tight_layout()
	return figure


def render_faceted_heatmap(data: FacetedHeatmapData) -> Figure:
	"""Render one heatmap per facet combination and return its Figure."""

	if not data.facets:
		raise ValueError("Cannot render an empty set of heatmap facets")
	columns = min(3, len(data.facets))
	rows = int(np.ceil(len(data.facets) / columns))
	figure, axes = _make_subplots(rows, columns)
	axes = np.asarray(axes, dtype=object).reshape(-1)
	for axis, (key, facet) in zip(axes, data.facets.items()):
		image = axis.imshow(
			facet.values,
			origin="lower",
			aspect="auto",
			interpolation="none",
			extent=_heatmap_extent(facet),
			cmap="jet",
		)
		axis.set_xticks(facet.x_values)
		axis.set_yticks(facet.y_values)
		_annotate_heatmap(axis, facet)
		label = " | ".join(f"{name}={value:g}" for name, value in zip(data.facet_variables, key))
		axis.set_title(label)
		axis.set_xlabel(facet.x_variable)
		axis.set_ylabel(facet.y_variable)
		figure.colorbar(image, ax=axis)
	for axis in axes[len(data.facets):]:
		axis.set_visible(False)
	figure.suptitle(data.base.metric_name)
	figure.tight_layout()
	return figure


def render_parallel_coordinates(data: ParallelCoordinatesData) -> Figure:
	"""Render normalized parallel-coordinate lines colored by metric value."""

	figure = Figure()
	axis = figure.subplots()
	if data.values.shape[1] == 0:
		raise ValueError("Parallel-coordinate data has no variables")
	axis_values = np.arange(data.values.shape[1])
	minimum = np.nanmin(data.values, axis=0)
	maximum = np.nanmax(data.values, axis=0)
	spans = np.where(maximum > minimum, maximum - minimum, 1.0)
	normalized = (data.values - minimum) / spans
	for row, metric_value in zip(normalized, data.metric_values):
		axis.plot(axis_values, row, color=_metric_color(metric_value, data.metric_values), alpha=0.75)
	axis.set_xticks(axis_values, data.variables)
	axis.set_ylim(0, 1)
	axis.set_ylabel(data.metric_name)
	axis.set_title("Parallel Coordinates")
	axis.grid(True, axis="y", alpha=0.3)
	figure.tight_layout()
	return figure


def render_plot_data(data: Any, *, scatter: bool = False) -> Figure:
	"""Dispatch to the renderer matching a plot-data dataclass."""

	if isinstance(data, LinePlotData):
		return render_line(data, scatter=scatter)
	if isinstance(data, HeatmapPlotData):
		return render_heatmap(data)
	if isinstance(data, FacetedHeatmapData):
		return render_faceted_heatmap(data)
	if isinstance(data, ParallelCoordinatesData):
		return render_parallel_coordinates(data)
	raise TypeError(f"Unsupported plot-data type: {type(data).__name__}")


def _heatmap_extent(data: HeatmapPlotData) -> tuple[float, float, float, float]:
	"""Give imshow cells bounds halfway between adjacent sweep levels."""

	x_min, x_max = _cell_edges(data.x_values)
	y_min, y_max = _cell_edges(data.y_values)
	return (
		x_min,
		x_max,
		y_min,
		y_max,
	)


def _cell_edges(values: np.ndarray) -> tuple[float, float]:
	"""Return outer cell edges for sorted coordinate centers."""

	if len(values) == 1:
		padding = 0.5 if values[0] == 0 else abs(float(values[0])) * 0.05
		return float(values[0] - padding), float(values[0] + padding)
	step = np.diff(values)
	return float(values[0] - step[0] / 2), float(values[-1] + step[-1] / 2)


def _annotate_heatmap(axis: Any, data: HeatmapPlotData) -> None:
	"""Place each available cell value at its sweep-coordinate center."""

	for row_index, y_value in enumerate(data.y_values):
		for column_index, x_value in enumerate(data.x_values):
			value = data.values[row_index, column_index]
			if not np.isnan(value):
				axis.text(
					x_value,
					y_value,
					f"{value:.2f}",
					ha="center",
					va="center",
					color="white",
				)


def _make_subplots(rows: int, columns: int) -> tuple[Figure, Any]:
	"""Create a Figure and its axes without using pyplot global state."""

	figure = Figure()
	return figure, figure.subplots(rows, columns, squeeze=False)


def _metric_color(value: float, values: np.ndarray) -> tuple[float, float, float, float]:
	"""Map a metric value to a simple normalized blue-to-red color."""

	minimum = np.nanmin(values)
	maximum = np.nanmax(values)
	position = 0.5 if maximum == minimum else (value - minimum) / (maximum - minimum)
	return (float(position), 0.2, float(1.0 - position), 1.0)