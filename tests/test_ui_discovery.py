from pathlib import Path

from canopy_processor.ui import discover_dataset


REPOSITORY_ROOT = Path(__file__).parents[1]


def test_discover_dataset_finds_sample_sources() -> None:
	result = discover_dataset(REPOSITORY_ROOT)

	assert result.dxpx_directory == REPOSITORY_ROOT / "DATA_dXpx"
	assert result.raw_directory == REPOSITORY_ROOT / "DATA_Raw" / "MOS_COR_TyrePressureExploration"
	assert result.circuit_workbook == REPOSITORY_ROOT / "CircuitsData_Canopy_Hypercar.xlsx"
	assert result.variables
	assert not any("No .dXpx" in item for item in result.diagnostics)