from pathlib import Path

from canopy_processor import discover_job_variables, load_exploration_definition, load_job_records


RAW_DIRECTORY = Path(__file__).parents[1] / "DATA_Raw" / "MOS_COR_TyrePressureExploration"


def test_load_canopy_exploration_metadata() -> None:
    definition = load_exploration_definition(RAW_DIRECTORY)

    assert definition.design_name == "Factorial"
    assert [variable.units for variable in definition.variables] == ["bar", "bar"]
    assert definition.variables[0].path.endswith("front.INITIAL_CONDITIONS.InfPress")
    assert definition.variables[0].values == (1.8, 1.85, 1.9, 1.95, 2.0, 1.8, 1.85, 1.9, 1.95, 2.0, 1.8, 1.85, 1.9, 1.95, 2.0, 1.8, 1.85, 1.9, 1.95, 2.0, 1.8, 1.85, 1.9, 1.95, 2.0)
    assert len(definition.coordinates) == 25


def test_discover_variables_from_job_documents() -> None:
    variables = discover_job_variables(RAW_DIRECTORY)

    assert {variable.path for variable in variables} == {
        "car.tyres.front.INITIAL_CONDITIONS.InfPress",
        "car.tyres.rear.INITIAL_CONDITIONS.InfPress",
    }
    assert all(len(variable.values) == 26 for variable in variables)


def test_post_processor_is_not_classified_as_failed_simulation() -> None:
    records = load_job_records(RAW_DIRECTORY)
    post_processors = [record for record in records if record.is_post_processor]

    assert len(records) == 26
    assert [(record.index, record.name) for record in post_processors] == [(25, "Post Processor")]
    assert post_processors[0].state == "successful"
    assert post_processors[0].changes == ()
    assert all(record.is_post_processor or record.name.startswith("Factorial") for record in records)