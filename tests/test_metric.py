from pathlib import Path

import numpy as np

from canopy_processor import default_metrics, evaluate_metric
from canopy_processor.dxpx import DXPXRun


def test_default_front_force_metric_averages_left_and_right() -> None:
    run = DXPXRun(Path("synthetic.dxpx"), {}, {
        "FxTyreFL_filt": np.array([10.0, 12.0, 14.0]),
        "FxTyreFR_filt": np.array([12.0, 14.0, 16.0]),
    })
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