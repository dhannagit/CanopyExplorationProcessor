# Canopy Exploration Processor Build Log

This is the chronological engineering record for the Python migration. Keep entries concise and factual. Each entry should capture what changed, why it changed, how it was verified, and what comes next.

## 2026-10-27 - GitHub Release distribution

**Goal:** Distribute standalone releases on GitHub while retaining corporate
Artifactory for third-party dependencies and a normal wheel for future integration.

**Changed:** Bundle a checksum-verified wheel/manifest in Windows setup; remove the
corporate app updater and launch-time checks; generate versioned Windows ZIP,
wheel/source archive, manifest and checksums for GitHub upload. Retain staged
installation, rollback, private environments and per-user settings. Update the
Inno recipe, deployment guide and repository README. Use fresh build output paths
to avoid overwriting pre-existing administrator-owned artifacts.

**Evidence:** The fixture-independent regression run passed 81 tests with five
dataset-dependent tests deselected. The generated ZIP installed from its bundled
wheel with UV_FIND_LINKS cleared; locked dependencies came from corporate
Artifactory. An installed Qt/Matplotlib/native-library smoke check passed outside
the checkout, followed by same-version no-op setup and app-owned removal. Payload
integrity tests cover invalid/missing manifests, wheel hashes, version and lock
mismatches, downgrade rejection and preservation of the active environment.

**Next:** Upload tested assets to a draft GitHub Release after committing/tagging
the source. No upload or tag was created automatically. Inno Setup is not installed
here, so the EXE recipe remains uncompiled; the Windows ZIP is usable without it.
Validate signing policy and normal-user installation on a teammate's device.

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

## 2026-08-27 - Add sweep-variable axis roles

**Goal:** Let users configure how selected sweep variables participate in the eventual plot and analysis dimensions.

**Changed:** Replaced the plain candidate list in `main_window.py` with a multi-select table containing variable metadata and a per-row role selector. Each discovered variable can now be assigned `unused`, `x`, `y`, `facet`, or `color`. Confirmation persists only selected rows and their roles as `SweepVariableConfig` entries. Expanded the Qt tests to cover one selected variable with an `x` role and both pressure variables assigned to `x` and `y`.

**Decisions:** Keep variable selection and axis-role assignment together so the configuration is explicit before analysis begins. Do not infer axis roles from variable names or selection order; default every candidate to `unused` until the user chooses a role.

**Evidence:** Full test suite passes with 55 tests. The editor reports no diagnostics in the changed GUI module or tests.

**Next:** Connect the confirmed configuration to staged background loading, turn-zone preparation, metric reduction, plot-data generation, and Matplotlib rendering.

## 2026-08-27 - Fix discovery completion race

**Goal:** Resolve the GUI hang where discovery reached 100% on "Reading sweep metadata" without populating sweep variables, and cancellation left the window unresponsive.

**Changed:** Updated `main_window.py` to create discovery workers without starting them, connect every result/error/cancellation handler, and only then start the thread. This prevents fast discovery operations from emitting `result_ready` before the window is listening. Extended `AnalysisSession` so discovery can enter `CANCELLING` and return to `EMPTY` after cooperative cancellation when no prior result exists. Added focused cancellation coverage.

**Root cause:** `_start_discovery()` previously called `start_worker(operation)` with its default immediate start, then connected the signals. The final progress signal could arrive, but the result signal could be lost before `_discovery_succeeded()` was connected, leaving the progress display at 100% and the variable table empty.

**Evidence:** Focused GUI/session tests pass with 9 tests. Full test suite passes with 56 tests. The sample discovery workflow now reliably receives its result, and the editor reports no diagnostics in changed files.

**Next:** Connect the confirmed configuration to staged background loading, turn-zone preparation, metric reduction, plot-data generation, and Matplotlib rendering.

## 2026-08-27 - Load confirmed dataset and discover metrics

**Goal:** Move the GUI from reviewed configuration into real source-data loading without blocking the Qt event loop.

