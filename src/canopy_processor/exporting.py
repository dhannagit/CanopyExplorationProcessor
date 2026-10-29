"""Export rendered figures and analysis results using saved configuration."""

from __future__ import annotations

from pathlib import Path
from copy import deepcopy

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from .config import AnalysisConfig, EXPORT_ASPECT_RATIOS


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
	export_figure = figure
	ratio = EXPORT_ASPECT_RATIOS[config.export.aspect_ratio]
	if ratio is not None:
		export_figure = deepcopy(figure)
		FigureCanvasAgg(export_figure)
		width, height = figure.get_size_inches()
		if width / height > ratio:
			width = height * ratio
		else:
			height = width / ratio
		export_figure.set_size_inches(width, height, forward=False)
		layout = export_figure.get_layout_engine()
		if layout is not None:
			layout.execute(export_figure)
		else:
			export_figure.tight_layout()

	paths: list[Path] = []
	for export_format in config.export.formats:
		output_path = output_directory / f"{filename}.{export_format}"
		if export_format in {"svg", "png"}:
			export_figure.savefig(
				output_path, dpi=300,
				bbox_inches="tight" if ratio is None else export_figure.bbox_inches.frozen(),
			)
		paths.append(output_path)
	return paths
