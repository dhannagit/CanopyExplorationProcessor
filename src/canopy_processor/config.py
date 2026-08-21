"""Serializable configuration for a Canopy exploration analysis."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


PLOT_TYPES = {"line", "scatter", "heatmap", "faceted_heatmap", "parallel_coordinates"}
BASELINE_MODES = {"none", "loaded_run", "external_study"}
DELTA_MODES = {"none", "absolute", "percent"}
AXIS_ROLES = {"x", "y", "facet", "color", "unused"}
MASK_OPERATORS = {"and", "or"}
EXPORT_FORMATS = {"svg", "png", "csv", "json"}


@dataclass
class DatasetConfig:
	"""Locations and loading options for one analysis session."""

	dxpx_directory: Path
	raw_directory: Path
	circuit_workbook: Path | None = None
	baseline_path: Path | None = None
	generate_missing_turn_zones: bool = True


@dataclass
class SweepVariableConfig:
	"""A discovered sweep variable selected by the user."""

	path: str
	display_name: str | None = None
	units: str | None = None
	role: str = "unused"
	scale: float = 1.0
	offset: float = 0.0

	def __post_init__(self) -> None:
		if not self.path:
			raise ValueError("Sweep variable path cannot be empty")
		if self.role not in AXIS_ROLES:
			raise ValueError(f"Unknown sweep-variable role: {self.role}")
		if self.scale == 0:
			raise ValueError("Sweep variable scale cannot be zero")

	@property
	def label(self) -> str:
		"""Return the configured label, falling back to the raw path."""

		return self.display_name or self.path


@dataclass
class FilterConfig:
	"""Phase and turn-zone selections used to mask time-series metrics."""

	phases: tuple[str, ...] = ()
	turn_zones: tuple[str, ...] = ()
	phase_operator: str = "or"
	turn_zone_operator: str = "or"
	category_operator: str = "and"

	def __post_init__(self) -> None:
		for name, operator in (
			("phase_operator", self.phase_operator),
			("turn_zone_operator", self.turn_zone_operator),
			("category_operator", self.category_operator),
		):
			if operator not in MASK_OPERATORS:
				raise ValueError(f"Unknown {name}: {operator}")


@dataclass
class BaselineConfig:
	"""Optional baseline and delta-comparison settings."""

	mode: str = "none"
	run_index: int | None = None
	external_path: Path | None = None
	lap_index: int | None = None
	delta_mode: str = "none"

	def __post_init__(self) -> None:
		if self.mode not in BASELINE_MODES:
			raise ValueError(f"Unknown baseline mode: {self.mode}")
		if self.delta_mode not in DELTA_MODES:
			raise ValueError(f"Unknown delta mode: {self.delta_mode}")
		if self.mode == "none" and self.delta_mode != "none":
			raise ValueError("A delta mode requires a baseline")
		if self.mode == "loaded_run" and self.run_index is None:
			raise ValueError("loaded_run baseline requires run_index")
		if self.mode == "external_study" and self.external_path is None:
			raise ValueError("external_study baseline requires external_path")
		if self.lap_index is not None and self.lap_index < 0:
			raise ValueError("lap_index cannot be negative")


@dataclass
class PlotConfig:
	"""Plot family and axis assignments for the analysis result."""

	plot_type: str = "line"
	x_variable: str | None = None
	y_variable: str | None = None
	facet_variables: tuple[str, ...] = ()
	color_variable: str | None = None
	annotate: bool = True

	def __post_init__(self) -> None:
		if self.plot_type not in PLOT_TYPES:
			raise ValueError(f"Unknown plot type: {self.plot_type}")


@dataclass
class ExportConfig:
	"""Output preferences stored with the analysis for reproducibility."""

	output_directory: Path | None = None
	formats: tuple[str, ...] = ("svg", "png", "csv", "json")
	include_configuration: bool = True

	def __post_init__(self) -> None:
		unknown_formats = set(self.formats) - EXPORT_FORMATS
		if unknown_formats:
			raise ValueError(f"Unknown export formats: {sorted(unknown_formats)}")


@dataclass
class AnalysisConfig:
	"""Complete saved state for one exploration analysis."""

	name: str = "Canopy Analysis"
	schema_version: int = 1
	dataset: DatasetConfig | None = None
	sweep_variables: list[SweepVariableConfig] = field(default_factory=list)
	metrics: list[str] = field(default_factory=list)
	filters: FilterConfig = field(default_factory=FilterConfig)
	baseline: BaselineConfig = field(default_factory=BaselineConfig)
	plot: PlotConfig = field(default_factory=PlotConfig)
	export: ExportConfig = field(default_factory=ExportConfig)

	def validate(self) -> None:
		"""Validate relationships that span multiple configuration sections."""

		if self.schema_version != 1:
			raise ValueError(f"Unsupported configuration schema: {self.schema_version}")
		paths = [variable.path for variable in self.sweep_variables]
		if len(paths) != len(set(paths)):
			raise ValueError("Sweep variable paths must be unique")
		if self.plot.x_variable and self.plot.x_variable not in paths:
			raise ValueError("Plot x_variable is not a selected sweep variable")
		if self.plot.y_variable and self.plot.y_variable not in paths:
			raise ValueError("Plot y_variable is not a selected sweep variable")
		if any(variable not in paths for variable in self.plot.facet_variables):
			raise ValueError("Plot facet variable is not a selected sweep variable")
		if self.plot.color_variable and self.plot.color_variable not in paths:
			raise ValueError("Plot color_variable is not a selected sweep variable")

	def to_dict(self) -> dict[str, Any]:
		"""Convert the configuration to JSON-compatible values."""

		self.validate()
		return _json_compatible(asdict(self))

	def save(self, path: str | Path) -> None:
		"""Write this configuration as readable JSON."""

		output_path = Path(path)
		output_path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

	@classmethod
	def from_dict(cls, values: dict[str, Any]) -> "AnalysisConfig":
		"""Construct and validate a configuration from decoded JSON values."""

		data = dict(values)
		dataset_values = data.get("dataset")
		data["dataset"] = _build_dataclass(DatasetConfig, dataset_values) if dataset_values else None
		data["sweep_variables"] = [
			_build_dataclass(SweepVariableConfig, item)
			for item in data.get("sweep_variables", [])
		]
		data["filters"] = _build_dataclass(FilterConfig, data.get("filters", {}))
		data["baseline"] = _build_dataclass(BaselineConfig, data.get("baseline", {}))
		data["plot"] = _build_dataclass(PlotConfig, data.get("plot", {}))
		data["export"] = _build_dataclass(ExportConfig, data.get("export", {}))
		config = cls(**data)
		config.validate()
		return config

	@classmethod
	def load(cls, path: str | Path) -> "AnalysisConfig":
		"""Read, decode, and validate a saved JSON configuration."""

		values = json.loads(Path(path).read_text(encoding="utf-8"))
		if not isinstance(values, dict):
			raise ValueError("Configuration JSON must contain an object")
		return cls.from_dict(values)


def _build_dataclass(model: type[Any], values: dict[str, Any]) -> Any:
	"""Convert path strings and JSON lists before constructing a dataclass."""

	converted = dict(values)
	for field_name in ("dxpx_directory", "raw_directory", "circuit_workbook", "baseline_path", "external_path", "output_directory"):
		if field_name in converted and converted[field_name] is not None:
			converted[field_name] = Path(converted[field_name])
	for field_name in ("phases", "turn_zones", "facet_variables", "formats"):
		if field_name in converted:
			converted[field_name] = tuple(converted[field_name])
	return model(**converted)


def _json_compatible(value: Any) -> Any:
	"""Recursively convert Paths, tuples, and dataclasses into JSON values."""

	if isinstance(value, Path):
		return str(value)
	if isinstance(value, dict):
		return {key: _json_compatible(item) for key, item in value.items()}
	if isinstance(value, (list, tuple)):
		return [_json_compatible(item) for item in value]
	return value
