import json
from pathlib import Path

from canopy_processor import discover_job_variables, load_exploration_definition, load_job_records


def _write_exploration(
    directory: Path,
    *,
    design_name: str,
    variables: tuple[tuple[str, str], ...],
    values: tuple[tuple[float, ...], ...],
    coordinates: list[list[float]],
) -> Path:
    directory.mkdir(parents=True)
    (directory / "exploration-map.json").write_text(
        json.dumps({"designName": design_name, "coordinates": coordinates, "jobNames": []}),
        encoding="utf-8",
    )
    metadata_rows = ["fullName,units", *(f"{name},{unit}" for name, unit in variables)]
    (directory / "scalar-inputs-metadata.csv").write_text("\n".join(metadata_rows), encoding="utf-8")
    headers = [name for name, _ in variables]
    input_rows = [",".join(headers)]
    input_rows.extend(",".join(str(value) for value in row) for row in values)
    (directory / "scalar-inputs.csv").write_text("\n".join(input_rows), encoding="utf-8")
    return directory


def _write_job(directory: Path, index: int, name: str, changes: list[dict]) -> None:
    job_directory = directory / str(index)
    job_directory.mkdir(parents=True, exist_ok=True)
    document = {"name": name, "data": {"state": "successful", "changes": changes}}
    (job_directory / "job-document.json").write_text(json.dumps(document), encoding="utf-8")


def test_load_factorial_exploration_metadata(tmp_path: Path) -> None:
    raw_directory = _write_exploration(
        tmp_path / "factorial-study",
        design_name="Factorial",
        variables=(("setup.front.pressure", "bar"), ("setup.rear.pressure", "bar")),
        values=((1.8, 2.0), (1.9, 2.1)),
        coordinates=[[1.8, 2.0], [1.9, 2.1]],
    )
    definition = load_exploration_definition(raw_directory)

    assert definition.design_name == "Factorial"
    assert [variable.units for variable in definition.variables] == ["bar", "bar"]
    assert definition.variables[0].path == "setup.front.pressure"
    assert definition.variables[0].values == (1.8, 1.9)
    assert len(definition.coordinates) == 2


def test_load_star_exploration_metadata(tmp_path: Path) -> None:
    raw_directory = _write_exploration(
        tmp_path / "star-study",
        design_name="Star",
        variables=(("track.temperature", "degC"), ("tyre.pressure", "bar")),
        values=((20.0, 2.0), (30.0, 2.1), (40.0, 2.2)),
        coordinates=[[20.0, 2.0], [30.0, 2.1], [40.0, 2.2]],
    )
    definition = load_exploration_definition(raw_directory)

    assert definition.design_name == "Star"
    assert len(definition.variables) == 2
    assert definition.coordinates[0] == (20.0, 2.0)
    assert len(definition.coordinates) == 3


def test_discover_variables_from_job_documents(tmp_path: Path) -> None:
    _write_job(tmp_path, 0, "Sweep 0", [{"path": "setup.front.pressure", "value": 1.8}])
    _write_job(tmp_path, 1, "Sweep 1", [{"path": "setup.front.pressure", "value": 1.9}])
    variables = discover_job_variables(tmp_path)

    assert [variable.path for variable in variables] == ["setup.front.pressure"]
    assert variables[0].values == (1.8, 1.9)


def test_post_processor_is_not_classified_as_failed_simulation(tmp_path: Path) -> None:
    _write_job(tmp_path, 0, "Sweep 0", [{"path": "setup.pressure", "value": 1.8}])
    _write_job(tmp_path, 1, "Post Processor", [])
    records = load_job_records(tmp_path)
    post_processors = [record for record in records if record.is_post_processor]

    assert len(records) == 2
    assert [(record.index, record.name) for record in post_processors] == [(1, "Post Processor")]
    assert post_processors[0].state == "successful"
    assert post_processors[0].changes == ()
    assert all(record.is_post_processor or record.name.startswith("Sweep") for record in records)