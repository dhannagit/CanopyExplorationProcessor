"""Per-user locations for externally maintained circuit resources."""

from pathlib import Path

from PySide6.QtCore import QSettings

from ..turn_zones import list_circuit_names


RESOURCE_DIRECTORY_KEY = "paths/circuit_resource_dir"
WORKBOOK_FILENAME = "CircuitsData_Canopy_Hypercar.xlsx"


def create_settings() -> QSettings:
	return QSettings("canopy-exploration-processor", "canopy-exploration-ui")


def circuit_workbook(resource_directory: str) -> Path | None:
	directory = resource_directory.strip()
	return Path(directory).expanduser().resolve() / WORKBOOK_FILENAME if directory else None


def validate_resource_directory(resource_directory: str) -> None:
	workbook = circuit_workbook(resource_directory)
	if workbook is not None and not list_circuit_names(workbook):
		raise ValueError("The circuit workbook's Turns sheet contains no circuit names")