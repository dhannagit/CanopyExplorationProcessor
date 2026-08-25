"""Core loading and normalization utilities for Canopy explorations."""

from .dxpx import DXPXLoadError, DXPXRun, load_dxpx
from .config import (
	AnalysisConfig,
	BaselineConfig,
	DatasetConfig,
	ExportConfig,
	FilterConfig,
	PlotConfig,
	SweepVariableConfig,
)
from .analysis import (
	MetricResult,
	analyze_metric,
	analyze_runs,
	build_filter_mask,
	reduce_signal,
)
from .exploration import (
	ExplorationDefinition,
	JobRecord,
	SweepVariable,
	discover_job_variables,
	load_job_records,
	load_exploration_definition,
)
from .metric import Metric, average_metric, default_metrics, evaluate_metric, source_metric
from .results import AnalysisRow, join_sweep_variables, run_index
from .turn_zones import TurnZoneError, add_turn_zones

__all__ = [
	"DXPXLoadError",
	"DXPXRun",
	"AnalysisConfig",
	"AnalysisRow",
	"MetricResult",
	"BaselineConfig",
	"DatasetConfig",
	"ExportConfig",
	"FilterConfig",
	"ExplorationDefinition",
	"JobRecord",
	"Metric",
	"PlotConfig",
	"SweepVariable",
	"SweepVariableConfig",
	"TurnZoneError",
	"add_turn_zones",
	"analyze_metric",
	"analyze_runs",
	"average_metric",
	"default_metrics",
	"build_filter_mask",
	"discover_job_variables",
	"evaluate_metric",
	"join_sweep_variables",
	"load_job_records",
	"load_exploration_definition",
	"load_dxpx",
	"reduce_signal",
	"run_index",
	"source_metric",
]