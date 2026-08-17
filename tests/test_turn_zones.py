from pathlib import Path

import numpy as np

from canopy_processor import add_turn_zones, load_dxpx


REPOSITORY_ROOT = Path(__file__).parents[1]
SAMPLE_DXPX = next((REPOSITORY_ROOT / "DATA_dXpx").rglob("*.dXpx"))
WORKBOOK = REPOSITORY_ROOT / "CircuitsData_Canopy_Hypercar.xlsx"


def test_generate_ctmp_turn_zones_from_sample() -> None:
    result = add_turn_zones(load_dxpx(SAMPLE_DXPX), WORKBOOK)

    assert result.turn_zone_names == [f"isTurnZone{i}" for i in range(1, 13)]
    assert all(np.asarray(result.data[name]).shape == np.asarray(result.data["sLap"]).shape for name in result.turn_zone_names)
    assert np.count_nonzero(result.data["isTurnZone1"]) > 0


def test_existing_turn_zones_are_preserved() -> None:
    run = load_dxpx(SAMPLE_DXPX)
    existing = np.ones_like(np.asarray(run.data["sLap"]))
    run.data["isTurnZone1"] = existing

    result = add_turn_zones(run, WORKBOOK)

    assert result is run
    assert np.array_equal(result.data["isTurnZone1"], existing)