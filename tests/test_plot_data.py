import numpy as np
import pytest

from canopy_processor import (
	AnalysisRow,
	GridResult,
	MetricResult,
	build_faceted_heatmap_data,
	build_grid,
	build_heatmap_data,
	build_line_data,
	build_parallel_coordinates_data,
)


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