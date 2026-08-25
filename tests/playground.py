"""Loose interactive scratchpad for exploring the Canopy processor package."""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog

import numpy as np

from canopy_processor import (
    AnalysisConfig,
    DatasetConfig,
    PlotConfig,
    SweepVariableConfig,
    FilterConfig,
    add_turn_zones,
    default_metrics,
    discover_job_variables,
    evaluate_metric,
    load_dxpx,
    load_exploration_definition,
    load_job_records,
    analyze_runs,
    analyze_metric,
    join_sweep_variables
)


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

    # Join reduced metric results back to their sweep-variable coordinates.
    filters = FilterConfig(phases=("isApex",))
    grip_results = analyze_runs(runs, metrics["gCarPotential"], filters, method="mean")
    rows = join_sweep_variables(runs, grip_results, job_variables)
    for row in rows:
        print(
            f"Run {row.run_index}: {row.sweep_values} -> "
            f"{row.metric_result.method} {row.metric_result.metric_name}="
            f"{row.metric_result.value:.4f}"
        )

    config = AnalysisConfig(
        dataset=DatasetConfig(
            dxpx_directory=Path(dxpx_directory),
            raw_directory=Path(raw_directory),
            circuit_workbook=Path(circuit_data_path),
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

    results = analyze_runs(
        runs=[run_with_turn_zones],
        metric=metrics["gCarPotential"],
        filters=filters,
        method="mean",
    )

    for result in results:
        print(
            f"Run: {run_with_turn_zones.path}, Metric: {result.metric_name}, "
            f"Mean: {result.value}, Samples: {result.selected_samples}"
        )
finally:
    root.destroy()