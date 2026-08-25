from pathlib import Path

import numpy as np
import pytest

from canopy_processor import DXPXLoadError, load_dxpx, load_dxpx_laps


REPOSITORY_ROOT = Path(__file__).parents[1]
SAMPLE_DXPX = next((REPOSITORY_ROOT / "DATA_dXpx").rglob("*.dXpx"))
BASELINE_DXPX = next((REPOSITORY_ROOT / "BaselineExample").rglob("*.dXpx"))


def test_load_sample_dxpx() -> None:
    result = load_dxpx(SAMPLE_DXPX)

    assert result.path == SAMPLE_DXPX
    assert result.track_name == "CTMP"
    assert result.header["NRun"] == 1
    assert len(result.data) >= 500
    assert result.turn_zone_names == []
    assert isinstance(result.data["sLap"], np.ndarray)
    assert result.data["sLap"].size > 0


def test_load_dxpx_rejects_a_multi_lap_file() -> None:
    with pytest.raises(DXPXLoadError, match="single-lap"):
        load_dxpx(BASELINE_DXPX)


def test_load_dxpx_laps_reads_a_single_lap_file() -> None:
    laps = load_dxpx_laps(SAMPLE_DXPX)

    assert len(laps) == 1
    assert laps[0].track_name == "CTMP"


def test_load_dxpx_laps_reads_a_multi_lap_baseline_file() -> None:
    laps = load_dxpx_laps(BASELINE_DXPX)

    assert len(laps) == 11
    assert all(lap.path == BASELINE_DXPX for lap in laps)
    assert all(isinstance(lap.data["sLap"], np.ndarray) for lap in laps)