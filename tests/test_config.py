from pathlib import Path

import pytest

from canopy_processor import (
	AnalysisConfig,
	BaselineConfig,
	DatasetConfig,
	FilterConfig,
	PlotConfig,
	SweepVariableConfig,
)


def test_analysis_config_round_trips_as_json(tmp_path: Path) -> None:
	config = AnalysisConfig(
		dataset=DatasetConfig(
			dxpx_directory=Path("data/dxpx"),
			raw_directory=Path("data/raw"),
		),
		sweep_variables=[
			SweepVariableConfig(
				path="car.tyres.front.INITIAL_CONDITIONS.InfPress",
				display_name="Front Pressure",
				units="bar",
				role="x",
			)
		],
		metrics=["gCarPotential"],
		filters=FilterConfig(phases=("isApex",), turn_zones=("isTurnZone1",)),
		plot=PlotConfig(plot_type="line", x_variable="car.tyres.front.INITIAL_CONDITIONS.InfPress"),
	)
	path = tmp_path / "analysis.json"

	config.save(path)
	loaded = AnalysisConfig.load(path)

	assert loaded == config
	assert loaded.dataset is not None
	assert isinstance(loaded.dataset.dxpx_directory, Path)


def test_external_baseline_requires_a_path() -> None:
	with pytest.raises(ValueError, match="external_path"):
		BaselineConfig(mode="external_study")


def test_plot_variable_must_be_selected() -> None:
	config = AnalysisConfig(plot=PlotConfig(x_variable="missing"))

	with pytest.raises(ValueError, match="x_variable"):
		config.validate()