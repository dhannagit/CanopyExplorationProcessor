from pathlib import Path

import numpy as np

from canopy_processor import load_dxpx


REPOSITORY_ROOT = Path(__file__).parents[1]
SAMPLE_DXPX = next((REPOSITORY_ROOT / "DATA_dXpx").rglob("*.dXpx"))


def test_load_sample_dxpx() -> None:
    result = load_dxpx(SAMPLE_DXPX)

    assert result.path == SAMPLE_DXPX
    assert result.track_name == "CTMP"
    assert result.header["NRun"] == 1
    assert len(result.data) >= 500
    assert result.turn_zone_names == []
    assert isinstance(result.data["sLap"], np.ndarray)
    assert result.data["sLap"].size > 0