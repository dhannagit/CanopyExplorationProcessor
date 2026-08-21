from pathlib import Path

import numpy as np

from canopy_processor import default_metrics, evaluate_metric, load_dxpx


SAMPLE_DXPX = next((Path(__file__).parents[1] / "DATA_dXpx").rglob("*.dXpx"))


def test_default_front_force_metric_averages_left_and_right() -> None:
    run = load_dxpx(SAMPLE_DXPX)
    metrics = default_metrics()

    expected = (
        np.asarray(run.data["FxTyreFL_filt"])
        + np.asarray(run.data["FxTyreFR_filt"])
    ) / 2

    actual = evaluate_metric(metrics, "FxFront", run)

    assert actual.shape == expected.shape
    np.testing.assert_allclose(actual, expected)


def test_default_metrics_include_current_script_catalog() -> None:
    metrics = default_metrics()

    assert {"gCarPotential", "tLapEnd", "FxFront", "FyRear"}.issubset(metrics)
    assert metrics["FyFront"].use_absolute_value is True
    assert metrics["TTyreSurfaceFL"].units == "degC"