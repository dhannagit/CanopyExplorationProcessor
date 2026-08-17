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
    """Load one Canopy ``.dxpx`` MAT file into a :class:`DXPXRun`."""

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

    result = _matlab_struct_to_mapping(raw_result)
    if not isinstance(result, dict) or not isinstance(result.get("Header"), dict):
        raise DXPXLoadError(f"DXPX D variable has no Header struct: {file_path}")
    if not isinstance(result.get("Data"), dict):
        raise DXPXLoadError(f"DXPX D variable has no Data struct: {file_path}")

    return DXPXRun(
        path=file_path,
        header=result["Header"],
        data=result["Data"],
        unit=result.get("Unit"),
        type_info=result.get("Type"),
    )


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