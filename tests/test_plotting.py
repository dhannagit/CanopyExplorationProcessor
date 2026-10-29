import matplotlib

matplotlib.use("Agg")

import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg

from canopy_processor import (
	AnalysisRow,
	GridResult,
	MetricResult,
	FilterConfig,
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
	assert figure.axes[0].get_title() == "grip"
	assert figure._suptitle is None


def test_render_options_hide_annotations_and_use_labels() -> None:
	data = build_heatmap_data(_grid().points, "x", "y")
	figure = render_plot_data(data, annotate=False, labels={"x": "Pressure [bar]"})
	assert not figure.axes[0].texts
	assert figure.axes[0].get_xlabel() == "Pressure [bar]"
	assert data.x_variable == "x"
	facets = build_faceted_heatmap_data(_grid().points, "x", "y", ("facet",))
	figure = render_plot_data(facets, annotate=False)
	assert all(not axis.texts for axis in figure.axes)


def test_long_numeric_ticks_do_not_overlap_or_lose_precision() -> None:
	values = [-0.05235987755982989, -0.04363323129985824, -0.03490658503988659, -0.026179938779914945]
	rows = [_row(index, value, 10., float(index)) for index, value in enumerate(values)]
	data = build_heatmap_data(build_grid(rows).points, "x", "y")
	figure = render_heatmap(data)
	canvas = FigureCanvasAgg(figure)
	canvas.draw()
	labels = [label for label in figure.axes[0].get_xticklabels() if label.get_visible()]
	assert {label.get_text() for label in labels} == {str(value) for value in values}
	boxes = [label.get_window_extent(canvas.get_renderer()) for label in labels]
	assert all(not first.overlaps(second) for index, first in enumerate(boxes) for second in boxes[index + 1:])


@pytest.mark.parametrize("kind", ["line", "scatter", "heatmap", "faceted", "parallel"])
def test_tick_layout_stays_readable_when_resized(kind: str) -> None:
	values = [-0.05235987755982989, -0.04363323129985824, -0.03490658503988659, -0.026179938779914945]
	rows = [
		_row(index, value, -0.061086523819801536, float(index), facet=facet)
		for index, (facet, value) in enumerate((facet, value) for facet in (1., 2., 3., 4.) for value in values)
	]
	grid = build_grid(rows)
	if kind in {"line", "scatter"}:
		data = build_line_data(grid.points, "x")
	elif kind == "heatmap":
		data = build_heatmap_data(grid.points, "x", "y")
	elif kind == "faceted":
		data = build_faceted_heatmap_data(grid.points, "x", "y", ("facet",))
	else:
		data = build_parallel_coordinates_data(grid.points)
	figure = render_plot_data(data, scatter=kind == "scatter", labels={
		"x": "Front camber setup [rad]", "y": "Rear camber setup [rad]", "facet": "Front toe setup [m]",
	})
	canvas = FigureCanvasAgg(figure)
	for width, height in ((12, 8), (9, 7), (15, 8)):
		figure.set_size_inches(width, height)
		canvas.draw()
		for axis in figure.axes:
			if not axis.get_visible():
				continue
			labels = [label for label in axis.get_xticklabels() if label.get_visible()]
			boxes = [label.get_window_extent(canvas.get_renderer()) for label in labels]
			assert all(not first.overlaps(second) for index, first in enumerate(boxes) for second in boxes[index + 1:])


@pytest.mark.parametrize("kind", ["line", "scatter", "heatmap", "faceted", "parallel"])
def test_filter_title_preserves_masks_and_boolean_logic(kind: str) -> None:
	grid = _grid()
	if kind in {"line", "scatter"}:
		data = build_line_data(grid.points, "x")
	elif kind == "heatmap":
		data = build_heatmap_data(grid.points, "x", "y")
	elif kind == "faceted":
		data = build_faceted_heatmap_data(grid.points, "x", "y", ("facet",))
	else:
		data = build_parallel_coordinates_data(grid.points)
	filters = FilterConfig(
		phases=("isEntry", "isApex"), turn_zones=("isTurnZone1", "isTurnZone2"),
		phase_operator="or", turn_zone_operator="and", category_operator="or",
	)
	figure = render_plot_data(data, scatter=kind == "scatter", filters=filters)
	figure.set_size_inches(12, 8)
	FigureCanvasAgg(figure).draw()
	title = figure._suptitle.get_text().replace("\n", " ")
	assert "Filters: Phases: (isEntry OR isApex) OR Turn zones: (isTurnZone1 AND isTurnZone2)" in title
	assert "grip" in title or "Parallel Coordinates" in title
	if kind == "faceted":
		assert "facet=0" in figure.axes[0].get_title()


@pytest.mark.parametrize("filters,expected", [
	(FilterConfig(phases=("isApex",)), "Phases: (isApex)"),
	(FilterConfig(turn_zones=("isTurnZone3",)), "Turn zones: (isTurnZone3)"),
])
def test_single_filter_category_does_not_imply_other_restrictions(filters: FilterConfig, expected: str) -> None:
	figure = render_plot_data(build_line_data(_grid().points, "x"), filters=filters)
	assert figure._suptitle.get_text() == f"grip\nFilters: {expected}"