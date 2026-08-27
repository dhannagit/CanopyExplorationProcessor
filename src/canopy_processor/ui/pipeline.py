"""Background-friendly dataset loading for the desktop workbench."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..dxpx import DXPXRun, load_dxpx
from ..metric import Metric, default_metrics
from ..turn_zones import add_turn_zones
from .discovery import DiscoveryResult


@dataclass(frozen=True)
class LoadedDataset:
	"""Loaded runs, compatible metrics, and non-fatal loading diagnostics."""

	runs: tuple[DXPXRun, ...]
	metrics: dict[str, Metric]
	diagnostics: tuple[str, ...]


def load_dataset(
	discovery: DiscoveryResult,
	is_cancelled: Callable[[], bool] = lambda: False,
	progress: Callable[[str, int, int], None] | None = None,
) -> LoadedDataset:
	"""Load discovered DXPX runs and prepare missing turn-zone masks."""

	if discovery.dxpx_directory is None:
		raise FileNotFoundError("No DXPX directory was discovered")
	files = sorted(
		(path for path in discovery.dxpx_directory.rglob("*.dXpx") if path.parent.name.isdigit()),
		key=lambda path: (int(path.parent.name), str(path)),
	)
	if not files:
		raise FileNotFoundError(f"No numbered .dXpx files found below {discovery.dxpx_directory}")

	diagnostics = list(discovery.diagnostics)
	runs: list[DXPXRun] = []
	for index, path in enumerate(files, start=1):
		if is_cancelled():
			return LoadedDataset(tuple(runs), {}, tuple(diagnostics + ["Loading cancelled"]))
		if progress:
			progress("Loading simulation runs", index - 1, len(files))
		try:
			run = load_dxpx(path)
			if not run.turn_zone_names and discovery.circuit_workbook is not None:
				run = add_turn_zones(run, discovery.circuit_workbook)
			runs.append(run)
		except Exception as error:
			diagnostics.append(f"Run {path.parent.name} could not be loaded: {error}")
	if progress:
		progress("Checking available metrics", len(files), len(files))

	metrics: dict[str, Metric] = {}
	if runs:
		for name, metric in default_metrics().items():
			try:
				metric.evaluate(runs[0])
			except (KeyError, ValueError, TypeError):
				continue
			metrics[name] = metric
		if not metrics:
			diagnostics.append("No default metrics are compatible with the loaded runs")
	else:
		diagnostics.append("No simulation runs were loaded")
	return LoadedDataset(tuple(runs), metrics, tuple(diagnostics))