"""Dataset discovery used by the desktop workbench."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..exploration import ExplorationDefinition, SweepVariable, discover_job_variables, load_exploration_definition


@dataclass(frozen=True)
class DiscoveryResult:
	"""Resolved source locations and candidate variables for one root."""

	root: Path
	dxpx_directory: Path | None
	raw_directory: Path | None
	circuit_workbook: Path | None
	variables: tuple[SweepVariable, ...]
	exploration: ExplorationDefinition | None
	diagnostics: tuple[str, ...]


def discover_dataset(root: str | Path) -> DiscoveryResult:
	"""Discover Canopy inputs below a user-selected root directory."""

	root_path = Path(root).expanduser().resolve()
	diagnostics: list[str] = []
	dxpx_directory = _find_directory(root_path, "DATA_dXpx", "dXpx")
	raw_directory = _find_directory(root_path, "DATA_Raw", "Raw")
	if raw_directory is not None and not (raw_directory / "exploration-map.json").is_file():
		nested_metadata = sorted(raw_directory.rglob("exploration-map.json"))
		if nested_metadata:
			raw_directory = nested_metadata[0].parent
	if dxpx_directory is not None and not any(dxpx_directory.rglob("*.dXpx")):
		nested_dxpx = sorted(dxpx_directory.rglob("*.dXpx"))
		if nested_dxpx:
			dxpx_directory = nested_dxpx[0].parent
	if dxpx_directory is None and any(root_path.rglob("*.dXpx")):
		dxpx_directory = root_path
	if raw_directory is None and any(root_path.glob("*/job-document.json")):
		raw_directory = root_path
	if dxpx_directory is None:
		diagnostics.append("No .dXpx files were found below the selected root")
	if raw_directory is None:
		diagnostics.append("No numbered raw job folders were found below the selected root")

	workbook = next(root_path.glob("CircuitsData_*.xlsx"), None)
	if workbook is None:
		diagnostics.append("No circuit workbook was discovered")

	exploration = None
	variables: tuple[SweepVariable, ...] = ()
	if raw_directory is not None:
		try:
			exploration = load_exploration_definition(raw_directory)
			variables = exploration.variables
		except (FileNotFoundError, ValueError, KeyError) as error:
			diagnostics.append(f"Exploration metadata unavailable: {error}")
			try:
				variables = discover_job_variables(raw_directory)
			except (FileNotFoundError, ValueError) as fallback_error:
				diagnostics.append(f"Job-variable discovery failed: {fallback_error}")
		if not variables:
			diagnostics.append("No numeric sweep variables were discovered")

	return DiscoveryResult(
		root=root_path,
		dxpx_directory=dxpx_directory,
		raw_directory=raw_directory,
		circuit_workbook=workbook,
		variables=variables,
		exploration=exploration,
		diagnostics=tuple(diagnostics),
	)


def _find_directory(root: Path, *names: str) -> Path | None:
	"""Find the first matching conventional source directory."""

	for name in names:
		candidate = root / name
		if candidate.is_dir():
			return candidate
	for name in names:
		matches = sorted(candidate for candidate in root.rglob(name) if candidate.is_dir())
		if matches:
			return matches[0]
	for marker in ("exploration-map.json", "study-document.json"):
		matches = sorted(path.parent for path in root.rglob(marker))
		if matches:
			return matches[0]
	return None