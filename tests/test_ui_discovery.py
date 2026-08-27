from pathlib import Path

from canopy_processor.ui import discover_dataset


REPOSITORY_ROOT = Path(__file__).parents[1]
SAMPLE_RAW_STUDY = REPOSITORY_ROOT / "DATA_Raw" / "MOS_COR_TyrePressureExploration"


def test_discover_dataset_finds_sample_sources() -> None:
	result = discover_dataset(SAMPLE_RAW_STUDY)

	assert result.dxpx_directory == REPOSITORY_ROOT / "DATA_dXpx" / "MOS_COR_TyrePressureExploration"
	assert result.raw_directory == REPOSITORY_ROOT / "DATA_Raw" / "MOS_COR_TyrePressureExploration"
	assert result.circuit_workbook == REPOSITORY_ROOT / "CircuitsData_Canopy_Hypercar.xlsx"
	assert result.variables
	assert not any("No .dXpx" in item for item in result.diagnostics)
	assert result.dxpx_candidates


def test_discover_dataset_matches_worksheet_study_layout(tmp_path: Path) -> None:
	raw = tmp_path / "DATA_Raw" / "02_Worksheets" / "WorksheetA" / "StudyA"
	dxpx = tmp_path / "DATA_dXpx" / "WorksheetA" / "StudyA"
	raw.mkdir(parents=True)
	dxpx.mkdir(parents=True)
	(raw / "exploration-map.json").write_text('{"designName": "Factorial", "coordinates": [], "jobNames": []}', encoding="utf-8")
	(raw / "scalar-inputs-metadata.csv").write_text("fullName,units\nsetup.pressure,bar\n", encoding="utf-8")
	(raw / "scalar-inputs.csv").write_text("setup.pressure\n2.0\n", encoding="utf-8")
	(raw / "0").mkdir()
	(raw / "0" / "job-document.json").write_text('{"name": "Study", "data": {"changes": [{"path": "setup.pressure", "value": 2.0}]}}', encoding="utf-8")
	(dxpx / "0").mkdir()
	(dxpx / "0" / "0.dXpx").write_bytes(b"placeholder")

	result = discover_dataset(raw)

	assert result.raw_directory == raw
	assert result.dxpx_directory == dxpx
	assert result.dxpx_candidates == (dxpx,)