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

## Logging Checklist

For each future milestone, append one dated entry with:

- The user-facing goal.
- The files or modules changed.
- Decisions and tradeoffs.
- Validation results and sample data used.
- A link or path to screenshots when visual behavior changes.
- The next milestone or known follow-up.
