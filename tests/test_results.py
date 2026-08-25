from pathlib import Path

import numpy as np
import pytest

from canopy_processor import (
	BaselineConfig,
	BaselineResult,
	JobRecord,
	MetricResult,
	SweepVariable,
	analyze_baseline,
	build_grid,
	compare_rows_to_baseline,
	compute_delta,
	default_metrics,
	find_missing_runs,
	join_sweep_variables,
	load_dxpx,
	load_dxpx_laps,
	resolve_baseline_laps,
	run_index,
)
from canopy_processor.dxpx import DXPXRun
from canopy_processor.results import AnalysisRow


REPOSITORY_ROOT = Path(__file__).parents[1]
SAMPLE_DXPX = next((REPOSITORY_ROOT / "DATA_dXpx").rglob("*.dXpx"))
BASELINE_DXPX = next((REPOSITORY_ROOT / "BaselineExample").rglob("*.dXpx"))


def _fake_run(folder_index: int) -> DXPXRun:
	path = Path(f"/dataset/{folder_index}/example.dXpx")
	return DXPXRun(path=path, header={}, data={})


def test_run_index_reads_the_numbered_parent_folder() -> None:
	assert run_index(_fake_run(3)) == 3


def test_run_index_rejects_non_numbered_folders() -> None:
	run = DXPXRun(path=Path("/dataset/not-a-number/example.dXpx"), header={}, data={})

	with pytest.raises(ValueError, match="numbered"):
		run_index(run)


def test_join_sweep_variables_looks_up_by_run_index() -> None:
	runs = [_fake_run(0), _fake_run(2)]
	results = [
		MetricResult("gCarPotential", 1.1, "mean", 10, 10),
		MetricResult("gCarPotential", 2.2, "mean", 10, 10),
	]
	variables = [
		SweepVariable(path="front.pressure", units="bar", values=(1.8, 1.85, 1.9)),
		SweepVariable(path="rear.pressure", units="bar", values=(1.8, 1.8, 1.8)),
	]

	rows = join_sweep_variables(runs, results, variables)

	assert [row.run_index for row in rows] == [0, 2]
	assert rows[0].sweep_values == {"front.pressure": 1.8, "rear.pressure": 1.8}
	assert rows[1].sweep_values == {"front.pressure": 1.9, "rear.pressure": 1.8}
	assert rows[1].metric_result.value == pytest.approx(2.2)


def test_join_sweep_variables_requires_matching_lengths() -> None:
	with pytest.raises(ValueError, match="same length"):
		join_sweep_variables([_fake_run(0)], [], [])


def test_analyze_baseline_pools_multiple_laps() -> None:
	laps = load_dxpx_laps(BASELINE_DXPX)[:2]
	metric = default_metrics()["gCarPotential"]

	result = analyze_baseline(laps, metric)

	expected_samples = sum(np.asarray(metric.evaluate(lap)).size for lap in laps)
	assert result.lap_count == 2
	assert result.selected_samples == expected_samples


def test_analyze_baseline_accepts_a_single_run() -> None:
	run = load_dxpx(SAMPLE_DXPX)
	metric = default_metrics()["gCarPotential"]

	result = analyze_baseline(run, metric)

	assert result.lap_count == 1
	assert result.value == pytest.approx(np.nanmean(metric.evaluate(run)))


def test_compute_delta_absolute_and_percent() -> None:
	assert compute_delta(11.0, 10.0, "absolute") == (pytest.approx(1.0), True)
	assert compute_delta(11.0, 10.0, "percent") == (pytest.approx(10.0), True)


def test_compute_delta_handles_zero_and_nan_baseline() -> None:
	delta, valid = compute_delta(1.0, 0.0, "percent")
	assert valid is False
	assert np.isnan(delta)

	delta, valid = compute_delta(1.0, float("nan"), "absolute")
	assert valid is False
	assert np.isnan(delta)


