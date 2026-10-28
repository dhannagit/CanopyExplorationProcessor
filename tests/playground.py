"""Loose interactive scratchpad for exploring the Canopy Exploration Processor package."""

from pathlib import Path
from dataclasses import replace
import tkinter as tk
from tkinter import filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import numpy as np

from canopy_processor import (
    AnalysisConfig,
    DatasetConfig,
    BaselineConfig,
    ExportConfig,
    PlotConfig,
    SweepVariableConfig,
    FilterConfig,
    add_turn_zones,
    default_metrics,
    discover_job_variables,
    evaluate_metric,
    load_dxpx,
    load_dxpx_laps,
    load_exploration_definition,
    load_job_records,
    export_analysis,
    render_plot_data,
)
from canopy_processor.ui.discovery import discover_dataset
from canopy_processor.ui.pipeline import load_dataset, prepare_turn_zones, analyze_loaded_dataset


def _lap_label(index: int, lap) -> str:
    lap_number_field = lap.data.get("NLap")
    lap_number = int(np.asarray(lap_number_field).reshape(-1)[0]) if lap_number_field is not None else index + 1
    lap_time_field = lap.data.get("tLapEnd")
    lap_time = f"{float(np.asarray(lap_time_field).reshape(-1)[0]):.3f}s" if lap_time_field is not None else "unknown"
    return f"Lap {lap_number} - {lap_time}"


def _prompt_lap_indices(parent: tk.Tk, laps: list) -> tuple[int, ...]:
    """Show a multi-select listbox of laps and return the chosen indices."""

    dialog = tk.Toplevel(parent)
    dialog.title("Select Baseline Laps")
    dialog.grab_set()
    tk.Label(dialog, text="Select one or more laps to combine as the baseline:").pack(padx=10, pady=(10, 0))
    listbox = tk.Listbox(dialog, selectmode=tk.MULTIPLE, exportselection=False, width=40, height=min(15, len(laps)))
    for index, lap in enumerate(laps):
        listbox.insert(tk.END, _lap_label(index, lap))
    listbox.pack(padx=10, pady=10)

    selected: list[int] = []

    def on_ok() -> None:
        selected.extend(listbox.curselection())
        dialog.destroy()

    tk.Button(dialog, text="OK", command=on_ok).pack(pady=(0, 10))
    dialog.wait_window()
    return tuple(selected)


root = tk.Tk()
root.withdraw()