**Changed:** Added `src/canopy_processor/ui/pipeline.py` with `LoadedDataset` and `load_dataset()`. The loader finds numbered `.dXpx` runs, loads them through the native adapter, generates missing turn-zone masks from the discovered circuit workbook, retains non-fatal run diagnostics, and checks the default metric catalog against loaded data. Added a `LOADING` session state and connected variable confirmation to a background loading worker. The GUI now stores loaded runs in session state and populates the metric selector with compatible metrics.

**Decisions:** Keep loading separate from analysis reduction and plotting. Treat individual run failures as diagnostics while allowing valid runs to continue. Adapt cancellation through a callable predicate so the pipeline remains independent of Qt.

**Evidence:** Confirming both pressure variables against the sample data loads 25 simulation runs and populates the metric selector. Full test suite passes with 56 tests. A focused integration test also caught and fixed an incorrect boolean/callable cancellation adapter.

**Next:** Add metric/filter/reduction controls and connect the loaded runs to joined sweep results, grid diagnostics, plot-data generation, and Matplotlib rendering.

## 2026-08-27 - Match raw and DXPX study folders

**Goal:** Make DXPX autodetection follow the production Canopy directory layout instead of stopping at the `DATA_dXpx` container.

**Changed:** Updated `ui/discovery.py` to identify the raw study directory under `DATA_Raw`, match its study name and worksheet parent against DXPX directories above their numbered run folders, and expose all matching DXPX candidates. Updated `main_window.py` to show the resolved raw and DXPX paths separately, enable a manual `Choose DXPX folder` override, and use the selected path for later loading. Added tests for the `DATA_Raw/02_Worksheets/WorksheetName/StudyName` to `DATA_dXpx/WorksheetName/StudyName` pairing and verified the existing sample now resolves to its study-level DXPX directory.

**Decisions:** Prefer an exact worksheet/study match, then fall back to a study-name match. Keep manual selection available when multiple studies or nonstandard folder names prevent a unique automatic match. The DXPX path shown to the user is the actual study folder containing numbered run directories, not merely the top-level data container.

**Evidence:** Focused discovery and GUI tests pass with 5 tests. Full test suite passes with 57 tests. The sample resolves `DATA_dXpx/MOS_COR_TyrePressureExploration`, and the GUI displays that path below the raw directory. The editor reports no diagnostics in changed files.

**Next:** Add metric/filter/reduction controls and connect the loaded runs to joined sweep results, grid diagnostics, plot-data generation, and Matplotlib rendering.

## 2026-08-27 - Select one raw study as the GUI input

**Goal:** Prevent dataset discovery from scanning an entire worksheet containing many studies and ensure the DXPX path belongs to the selected raw study.

**Changed:** Updated `ui/discovery.py` so the selected path is one raw `StudyName` directory containing its numbered job folders and exploration metadata. DXPX autodetection now derives the sibling path by replacing `DATA_Raw/02_Worksheets` with `DATA_dXpx`, then validates that the DXPX study contains numbered run folders with `.dXpx` files. Updated `main_window.py` so the entry button reads `Select raw study folder`; the displayed Study, Raw, and DXPX paths now represent the selected study rather than a broad container. Added matching-layout coverage and adjusted GUI tests to use the study-level input.

**Decisions:** Do not auto-select among hundreds of `StudyName` folders. The user chooses exactly one raw study, and the application derives its DXPX counterpart from the known directory contract. The manual DXPX chooser remains available for exceptional or nonstandard layouts.

**Evidence:** The sample workflow now starts from `DATA_Raw/MOS_COR_TyrePressureExploration` and resolves `DATA_dXpx/MOS_COR_TyrePressureExploration`. The production-layout test covers `DATA_Raw/02_Worksheets/WorksheetA/StudyA` paired with `DATA_dXpx/WorksheetA/StudyA`. Full test suite passes with 57 tests, and the combined GUI tests pass without Qt teardown failures.

**Next:** Add metric/filter/reduction controls and connect the loaded runs to joined sweep results, grid diagnostics, plot-data generation, and Matplotlib rendering.

## 2026-08-27 - Verify DXPX override and raw-study refresh

