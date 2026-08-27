# Canopy Exploration Processor Build Log

This is the chronological engineering record for the Python migration. Keep entries concise and factual. Each entry should capture what changed, why it changed, how it was verified, and what comes next.

## Entry Format

```markdown
## YYYY-MM-DD - Short milestone title

**Goal:** What problem or capability this work addressed.

**Changed:** Files, modules, or user-visible behavior changed.

**Decisions:** Important choices made and alternatives rejected.

**Evidence:** Tests, sample data, measurements, or screenshots.

**Next:** The next concrete milestone.
```

## 2026-08-17 - Project foundation

**Goal:** Start the exploration-agnostic Python migration from the three MATLAB analysis scripts.

**Changed:** Added the Python project metadata in `pyproject.toml`, a `src/canopy_processor` package, a native `.dxpx` loader, exploration metadata discovery, job-document classification, and initial tests.

**Decisions:** Treat `.dxpx` files as MATLAB Level-5 MAT files; prefer Canopy's `exploration-map.json` and scalar input metadata for sweep definitions; preserve numeric run-folder alignment; classify the extra successful `Post Processor` job separately from simulation failures.

**Evidence:** The sample `.dxpx` contains a top-level `D` struct with `Header` and `Data`; the sample has 26 numbered jobs, 25 simulation `.dxpx` files, and one post-processor job. The test suite passes with 6 tests.

**Next:** Implement normalized metrics, filtering, baseline comparison, and reduction independent of the GUI.

## 2026-08-17 - Add metric framework

**Goal:** Give the analysis layer a reusable contract for source and derived performance metrics.

**Changed:** Added `src/canopy_processor/metric.py` with `Metric`, `source_metric`, `average_metric`, `default_metrics`, and `evaluate_metric`. Added real-sample tests for front-force derivation and the current metric catalog.

**Decisions:** Metrics evaluate one `DXPXRun` into a scalar or time-series NumPy array. Filtering and plotting remain outside the metric registry. Derived axle forces average source tyre signals elementwise; Fy metrics preserve the MATLAB absolute-value policy.

**Evidence:** The focused metric tests pass with 2 tests against the sample `.dxpx` file.

**Next:** Add the independent filtering and reduction engine, including phase and turn-zone masks.

## 2026-08-21 - Add analysis configuration

**Goal:** Create a saved, reproducible representation of one configured analysis.

**Changed:** Added dataclass-based configuration models in `src/canopy_processor/config.py` for dataset paths, sweep-variable roles and transforms, metrics, phase/turn-zone filters, baselines, plot settings, and export settings. Added JSON save/load support and public package exports. Added focused configuration tests.

**Decisions:** Use standard-library dataclasses and readable JSON. Store paths as `Path` objects in Python and convert them during serialization. Keep configuration limited to selections and settings; loaded time-series data remains the responsibility of the data layer. Validate cross-section relationships such as plot axes referring to selected sweep variables.

**Evidence:** Configuration round-trip, baseline validation, and plot-axis validation pass. Full test suite passes with 11 tests.

**Next:** Implement the independent filtering and reduction engine using the metric and filter configuration models.

## 2026-08-21 - Add playground.py for interactive function testing

**Goal:** Create a script for the users/developers to explore functions and interactively test scripts developed by Github Co-Pilot and other developers

**Changed:** Added `tests/playground.py` as a lightweight top-level scratchpad. It uses Tkinter file dialogs to select the raw exploration directory, `.dXpx` directory, and circuit workbook; loads one representative run; prints signal, turn-zone, exploration-variable, job, metric, and configuration information; and optionally saves and reloads an analysis configuration. It also handles cancellation, discovers `.dXpx` files recursively, reports missing summary signals, and cleans up the Tk root.

**Decisions:** Keep this as a loose developer playground rather than a production GUI, reusable application module, or automated test. Use the first discovered `.dXpx` only as a convenient starting point; the full run-loading and analysis workflow will be implemented separately. Keep exploratory expressions and print statements easy to edit as new functions are added.

**Evidence:** `tests/playground.py` compiles successfully with `python -m py_compile tests/playground.py`, and the editor reports no errors. The interactive flow has not been automated because it requires Tkinter dialogs and user-selected paths.

**Next:** Use the playground to inspect the sample data while implementing the analysis/reduction engine, then add non-interactive tests for any behavior discovered here.

## 2026-08-21 - Add analysis and reduction engine

**Goal:** Convert evaluated metric signals into filtered, one-value-per-run analysis results independently of the GUI and plotting layers.

**Changed:** Added `src/canopy_processor/analysis.py` with `MetricResult`, `build_filter_mask`, `reduce_signal`, `analyze_metric`, and `analyze_runs`. The module supports phase and turn-zone mask selection, configurable AND/OR combinations, NaN-aware mean/median/minimum/maximum/peak reductions, scalar metrics, and sample-count diagnostics. Added focused analysis tests and public package exports.

