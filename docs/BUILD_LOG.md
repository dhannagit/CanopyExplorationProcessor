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

## Logging Checklist

For each future milestone, append one dated entry with:

- The user-facing goal.
- The files or modules changed.
- Decisions and tradeoffs.
- Validation results and sample data used.
- A link or path to screenshots when visual behavior changes.
- The next milestone or known follow-up.
