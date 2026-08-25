"""Read Canopy .dxpx files.

Canopy files are MATLAB Level-5 MAT files with a different extension. The
loader deliberately preserves the Header/Data split used by the MATLAB tools
while converting MATLAB structs into ordinary Python mappings.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import loadmat


class DXPXLoadError(RuntimeError):
    """Raised when a .dxpx file cannot be loaded as a Canopy result."""


@dataclass(frozen=True)
class DXPXRun:
    """Normalized representation of one Canopy result file."""

    path: Path
    header: dict[str, Any]
    data: dict[str, Any]
    unit: dict[str, Any] | Any = None
    type_info: dict[str, Any] | Any = None

    @property
    def track_name(self) -> str | None:
        value = self.header.get("TrackName")
        return None if value is None else str(value)

    @property
    def turn_zone_names(self) -> list[str]:
        return sorted(
            (name for name in self.data if name.startswith("isTurnZone")),
            key=lambda name: int(name.removeprefix("isTurnZone"))
            if name.removeprefix("isTurnZone").isdigit()
            else name,
        )


def load_dxpx(path: str | Path) -> DXPXRun:
    """Load one Canopy ``.dxpx`` MAT file that contains a single lap.

    Sweep run folders always hold exactly one lap; use load_dxpx_laps for
    baseline files, which may hold several.
    """

    laps = load_dxpx_laps(path)
    if len(laps) != 1:
        raise DXPXLoadError(
            f"Expected a single-lap DXPX file but found {len(laps)} laps: {path}"
        )
    return laps[0]


def load_dxpx_laps(path: str | Path) -> list[DXPXRun]:
    """Load a Canopy ``.dxpx`` MAT file that may hold one lap or an array of laps.

    Baseline studies store multiple laps as a MATLAB struct array; sweep run
    files hold exactly one. Every returned :class:`DXPXRun` shares the same
    source ``path`` because laps are not separate files.
    """

    file_path = Path(path)
    if not file_path.is_file():
        raise DXPXLoadError(f"DXPX file does not exist: {file_path}")

    try:
        mat = loadmat(
            file_path,
            struct_as_record=False,
            squeeze_me=True,
            simplify_cells=False,
        )
    except Exception as exc:  # scipy exposes several format-specific errors
        raise DXPXLoadError(f"Could not read DXPX file {file_path}: {exc}") from exc

    raw_result = mat.get("D")
    if raw_result is None:
        raise DXPXLoadError(f"DXPX file has no top-level D variable: {file_path}")

    laps: list[DXPXRun] = []
    for raw_lap in _iter_struct_entries(raw_result, file_path):
        result = _matlab_struct_to_mapping(raw_lap)
        if not isinstance(result, dict) or not isinstance(result.get("Header"), dict):
            raise DXPXLoadError(f"DXPX D variable has no Header struct: {file_path}")
        if not isinstance(result.get("Data"), dict):
            raise DXPXLoadError(f"DXPX D variable has no Data struct: {file_path}")
        laps.append(
            DXPXRun(
                path=file_path,
                header=result["Header"],
                data=result["Data"],
                unit=result.get("Unit"),
                type_info=result.get("Type"),
            )
        )
    return laps


def _iter_struct_entries(raw_result: Any, file_path: Path) -> list[Any]:
    """Return each struct entry whether ``D`` is a scalar struct or an array."""

    if hasattr(raw_result, "_fieldnames"):
        return [raw_result]
    if isinstance(raw_result, np.ndarray):
        return list(raw_result.flat)
    raise DXPXLoadError(f"DXPX D variable is neither a struct nor a struct array: {file_path}")


def _matlab_struct_to_mapping(value: Any) -> Any:
    """Convert scipy MATLAB structs while preserving numeric arrays/scalars."""

    if hasattr(value, "_fieldnames"):
        return {
            field_name: _matlab_struct_to_mapping(getattr(value, field_name))
            for field_name in value._fieldnames
        }
    if isinstance(value, np.ndarray):
        if value.dtype == object:
            return np.array(
                [_matlab_struct_to_mapping(item) for item in value.flat],
                dtype=object,
            ).reshape(value.shape)
        return value
    if isinstance(value, np.generic):
        return value.item()
    return value