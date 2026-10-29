from pathlib import Path

import pytest

from canopy_processor.ui import discover_dataset


REPOSITORY_ROOT = Path(__file__).parents[1]


@pytest.mark.local_data
def test_discover_dataset_finds_sample_sources(sample_exploration) -> None:
	result = discover_dataset(sample_exploration.raw_directory, sample_exploration.workbook)

	assert result.dxpx_directory == sample_exploration.dxpx_directory
	assert result.raw_directory == sample_exploration.raw_directory
	assert result.circuit_workbook == sample_exploration.workbook
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


def test_discover_star_design_variables(tmp_path: Path) -> None:
	raw = tmp_path / "star-study"
	raw.mkdir()
	(raw / "exploration-map.json").write_text(
		'{"designName":"Star","coordinates":[[20,2],[30,2.1],[40,2.2]],"jobNames":[]}',
		encoding="utf-8",
	)
	(raw / "scalar-inputs-metadata.csv").write_text(
		"fullName,units\ntrack.temperature,degC\ntyre.pressure,bar\n", encoding="utf-8"
	)
	(raw / "scalar-inputs.csv").write_text(
		"track.temperature,tyre.pressure\n20,2\n30,2.1\n40,2.2\n", encoding="utf-8"
	)
	(raw / "0").mkdir()
	(raw / "0" / "job-document.json").write_text(
		'{"name":"Sweep 0","data":{"changes":[{"path":"track.temperature","value":20}]}}',
		encoding="utf-8",
	)
	result = discover_dataset(raw)

	assert result.exploration is not None
	assert result.exploration.design_name == "Star"
	assert len(result.variables) == 2
	assert result.variables[0].path == "track.temperature"
	assert result.variables[0].values == (20.0, 30.0, 40.0)
	assert not any("No numeric sweep variables" in item for item in result.diagnostics)