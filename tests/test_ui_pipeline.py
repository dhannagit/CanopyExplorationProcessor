from pathlib import Path

import pytest
import numpy as np

from canopy_processor import (
	AnalysisConfig,
	BaselineConfig,
	DatasetConfig,
	FilterConfig,
	PlotConfig,
	SweepVariableConfig,
	SweepVariable,
)
from canopy_processor.dxpx import DXPXRun
from canopy_processor.metric import source_metric
from canopy_processor.ui import discover_dataset, load_dataset
from canopy_processor.ui.pipeline import LoadedDataset, analyze_loaded_dataset, prepare_turn_zones


ROOT = Path(__file__).parents[1]
RAW = ROOT / "DATA_Raw" / "MOS_COR_TyrePressureExploration"
EXTERNAL_BASELINE = next((ROOT / "BaselineExample").rglob("*.dXpx"), None)
requires_samples = pytest.mark.skipif(
	not (ROOT / "DATA_dXpx").is_dir() or EXTERNAL_BASELINE is None,
	reason="Local study and baseline sample data are not installed",
)


@requires_samples
def test_analyze_loaded_pressure_dataset_builds_heatmap_data() -> None:
	discovery = discover_dataset(RAW)
	loaded = load_dataset(discovery)
	config = AnalysisConfig(
		dataset=DatasetConfig(loaded.runs[0].path.parents[1], RAW, discovery.circuit_workbook),
		sweep_variables=[
			SweepVariableConfig(discovery.variables[0].path, units="bar", role="x"),
			SweepVariableConfig(discovery.variables[1].path, units="bar", role="y"),
		],
		metric="gCarPotential",
		plot=PlotConfig(plot_type="heatmap"),
		filters=FilterConfig(),
	)

	output = analyze_loaded_dataset(loaded, config, discovery.variables)

	assert len(output.rows) == 25
	assert output.plot_data.values.shape == (5, 5)


@requires_samples
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
		metric="gCarPotential",
		plot=PlotConfig(plot_type="heatmap"),
		baseline=BaselineConfig(mode="loaded_run", run_index=baseline_index, delta_mode="absolute"),
	)

	output = analyze_loaded_dataset(loaded, config, discovery.variables)

	assert len(output.compared_rows) == len(output.rows) == 25
	assert output.compared_rows[0].baseline.value == output.rows[0].metric_result.value


@requires_samples
def test_analyze_loaded_dataset_compares_against_external_laps() -> None:
	discovery = discover_dataset(RAW)
	loaded = load_dataset(discovery)
	config = AnalysisConfig(
		dataset=DatasetConfig(loaded.runs[0].path.parents[1], RAW, discovery.circuit_workbook),
		sweep_variables=[
			SweepVariableConfig(discovery.variables[0].path, role="x"),
			SweepVariableConfig(discovery.variables[1].path, role="y"),
		],
		metric="gCarPotential",
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


@requires_samples
def test_external_baseline_turn_zones_require_confirmed_track() -> None:
	discovery = discover_dataset(RAW, ROOT / "CircuitsData_Canopy_Hypercar.xlsx")
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
		metric="gCarPotential",
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


def test_synthetic_recipe_analyzes_roles_and_filters_without_mutating_intent(tmp_path: Path) -> None:
	runs = tuple(DXPXRun(tmp_path / str(index) / "run.dxpx", {"TrackName": "CTMP"}, {
		"sLap": np.array([0., 1., 2.]), "grip": np.array([1., 2. + index, 3.]),
		"isApex": np.array([0, 1, 0]),
	}) for index in range(2))
	loaded = LoadedDataset(runs, {"grip": source_metric("grip", "Grip", "grip", "g")}, ())
	config = AnalysisConfig(
		dataset=DatasetConfig(tmp_path, tmp_path), metric="grip",
		sweep_variables=[SweepVariableConfig("pressure", "Pressure", "bar", "x")],
		filters=FilterConfig(phases=("isApex",)),
	)
	output = analyze_loaded_dataset(loaded, config, (SweepVariable("pressure", "bar", (1., 2.)),))
	assert config.plot.plot_type == "suggested"
	assert [row.metric_result.value for row in output.rows] == [2., 3.]
	assert [row.metric_result.selected_samples for row in output.rows] == [1, 1]
	assert output.plot_data.x_variable == "pressure"


def test_baseline_with_different_header_cannot_reuse_sweep_confirmation(monkeypatch, tmp_path: Path) -> None:
	run = DXPXRun(tmp_path / "0" / "run.dxpx", {"TrackName": "CTMP"}, {
		"sLap": np.array([0., 1.]), "grip": np.array([1., 2.]), "isTurnZone1": np.array([1, 0]),
	})
	baseline = DXPXRun(tmp_path / "baseline.dxpx", {"TrackName": "Watkins-Glen"}, {
		"sLap": np.array([0., 1.]), "grip": np.array([1., 2.]),
	})
	loaded = LoadedDataset((run,), {"grip": source_metric("grip", "Grip", "grip", "g")}, ())
	config = AnalysisConfig(
		dataset=DatasetConfig(tmp_path, tmp_path, tmp_path / "circuits.xlsx", "CTMP", "CTMP"),
		metric="grip", sweep_variables=[SweepVariableConfig("pressure", role="x")],
		filters=FilterConfig(turn_zones=("isTurnZone1",)),
		baseline=BaselineConfig(mode="external_study", external_path=baseline.path),
	)
	monkeypatch.setattr("canopy_processor.ui.pipeline.resolve_baseline_laps", lambda *args, **kwargs: [baseline])
	with pytest.raises(ValueError, match="Baseline track does not match"):
		analyze_loaded_dataset(loaded, config, (SweepVariable("pressure", "bar", (1.,)),))