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
	dxpx_candidates: tuple[Path, ...] = ()


def discover_dataset(root: str | Path, circuit_workbook: str | Path | None = None) -> DiscoveryResult:
	"""Discover one raw study and its matching DXPX study directory.

	The selected path is expected to be a single ``StudyName`` directory,
	not the parent containing many studies.
	"""

	root_path = Path(root).expanduser().resolve()
	diagnostics: list[str] = []
	raw_directory = root_path
	dxpx_directory = _derive_dxpx_directory(raw_directory)
	dxpx_candidates = (dxpx_directory,) if dxpx_directory is not None else ()
	if not _looks_like_raw_study(raw_directory):
		diagnostics.append("Select one raw StudyName folder containing numbered job folders")
		raw_directory = None
	if dxpx_directory is None or not _has_indexed_dxpx_runs(dxpx_directory):
		diagnostics.append("No matching DXPX StudyName folder with indexed .dXpx runs was found")
		dxpx_directory = None
	if dxpx_directory is None:
		diagnostics.append("No .dXpx files were found below the selected root")
	if raw_directory is None:
		diagnostics.append("No numbered raw job folders were found below the selected root")

	workbook = Path(circuit_workbook).expanduser().resolve() if circuit_workbook else None
	if workbook is None:
		diagnostics.append("Configure the circuit workbook folder in File > Settings")
	elif not workbook.is_file():
		diagnostics.append(f"Circuit workbook unavailable: {workbook}. Check File > Settings and OneDrive sync.")

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
		dxpx_candidates=dxpx_candidates,
	)


def _looks_like_raw_study(path: Path) -> bool:
	"""Identify a selected raw study without scanning sibling studies."""

	return any(path.glob("*/job-document.json")) and (
		(path / "exploration-map.json").is_file() or (path / "study-document.json").is_file()
	)


def _derive_dxpx_directory(raw_directory: Path) -> Path | None:
	"""Map a raw study path to its corresponding DXPX study path."""

	parts = list(raw_directory.parts)
	if "DATA_Raw" not in parts:
		return None
	raw_index = parts.index("DATA_Raw")
	remainder = parts[raw_index + 1 :]
	if remainder and remainder[0] == "02_Worksheets":
		remainder = remainder[1:]
	return Path(*parts[:raw_index], "DATA_dXpx", *remainder)


def _has_indexed_dxpx_runs(path: Path) -> bool:
	"""Return whether a DXPX study has at least one numbered run file."""

	return path.is_dir() and any(
		file.is_file() and file.suffix.lower() == ".dxpx"
		for folder in path.iterdir()
		if folder.is_dir() and folder.name.isdigit()
		for file in folder.iterdir()
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


def _matching_dxpx_directories(container: Path, raw_study: Path) -> tuple[Path, ...]:
	"""Find DXPX study folders matching a raw study name and worksheet."""

	study_name = raw_study.name
	worksheet_name = raw_study.parent.name
	study_directories = {
		path.parent.parent if path.parent.name.isdigit() else path.parent
		for path in container.rglob("*.dXpx")
	}
	candidates = {
		study
		for study in study_directories
		if study.name == study_name and study.parent.name == worksheet_name
	}
	if not candidates:
		candidates = {
			study
			for study in study_directories
			if study.name == study_name
		}
	return tuple(sorted(candidates))