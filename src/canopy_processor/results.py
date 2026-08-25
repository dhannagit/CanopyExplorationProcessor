"""Assemble multi-run result tables from single-run metric reductions.

This is a distinct layer from analysis.py: analysis.py reduces one run's
metric to one value, while this module joins those reduced values across many
runs to their sweep-variable coordinates. Duplicate-point aggregation,
missing-cell diagnostics, and baseline deltas belong here as they are added.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .analysis import MetricResult
from .dxpx import DXPXRun
from .exploration import SweepVariable


@dataclass(frozen=True)
class AnalysisRow:
	"""One run's sweep-variable coordinates joined to its metric result."""

	run_index: int
	sweep_values: dict[str, float]
	metric_result: MetricResult


def run_index(run: DXPXRun) -> int:
	"""Return a run's numbered-folder index, used to join sweep variables."""

	folder_name = run.path.parent.name
	if not folder_name.isdigit():
		raise ValueError(f"Run folder is not numbered, cannot determine run index: {run.path}")
	return int(folder_name)


def join_sweep_variables(
	runs: Iterable[DXPXRun],
	results: Iterable[MetricResult],
	variables: Iterable[SweepVariable],
) -> list[AnalysisRow]:
	"""Join each run's analyzed metric result to its sweep-variable values.

	``runs`` and ``results`` must be the same length and in the same order,
	as produced by :func:`canopy_processor.analysis.analyze_runs`. Sweep values
	are looked up by each run's numbered-folder index, not by list position, so
	callers may join a subset of runs in any order.
	"""

	run_list = list(runs)
	result_list = list(results)
	if len(run_list) != len(result_list):
		raise ValueError(
			f"runs ({len(run_list)}) and results ({len(result_list)}) must have the same length"
		)

	variable_list = list(variables)
	rows: list[AnalysisRow] = []
	for run, result in zip(run_list, result_list):
		index = run_index(run)
		sweep_values: dict[str, float] = {}
		for variable in variable_list:
			if index >= len(variable.values):
				raise ValueError(
					f"Sweep variable {variable.path!r} has no value for run {index}"
				)
			sweep_values[variable.path] = variable.values[index]
		rows.append(AnalysisRow(run_index=index, sweep_values=sweep_values, metric_result=result))
	return rows