**Goal:** Confirm that manual DXPX changes affect the actual loading call and that changing the raw study re-runs variable discovery.

**Changed:** Added GUI regression tests around the existing path flow. The manual override test replaces `DiscoveryResult.dxpx_directory`, starts the loading stage, and captures the `DiscoveryResult` received by `load_dataset()`. The raw-study refresh test submits two distinct discovery paths and verifies that the second result replaces both the stored discovery result and discovered sweep variables.

**Decisions:** Keep manual DXPX selection scoped to the current raw study; changing the raw study remains the operation that resets and rediscoveries the complete source configuration. No stale variables are retained across raw-study selections.

**Evidence:** Full test suite passes with 59 tests. The override reaches the loading boundary with the manually selected path unchanged, and sequential raw-study discovery publishes the second study's variables.

**Next:** Add metric/filter/reduction controls and connect the loaded runs to joined sweep results, grid diagnostics, plot-data generation, and Matplotlib rendering.

## 2026-08-27 - Support star exploration metadata

**Goal:** Restore numeric sweep-variable discovery for the newly added `MOS_COR_TrackTempSweep` star exploration.

**Root cause:** `exploration-map.json` for the star study stores coordinates as nested arrays such as `[[[25.0, 20.0, ...]]]`, while the factorial sample uses a different nesting depth. `_unwrap_coordinate()` removed only one-element list wrappers, leaving inner lists and causing `float(list)` to fail. The GUI caught that metadata error and displayed no variables even though the raw job documents contained all numeric changes.

**Changed:** Updated `exploration.py` to recursively flatten coordinate arrays before converting values to floats. Added real TrackTemp tests for the `Star` design, eight numeric variables, and six coordinates, plus GUI discovery coverage for `track.TTrack` and its six values.

**Evidence:** Direct fallback inspection showed eight numeric changed paths in the TrackTemp job documents. After the parser fix, both factorial pressure and star TrackTemp discovery pass. Full test suite passes with 61 tests and no editor diagnostics in the changed files.

**Next:** Add metric/filter/reduction controls and connect the loaded runs to joined sweep results, grid diagnostics, plot-data generation, and Matplotlib rendering.

## 2026-08-27 - Connect first real analysis results to the GUI

**Goal:** Move the workbench from loaded data to an actual reduced analysis, rendered plot, and inspectable result table.

**Changed:** Added `analyze_loaded_dataset()` and `AnalysisOutput` in `ui/pipeline.py`. The operation applies the selected metric and current filters, joins reduced values to discovered sweep coordinates, builds the sparse/duplicate-aware grid, and creates renderer-independent plot data. Connected `Apply / Analyze` in `main_window.py` to a background worker, with suggested plot selection based on assigned roles. Added a Matplotlib Qt canvas and populated result table; the initial path supports line/scatter and heatmap rendering.

**Decisions:** Keep reduction, coordinate joining, grid diagnostics, and plot-data generation in the existing core/pipeline layers. Render the returned plot data on the Qt thread only after the worker completes. Use the first selected metric for this initial slice and require explicit x/y roles for heatmaps.

**Evidence:** The real pressure sweep end-to-end GUI test selects `gCarPotential`, produces a 5x5 heatmap, renders a figure, and populates 25 result rows. Full test suite passes with 62 tests and no editor diagnostics in changed files.

**Next:** Add filter controls, plot-axis controls, visible diagnostics for incomplete/duplicate points, and baseline comparison to the Results/Comparison tabs.

## 2026-08-27 - Synchronize axis roles before analysis

**Goal:** Fix heatmap analysis failing even though the GUI visibly showed selected x and y roles.

**Root cause:** Role selectors were read when variables were confirmed, but the controls remained editable afterward. A user could change the visible roles to x/y after loading while `AnalysisConfig` still contained `unused` roles; analysis correctly rejected the stale configuration.

**Changed:** Updated `main_window.py` so role edits immediately update matching `SweepVariableConfig` entries and are synchronized again immediately before analysis. Extended the end-to-end GUI test to confirm variables with default roles, change them to x/y afterward, and successfully produce the heatmap.

