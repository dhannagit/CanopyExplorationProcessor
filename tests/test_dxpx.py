import numpy as np
import pytest

from canopy_processor import DXPXLoadError, load_dxpx, load_dxpx_laps


@pytest.mark.local_data
def test_load_sample_dxpx(sample_dxpx) -> None:
    result = load_dxpx(sample_dxpx)

    assert result.path == sample_dxpx
    assert result.track_name
    assert isinstance(result.data["sLap"], np.ndarray)
    assert result.data["sLap"].size > 0


@pytest.mark.local_data
def test_load_dxpx_rejects_a_multi_lap_file(multi_lap_baseline_dxpx) -> None:
    with pytest.raises(DXPXLoadError, match="single-lap"):
        load_dxpx(multi_lap_baseline_dxpx)


def test_load_dxpx_reads_a_synthetic_single_lap(synthetic_single_lap_dxpx) -> None:
    result = load_dxpx(synthetic_single_lap_dxpx)

    assert result.track_name == "Synthetic Circuit"
    np.testing.assert_array_equal(result.data["sLap"], [0.0, 1.0, 2.0])


def test_load_dxpx_laps_reads_a_synthetic_multi_lap(synthetic_multi_lap_dxpx) -> None:
    laps = load_dxpx_laps(synthetic_multi_lap_dxpx)

    assert len(laps) == 3
    assert all(lap.track_name == "Synthetic Circuit" for lap in laps)
    assert all(lap.path == synthetic_multi_lap_dxpx for lap in laps)


@pytest.mark.local_data
def test_load_dxpx_laps_reads_a_sample_single_lap(sample_dxpx) -> None:
    laps = load_dxpx_laps(sample_dxpx)

    assert len(laps) == 1
    assert laps[0].track_name


@pytest.mark.local_data
def test_load_dxpx_laps_reads_a_sample_multi_lap_baseline(multi_lap_baseline_dxpx) -> None:
    laps = load_dxpx_laps(multi_lap_baseline_dxpx)

    assert len(laps) > 1
    assert all(lap.path == multi_lap_baseline_dxpx for lap in laps)
    assert all(isinstance(lap.data["sLap"], np.ndarray) for lap in laps)