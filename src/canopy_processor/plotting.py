"""Render prepared exploration plot data with Matplotlib."""

from __future__ import annotations

from typing import Any
from textwrap import fill

import numpy as np
from matplotlib.figure import Figure
from matplotlib.layout_engine import TightLayoutEngine
from matplotlib.ticker import FuncFormatter

from .config import FilterConfig

from .plot_data import (
	FacetedHeatmapData,
	HeatmapPlotData,
	LinePlotData,
	ParallelCoordinatesData,
)


def _full_precision_tick(value: float, position: int | None = None) -> str:
	return str(int(value)) if float(value).is_integer() else str(float(value))


class ReadablePlotLayout(TightLayoutEngine):
	"""Reflow tick labels and titles for each interactive or exported draw."""

	def __init__(self) -> None:
		super().__init__()
		self._title_sources = {}

	def execute(self, figure: Figure) -> None:
		renderer = figure._get_renderer()
		for _ in range(2):
			for axis in figure.axes:
				if axis.get_visible():
					self._fit_ticks(axis, renderer)
					self._wrap_title(axis.title, axis.bbox.width, renderer)
			if figure._suptitle is not None:
				self._wrap_title(figure._suptitle, figure.bbox.width * 0.94, renderer)
			super().execute(figure)

	@staticmethod
	def _overlap(labels: list, renderer: Any) -> bool:
		boxes = [label.get_window_extent(renderer) for label in labels if label.get_visible()]
		return any(first.overlaps(second) for index, first in enumerate(boxes) for second in boxes[index + 1:])

	def _fit_ticks(self, axis: Any, renderer: Any) -> None:
		for tick in axis.xaxis.get_major_ticks():
			tick.label1.set_visible(True)
		axis.get_xticklabels()
		lower, upper = sorted(axis.get_xlim())
		labels = [
			tick.label1 for tick in axis.xaxis.get_major_ticks()
			if lower <= tick.get_loc() <= upper and tick.label1.get_text()
		]
		if not labels:
			return
		chosen_angle = 0
		for angle in (0, 45, 90):
			for label in labels:
				label.set_rotation(angle)
				label.set_horizontalalignment("right" if angle == 45 else "center")
				label.set_rotation_mode("anchor")
			if angle and max(label.get_window_extent(renderer).height for label in labels) > max(40, axis.bbox.height * 0.75):
				continue
			chosen_angle = angle
			if not self._overlap(labels, renderer):
				return
		for label in labels:
			label.set_rotation(chosen_angle)
			label.set_horizontalalignment("right" if chosen_angle == 45 else "center")
		for stride in range(2, len(labels) + 1):
			for index, label in enumerate(labels):
				label.set_visible(index % stride == 0)
			if not self._overlap(labels, renderer):
				break

	def _wrap_title(self, title: Any, width: float, renderer: Any) -> None:
		current = title.get_text()
		source, previous = self._title_sources.get(title, (current, current))
		if current != previous:
			source = current
		character_width = renderer.get_text_width_height_descent("M", title.get_fontproperties(), False)[0]
		columns = max(8, int(width / max(1, character_width)))
		wrapped = "\n".join(fill(line, width=columns) for line in source.split("\n"))
		title.set_text(wrapped)
		self._title_sources[title] = (source, wrapped)


def _finish_layout(figure: Figure) -> None:
	if not isinstance(figure.get_layout_engine(), ReadablePlotLayout):
		figure.set_layout_engine(ReadablePlotLayout())


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
	axis.xaxis.set_major_formatter(FuncFormatter(_full_precision_tick))
	axis.grid(True, alpha=0.3)
	_finish_layout(figure)
	return figure


def render_heatmap(data: HeatmapPlotData, *, annotate: bool = True) -> Figure:
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
	axis.xaxis.set_major_formatter(FuncFormatter(_full_precision_tick))
	axis.yaxis.set_major_formatter(FuncFormatter(_full_precision_tick))
	if annotate:
		_annotate_heatmap(axis, data)
	axis.set_xlabel(data.x_variable)
	axis.set_ylabel(data.y_variable)
	axis.set_title(data.metric_name)
	figure.colorbar(image, ax=axis, label=data.metric_name)
	_finish_layout(figure)
	return figure


def render_faceted_heatmap(data: FacetedHeatmapData, *, annotate: bool = True) -> Figure:
	"""Render one heatmap per facet combination and return its Figure."""

	if not data.facets:
		raise ValueError("Cannot render an empty set of heatmap facets")
	columns = min(3, int(np.ceil(np.sqrt(len(data.facets)))))
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
		axis.xaxis.set_major_formatter(FuncFormatter(_full_precision_tick))
		axis.yaxis.set_major_formatter(FuncFormatter(_full_precision_tick))
		if annotate:
			_annotate_heatmap(axis, facet)
		label = " | ".join(f"{name}={_full_precision_tick(value)}" for name, value in zip(data.facet_variables, key))
		axis.set_title(label)
		axis.set_xlabel(facet.x_variable)
		axis.set_ylabel(facet.y_variable)
		figure.colorbar(image, ax=axis)
	for axis in axes[len(data.facets):]:
		axis.set_visible(False)
	figure.suptitle(data.base.metric_name)
	_finish_layout(figure)
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
	_finish_layout(figure)
	return figure


def render_plot_data(
	data: Any, *, scatter: bool = False, annotate: bool = True,
	labels: dict[str, str] | None = None,
	filters: FilterConfig | None = None,
) -> Figure:
	"""Dispatch to the renderer matching a plot-data dataclass."""

	if isinstance(data, LinePlotData):
		figure = render_line(data, scatter=scatter)
	elif isinstance(data, HeatmapPlotData):
		figure = render_heatmap(data, annotate=annotate)
	elif isinstance(data, FacetedHeatmapData):
		figure = render_faceted_heatmap(data, annotate=annotate)
	elif isinstance(data, ParallelCoordinatesData):
		figure = render_parallel_coordinates(data)
	else:
		raise TypeError(f"Unsupported plot-data type: {type(data).__name__}")
	if labels:
		for axis in figure.axes:
			axis.set_xlabel(labels.get(axis.get_xlabel(), axis.get_xlabel()))
			axis.set_ylabel(labels.get(axis.get_ylabel(), axis.get_ylabel()))
			if isinstance(data, ParallelCoordinatesData):
				axis.set_xticks(axis.get_xticks(), [labels.get(name, name) for name in data.variables])
			if isinstance(data, FacetedHeatmapData):
				title = axis.get_title()
				for path in sorted(labels, key=len, reverse=True):
					title = title.replace(f"{path}=", f"{labels[path]}=")
				axis.set_title(title)
	if filters and (filters.phases or filters.turn_zones):
		parts = []
		if filters.phases:
			parts.append("Phases: (" + f" {filters.phase_operator.upper()} ".join(filters.phases) + ")")
		if filters.turn_zones:
			parts.append("Turn zones: (" + f" {filters.turn_zone_operator.upper()} ".join(filters.turn_zones) + ")")
		summary = f" {filters.category_operator.upper()} ".join(parts)
		if figure._suptitle is not None:
			title = figure._suptitle.get_text()
		else:
			title = figure.axes[0].get_title()
			figure.axes[0].set_title("")
		figure.suptitle(f"{title}\nFilters: {summary}")
	_finish_layout(figure)
	return figure


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