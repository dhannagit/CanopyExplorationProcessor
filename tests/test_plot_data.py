import numpy as np
import pytest

from canopy_processor import (
	AnalysisRow,
	GridResult,
	MetricResult,
	PlotConfig,
	SweepVariableConfig,
	build_faceted_heatmap_data,
	build_grid,
	build_heatmap_data,
	build_line_data,
	build_parallel_coordinates_data,
)
from canopy_processor.plot_data import FacetedHeatmapData, build_plot_data, resolve_plot


def _row(index: int, x: float, y: float, value: float, facet: float = 0.0) -> AnalysisRow:
	return AnalysisRow(
		run_index=index,
		sweep_values={"x": x, "y": y, "facet": facet},
		metric_result=MetricResult("grip", value, "mean", 10, 10),
	)


def _grid(*rows: AnalysisRow) -> GridResult:
	return build_grid(rows, variable_paths=("x", "y", "facet"))


def test_build_line_data_sorts_by_x() -> None:
	grid = _grid(_row(0, 2.0, 0.0, 20.0), _row(1, 1.0, 0.0, 10.0))

	result = build_line_data(grid.points, "x")

	np.testing.assert_array_equal(result.x_values, [1.0, 2.0])
	np.testing.assert_array_equal(result.y_values, [10.0, 20.0])


def test_build_heatmap_data_uses_y_rows_and_x_columns() -> None:
	grid = _grid(
		_row(0, 2.0, 10.0, 210.0),
		_row(1, 1.0, 10.0, 110.0),
		_row(2, 1.0, 20.0, 120.0),
	)

	result = build_heatmap_data(grid.points, "x", "y")

	np.testing.assert_array_equal(result.x_values, [1.0, 2.0])
	np.testing.assert_array_equal(result.y_values, [10.0, 20.0])
	np.testing.assert_allclose(result.values, [[110.0, 210.0], [120.0, np.nan]], equal_nan=True)


def test_faceted_heatmap_groups_remaining_dimension() -> None:
	grid = _grid(
		_row(0, 1.0, 10.0, 110.0, facet=1.0),
		_row(1, 1.0, 10.0, 210.0, facet=2.0),
	)

	result = build_faceted_heatmap_data(grid.points, "x", "y", ("facet",))

	assert result.facet_variables == ("facet",)
	assert set(result.facets) == {(1.0,), (2.0,)}
	assert result.facets[(2.0,)].values[0, 0] == 210.0


def test_parallel_coordinates_data_is_rectangular() -> None:
	grid = _grid(_row(0, 1.0, 10.0, 5.0), _row(1, 2.0, 20.0, 6.0))

	result = build_parallel_coordinates_data(grid.points)

	assert result.variables == ("facet", "x", "y")
	assert result.values.shape == (2, 3)
	np.testing.assert_array_equal(result.metric_values, [5.0, 6.0])
	np.testing.assert_array_equal(result.run_indices, [0, 1])


def test_plot_data_requires_axes() -> None:
	grid = _grid(_row(0, 1.0, 10.0, 5.0))

	with pytest.raises(ValueError, match="x_variable"):
		build_line_data(grid.points, None)


def test_suggested_heatmap_preserves_multiple_facet_dimensions() -> None:
	variables = [
		SweepVariableConfig("front_toe", role="facet"),
		SweepVariableConfig("rear_toe", role="facet"),
		SweepVariableConfig("front_camber", role="x"),
		SweepVariableConfig("rear_camber", role="y"),
	]
	rows = [
		AnalysisRow(index, {
			"front_toe": front_toe, "rear_toe": rear_toe,
			"front_camber": -0.05, "rear_camber": -0.06,
		}, MetricResult("grip", float(index), "mean", 10, 10))
		for index, (front_toe, rear_toe) in enumerate(((0.001, -0.003), (0.001, -0.001), (0.003, -0.003), (0.003, -0.001)))
	]
	plot = PlotConfig("suggested")
	resolved = resolve_plot(plot, variables)
	assert resolved.plot_type == "faceted_heatmap"
	assert plot.plot_type == "suggested"
	data = build_plot_data(build_grid(rows), resolved)
	assert isinstance(data, FacetedHeatmapData)
	assert data.facet_variables == ("front_toe", "rear_toe")
	assert set(data.facets) == {(0.001, -0.003), (0.001, -0.001), (0.003, -0.003), (0.003, -0.001)}
	for index, key in enumerate(sorted(data.facets)):
		assert data.facets[key].values[0, 0] == float(index)


@pytest.mark.parametrize("plot_type,roles,expected", [
	("suggested", ("x",), "line"),
	("suggested", ("x", "y"), "heatmap"),
	("suggested", ("x", "y", "facet"), "faceted_heatmap"),
	("heatmap", ("x", "y", "facet"), "heatmap"),
])
def test_plot_resolution_respects_roles_and_explicit_choice(plot_type: str, roles: tuple[str, ...], expected: str) -> None:
	variables = [SweepVariableConfig(f"variable_{index}", role=role) for index, role in enumerate(roles)]
	assert resolve_plot(PlotConfig(plot_type), variables).plot_type == expected