**Evidence:** The exact reported post-confirmation x/y workflow now passes. Full test suite passes with 62 tests and no editor diagnostics in changed files.

**Next:** Add filter controls, plot-axis controls, visible diagnostics for incomplete/duplicate points, and baseline comparison to the Results/Comparison tabs.

## 2026-08-27 - Add configurable phase and turn-zone filters

**Goal:** Fix analysis configuration gaps exposed by the first real heatmap workflow.

**Changed:** Updated `main_window.py` to populate selectable phase and turn-zone lists from loaded runs, with separate OR/AND operators within each category and an AND/OR operator between categories. The selected values are now written into `FilterConfig` immediately before analysis. Added a role-recovery guard that rebuilds the active sweep-variable configuration from visible x/y controls when confirmation captured an incomplete role set. Expanded the real GUI test to exercise post-confirmation role changes and phase/turn-zone selection.

**Root cause:** The checkbox only displayed an intention to use turn-zone masks; it did not provide mask selection or write any filter state. Separately, role controls could display x/y while the confirmed configuration lacked one axis, producing the heatmap validation error.

**Decisions:** Empty phase and zone selections remain unrestricted, matching the core filter contract. Visible role controls are synchronized before every analysis, and a visible x/y pair is used to recover missing axis entries rather than failing with a misleading generic message.

**Evidence:** The pressure-sweep GUI test now selects a phase and turn zone, configures their operators, recovers a missing saved y role, and completes the heatmap. Full test suite passes with 62 tests and no editor diagnostics in changed files.

**Next:** Add visible diagnostics for incomplete/duplicate points and baseline comparison to the Results/Comparison tabs.

## 2026-08-27 - Make the GUI control rail responsive

**Goal:** Keep the increasingly detailed left-side configuration controls usable on standard laptop and desktop screens.

**Changed:** Updated `main_window.py` to place the control rail inside a vertical `QScrollArea`, bound its width between 285 and 360 pixels, reduce the default window size to 1100x700 with a 900x600 minimum, and shorten long dataset paths on screen while retaining the full path in tooltips. Added layout regression assertions for the scroll area and size constraints.

**Decisions:** Preserve every control and let the rail scroll vertically rather than shrinking controls until labels and selectors become unusable. Keep the Results area as the flexible region. Long paths are informationally compact but remain fully inspectable by hover.

**Evidence:** Focused GUI tests pass with 5 tests, including responsive rail assertions. Full test suite passes with 62 tests and no editor diagnostics in changed files.

**Next:** Add visible diagnostics for incomplete/duplicate points and baseline comparison to the Results/Comparison tabs.

## 2026-10-23 - Wire turn-zone filters and baseline comparison

**Goal:** Confirm that generated turn-zone masks are available and usable in the GUI, and make both baseline choices functional.

**Root cause:** The GUI displayed only a 70-pixel turn-zone list, and its existing integration test checked filter configuration but not selected sample counts. The baseline selector had no change handler, no run/file chooser, and the Comparison tab was static text; baseline comparison existed only in the core results module.

**Changed:** `pipeline.py` now reports mask-generation failures separately without discarding otherwise loadable runs, and analysis builds baseline values and deltas through the existing core functions. `main_window.py` shows masks shared by all loaded runs, enlarges the selector, exposes run or external DXPX controls and delta mode, and renders per-run comparisons. Tests cover selected-zone reductions and both baseline sources.

**Decisions:** External files use explicit zero-based comma-separated lap indices. Percent difference is the default; absolute difference is also available. A selected zone must exist on every loaded run before it is offered.

**Evidence:** The sample study loads 25 runs with 12 turn-zone masks each and no load diagnostics. Selecting `isTurnZone1` reduces one run from 7,724 available samples to 785 selected samples. Focused GUI/pipeline tests pass with 9 tests; the full suite passes with 65 tests.

**Next:** Add visible diagnostics for incomplete/duplicate sweep points and validate external-baseline filtering with studies that have differing mask availability.

## 2026-10-23 - Use bundled circuit data for external studies

