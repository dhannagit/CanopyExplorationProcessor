from pathlib import Path

from matplotlib.figure import Figure

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
		plot=PlotConfig(plot_type="line", x_variable="pressure"),
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