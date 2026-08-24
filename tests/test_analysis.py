from pathlib import Path

import numpy as np
import pytest

from canopy_processor import (
	FilterConfig,
	add_turn_zones,
	analyze_metric,
	build_filter_mask,
	default_metrics,
	load_dxpx,
	reduce_signal,
)


SAMPLE_DXPX = next((Path(__file__).parents[1] / "DATA_dXpx").rglob("*.dXpx"))
WORKBOOK = Path(__file__).parents[1] / "CircuitsData_Canopy_Hypercar.xlsx"


def test_reduce_signal_supports_nan_aware_methods() -> None:
	signal = np.array([-4.0, np.nan, 2.0, -1.0])

	assert reduce_signal(signal) == pytest.approx(-1.0)
	assert reduce_signal(signal, method="maximum") == pytest.approx(2.0)
	assert reduce_signal(signal, method="peak") == pytest.approx(4.0)


def test_build_filter_mask_combines_phase_and_zone() -> None:
	run = load_dxpx(SAMPLE_DXPX)
	run.data["phaseA"] = np.array([1, 1, 0, 0])
	run.data["phaseB"] = np.array([0, 1, 1, 0])
	run.data["zoneA"] = np.array([1, 0, 1, 0])
	run.data["sLap"] = np.arange(4)

	filters = FilterConfig(
		phases=("phaseA", "phaseB"),
		turn_zones=("zoneA",),
		phase_operator="or",
		category_operator="and",
	)

	np.testing.assert_array_equal(build_filter_mask(run, filters), [True, False, True, False])


def test_analyze_metric_reports_filtered_sample_count() -> None:
	run = add_turn_zones(load_dxpx(SAMPLE_DXPX), WORKBOOK)
	filters = FilterConfig(turn_zones=("isTurnZone1",))
	result = analyze_metric(run, default_metrics()["gCarPotential"], filters)

	assert result.metric_name == "gCarPotential"
	assert result.selected_samples > 0
	assert result.selected_samples < result.available_samples