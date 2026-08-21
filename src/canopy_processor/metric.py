"""Metric definitions for Canopy explorations.

This module deliberately does not perform filtering or plotting. A metric
describes what signal to read from one :class:`DXPXRun`; the analysis layer can
then apply phase/turn-zone masks and reduce that signal consistently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

import numpy as np

from .dxpx import DXPXRun


MetricEvaluator = Callable[[DXPXRun], np.ndarray]


@dataclass(frozen=True)
class Metric:
	"""Description and evaluator for one performance metric.

	``evaluator`` returns the raw signal for one run. It may return a scalar
	for scalar metrics such as lap time or a vector for time-series metrics.
	"""

	name: str
	label: str
	units: str
	evaluator: MetricEvaluator
	use_absolute_value: bool = False

	def evaluate(self, run: DXPXRun) -> np.ndarray:
		"""Evaluate this metric and normalize the result to a NumPy array."""

		values = np.asarray(self.evaluator(run), dtype=float)
		return np.abs(values) if self.use_absolute_value else values


def source_metric(
	name: str,
	label: str,
	field_name: str,
	units: str,
	*,
	use_absolute_value: bool = False,
) -> Metric:
	"""Create a metric that reads one field from ``run.data``."""

	def evaluate(run: DXPXRun) -> np.ndarray:
		try:
			return np.asarray(run.data[field_name])
		except KeyError as exc:
			raise KeyError(f"Metric {name!r} requires Data.{field_name}") from exc

	return Metric(name, label, units, evaluate, use_absolute_value)


def average_metric(
	name: str,
	label: str,
	field_names: tuple[str, ...],
	units: str,
	*,
	use_absolute_value: bool = False,
) -> Metric:
	"""Create an elementwise average metric from two or more source fields."""

	def evaluate(run: DXPXRun) -> np.ndarray:
		missing = [field for field in field_names if field not in run.data]
		if missing:
			fields = ", ".join(f"Data.{field}" for field in missing)
			raise KeyError(f"Metric {name!r} requires {fields}")
		signals = [np.asarray(run.data[field], dtype=float) for field in field_names]
		try:
			return np.nanmean(np.stack(signals), axis=0)
		except ValueError as exc:
			raise ValueError(f"Metric {name!r} source signals have incompatible shapes") from exc

	return Metric(name, label, units, evaluate, use_absolute_value)


def default_metrics() -> Mapping[str, Metric]:
	"""Return the standard metrics represented by the MATLAB scripts."""

	metrics = [
		source_metric("gCarPotential", "Grip Potential", "gCarPotential", "g"),
		source_metric("tLapEnd", "Lap Time", "tLapEnd", "s"),
		source_metric("USOSaSlipTyre_filt", "US Gradient", "USOSaSlipTyre_filt", "-"),
		average_metric(
			"FxFront",
			"Fx Front",
			("FxTyreFL_filt", "FxTyreFR_filt"),
			"N",
		),
		average_metric(
			"FxRear",
			"Fx Rear",
			("FxTyreRL_filt", "FxTyreRR_filt"),
			"N",
		),
		average_metric(
			"FyFront",
			"Fy Front",
			("FyTyreFL_filt", "FyTyreFR_filt"),
			"N",
			use_absolute_value=True,
		),
		average_metric(
			"FyRear",
			"Fy Rear",
			("FyTyreRL_filt", "FyTyreRR_filt"),
			"N",
			use_absolute_value=True,
		),
	]
	for corner in ("FL", "FR", "RL", "RR"):
		metrics.append(
			source_metric(
				f"TTyreSurface{corner}",
				f"Surface Temperature {corner}",
				f"TTyreSurface{corner}",
				"degC",
			)
		)
		metrics.append(
			source_metric(
				f"TTyreInnerLiner{corner}",
				f"Inner Liner Temperature {corner}",
				f"TTyreInnerLiner{corner}",
				"degC",
			)
		)
	return {metric.name: metric for metric in metrics}


def evaluate_metric(metrics: Mapping[str, Metric], name: str, run: DXPXRun) -> np.ndarray:
	"""Evaluate a named metric from a registry with a useful lookup error."""

	try:
		metric = metrics[name]
	except KeyError as exc:
		available = ", ".join(sorted(metrics))
		raise KeyError(f"Unknown metric {name!r}. Available metrics: {available}") from exc
	return metric.evaluate(run)