**Goal:** Populate turn-zone filters when an external raw study has no circuit workbook in its directory ancestry.

**Root cause:** Discovery searched only the selected study and its parents. The reported conversion tree had no nearby `CircuitsData_*.xlsx`, so runs loaded without masks and the GUI correctly showed no selectable zones.

**Changed:** `discovery.py` now prefers any study-local workbook and falls back to the app-bundled `CircuitsData_Canopy_Hypercar.xlsx` when none is found. Added a discovery regression test.

**Evidence:** The reported external study uses `Watkins-Glen`, which is present in the bundled workbook. The exact study now loads 21 runs, each with 13 generated turn-zone masks and no diagnostics. Full suite passes with 66 tests.

**Next:** Surface a helpful warning when neither the study workbook nor the bundled workbook supports the run's track.

## 2026-10-23 - Confirm circuit before generating zones

**Goal:** Keep the DXPX header as the detected track, but require the user to verify the circuit used for newly generated masks and always use the central workbook.

**Clarification:** The earlier path supplied for this investigation was a Watkins-Glen study, and both its DXPX header and study metadata said Watkins-Glen. The corrected CTMP path has `Header.TrackName == "CTMP"` on all 25 runs. The earlier assumption was based on the first path, not a track-name parsing defect.

**Changed:** Discovery now always references `C:\Bib\Git\CanopyExplorationProcessor\CircuitsData_Canopy_Hypercar.xlsx`, ignoring workbooks near the data. Loading no longer adds zones automatically. The UI displays the DXPX header track, lets the user choose a circuit from the central workbook, and generates zones only after confirmation. The detected and confirmed track are both retained in the UI and saved analysis configuration. Baseline zone generation uses the confirmed circuit and refuses to infer it silently.

**Evidence:** The corrected CTMP study loads 25 runs with CTMP headers and no existing masks. After explicit CTMP confirmation, every run receives 12 masks with no diagnostics. Full suite passes with 68 tests.

**Next:** Manually verify the confirmation interaction in the desktop app on the corrected CTMP study.

## 2026-10-23 - Make phase and zone filters toggleable

**Goal:** Let users deselect an individual phase or turn-zone filter with a normal click.

**Changed:** Replaced extended row selection with checkable list items for both filter lists. Analysis now reads checked items only; an empty checked set remains unrestricted. Added a GUI integration test that clicks a zone checkbox off and on before verifying the analyzed filter.

**Evidence:** Focused GUI/pipeline tests pass with 10 tests. Full suite passes with 68 tests.

**Next:** Manually confirm checkbox hit targets and scrolling on the standard desktop layout.

## 2026-10-23 - Move controls into a three-tab workspace

**Goal:** Reduce clutter by replacing the narrow control rail and nested Results/Comparison tabs with three full-width workspace tabs.

**Changed:** `main_window.py` now has top-level Analysis, Results, and Comparison tabs. Analysis places Dataset and Sweep variables side by side in the first row, then Phases, Turn zones, and Analysis settings side by side in the second row. The Analysis page can scroll vertically without the former 360-pixel rail-width cap; sweep-variable columns use available width.

**Evidence:** Main-window integration tests pass with 6 tests; full suite passes with 68 tests.

**Next:** Manually review path readability and group sizing at standard desktop resolutions and display scaling.

## 2026-10-23 - Expand Analysis controls with the window

**Goal:** Improve the three-tab Analysis page after review showed unused space on large displays and paths that were still truncated.

**Changed:** Removed the Analysis page's scroll wrapper and fixed list-height caps. Dataset, Sweep variables, Phases, Turn zones, and Analysis settings now expand with available window dimensions, with proportionally more height for the lower configuration row. Dataset paths are displayed in full and wrap within their labels.

**Decisions:** Keep the existing two-row, five-group Analysis structure and let Qt's expanding size policies use the available space rather than adding further navigation or scroll behavior.

**Evidence:** GUI geometry tests verify the variable table widens and the turn-zone list grows between 1920x1200 and 2560x1440. Long paths remain untruncated. Main-window integration tests pass with 6 tests; full suite passes with 68 tests.

