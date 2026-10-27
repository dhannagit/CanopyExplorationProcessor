from pathlib import Path

import pytest

from canopy_processor import (
	AnalysisConfig,
	BaselineConfig,
	DatasetConfig,
	ExportConfig,
	FilterConfig,
	PlotConfig,
	SweepVariableConfig,
)


def test_analysis_config_round_trips_as_json(tmp_path: Path) -> None:
	config = AnalysisConfig(
		dataset=DatasetConfig(
			dxpx_directory=Path("data/dxpx"),
			raw_directory=Path("data/raw"),
			track_name="CTMP",
		),
		sweep_variables=[
			SweepVariableConfig(
				path="car.tyres.front.INITIAL_CONDITIONS.InfPress",
				display_name="Front Pressure",
				units="bar",
				role="x",
			)
		],
		metric="gCarPotential",
		filters=FilterConfig(phases=("isApex",), turn_zones=("isTurnZone1",)),
		plot=PlotConfig(plot_type="line"),
	)
	path = tmp_path / "analysis.json"

	config.save(path)
	loaded = AnalysisConfig.load(path)

	assert loaded.to_dict() == AnalysisConfig.load(path).to_dict()
	assert loaded.dataset is not None
	assert isinstance(loaded.dataset.dxpx_directory, Path)
	assert loaded.dataset.dxpx_directory == (tmp_path / "data/dxpx").resolve()
	assert loaded.metric == config.metric
	assert loaded.sweep_variables == config.sweep_variables


def test_external_baseline_draft_does_not_require_a_path() -> None:
	config = AnalysisConfig(baseline=BaselineConfig(mode="external_study", lap_indices=(0, 2)))
	assert AnalysisConfig.from_dict(config.to_dict()) == config


def test_draft_is_saveable_but_not_ready() -> None:
	config = AnalysisConfig()
	config.validate()
	with pytest.raises(ValueError, match="directories"):
		config.validate_ready()


def test_full_recipe_round_trip_preserves_inactive_choices(tmp_path: Path) -> None:
	config = AnalysisConfig(
		name="CTMP draft",
		dataset=DatasetConfig(tmp_path / "dxpx", tmp_path / "raw", track_name="CTMP",
			confirmed_header_track="CTMP", confirmed_workbook_digest="digest"),
		sweep_variables=[SweepVariableConfig("setup.pressure", "Pressure", "bar", "x")],
		metric="grip",
		baseline=BaselineConfig(mode="none", run_index=4, external_path=tmp_path / "baseline.dxpx",
			lap_indices=(0, 3), delta_mode="percent"),
		filters=FilterConfig(("isApex",), ("isTurnZone1",), "and", "or", "or"),
		plot=PlotConfig("suggested", False),
		export=ExportConfig(tmp_path / "figures", ("svg",)),
	)
	path = tmp_path / "recipe.json"
	config.save(path)
	assert AnalysisConfig.load(path) == config


def test_atomic_save_failure_preserves_previous_file(monkeypatch, tmp_path: Path) -> None:
	path = tmp_path / "recipe.json"
	AnalysisConfig(name="original").save(path)
	before = path.read_bytes()
	def fail_replace(*args):
		raise OSError("disk unavailable")
	monkeypatch.setattr("canopy_processor.config.os.replace", fail_replace)
	with pytest.raises(OSError, match="disk unavailable"):
		AnalysisConfig(name="edited").save(path)
	assert path.read_bytes() == before
	assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("update", [
	{"schema_version": 1}, {"metric": ["grip"]}, {"plot": {"annotate": "false"}},
	{"filters": {"phases": "isApex"}}, {"baseline": {"lap_indices": [True]}},
])
def test_malformed_recipe_is_rejected(update: dict) -> None:
	values = AnalysisConfig().to_dict()
	values.update(update)
	with pytest.raises((ValueError, TypeError)):
		AnalysisConfig.from_dict(values)


def test_duplicate_axis_roles_are_drafts_not_ready(tmp_path: Path) -> None:
	config = AnalysisConfig(
		dataset=DatasetConfig(tmp_path, tmp_path), metric="grip",
		sweep_variables=[SweepVariableConfig("first", role="x"), SweepVariableConfig("second", role="x")],
	)
	config.to_dict()
	with pytest.raises(ValueError, match="at most one"):
		config.validate_ready()