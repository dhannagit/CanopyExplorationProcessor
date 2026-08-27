from pathlib import Path

from canopy_processor import DatasetConfig, FilterConfig, PlotConfig, SweepVariableConfig
from canopy_processor.ui import discover_dataset, load_dataset
from canopy_processor.ui.pipeline import analyze_loaded_dataset


ROOT = Path(__file__).parents[1]
RAW = ROOT / "DATA_Raw" / "MOS_COR_TyrePressureExploration"


def test_analyze_loaded_pressure_dataset_builds_heatmap_data() -> None:
	discovery = discover_dataset(RAW)
	loaded = load_dataset(discovery)
	config = __import__("canopy_processor").AnalysisConfig(
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