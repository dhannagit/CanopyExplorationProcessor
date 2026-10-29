from pathlib import Path

import numpy as np
from openpyxl import Workbook

from canopy_processor import add_turn_zones
from canopy_processor.dxpx import DXPXRun


def _synthetic_run(track_name: str = "Synthetic Circuit") -> DXPXRun:
    return DXPXRun(
        path=Path("synthetic.dxpx"),
        header={"TrackName": track_name},
        data={"sLap": np.arange(6, dtype=float)},
    )


def _write_workbook(path: Path, track_name: str = "Synthetic Circuit") -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Turns"
    sheet.append(["Circuit", "Zone 1 Start", "Zone 1 End", "Zone 2 Start", "Zone 2 End"])
    sheet.append([track_name, 1.0, 2.0, 3.0, 4.0])
    workbook.save(path)
    return path


def test_generate_turn_zones_from_synthetic_workbook(tmp_path: Path) -> None:
    result = add_turn_zones(_synthetic_run(), _write_workbook(tmp_path / "circuits.xlsx"))

    assert result.turn_zone_names == ["isTurnZone1", "isTurnZone2"]
    assert all(np.asarray(result.data[name]).shape == np.asarray(result.data["sLap"]).shape for name in result.turn_zone_names)
    np.testing.assert_array_equal(result.data["isTurnZone1"], [0, 1, 1, 0, 0, 0])
    np.testing.assert_array_equal(result.data["isTurnZone2"], [0, 0, 0, 1, 1, 0])


def test_existing_turn_zones_are_preserved(tmp_path: Path) -> None:
    run = _synthetic_run()
    existing = np.ones_like(np.asarray(run.data["sLap"]))
    run.data["isTurnZone1"] = existing

    result = add_turn_zones(run, tmp_path / "unused.xlsx")

    assert result is run
    assert np.array_equal(result.data["isTurnZone1"], existing)


def test_explicit_track_override_does_not_change_header_track(tmp_path: Path) -> None:
    run = _synthetic_run("Header Track")
    workbook = _write_workbook(tmp_path / "circuits.xlsx", "Selected Track")
    result = add_turn_zones(run, workbook, track_name="Selected Track")

    assert run.track_name == "Header Track"
    assert result.track_name == "Header Track"
    assert len(result.turn_zone_names) == 2