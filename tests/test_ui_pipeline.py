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
from canopy_processor.ui import discover_dataset, load_dataset
from canopy_processor.ui.pipeline import analyze_loaded_dataset, prepare_turn_zones


ROOT = Path(__file__).parents[1]
RAW = ROOT / "DATA_Raw" / "MOS_COR_TyrePressureExploration"
EXTERNAL_BASELINE = next((ROOT / "BaselineExample").rglob("*.dXpx"))


def test_analyze_loaded_pressure_dataset_builds_heatmap_data() -> None:
	discovery = discover_dataset(RAW)
	loaded = load_dataset(discovery)
	config = AnalysisConfig(
		dataset=DatasetConfig(loaded.runs[0].path.parents[1], RAW, discovery.circuit_workbook),
		sweep_variables=[
			SweepVariableConfig(discovery.variables[0].path, units="bar", role="x"),
			SweepVariableConfig(discovery.variables[1].path, units="bar", role="y"),
		],
		metrics=["gCarPotential"],
		plot=PlotConfig(plot_type="heatmap"),
		filters=FilterConfig(),
	)

	output = analyze_loaded_dataset(loaded, config, discovery.variables)

	assert len(output.rows) == 25
	assert output.plot_data.values.shape == (5, 5)


def test_analyze_loaded_dataset_compares_against_loaded_run() -> None:
	discovery = discover_dataset(RAW)
	loaded = load_dataset(discovery)
	baseline_index = int(loaded.runs[0].path.parent.name)
	config = AnalysisConfig(
		dataset=DatasetConfig(loaded.runs[0].path.parents[1], RAW, discovery.circuit_workbook),
		sweep_variables=[
			SweepVariableConfig(discovery.variables[0].path, role="x"),
			SweepVariableConfig(discovery.variables[1].path, role="y"),
		],
		metrics=["gCarPotential"],
		plot=PlotConfig(plot_type="heatmap"),
		baseline=BaselineConfig(mode="loaded_run", run_index=baseline_index, delta_mode="absolute"),
	)

	output = analyze_loaded_dataset(loaded, config, discovery.variables)

	assert len(output.compared_rows) == len(output.rows) == 25
	assert output.compared_rows[0].baseline.value == output.rows[0].metric_result.value


def test_analyze_loaded_dataset_compares_against_external_laps() -> None:
	discovery = discover_dataset(RAW)
	loaded = load_dataset(discovery)
	config = AnalysisConfig(
		dataset=DatasetConfig(loaded.runs[0].path.parents[1], RAW, discovery.circuit_workbook),
		sweep_variables=[
			SweepVariableConfig(discovery.variables[0].path, role="x"),
			SweepVariableConfig(discovery.variables[1].path, role="y"),
		],
		metrics=["gCarPotential"],
		plot=PlotConfig(plot_type="heatmap"),
		baseline=BaselineConfig(
			mode="external_study",
			external_path=EXTERNAL_BASELINE,
			lap_indices=(0, 2),
			delta_mode="percent",
		),
	)

	output = analyze_loaded_dataset(loaded, config, discovery.variables)

	assert len(output.compared_rows) == 25
	assert output.compared_rows[0].baseline.lap_count == 2
	assert output.compared_rows[0].delta_mode == "percent"


def test_external_baseline_turn_zones_require_confirmed_track() -> None:
	discovery = discover_dataset(RAW)
	loaded = prepare_turn_zones(load_dataset(discovery), discovery.circuit_workbook, "CTMP")
	config = AnalysisConfig(
		dataset=DatasetConfig(
			loaded.runs[0].path.parents[1],
			RAW,
			discovery.circuit_workbook,
		),
		sweep_variables=[
			SweepVariableConfig(discovery.variables[0].path, role="x"),
			SweepVariableConfig(discovery.variables[1].path, role="y"),
		],
		metrics=["gCarPotential"],
		filters=FilterConfig(turn_zones=("isTurnZone1",)),
		baseline=BaselineConfig(
			mode="external_study",
			external_path=EXTERNAL_BASELINE,
			lap_indices=(0,),
			delta_mode="absolute",
		),
		plot=PlotConfig(plot_type="heatmap"),
	)

	with pytest.raises(ValueError, match="Confirm a circuit"):
		analyze_loaded_dataset(loaded, config, discovery.variables)