**Next:** Manually review the expanded layout at additional Windows display-scaling settings.

## 2026-10-23 - Windows distribution implementation

**Goal:** Start team distribution following DataConverter's corporate tooling and
Artifactory model, with independently maintained shared circuit resources.

**Changed:** Added File > Settings with isolated per-user folder preferences and
workbook validation; explicit workbook input to discovery; console-free entry
point, rotating GUI logs and installed-release smoke check; hashed runtime lock;
release build/manifest command; staged Windows setup/update/rollback/removal
controller and batch launchers; Inno Setup recipe and distribution documentation.

**Decisions:** Windows x64/Python 3.13; stable automatic updates; no TLS bypasses or
forced process termination; active release changes only after candidate validation;
rollback pauses updates until the manual updater runs. Shared workbooks and user
data are never installer payloads or uninstall targets.

**Evidence:** 37 fixture-independent regression tests passed. Following Unicode
path changes, all 11 deployment/settings tests passed again. Built wheel and source
archive; installed the wheel with its hashed dependencies in a fresh Python 3.13.14
environment, ran dependency compatibility checks and constructed/drew the Qt GUI
outside the checkout. Real deployment-controller setup, no-op update and removal
passed against the locally built wheel in a temporary installation. Editor checks
reported no errors in changed GUI modules.

**Next:** Inno Setup is not installed on the build machine, so the installer recipe
has not been compiled or exercised. Obtain approved compiler/signing and Artifactory
publishing access, validate on a teammate's normal Windows account, and provision
the external sample datasets for full numerical/GUI regression testing. No release
has been published and no production installation was modified.

## 2026-10-27 - Save and reopen analysis recipes

**Goal:** Save current analysis edits, including incomplete drafts, and reopen their original source data without storing loaded signals or computed results.

**Changed:** Added File > Open Analysis, Save, and Save As with unsaved-change prompts, atomic JSON replacement, source-path relocation, and candidate loading that preserves the active session on failure or cancellation. Added analysis names, variable display-name/unit editors, heatmap annotation settings, and SVG/PNG figure export. Save and Apply share a current-controls snapshot; reopening waits for Apply. The playground now analyzes the reopened recipe rather than continuing with its original settings.

**Decisions:** The pre-production schema is version 2 with one active metric and variable roles as the canonical axis assignments. Removed unused coordinate transforms and redundant dataset/axis fields without legacy migration. Preserve inactive baseline settings. Use current per-user circuit resources, and reuse saved zone confirmation only when the detected track and workbook fingerprint match; mismatched baseline tracks cannot reuse sweep approval.

**Evidence:** Full suite passes with 96 tests after pressure, TrackTempSweep, and baseline fixtures were restored. Tests cover draft round trips, failed atomic writes, background reopening, DXPX overrides, track-confirmation reuse/mismatch, cancellation/failure preservation, annotation/label rendering, and reopen-to-analysis-to-SVG/PNG export. Temporary test directories created during this work were removed.

**Next:** Manually review the new editors and Save/Open/Export dialogs on the target Windows display-scaling settings.

## 2026-10-27 - Keep assigned sweep axes in saved analyses

**Goal:** Fix heatmaps reporting a missing y axis when the GUI visibly assigned one, and prevent Save from omitting that variable.

**Root cause:** Confirmation included only highlighted rows, while role edits updated only variables already in the confirmed configuration. Assigning a visible role to another row did not include that variable. Recipe persistence exposed this discrepancy after the old role-recovery heuristic was removed.

**Changed:** Confirmation now includes explicitly assigned roles as well as highlighted rows. Assigning a role to another variable after confirmation also includes that variable, preserving its display name and units. Highlighting alone still does not change an already-confirmed analysis.

**Evidence:** New regression cases assign front=y and rear=x with only the rear row highlighted, both before and after confirmation. Each verifies that saved JSON contains both axes and analysis renders a labeled 2x2 heatmap. Full suite passes with 98 tests.

**Next:** Manually verify the corrected selection workflow with the user's pressure-analysis recipe.

## 2026-10-27 - Correct menu, table, and plot sizing