def test_compare_rows_to_baseline() -> None:
	rows = [
		AnalysisRow(0, {"pressure": 1.8}, MetricResult("gCarPotential", 1.1, "mean", 10, 10)),
		AnalysisRow(1, {"pressure": 1.9}, MetricResult("gCarPotential", 1.21, "mean", 10, 10)),
	]
	baseline = BaselineResult(value=1.0, method="mean", lap_count=1, selected_samples=10)

	compared = compare_rows_to_baseline(rows, baseline, delta_mode="percent")

	assert [round(c.delta, 2) for c in compared] == [10.0, 21.0]
	assert all(c.baseline_valid for c in compared)


def test_resolve_baseline_laps_for_loaded_run() -> None:
	run = _fake_run(3)
	config = BaselineConfig(mode="loaded_run", run_index=3, delta_mode="absolute")

	resolved = resolve_baseline_laps(config, sweep_runs=[run])

	assert resolved == [run]


def test_resolve_baseline_laps_for_external_study_selects_lap_indices() -> None:
	config = BaselineConfig(
		mode="external_study",
		external_path=BASELINE_DXPX,
		lap_indices=(0, 2),
		delta_mode="absolute",
	)

	resolved = resolve_baseline_laps(config)

	assert len(resolved) == 2


def test_resolve_baseline_laps_requires_lap_indices_for_multi_lap_file() -> None:
	config = BaselineConfig(mode="external_study", external_path=BASELINE_DXPX, delta_mode="absolute")

	with pytest.raises(ValueError, match="lap_indices"):
		resolve_baseline_laps(config)


def _fake_job_record(index: int, is_post_processor: bool = False) -> JobRecord:
	return JobRecord(
		index=index,
		name=f"Factorial {index}",
		state="successful",
		is_post_processor=is_post_processor,
		changes=(),
		error_messages=(),
	)


def _fake_row(folder_index: int, value: float, pressure: float) -> AnalysisRow:
	return AnalysisRow(
		run_index=folder_index,
		sweep_values={"pressure": pressure},
		metric_result=MetricResult("gCarPotential", value, "mean", 10, 10),
	)


def test_find_missing_runs_reports_jobs_with_no_row() -> None:
	job_records = [_fake_job_record(0), _fake_job_record(1), _fake_job_record(2, is_post_processor=True)]
	rows = [_fake_row(0, 1.0, 1.8)]

	assert find_missing_runs(job_records, rows) == (1,)


def test_build_grid_aggregates_duplicate_points_by_mean() -> None:
	rows = [_fake_row(0, 1.0, 1.8), _fake_row(1, 3.0, 1.8), _fake_row(2, 2.0, 1.9)]

	result = build_grid(rows)

	points = {tuple(point.sweep_values.items()): point for point in result.points}
	duplicate_point = points[(("pressure", 1.8),)]
	assert duplicate_point.metric_result.value == pytest.approx(2.0)
	assert duplicate_point.run_indices == (0, 1)
	assert duplicate_point.metric_result.selected_samples == 20
	assert result.incomplete_rows == ()


def test_build_grid_raises_on_duplicates_when_method_is_error() -> None:
	rows = [_fake_row(0, 1.0, 1.8), _fake_row(1, 3.0, 1.8)]

	with pytest.raises(ValueError, match="Duplicate sweep point"):
		build_grid(rows, duplicate_method="error")


def test_build_grid_separates_rows_with_nan_coordinates() -> None:
	rows = [_fake_row(0, 1.0, 1.8), _fake_row(1, 2.0, float("nan"))]

	result = build_grid(rows)

	assert len(result.points) == 1
	assert len(result.incomplete_rows) == 1
	assert result.incomplete_rows[0].run_index == 1


def test_build_grid_rejects_unknown_duplicate_method() -> None:
	with pytest.raises(ValueError, match="duplicate_method"):
		build_grid([_fake_row(0, 1.0, 1.8)], duplicate_method="bogus")
