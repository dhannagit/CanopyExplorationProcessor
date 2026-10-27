"""Serializable configuration for a Canopy exploration analysis."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


PLOT_TYPES = {"suggested", "line", "scatter", "heatmap", "faceted_heatmap", "parallel_coordinates"}
BASELINE_MODES = {"none", "loaded_run", "external_study"}
DELTA_MODES = {"none", "absolute", "percent"}
AXIS_ROLES = {"x", "y", "facet", "color", "unused"}
MASK_OPERATORS = {"and", "or"}
EXPORT_FORMATS = {"svg", "png"}


@dataclass
class DatasetConfig:
	"""Locations and loading options for one analysis session."""

	dxpx_directory: Path | None = None
	raw_directory: Path | None = None
	circuit_workbook: Path | None = None
	track_name: str | None = None
	confirmed_header_track: str | None = None
	confirmed_workbook_digest: str | None = None

	def __post_init__(self) -> None:
		for name in ("dxpx_directory", "raw_directory", "circuit_workbook"):
			value = getattr(self, name)
			if value is not None and not isinstance(value, Path):
				raise ValueError(f"{name} must be a Path or null")
		for name in ("track_name", "confirmed_header_track", "confirmed_workbook_digest"):
			value = getattr(self, name)
			if value is not None and (not isinstance(value, str) or not value):
				raise ValueError(f"{name} must be nonempty text or null")


@dataclass
class SweepVariableConfig:
	"""A discovered sweep variable selected by the user."""

	path: str
	display_name: str | None = None
	units: str | None = None
	role: str = "unused"

	def __post_init__(self) -> None:
		if not isinstance(self.path, str) or not self.path:
			raise ValueError("Sweep variable path cannot be empty")
		for value in (self.display_name, self.units):
			if value is not None and not isinstance(value, str):
				raise ValueError("Display name and units must be text or null")
		if self.role not in AXIS_ROLES:
			raise ValueError(f"Unknown sweep-variable role: {self.role}")

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
		for values in (self.phases, self.turn_zones):
			if not isinstance(values, (tuple, list)) or any(not isinstance(value, str) or not value for value in values):
				raise ValueError("Filter selections must be arrays of nonempty identifiers")
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
	lap_indices: tuple[int, ...] = ()
	delta_mode: str = "none"

	def __post_init__(self) -> None:
		if self.mode not in BASELINE_MODES:
			raise ValueError(f"Unknown baseline mode: {self.mode}")
		if self.delta_mode not in DELTA_MODES:
			raise ValueError(f"Unknown delta mode: {self.delta_mode}")
		if self.run_index is not None and (type(self.run_index) is not int or self.run_index < 0):
			raise ValueError("run_index must be a nonnegative integer")
		if any(type(index) is not int for index in self.lap_indices):
			raise ValueError("lap_indices must contain integers")
		if any(index < 0 for index in self.lap_indices):
			raise ValueError("lap_indices cannot contain negative values")


@dataclass
class PlotConfig:
	"""Saved plot intent; variable roles own all axis assignments."""

	plot_type: str = "suggested"
	annotate: bool = True

	def __post_init__(self) -> None:
		if self.plot_type not in PLOT_TYPES:
			raise ValueError(f"Unknown plot type: {self.plot_type}")
		if type(self.annotate) is not bool:
			raise ValueError("annotate must be a boolean")


@dataclass
class ExportConfig:
	"""Output preferences stored with the analysis for reproducibility."""

	output_directory: Path | None = None
	formats: tuple[str, ...] = ("svg", "png")

	def __post_init__(self) -> None:
		unknown_formats = set(self.formats) - EXPORT_FORMATS
		if unknown_formats:
			raise ValueError(f"Unknown export formats: {sorted(unknown_formats)}")


@dataclass
class AnalysisConfig:
	"""Complete saved state for one exploration analysis."""

	name: str = "Canopy Analysis"
	schema_version: int = 2
	dataset: DatasetConfig | None = None
	sweep_variables: list[SweepVariableConfig] = field(default_factory=list)
	metric: str | None = None
	filters: FilterConfig = field(default_factory=FilterConfig)
	baseline: BaselineConfig = field(default_factory=BaselineConfig)
	plot: PlotConfig = field(default_factory=PlotConfig)
	export: ExportConfig = field(default_factory=ExportConfig)

	def validate(self) -> None:
		"""Validate relationships that span multiple configuration sections."""

		if type(self.schema_version) is not int or self.schema_version != 2:
			raise ValueError(f"Unsupported configuration schema: {self.schema_version}")
		if not isinstance(self.name, str):
			raise ValueError("Analysis name must be text")
		if self.metric is not None and (not isinstance(self.metric, str) or not self.metric):
			raise ValueError("Metric must be a nonempty identifier or null")
		if self.dataset is not None:
			self.dataset.__post_init__()
		self.filters.__post_init__()
		self.baseline.__post_init__()
		self.plot.__post_init__()
		self.export.__post_init__()
		for variable in self.sweep_variables:
			variable.__post_init__()
		paths = [variable.path for variable in self.sweep_variables]
		if len(paths) != len(set(paths)):
			raise ValueError("Sweep variable paths must be unique")

	def validate_ready(self) -> None:
		"""Validate complete analysis inputs without rejecting saveable drafts."""

		self.validate()
		if self.dataset is None or not self.dataset.raw_directory or not self.dataset.dxpx_directory:
			raise ValueError("Select raw and DXPX study directories")
		if not self.metric:
			raise ValueError("Select a metric before analysis")
		if not self.sweep_variables:
			raise ValueError("Confirm at least one sweep variable")
		roles = [variable.role for variable in self.sweep_variables]
		for role in ("x", "y", "color"):
			if roles.count(role) > 1:
				raise ValueError(f"Assign at most one variable to the {role} role")
		plot_type = self.plot.plot_type
		if plot_type != "parallel_coordinates" and "x" not in roles:
			raise ValueError("Assign one selected variable to the x role")
		if plot_type in {"heatmap", "faceted_heatmap"} and "y" not in roles:
			raise ValueError("Heatmaps require a y role")
		if plot_type == "faceted_heatmap" and "facet" not in roles:
			raise ValueError("Faceted heatmaps require a facet role")
		if self.baseline.mode == "loaded_run" and self.baseline.run_index is None:
			raise ValueError("Select a loaded baseline run")
		if self.baseline.mode == "external_study" and not self.baseline.external_path:
			raise ValueError("Select an external baseline file")

	def to_dict(self) -> dict[str, Any]:
		"""Convert the configuration to JSON-compatible values."""

		self.validate()
		return _json_compatible(asdict(self))

	def save(self, path: str | Path) -> None:
		"""Atomically replace a readable JSON recipe without damaging an existing file."""

		output_path = Path(path)
		content = json.dumps(self.to_dict(), indent=2) + "\n"
		temporary_path: Path | None = None
		try:
			with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output_path.parent, delete=False) as temporary:
				temporary_path = Path(temporary.name)
				temporary.write(content)
			os.replace(temporary_path, output_path)
		finally:
			if temporary_path is not None:
				temporary_path.unlink(missing_ok=True)

	@classmethod
	def from_dict(cls, values: dict[str, Any]) -> "AnalysisConfig":
		"""Construct and validate a configuration from decoded JSON values."""

		if not isinstance(values, dict):
			raise ValueError("Configuration must contain an object")
		data = dict(values)
		dataset_values = data.get("dataset")
		data["dataset"] = _build_dataclass(DatasetConfig, dataset_values) if dataset_values is not None else None
		if not isinstance(data.get("sweep_variables", []), list):
			raise ValueError("sweep_variables must be an array")
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
		config = cls.from_dict(values)
		base = Path(path).resolve().parent
		for model in (config.dataset, config.baseline, config.export):
			if model is not None:
				for key, value in vars(model).items():
					if isinstance(value, Path) and not value.is_absolute():
						setattr(model, key, (base / value).resolve())
		return config


def _build_dataclass(model: type[Any], values: dict[str, Any]) -> Any:
	"""Convert path strings and JSON lists before constructing a dataclass."""

	if not isinstance(values, dict):
		raise ValueError(f"{model.__name__} must contain an object")
	converted = dict(values)
	for field_name in ("dxpx_directory", "raw_directory", "circuit_workbook", "external_path", "output_directory"):
		if field_name in converted and converted[field_name] is not None:
			converted[field_name] = Path(converted[field_name])
	for field_name in ("phases", "turn_zones", "formats", "lap_indices"):
		if field_name in converted:
			if not isinstance(converted[field_name], (list, tuple)):
				raise ValueError(f"{field_name} must be an array")
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
