"""Loose interactive scratchpad for exploring the Canopy processor package."""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import numpy as np

from canopy_processor import (
    AnalysisConfig,
    DatasetConfig,
    BaselineConfig,
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
    analyze_runs,
    analyze_baseline,
    analyze_metric,
    join_sweep_variables,
    resolve_baseline_laps,
    compare_rows_to_baseline,
    build_grid,
    build_heatmap_data,
    render_line,
    render_parallel_coordinates,
    render_heatmap,
    render_faceted_heatmap
)


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
        title="Select the raw directory containing Canopy exploration data",
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

    config = AnalysisConfig(
        dataset=DatasetConfig(
            dxpx_directory=Path(dxpx_directory),
            raw_directory=Path(raw_directory),
            circuit_workbook=Path(circuit_data_path),
        ),
        baseline=BaselineConfig(
            mode="external_study",
            external_path=Path(baseline_file),
            lap_indices=lap_indices,
            delta_mode="absolute"
        ),
        sweep_variables=[
            SweepVariableConfig(
                path="car.tyres.front.INITIAL_CONDITIONS.InfPress",
                units="bar",
                display_name="Front Tyre Pressure",
                role="x",
            )
        ],
        metrics=["gCarPotential"],
        plot=PlotConfig(
            plot_type="line",
            x_variable="car.tyres.front.INITIAL_CONDITIONS.InfPress",
        ),
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
        loaded_config = AnalysisConfig.load(load_path)
        print(f"Loaded configuration: {loaded_config.name}\n")

    filters = config.filters


    # Join reduced metric results back to their sweep-variable coordinates and compare to baseline.
    filters = FilterConfig(phases=("isApex",))
    grip_results = analyze_runs(runs, metrics["gCarPotential"], filters, method="mean")
    rows = join_sweep_variables(runs, grip_results, job_variables)
    laps = resolve_baseline_laps(config.baseline)
    baseline_grip = analyze_baseline(laps, metrics["gCarPotential"], filters, method="mean")
    compared = compare_rows_to_baseline(rows, baseline_grip, delta_mode=config.baseline.delta_mode)
    for (row, comparison) in zip(rows, compared):
        print(
            f"Run {row.run_index}: {row.sweep_values} -> "
            f"{row.metric_result.method} {row.metric_result.metric_name}= "
            f"{row.metric_result.value:.4f} "
            f"{comparison.delta_mode} difference = {comparison.delta:.4f}"
        )

    grid = build_grid(
        rows,
        variable_paths=(
            "car.tyres.front.INITIAL_CONDITIONS.InfPress",
            "car.tyres.rear.INITIAL_CONDITIONS.InfPress",
        ),
    )
    heatmap_data = build_heatmap_data(
        grid.points,
        x_variable="car.tyres.rear.INITIAL_CONDITIONS.InfPress",
        y_variable="car.tyres.front.INITIAL_CONDITIONS.InfPress",
    )
    print(
        f"\nHeatmap: x={heatmap_data.x_variable}, "
        f"y={heatmap_data.y_variable}, shape={heatmap_data.values.shape}"
    )
    print(f"Heatmap x values: {heatmap_data.x_values}")
    print(f"Heatmap y values: {heatmap_data.y_values}")
    print(f"Missing heatmap cells: {np.isnan(heatmap_data.values).sum()}")

    rendered_heatmap = render_heatmap(heatmap_data)
    plot_window = tk.Toplevel(root)
    plot_window.title("Grip Heatmap")
    canvas = FigureCanvasTkAgg(rendered_heatmap, master=plot_window)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    plot_window.protocol("WM_DELETE_WINDOW", plot_window.destroy)
    plot_window.mainloop()
finally:
    root.destroy()