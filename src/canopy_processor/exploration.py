"""Discover sweep variables from Canopy exploration artifacts."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class JobRecord:
    """Metadata for one numbered Canopy job folder."""

    index: int
    name: str
    state: str | None
    is_post_processor: bool
    changes: tuple[dict[str, Any], ...]
    error_messages: tuple[str, ...]


@dataclass(frozen=True)
class SweepVariable:
    """One candidate variable that can be assigned to a sweep axis."""

    path: str
    units: str | None
    values: tuple[float, ...]


@dataclass(frozen=True)
class ExplorationDefinition:
    """Canopy factorial/exploration metadata in user-facing form."""

    design_name: str | None
    variables: tuple[SweepVariable, ...]
    coordinates: tuple[tuple[float, ...], ...]
    job_names: tuple[str, ...]


def load_exploration_definition(raw_directory: str | Path) -> ExplorationDefinition:
    """Load Canopy's exploration-map and input metadata files."""

    directory = Path(raw_directory)
    map_path = directory / "exploration-map.json"
    metadata_path = directory / "scalar-inputs-metadata.csv"
    inputs_path = directory / "scalar-inputs.csv"
    if not map_path.is_file():
        raise FileNotFoundError(f"Missing exploration metadata: {map_path}")
    if not metadata_path.is_file() or not inputs_path.is_file():
        raise FileNotFoundError(f"Missing scalar input metadata in {directory}")

    exploration_map = json.loads(map_path.read_text(encoding="utf-8"))
    metadata = list(csv.DictReader(metadata_path.open(encoding="utf-8", newline="")))
    input_rows = list(csv.DictReader(inputs_path.open(encoding="utf-8", newline="")))
    input_names = list(input_rows[0]) if input_rows else []

    variables: list[SweepVariable] = []
    for column_index, row in enumerate(metadata):
        path = row.get("fullName") or row.get("inputName") or ""
        if column_index < len(input_names):
            values = tuple(float(item[input_names[column_index]]) for item in input_rows)
        else:
            values = ()
        variables.append(SweepVariable(path=path, units=row.get("units") or None, values=values))

    coordinates = tuple(
        tuple(float(_unwrap_coordinate(value)) for value in coordinate)
        for coordinate in exploration_map.get("coordinates", [])
    )
    return ExplorationDefinition(
        design_name=exploration_map.get("designName"),
        variables=tuple(variables),
        coordinates=coordinates,
        job_names=tuple(str(name) for name in exploration_map.get("jobNames", [])),
    )


def discover_job_variables(raw_directory: str | Path) -> tuple[SweepVariable, ...]:
    """Discover numeric changed paths from per-run job-document files.

    This fallback is useful when Canopy's aggregate exploration artifacts are
    absent. Values retain the numeric run-folder ordering.
    """

    directory = Path(raw_directory)
    records = load_job_records(directory)
    run_count = max((record.index for record in records), default=-1) + 1
    by_path: dict[str, list[float]] = {}
    for record in records:
        if record.is_post_processor:
            continue
        for change in record.changes:
            path = str(change.get("path", ""))
            value = change.get("value")
            if path and isinstance(value, (int, float)) and not isinstance(value, bool):
                values = by_path.setdefault(path, [float("nan")] * run_count)
                values[record.index] = float(value)

    return tuple(
        SweepVariable(path=path, units=None, values=tuple(values))
        for path, values in by_path.items()
    )


def load_job_records(raw_directory: str | Path) -> tuple[JobRecord, ...]:
    """Load numbered job documents and classify Canopy post-processing jobs."""

    directory = Path(raw_directory)
    records: list[JobRecord] = []
    job_paths = sorted(
        (path for path in directory.glob("*/job-document.json") if path.parent.name.isdigit()),
        key=lambda path: int(path.parent.name),
    )
    for job_path in job_paths:
        document: dict[str, Any] = json.loads(job_path.read_text(encoding="utf-8"))
        data = document.get("data") or {}
        name = str(document.get("name") or "")
        lower_name = str(document.get("lowerName") or name).strip().lower()
        changes = tuple(data.get("changes") or ())
        is_post_processor = (
            lower_name == "post processor"
            or name.strip().lower() == "post processor"
            or (not changes and float(data.get("computeCredits") or 0) == 0)
        )
        error_messages = tuple(str(message) for message in data.get("errorMessages") or ())
        records.append(
            JobRecord(
                index=int(job_path.parent.name),
                name=name,
                state=data.get("state"),
                is_post_processor=is_post_processor,
                changes=changes,
                error_messages=error_messages,
            )
        )
    return tuple(records)


def _unwrap_coordinate(value: Any) -> Any:
    """Unwrap Canopy's one-element coordinate arrays."""

    while isinstance(value, list) and len(value) == 1:
        value = value[0]
    return value