try:
    raw_directory = filedialog.askdirectory(
        parent=root,
        title="Select the raw directory containing Canopy simulation exploration data",
    )
    if not raw_directory:
        raise RuntimeError("No raw directory selected.")

    dxpx_directory = filedialog.askdirectory(
        parent=root,
        title="Select the dXpx file directory",
    )
    if not dxpx_directory:
        raise RuntimeError("No dXpx directory selected.")

    dxpx_files = sorted(Path(dxpx_directory).rglob("*.dXpx"))
    if not dxpx_files:
        raise FileNotFoundError(f"No .dXpx files found below: {dxpx_directory}")

    baseline_file = filedialog.askopenfilename(
        parent=root,
        title="Select the baseline .dXpx file",
        filetypes=[("DXPX files", "*.dXpx")],
    )
    if not baseline_file:
        raise RuntimeError("No baseline .dXpx file selected.")

    baseline_run = load_dxpx_laps(baseline_file)

    # Load one run as a convenient starting point for interactive exploration.
    run = load_dxpx(dxpx_files[0])
    print(f"Loaded: {run.path}")
    print(f"Track: {run.track_name}")
    print(f"Data fields: {len(run.data)}")

    print("\nAvailable data fields:")
    for key in run.data:
        print(key)

    for name in [
        "sLap",
        "gCarPotential",
        "FxTyreFL_filt",
        "TTyreSurfaceFL",
    ]:
        if name not in run.data:
            print(f"{name}: not present")
            continue
        value = np.asarray(run.data[name])
        print(
            f"{name}: shape={value.shape}, dtype={value.dtype}, "
            f"min={np.nanmin(value)}, max={np.nanmax(value)}"
        )

    circuit_data_path = filedialog.askopenfilename(
        parent=root,
        title="Select the circuit data file",
        filetypes=[("Excel files", "*.xlsx")],
    )
    if not circuit_data_path:
        raise RuntimeError("No circuit data file selected.")

    run_with_turn_zones = add_turn_zones(run, circuit_data_path)
    print(f"\nTurn zones: {run_with_turn_zones.turn_zone_names}")
    if "isTurnZone1" in run_with_turn_zones.data:
        zone = np.asarray(run_with_turn_zones.data["isTurnZone1"])
        print(f"Turn zone 1 samples: {zone.sum()} / {zone.size}")

    # Load every run so results can be joined across the full sweep.
    runs = [add_turn_zones(load_dxpx(path), circuit_data_path) for path in dxpx_files]
    print(f"\nLoaded {len(runs)} runs for sweep-wide analysis")

    definition = load_exploration_definition(raw_directory)
    job_variables = discover_job_variables(raw_directory)
    job_records = load_job_records(raw_directory)

    print(f"\nExploration: {definition.design_name}")
    for variable in definition.variables:
        print(f"Variable: {variable.path}, Units: {variable.units}")

    for record in job_records:
        print(
            f"Job {record.index}: {record.name}, state={record.state}, "
            f"post_processor={record.is_post_processor}"
        )

    for variable in job_variables:
        print(f"Job variable: {variable.path}, values={variable.values}")

    metrics = default_metrics()
    print(f"\nAvailable metrics: {list(metrics)}")

    grip = metrics["gCarPotential"].evaluate(run_with_turn_zones)
    print(f"Mean Grip: {np.nanmean(grip)}")

    fx_front = metrics["FxFront"].evaluate(run_with_turn_zones)
    print(f"Mean Front Fx: {np.nanmean(fx_front)}")

    for name in metrics:
        result = evaluate_metric(metrics, name, run_with_turn_zones)
        print(f"Metric: {name}, shape={result.shape}, mean={np.nanmean(result)}")

    lap_indices = (0,) if len(baseline_run) == 1 else _prompt_lap_indices(root, baseline_run)
    if not lap_indices:
        raise RuntimeError("No baseline laps selected.")

    output_directory = filedialog.askdirectory(
        parent=root,
        title="Select the analysis export directory",
    )
    if not output_directory:
        raise RuntimeError("No analysis export directory selected.")

    config = AnalysisConfig(
        dataset=DatasetConfig(
            dxpx_directory=Path(dxpx_directory),
            raw_directory=Path(raw_directory),
            circuit_workbook=Path(circuit_data_path),
            track_name=run.track_name,
        ),
        baseline=BaselineConfig(
            mode="external_study",
            external_path=Path(baseline_file),
            lap_indices=lap_indices,
            delta_mode="absolute"
        ),
        export=ExportConfig(
            output_directory=Path(output_directory),
        ),
        sweep_variables=[
            SweepVariableConfig(
                path="car.tyres.front.INITIAL_CONDITIONS.InfPress",
                units="bar",
                display_name="Front Tyre Pressure",
                role="x",
            ),
            SweepVariableConfig(
                path="car.tyres.rear.INITIAL_CONDITIONS.InfPress",
                units="bar",
                display_name="Rear Tyre Pressure",
                role="y",
            ),
        ],
        metric="gCarPotential",
        plot=PlotConfig(plot_type="heatmap"),
        filters=FilterConfig(phases=("isApex",))
    )

    config.validate()
    print("\nConfiguration is valid:")
    print(config.to_dict())

    save_path = filedialog.asksaveasfilename(
        parent=root,
        title="Save Analysis Configuration",
        defaultextension=".json",
        filetypes=[("JSON files", "*.json")],
    )
    if save_path:
        config.save(save_path)
        print(f"Saved configuration: {save_path}")

    load_path = filedialog.askopenfilename(
        parent=root,
        title="Load Analysis Configuration",
        filetypes=[("JSON files", "*.json")],
    )
    if load_path:
        config = AnalysisConfig.load(load_path)
        print(f"Loaded configuration: {config.name}\n")

    discovery = discover_dataset(config.dataset.raw_directory, config.dataset.circuit_workbook)
    discovery = replace(discovery, dxpx_directory=config.dataset.dxpx_directory)
    loaded = load_dataset(discovery)
    if config.filters.turn_zones:
        from tkinter import messagebox
        if not messagebox.askyesno("Confirm circuit", f"Generate turn zones for {config.dataset.track_name}?", parent=root):
            raise RuntimeError("Circuit confirmation cancelled")
        loaded = prepare_turn_zones(loaded, config.dataset.circuit_workbook, config.dataset.track_name)
        config.dataset.confirmed_header_track = loaded.runs[0].track_name
    output = analyze_loaded_dataset(loaded, config, discovery.variables)
    rendered = render_plot_data(
        output.plot_data,
        scatter=config.plot.plot_type == "scatter",
        annotate=config.plot.annotate,
        labels={variable.path: variable.label for variable in config.sweep_variables},
    )
    plot_window = tk.Toplevel(root)
    plot_window.title(config.name)
    canvas = FigureCanvasTkAgg(rendered, master=plot_window)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    if config.export.output_directory and config.export.formats:
        for path in export_analysis(rendered, config, filename="analysis"):
            print(f"Exported: {path}")
    root.wait_window(plot_window)

finally:
    root.destroy()