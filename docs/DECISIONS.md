# Architecture Decision Log

Record decisions that affect the design or future maintenance. Use one entry per decision; do not duplicate ordinary implementation details from the build log.

## ADR-001 - Use a layered Python application

**Status:** Accepted

**Decision:** Keep file loading, exploration discovery, analysis/reduction, plotting, and GUI code in separate layers.

**Reason:** The same computation must support interactive use, automated tests, saved configurations, and future headless execution.

## ADR-002 - Read `.dxpx` files as MATLAB MAT files

**Status:** Accepted

**Decision:** Use SciPy to read the MATLAB Level-5 container behind the `.dxpx` extension and convert MATLAB structs into Python mappings.

**Reason:** The sample file begins with the MATLAB 5.0 MAT signature and exposes the `D.Header` and `D.Data` structure used by the existing scripts.

## ADR-003 - Prefer Canopy exploration metadata

**Status:** Accepted

**Decision:** Use `exploration-map.json`, `scalar-inputs.csv`, and `scalar-inputs-metadata.csv` as the primary sweep-variable contract. Use `job-document.json` for provenance and fallback discovery.

**Reason:** Aggregate Canopy metadata describes the factorial design, units, coordinates, and job ordering more reliably than inferring all behavior from string-matched JSON changes.

## ADR-004 - Treat post-processing as a distinct job type

**Status:** Accepted

**Decision:** Detect the extra successful `Post Processor` job and exclude it from simulation-variable discovery and failure counts.

**Reason:** Canopy creates one internal post-processing job without a corresponding `.dxpx`; this is expected behavior, not a failed simulation.

## ADR-005 - Deploy through Artifactory with private Windows environments

**Status:** Accepted

**Decision:** Distribute a versioned Python wheel and a thin Inno Setup installer
for managed Windows x64 PCs. Use corporate uv tooling and Python 3.13, with a
hashed runtime lock embedded in every wheel. Automatically install stable releases
at launch into separate environments, validating dependencies and an offscreen
GUI before atomically activating a release. Preserve working releases on failure,
defer updates while sessions are running, and support explicit rollback.

**Reason:** This follows DataConverter's corporate distribution model without
freezer-specific native dependency handling, certificate bypasses, forced process
termination, or in-place upgrades that can break the working installation.

## ADR-006 - Configure shared circuit resources per user

**Status:** Accepted

**Decision:** File > Settings accepts a locally synced SharePoint/OneDrive folder
containing `CircuitsData_Canopy_Hypercar.xlsx`. Persist it in Canopy-specific
QSettings, outside the installation. Remove developer-checkout fallbacks. Allow
startup without configuration, report unavailable resources when needed, and apply
folder changes to subsequent study loads without rewriting loaded dataset paths.

**Reason:** User sync paths differ, and the workbook is maintained independently
of application releases. This matches DataConverter's preferences workflow without
requiring SharePoint API credentials or distributing a stale bundled workbook.

## Presentation Evidence To Capture

- Before/after workflow diagram: three hardcoded MATLAB scripts versus one configurable Python application.
- Screenshot of discovered sweep variables and units.
- Screenshot of metric, filter, baseline, and plot selection controls.
- Example 1D, 2D, and faceted N-dimensional plots.
- Test summary and a representative MATLAB/Python parity comparison.
- A short list of remaining limitations and future work.