**Decisions:** Empty filter categories mean no restriction. Operators combine selections within each category, then combine phase and turn-zone categories. Scalar metrics bypass time-series masks. Baseline comparison, sweep-value joins, duplicate handling, and plotting remain separate future layers.

**Evidence:** Synthetic mask tests and real-sample turn-zone/metric tests pass. Full test suite passes with 14 tests and no editor diagnostics in the changed analysis files.

**Next:** Build a normalized multi-run result table that joins `MetricResult` values with discovered sweep-variable values, then add explicit baseline comparison.

## 2026-08-25 - Join metric results to sweep-variable values

**Goal:** Combine each run's reduced metric value with the sweep-variable values that produced it.

**Changed:** Added `src/canopy_processor/results.py` with `AnalysisRow`, `run_index`, and `join_sweep_variables`. This was first added to `analysis.py`, then moved out: `analysis.py` reduces one run's metric to one value, while joining reduced results across many runs to sweep-variable coordinates is the distinct concern the original implementation plan called a separate "N-dimensional table" step. `analysis.py` no longer imports `exploration.py`. Moved the corresponding tests to `tests/test_results.py`. Updated `tests/playground.py` to load every run in the sweep and print joined sweep-value/metric rows instead of a manual zip.

**Decisions:** Join by numbered folder index, matching how `discover_job_variables` indexes its arrays, instead of relying on list order. Raise a clear error for non-numbered run folders or out-of-range sweep-variable values rather than silently misaligning results. Keep `results.py` as the place duplicate-point aggregation, missing-cell diagnostics, and baseline deltas will be added, so `analysis.py` stays limited to single-run filtering and reduction.

**Evidence:** Focused and full test suites pass with 18 tests. Playground compiles with `python -m py_compile`.

**Next:** Add baseline comparison (absolute/percent delta) using the existing `BaselineConfig` and the joined result rows in `results.py`.

## 2026-08-25 - Add baseline comparison

**Goal:** Compare each sweep run's reduced metric value against a baseline, supporting no baseline, a loaded sweep run, or an external multi-lap study.

