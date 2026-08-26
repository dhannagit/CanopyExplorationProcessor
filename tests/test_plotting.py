import matplotlib

matplotlib.use("Agg")

import numpy as np

from canopy_processor import (
	AnalysisRow,
	GridResult,
	MetricResult,
	build_faceted_heatmap_data,
	build_grid,
	build_heatmap_data,
	build_line_data,
	build_parallel_coordinates_data,
	render_faceted_heatmap,
	render_heatmap,
	render_line,
	render_parallel_coordinates,
	render_plot_data,
)


def _row(index: int, x: float, y: float, value: float, facet: float = 0.0) -> AnalysisRow:
	return AnalysisRow(
		run_index=index,
		sweep_values={"x": x, "y": y, "facet": facet},
		metric_result=MetricResult("grip", value, "mean", 10, 10),
	)


def _grid() -> GridResult:
	return build_grid(
		[_row(0, 1.0, 10.0, 1.0), _row(1, 2.0, 10.0, 2.0)],
		variable_paths=("x", "y", "facet"),
	)


def test_render_line_returns_labeled_figure() -> None:
	data = build_line_data(_grid().points, "x")

	figure = render_line(data)

	assert figure.axes[0].get_xlabel() == "x"
	assert figure.axes[0].get_ylabel() == "grip"


def test_render_heatmap_returns_colorbar_axis() -> None:
	data = build_heatmap_data(_grid().points, "x", "y")

	figure = render_heatmap(data)

	assert figure.axes[0].get_xlabel() == "x"
	assert figure.axes[0].get_ylabel() == "y"
	assert tuple(figure.axes[0].get_xticks()) == (1.0, 2.0)
	assert tuple(figure.axes[0].get_yticks()) == (10.0,)
	assert figure.axes[0].images[0].cmap.name == "jet"
	assert len(figure.axes[0].texts) == 2
	assert len(figure.axes) == 2


def test_render_faceted_heatmap_creates_one_data_axis_per_facet() -> None:
	points = [_row(0, 1.0, 10.0, 1.0, 1.0), _row(1, 1.0, 10.0, 2.0, 2.0)]
	data = build_faceted_heatmap_data(build_grid(points).points, "x", "y", ("facet",))

	figure = render_faceted_heatmap(data)

	assert sum(axis.get_visible() for axis in figure.axes) >= 2


def test_render_parallel_coordinates_returns_figure() -> None:
	data = build_parallel_coordinates_data(_grid().points)

	figure = render_parallel_coordinates(data)

	assert figure.axes[0].get_title() == "Parallel Coordinates"
	assert len(figure.axes[0].lines) == 2


def test_render_plot_data_dispatches_by_type() -> None:
	data = build_line_data(_grid().points, "x")

	figure = render_plot_data(data, scatter=True)

	assert len(figure.axes[0].collections) == 1