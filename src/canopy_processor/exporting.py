"""Export rendered figures and analysis results using saved configuration."""

from __future__ import annotations

from pathlib import Path

from matplotlib.figure import Figure

from .config import AnalysisConfig


def export_analysis(
	figure: Figure,
	config: AnalysisConfig,
	*,
	filename: str = "canopy_analysis",
) -> list[Path]:
	"""Export a figure according to ``config.export``.

	SVG and PNG contain the rendered figure. Analysis configuration is saved
	separately through :meth:`AnalysisConfig.save`.
	"""

	config.validate()
	if config.export.output_directory is None:
		raise ValueError("ExportConfig.output_directory is required for export")
	if not filename or Path(filename).name != filename:
		raise ValueError("filename must be a simple file name without a directory")

	output_directory = config.export.output_directory
	output_directory.mkdir(parents=True, exist_ok=True)

	paths: list[Path] = []
	for export_format in config.export.formats:
		output_path = output_directory / f"{filename}.{export_format}"
		if export_format in {"svg", "png"}:
			figure.savefig(output_path, dpi=300, bbox_inches="tight")
		paths.append(output_path)
	return paths
