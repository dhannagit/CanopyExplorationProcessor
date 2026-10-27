from pathlib import Path
from xml.etree import ElementTree

import pytest
from matplotlib.figure import Figure
from PIL import Image

from canopy_processor import (
	AnalysisConfig,
	AnalysisRow,
	ExportConfig,
	MetricResult,
	PlotConfig,
	SweepVariableConfig,
	export_analysis,
)


def _row() -> AnalysisRow:
	return AnalysisRow(
		run_index=0,
		sweep_values={"pressure": 1.8},
		metric_result=MetricResult("grip", 1.65, "mean", 10, 20),
	)


def _config(output_directory: Path) -> AnalysisConfig:
	return AnalysisConfig(
		sweep_variables=[SweepVariableConfig(path="pressure", role="x")],
		plot=PlotConfig(plot_type="line"),
		export=ExportConfig(
		output_directory=output_directory,
		formats=("svg", "png"),
		),
	)


def test_export_analysis_writes_configured_outputs(tmp_path: Path) -> None:
	figure = Figure()
	axis = figure.subplots()
	axis.plot([1.8], [1.65])
	config = _config(tmp_path / "exports")

	paths = export_analysis(figure, config, filename="grip")

	assert {path.suffix for path in paths} == {".svg", ".png"}
	assert all(path.is_file() for path in paths)


def test_export_analysis_requires_output_directory(tmp_path: Path) -> None:
	config = _config(tmp_path)
	config.export.output_directory = None

	try:
		export_analysis(Figure(), config)
	except ValueError as error:
		assert "output_directory" in str(error)
	else:
		raise AssertionError("Expected output directory validation error")


@pytest.mark.parametrize("aspect", ["1:1", "5:4", "4:3", "3:2", "16:10", "16:9"])
def test_exports_have_selected_aspect_without_resizing_original(tmp_path: Path, aspect: str) -> None:
	figure = Figure(figsize=(4, 3))
	axis = figure.subplots()
	axis.plot([1, 2], [3, 4])
	axis.set_xlabel("Pressure [bar]")
	original_canvas = figure.canvas
	original_size = tuple(figure.get_size_inches())
	original_bounds = axis.get_position().bounds
	config = _config(tmp_path)
	config.export.aspect_ratio = aspect
	paths = export_analysis(figure, config, filename="aspect")
	width_part, height_part = (int(value) for value in aspect.split(":"))
	expected = width_part / height_part
	with Image.open(next(path for path in paths if path.suffix == ".png")) as image:
		assert image.width / image.height == pytest.approx(expected, abs=1 / image.height)
		assert image.width <= original_size[0] * 300 + 1
		assert image.height <= original_size[1] * 300 + 1
	root = ElementTree.parse(next(path for path in paths if path.suffix == ".svg")).getroot()
	view_box = [float(value) for value in root.attrib["viewBox"].split()]
	assert view_box[2] / view_box[3] == pytest.approx(expected)
	assert tuple(figure.get_size_inches()) == original_size
	assert figure.canvas is original_canvas
	assert axis.get_position().bounds == original_bounds


def test_fixed_aspect_exports_grow_with_displayed_figure(tmp_path: Path) -> None:
	figure = Figure(figsize=(4, 3))
	figure.subplots().plot([1, 2], [1, 2])
	config = _config(tmp_path)
	config.export.aspect_ratio = "16:9"
	config.export.formats = ("png",)
	first = export_analysis(figure, config, filename="small")[0]
	figure.set_size_inches(8, 6)
	second = export_analysis(figure, config, filename="large")[0]
	with Image.open(first) as small, Image.open(second) as large:
		assert large.width == small.width * 2
		assert large.height == small.height * 2