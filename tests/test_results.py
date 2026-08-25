from pathlib import Path

import pytest

from canopy_processor import MetricResult, SweepVariable, join_sweep_variables, run_index
from canopy_processor.dxpx import DXPXRun


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
