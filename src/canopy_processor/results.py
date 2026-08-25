"""Assemble multi-run result tables from single-run metric reductions.

This is a distinct layer from analysis.py: analysis.py reduces one run's
metric to one value, while this module joins those reduced values across many
runs to their sweep-variable coordinates and compares them to a baseline.
Duplicate-point aggregation and missing-cell diagnostics belong here too.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

from .analysis import MetricResult, build_filter_mask, reduce_signal
from .config import BaselineConfig, FilterConfig
from .dxpx import DXPXRun, load_dxpx_laps
from .exploration import SweepVariable
from .metric import Metric


@dataclass(frozen=True)
class AnalysisRow:
	"""One run's sweep-variable coordinates joined to its metric result."""

	run_index: int
	sweep_values: dict[str, float]
	metric_result: MetricResult


@dataclass(frozen=True)
class BaselineResult:
	"""A baseline value reduced from one or more laps pooled together."""

	value: float
	method: str
	lap_count: int
	selected_samples: int


@dataclass(frozen=True)
class ComparedRow:
	"""An analysis row together with its baseline comparison."""

	row: AnalysisRow
	baseline: BaselineResult
	delta_mode: str
	delta: float
	baseline_valid: bool


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


def resolve_baseline_laps(
	baseline: BaselineConfig,
	sweep_runs: Iterable[DXPXRun] = (),
) -> list[DXPXRun]:
	"""Resolve a BaselineConfig into the concrete lap(s) to reduce.

	For ``loaded_run``, the lap is looked up among ``sweep_runs`` by numbered
	folder index. For ``external_study``, the file is loaded and, if it
	contains multiple laps, ``lap_indices`` selects which zero-based laps to
	pool together.
	"""

	if baseline.mode == "none":
		raise ValueError("BaselineConfig mode is 'none'; there is no baseline to resolve")

	if baseline.mode == "loaded_run":
		run_map = {run_index(run): run for run in sweep_runs}
		try:
			return [run_map[baseline.run_index]]
		except KeyError as exc:
			raise ValueError(f"No loaded run with run_index={baseline.run_index}") from exc

	laps = load_dxpx_laps(baseline.external_path)
	if len(laps) == 1:
		return laps
	if not baseline.lap_indices:
		raise ValueError(
			f"Baseline file has {len(laps)} laps; BaselineConfig.lap_indices must select at least one"
		)
	try:
		return [laps[index] for index in baseline.lap_indices]
	except IndexError as exc:
		raise ValueError(
			f"lap_indices out of range for {len(laps)} laps: {baseline.lap_indices}"
		) from exc


def analyze_baseline(
	laps: DXPXRun | Iterable[DXPXRun],
	metric: Metric,
	filters: FilterConfig | None = None,
	method: str = "mean",
) -> BaselineResult:
	"""Reduce one or more baseline laps to a single pooled baseline value.

	Selected laps are pooled into one sample set before reducing once, so
	multiple laps behave as one combined baseline rather than an average of
	averages. Laps must already have turn-zone fields if ``filters`` uses them,
	matching how sweep runs are prepared before :func:`analyze_metric`.
	"""

	lap_list = [laps] if isinstance(laps, DXPXRun) else list(laps)
	if not lap_list:
		raise ValueError("At least one baseline lap is required")

	pooled: list[np.ndarray] = []
	for lap in lap_list:
		values = np.asarray(metric.evaluate(lap), dtype=float).reshape(-1)
		mask = build_filter_mask(lap, filters) if filters is not None and values.size > 1 else None
		if mask is not None:
			if mask.size != values.size:
				raise ValueError(
					f"Metric {metric.name!r} has {values.size} samples but its filter has {mask.size}"
				)
			values = values[mask]
		pooled.append(values)
	pooled_values = np.concatenate(pooled)

	return BaselineResult(
		value=reduce_signal(pooled_values, method=method),
		method=method,
		lap_count=len(lap_list),
		selected_samples=int(pooled_values.size),
	)


def compute_delta(value: float, baseline_value: float, delta_mode: str) -> tuple[float, bool]:
	"""Return ``(delta, baseline_valid)`` for one value against a baseline.

	A zero or NaN baseline, or a NaN value, produces ``nan`` with
	``baseline_valid=False`` rather than raising or dividing by zero.
	"""

	if delta_mode == "none":
		return float("nan"), True
	if delta_mode not in {"absolute", "percent"}:
		raise ValueError(f"Unknown delta mode: {delta_mode}")
	if np.isnan(value) or np.isnan(baseline_value) or (delta_mode == "percent" and baseline_value == 0):
		return float("nan"), False
	if delta_mode == "absolute":
		return value - baseline_value, True
	return (value - baseline_value) / abs(baseline_value) * 100.0, True


def compare_rows_to_baseline(
	rows: Iterable[AnalysisRow],
	baseline: BaselineResult,
	delta_mode: str = "percent",
) -> list[ComparedRow]:
	"""Compare each analysis row's metric value to one shared baseline."""

	compared: list[ComparedRow] = []
	for row in rows:
		delta, baseline_valid = compute_delta(row.metric_result.value, baseline.value, delta_mode)
		compared.append(
			ComparedRow(
				row=row,
				baseline=baseline,
				delta_mode=delta_mode,
				delta=delta,
				baseline_valid=baseline_valid,
			)
		)
	return compared
