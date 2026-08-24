"""Filtering and reduction of Canopy metrics.

This module sits between metric definitions and future plotting code. It turns
time-series signals into one value per run while keeping the filter behavior
explicit and testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import numpy as np

from .config import FilterConfig
from .dxpx import DXPXRun
from .metric import Metric


REDUCTION_METHODS = {"mean", "median", "minimum", "maximum", "peak"}


@dataclass(frozen=True)
class MetricResult:
	"""Reduced value and diagnostics for one metric on one run."""

	metric_name: str
	value: float
	method: str
	selected_samples: int
	available_samples: int


def build_filter_mask(run: DXPXRun, filters: FilterConfig) -> np.ndarray:
	"""Build a boolean mask from selected phase and turn-zone fields.

	An empty phase or turn-zone selection means no restriction in that category.
	Selections within a category use that category's operator; the two category
	results use ``category_operator``.
	"""

	length = _signal_length(run)
	phase_mask = _combine_fields(
		run,
		filters.phases,
		filters.phase_operator,
		length,
		"phase",
	)
	zone_mask = _combine_fields(
		run,
		filters.turn_zones,
		filters.turn_zone_operator,
		length,
		"turn-zone",
	)

	if not filters.phases:
		return zone_mask
	if not filters.turn_zones:
		return phase_mask
	if filters.category_operator == "and":
		return phase_mask & zone_mask
	return phase_mask | zone_mask


def reduce_signal(
	signal: np.ndarray,
	mask: np.ndarray | None = None,
	method: str = "mean",
) -> float:
	"""Reduce a scalar or time-series signal to one NaN-aware float.

	``mask`` is applied only to vector signals. Empty selections and all-NaN
	selections return ``nan`` rather than raising or silently using all samples.
	"""

	if method not in REDUCTION_METHODS:
		raise ValueError(f"Unknown reduction method: {method}")
	values = np.asarray(signal, dtype=float).reshape(-1)
	if mask is not None:
		mask_values = np.asarray(mask, dtype=bool).reshape(-1)
		if mask_values.size != values.size:
			raise ValueError("Signal and filter mask must have the same number of samples")
		values = values[mask_values]
	values = values[~np.isnan(values)]
	if values.size == 0:
		return float("nan")
	if method == "mean":
		return float(np.mean(values))
	if method == "median":
		return float(np.median(values))
	if method == "minimum":
		return float(np.min(values))
	if method == "maximum":
		return float(np.max(values))
	return float(np.max(np.abs(values)))


def analyze_metric(
	run: DXPXRun,
	metric: Metric,
	filters: FilterConfig | None = None,
	method: str = "mean",
) -> MetricResult:
	"""Evaluate and reduce one metric for one run."""

	values = np.asarray(metric.evaluate(run), dtype=float).reshape(-1)
	mask = build_filter_mask(run, filters) if filters is not None else None
	# Scalar metrics, such as a preselected lap time, have no sample axis to
	# filter. Treat them as one already-reduced observation.
	if values.size == 1:
		mask = None
	selected_samples = int(mask.sum()) if mask is not None else values.size
	if mask is not None and mask.size != values.size:
		raise ValueError(
			f"Metric {metric.name!r} has {values.size} samples but its filter has {mask.size}"
		)
	return MetricResult(
		metric_name=metric.name,
		value=reduce_signal(values, mask, method),
		method=method,
		selected_samples=selected_samples,
		available_samples=values.size,
	)


def analyze_runs(
	runs: Iterable[DXPXRun],
	metric: Metric,
	filters: FilterConfig | None = None,
	method: str = "mean",
) -> list[MetricResult]:
	"""Analyze the same metric and filter settings for multiple runs."""

	return [analyze_metric(run, metric, filters, method) for run in runs]


def _signal_length(run: DXPXRun) -> int:
	"""Find the sample count used to validate phase and zone masks."""

	for name in ("sLap", "tRun", "tLap"):
		if name in run.data:
			return np.asarray(run.data[name]).size
	data_lengths = [np.asarray(value).size for value in run.data.values() if np.asarray(value).ndim > 0]
	if not data_lengths:
		raise ValueError(f"Run contains no vector data: {run.path}")
	return max(data_lengths)


def _combine_fields(
	run: DXPXRun,
	field_names: Iterable[str],
	operator: str,
	length: int,
	category: str,
) -> np.ndarray:
	"""Combine selected binary mask fields with AND or OR."""

	fields = list(field_names)
	if not fields:
		return np.ones(length, dtype=bool)
	if operator not in {"and", "or"}:
		raise ValueError(f"Unknown {category} mask operator: {operator}")

	masks: list[np.ndarray] = []
	for field_name in fields:
		if field_name not in run.data:
			raise KeyError(f"Selected {category} field is missing: Data.{field_name}")
		mask = np.asarray(run.data[field_name]).reshape(-1)
		if mask.size != length:
			raise ValueError(
				f"Selected {category} field {field_name!r} has {mask.size} samples; expected {length}"
			)
		masks.append(mask == 1)

	result = masks[0]
	for mask in masks[1:]:
		result = result & mask if operator == "and" else result | mask
	return result