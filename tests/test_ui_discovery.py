from pathlib import Path

from canopy_processor.ui import discover_dataset


REPOSITORY_ROOT = Path(__file__).parents[1]
SAMPLE_RAW_STUDY = REPOSITORY_ROOT / "DATA_Raw" / "MOS_COR_TyrePressureExploration"
TRACK_TEMP_STUDY = REPOSITORY_ROOT / "DATA_Raw" / "MOS_COR_TrackTempSweep"


def test_discover_dataset_finds_sample_sources() -> None:
	result = discover_dataset(SAMPLE_RAW_STUDY, REPOSITORY_ROOT / "CircuitsData_Canopy_Hypercar.xlsx")

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


def test_discovery_requires_explicit_circuit_workbook(tmp_path: Path) -> None:
	(tmp_path / "CircuitsData_Local.xlsx").write_bytes(b"local workbook")
	result = discover_dataset(tmp_path)

	assert result.circuit_workbook is None
	assert any("File > Settings" in item for item in result.diagnostics)
	workbook = tmp_path / "shared" / "CircuitsData_Canopy_Hypercar.xlsx"
	result = discover_dataset(tmp_path, workbook)
	assert result.circuit_workbook == workbook
	assert any("Circuit workbook unavailable" in item for item in result.diagnostics)
	workbook.parent.mkdir()
	workbook.write_bytes(b"configured workbook")
	result = discover_dataset(tmp_path, workbook)
	assert result.circuit_workbook == workbook
	assert not any("workbook" in item.lower() for item in result.diagnostics)


def test_discover_track_temperature_variables() -> None:
	result = discover_dataset(TRACK_TEMP_STUDY)

	assert result.exploration is not None
	assert result.exploration.design_name == "Star"
	assert len(result.variables) == 8
	assert result.variables[0].path == "track.TTrack"
	assert result.variables[0].values[:6] == (25.0, 30.0, 35.0, 40.0, 45.0, 50.0)
	assert not any("No numeric sweep variables" in item for item in result.diagnostics)