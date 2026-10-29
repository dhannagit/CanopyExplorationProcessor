from pathlib import Path

import numpy as np
import pytest

from canopy_processor import (
	FilterConfig,
	analyze_metric,
	build_filter_mask,
	reduce_signal,
)
from canopy_processor.dxpx import DXPXRun
from canopy_processor.metric import source_metric


def test_reduce_signal_supports_nan_aware_methods() -> None:
	signal = np.array([-4.0, np.nan, 2.0, -1.0])

	assert reduce_signal(signal) == pytest.approx(-1.0)
	assert reduce_signal(signal, method="maximum") == pytest.approx(2.0)
	assert reduce_signal(signal, method="peak") == pytest.approx(4.0)


def test_build_filter_mask_combines_phase_and_zone() -> None:
	run = DXPXRun(Path("synthetic.dxpx"), {}, {
		"phaseA": np.array([1, 1, 0, 0]),
		"phaseB": np.array([0, 1, 1, 0]),
		"zoneA": np.array([1, 0, 1, 0]),
	})

	filters = FilterConfig(
		phases=("phaseA", "phaseB"),
		turn_zones=("zoneA",),
		phase_operator="or",
		category_operator="and",
	)

	np.testing.assert_array_equal(build_filter_mask(run, filters), [True, False, True, False])


def test_analyze_metric_reports_filtered_sample_count() -> None:
	run = DXPXRun(Path("synthetic.dxpx"), {}, {
		"sLap": np.arange(4),
		"grip": np.array([1.0, 2.0, 3.0, 4.0]),
		"isTurnZone1": np.array([1, 0, 1, 0]),
	})
	filters = FilterConfig(turn_zones=("isTurnZone1",))
	result = analyze_metric(run, source_metric("grip", "Grip", "grip", "g"), filters)

	assert result.metric_name == "grip"
	assert result.selected_samples == 2
	assert result.available_samples == 4