**Goal:** Separate File-menu shortcuts from labels, allow manual sweep-column sizing without losing responsive scaling, and resolve plots intermittently drawing small in the top-left corner.

**Root cause:** Rendering attached a new default-size Matplotlib figure to an existing Qt canvas without reinitializing the canvas sizing/DPI lifecycle. A regression test reproduced a 640-pixel figure inside a 1,350-pixel-wide widget without a subsequent resize event.

**Changed:** Added explicit menu-item spacing and retained the File menu on the window. All four sweep-variable columns now support manual resizing while their proportions scale with the viewport. Each rendered figure receives its own Qt canvas, replacing the prior canvas through the layout so visible/hidden tab transitions and window resizing synchronize figure dimensions.

**Evidence:** Full suite passes with 102 tests. Focused geometry tests also pass at 150% scaling. Tests cover repeated rendering without resizing, rendering while Results is hidden, subsequent window resizing, interactive table columns, and shortcut text widths. A readable offscreen menu capture was inspected for overlap; temporary captures and test directories were removed afterward.

**Follow-up:** Manual column resizing is now constrained to the table viewport. Growing a column shrinks neighboring columns to their minimum widths, then clamps further growth so no column moves beyond the right edge. Shrinking a column gives the released width to a neighbor, and automatic scaling retains the adjusted proportions. Tests drag every column beyond the viewport and back to its minimum at window widths of 900, 1100, 1920, and 2560 pixels, checking that the rightmost edge remains visible and no horizontal scrollbar appears. Full suite now passes with 114 tests.

**Next:** Add independent export size/aspect controls. Current export uses the displayed figure's dimensions at 300 DPI with tight cropping; exact export ratios will need a separate sizing policy rather than changing the interactive canvas dimensions.

## 2026-10-27 - Allow variable reconfirmation after analysis

**Goal:** Fix the exception raised when confirming sweep variables again after resizing columns and producing results.

**Root cause:** `mark_ready()` accepted only initial review/ready states, while the Confirm button could be used from a completed analysis. Reconfirmation also rebuilt the dataset settings and reloaded unchanged files, unnecessarily clearing filter selections and circuit confirmation.

**Changed:** Permit reconfirmation from results and from a failed operation with an existing discovery, while retaining guards for uninitialized/busy states. Reuse an unchanged loaded dataset when reconfirming variables, preserving checked masks, metric selection, and circuit confirmation.

**Evidence:** The regression test analyzes, resizes the Display name column, clicks Confirm variables, and analyzes again. It verifies no source reload, no exception, preserved masks/confirmation, and a valid heatmap. Full suite passes with 110 tests.

**Next:** Manually verify repeated configuration edits in reopened analyses.

## 2026-10-27 - Select figure export aspect ratios

**Goal:** Choose common image proportions while keeping export dimensions relative to the current plot/window size.

**Changed:** Added a Results export dropdown between the folder chooser and SVG/PNG checkboxes. Presets are Window, 1:1, 5:4, 4:3, 3:2, 16:10, and 16:9. The selected aspect is saved and restored with analysis recipes.

**Decisions:** Window preserves the existing tight-cropped export. Fixed ratios use an independent figure copy sized to the largest rectangle of the requested ratio within the displayed figure's dimensions. Recalculate layout and export the complete canvas at 300 DPI without tight cropping, which would otherwise alter the final image ratio. The interactive figure/canvas remains unchanged.

**Evidence:** Full suite passes with 122 tests. Tests check PNG pixel dimensions and SVG view boxes for all six fixed presets, proportional output growth with displayed-figure size, unchanged original figure dimensions/axes/canvas, recipe round trips, and dropdown placement. Temporary image outputs and test directories were removed after validation.

**Next:** Manually review the available export presets with representative heatmaps and faceted plots.

## Logging Checklist


For each future milestone, append one dated entry with:

- The user-facing goal.
- The files or modules changed.
- Decisions and tradeoffs.
- Validation results and sample data used.
- A link or path to screenshots when visual behavior changes.
- The next milestone or known follow-up.