**Changed:** Added `load_dxpx_laps` to `dxpx.py` so a `.dxpx` file can hold either a single lap (sweep runs) or a MATLAB struct array of laps (confirmed against `BaselineExample`, which has 11 laps); `load_dxpx` now rejects multi-lap files with a clear error instead of silently reading the first lap. Renamed `BaselineConfig.lap_index` to `lap_indices: tuple[int, ...]` (zero-based) so multiple laps can be selected and pooled. Added to `results.py`: `BaselineResult`, `ComparedRow`, `resolve_baseline_laps` (looks up a loaded run by `run_index` or loads/selects laps from an external file), `analyze_baseline` (pools selected laps' filtered samples into one reduction, not an average of averages), and `compute_delta`/`compare_rows_to_baseline` for absolute/percent deltas. Added tests for multi-lap loading and every baseline function.

**Decisions:** Multiple selected baseline laps are combined by pooling their filtered samples before reducing once, per your answer, rather than averaging per-lap results. Baseline laps must already carry turn-zone fields if the filter needs them, matching how `analyze_metric` already expects sweep runs to be prepared. A zero or NaN baseline (or NaN value) produces `nan` with `baseline_valid=False` instead of raising or dividing by zero, per your answer. Baseline filtering and turn-zone preparation should match the metric's, per your answers.

**Evidence:** Full test suite passes with 29 tests, including a real 11-lap `BaselineExample` file and the real sweep sample.

**Next:** Wire `resolve_baseline_laps`/`analyze_baseline`/`compare_rows_to_baseline` into a full playground example, then add duplicate-point and missing-cell handling for multi-dimensional sweeps.

## 2026-08-25 - Add missing-run and duplicate-point grid diagnostics

**Goal:** Stop `join_sweep_variables` results from silently hiding failed/missing jobs or overwriting duplicate sweep points, matching the original MATLAB scripts' known defects here.

**Changed:** Added to `results.py`: `find_missing_runs(job_records, rows)`, which reports simulation job indices (excluding the post-processor job) that produced no analyzed row, so a failed job is visible instead of just absent; and `build_grid(rows, variable_paths=None, duplicate_method="mean")`, which groups rows by sweep coordinate and combines duplicates using `mean`/`median`/`first`/`last`, or raises with `error` for cases that must be reviewed manually. Rows whose coordinate contains NaN (e.g. a sweep value the job-document never reported) are returned separately as `GridResult.incomplete_rows` instead of being silently placed or dropped. Added `GridPoint`/`GridResult` dataclasses and tests for missing jobs, duplicate aggregation, the `error` method, and NaN coordinates.

**Decisions:** Default duplicate aggregation is `mean` over the duplicate rows' already-reduced values (not re-pooling raw samples, since `analyze_runs` already reduced each run independently); `selected_samples`/`available_samples` are summed across duplicates for provenance. Grid points mixing different metric names, or rows missing a requested sweep-variable path, raise immediately rather than producing a malformed grid.

**Evidence:** Full test suite passes with 34 tests.

**Next:** Wire `find_missing_runs`/`build_grid` into a playground example alongside the baseline comparison, then start the plot-data builder that consumes `GridResult`.

## 2026-08-25 - Add renderer-independent plot-data builders

**Goal:** Convert deduplicated sweep results into arrays and labels that future plotting code can render.

**Changed:** Added `src/canopy_processor/plot_data.py` with `LinePlotData`, `HeatmapPlotData`, `FacetedHeatmapData`, `ParallelCoordinatesData`, and builders for line/scatter, 2D heatmap, N-D faceted heatmap, and parallel-coordinate data. Added `build_plot_data` as the plot-type dispatcher and focused synthetic tests.

**Decisions:** Keep this layer independent of Matplotlib and the GUI. Line data is sorted by x; heatmaps use y rows and x columns, with missing coordinate pairs represented by NaN; remaining dimensions become facet keys; parallel-coordinate values are emitted as a rectangular matrix. Rendering and visual styling remain a later concern.

**Evidence:** Full test suite passes with 39 tests and no editor diagnostics in the new module or tests.

**Next:** Add the Matplotlib rendering layer that consumes these plot-data objects, then connect rendering and export settings to the saved analysis configuration.


## 2026-08-26 - Add Matplotlib renderer

**Goal:** Render the prepared plot-data objects without coupling analysis or plot-data preparation to Matplotlib or the GUI.

**Changed:** Added `src/canopy_processor/plotting.py` with renderers for line/scatter plots, 2D heatmaps, faceted heatmaps, and parallel-coordinate plots, plus `render_plot_data` dispatch. Renderers return Matplotlib `Figure` objects so callers can display or export them. Added headless renderer tests and made Matplotlib a core project dependency.

**Decisions:** Keep rendering separate from plot-data preparation. Tests use the `Agg` backend and inspect figure/axis structure rather than pixel output. Heatmaps use lower-origin orientation and handle single-level axes without warnings.

**Evidence:** Full test suite passes with 44 tests and no editor diagnostics in the renderer or tests.

**Next:** Connect rendering and export settings to the saved analysis configuration, then begin the desktop GUI layer.

## 2026-08-26 - Align heatmap rendering with MATLAB output

**Goal:** Make generated heatmaps readable and visually consistent with the existing MATLAB plots.

**Changed:** Updated `plotting.py` so heatmap cells use midpoint-derived outer edges while ticks remain at the actual sweep-value centers. Added explicit x/y ticks, white cell-value annotations, and the `jet` colormap. Also corrected scatter plots so labels and titles are applied in both line and scatter modes.

**Evidence:** Renderer tests assert coordinate ticks, `jet` colormap selection, and annotation count. Full test suite passes with 44 tests.

**Next:** Connect renderer output to saved plot/export settings and begin the desktop GUI layer.

## 2026-08-26 - Connect rendering and export configuration

**Goal:** Make saved export settings control the files produced from a rendered figure and its analysis rows.

**Changed:** Added `export_analysis` in `src/canopy_processor/exporting.py`. It reads `ExportConfig`, creates the configured output directory, and exports SVG/PNG figures. Analysis configuration remains available separately through `AnalysisConfig.save()`. Updated `tests/playground.py` to prompt for an export directory, store it in `ExportConfig`, and export the displayed grip heatmap.

**Decisions:** Keep exporting separate from rendering. The same returned Matplotlib `Figure` is used for display and SVG/PNG file output. Saved configuration JSON remains separate from result-file export.

**Evidence:** Export tests verify all configured formats and serialized rows. Full test suite passes with 46 tests; playground compiles successfully.

**Next:** Begin the desktop GUI layer around the tested loading, configuration, analysis, plotting, and export APIs.

## 2026-08-27 - Add initial desktop GUI workbench

**Goal:** Create the first visible PySide6 desktop shell so the planned GUI layout and visual direction can be reviewed before implementing the full analysis workflow.

**Changed:** Added `src/canopy_processor/ui/session.py` with a framework-independent `AnalysisSession` lifecycle model covering discovery, review, ready, analysis, cancellation, results, and failure states while preserving the last valid result. Added `src/canopy_processor/ui/discovery.py` to resolve nested Canopy source folders, prefer exploration metadata, fall back to job-document variables, and return diagnostics. Added `src/canopy_processor/ui/main_window.py` with the initial dark graphite/cyan workbench: left control rail, dataset selection, sweep-variable area, metric/plot/baseline controls, Results and Comparison tabs, and persistent diagnostics/progress controls. Added `src/canopy_processor/ui/app.py` and the `canopy-exploration-gui` project script entry point.

**Decisions:** Keep the session and discovery contracts independent of Qt so the numerical and state behavior remains testable without constructing widgets. Treat the selected repository root as a container that may hold nested exploration directories. Keep the first shell intentionally non-destructive: selecting a root enters review state, while analysis controls report that the worker workflow is not connected yet.

**Evidence:** The GUI can be launched with `python -m canopy_processor.ui.app` from the activated project virtual environment. The workbench was manually opened and reviewed. Added session, discovery, and offscreen Qt smoke tests. Full test suite passes with 51 tests; focused GUI tests pass with 5 tests.

**Next:** Connect dataset discovery and analysis to background Qt workers with stage progress, cancellation, error handling, and last-valid-result preservation, then bind the discovered variables and real analysis controls to the workbench.

## 2026-08-27 - Add background discovery workflow

**Goal:** Make dataset discovery real and non-blocking in the desktop workbench, with a reusable cancellation and progress contract for future analysis operations.

**Changed:** Added `src/canopy_processor/ui/worker.py` with cooperative cancellation tokens, Qt worker signals, and thread startup helpers. Extended `AnalysisSession` to retain the `DiscoveryResult`. Connected root-folder selection in `main_window.py` to background discovery, populated the sweep-variable list from the actual sample data, surfaced discovery diagnostics, added explicit variable confirmation, and stored resolved dataset paths in `DatasetConfig`. Added worker lifecycle tests and a window test for real variable population.

**Decisions:** Keep blocking domain calls outside the Qt UI thread. Attach observers before starting workers so fast operations cannot lose signals. Cancellation is cooperative and preserves prior results. A selected root may contain nested exploration directories; discovery resolves the actual metadata-bearing directory before loading variables.

**Evidence:** Focused GUI tests pass with 5 tests, covering worker completion, cancellation, nested sample discovery, and Qt workbench integration. Full test suite passes with 54 tests. The sample repository root resolves its nested `DATA_Raw/MOS_COR_TyrePressureExploration` source and discovers the two pressure variables.

**Next:** Connect confirmed dataset state to the real load, turn-zone, metric-reduction, baseline, plot-data, and Matplotlib rendering pipeline through staged background analysis workers, then bind result plots and diagnostics to the workbench.

## 2026-08-27 - Correct sweep-variable selection behavior

**Goal:** Ensure the GUI's sweep-variable selection matches its intended multi-dimensional analysis workflow.

**Changed:** Updated `main_window.py` so the discovered-variable list uses Qt extended multi-selection. Confirmation now reads only the selected rows and stores those candidates as `SweepVariableConfig` entries; no selection is rejected instead of implicitly accepting every discovered variable. Added GUI tests covering both single-variable and multi-variable confirmation.

**Decisions:** Keep axis-role assignment as a follow-up control, but establish an explicit selection contract first. This prevents the GUI from presenting a single-selection affordance while silently configuring all candidates.

**Evidence:** Focused GUI tests pass with 3 tests, including real sample discovery, single-variable exclusion, and selecting both pressure variables. The editor reports no diagnostics in the changed files.

**Next:** Add per-variable axis-role controls and connect the confirmed configuration to staged background loading, reduction, plotting, and diagnostics.

## 2026-08-27 - Stabilize variable selection and worker cleanup

**Goal:** Make multi-variable selection explicit and keep repeated GUI discovery operations stable.

**Changed:** Updated `main_window.py` to use Qt extended multi-selection and persist only selected candidates as `SweepVariableConfig` entries. Added explicit rejection of an empty selection. Moved worker cleanup to `QThread.finished` and added close-event cancellation/wait handling to prevent active threads from outliving the window. Expanded GUI tests for single selection, selecting both pressure variables, and repeated Qt worker lifecycle behavior.

**Decisions:** Selecting one variable configures one variable; selecting several configures several; discovery results are never implicitly treated as the user's selection. Axis-role assignment remains the next configuration control. Worker shutdown is considered complete only after the thread finishes, not merely when the worker emits its completion signal.

**Evidence:** Focused GUI tests pass with 5 tests. Full test suite passes with 55 tests. The isolated Qt window suite passes without the access violation previously observed during worker cleanup.

**Next:** Add per-variable axis-role controls, then connect the confirmed configuration to staged background loading, reduction, plotting, and diagnostics.

## Logging Checklist

For each future milestone, append one dated entry with:

- The user-facing goal.
- The files or modules changed.
- Decisions and tradeoffs.
- Validation results and sample data used.
- A link or path to screenshots when visual behavior changes.
- The next milestone or known follow-up.
