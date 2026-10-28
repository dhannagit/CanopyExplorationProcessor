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

## ADR-003 - Prefer Canopy simulation exploration metadata

**Status:** Accepted

**Decision:** Use `exploration-map.json`, `scalar-inputs.csv`, and `scalar-inputs-metadata.csv` as the primary sweep-variable contract. Use `job-document.json` for provenance and fallback discovery.

**Reason:** Aggregate Canopy simulation metadata describes the factorial design, units, coordinates, and job ordering more reliably than inferring all behavior from string-matched JSON changes.

## ADR-004 - Treat post-processing as a distinct job type

**Status:** Accepted

**Decision:** Detect the extra successful `Post Processor` job and exclude it from simulation-variable discovery and failure counts.

**Reason:** The Canopy simulation software creates one internal post-processing job without a corresponding `.dxpx`; this is expected behavior, not a failed simulation.

## ADR-005 - Deploy through Artifactory with private Windows environments

**Status:** Superseded by ADR-008 for application delivery and update policy.

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
containing `CircuitsData_Canopy_Hypercar.xlsx`. Persist it in Canopy Exploration Processor-specific
QSettings, outside the installation. Remove developer-checkout fallbacks. Allow
startup without configuration, report unavailable resources when needed, and apply
folder changes to subsequent study loads without rewriting loaded dataset paths.

**Reason:** User sync paths differ, and the workbook is maintained independently
of application releases. This matches DataConverter's preferences workflow without
requiring SharePoint API credentials or distributing a stale bundled workbook.

## ADR-007 - Persist analysis recipes rather than result projects

**Status:** Accepted

**Decision:** Save current analysis controls, including incomplete drafts, as
versioned JSON recipes. Keep raw signals, reduced results, plot zoom, window
layout, and images outside the document. Reopen original sources in the background,
restore settings by stable identifiers, and wait for explicit Apply. Failed or
cancelled Open must preserve the current session. Replace saved JSON atomically.

Use one active metric and derive plot assignments from variable roles. Keep
suggested plot intent distinct from its runtime resolution. Preserve inactive
baseline choices. Resolve shared circuit resources through per-user settings;
reuse successful zone confirmation only when the header track and workbook
fingerprint match. External baseline headers must independently match approval.

**Reason:** Recipes stay small and reproducible while avoiding stale cached data
and hidden automatic analysis. Schema version 2 deliberately replaces the
pre-production format without a migration layer.

## ADR-008 - Deliver standalone applications through GitHub Releases

**Status:** Superseded by ADR-009 for delivery hosting and CI.

**Decision:** Publish the application as versioned GitHub Release assets: a Windows
setup ZIP, an optional Inno EXE, the normal Python wheel/source archive, a manifest
and checksums. Bundle the exact application wheel with setup. Fetch only third-party
runtime dependencies from corporate Artifactory using the embedded hashed lock.
Install into a candidate environment, validate it, and atomically activate it.
Users upgrade explicitly by installing a newer GitHub Release; normal launch does
not perform update/network checks. Preserve explicit rollback and user preferences.

**Reason:** The app currently needs independent distribution rather than company
updater integration. Keeping a normal wheel and existing package boundaries leaves
future host-tool/module integration open without imposing a plugin framework now.
Build on corporate Windows with Artifactory access, then upload final app artifacts;
do not assume public GitHub runners can reach internal dependency repositories.

## ADR-009 - Build standalone installers as GitLab job artifacts

**Status:** Superseded by ADR-011.

**Decision:** Add an opt-in protected-ref Windows pipeline with preflight, locked
tests/JUnit reporting, and packaging followed by production-lock installation/Qt
smoke validation. Store final artifacts under `dist/releases/v<version>` and upload
only that directory to the package job. No Generic Package Registry, application
updater or unverified publishing job is enabled. Keep the existing app layout and
wheel/private-environment deployment. CI and EXE compilation start disabled.

Use the corporate template's Artifactory uv index/dev-group conventions, but keep
the actual project's development `uv.lock` distinct from its embedded production
dependency lock. Do not copy template OAuth, embedded secrets, sample application,
stale lockfile, project IDs or generated version handling. Full tests require
explicitly provisioned approved datasets; the default suite reports its limited scope.

**Reason:** The supplied template and CI checkout name different shared workflow
repositories, and the runner/compiler contract remains unconfirmed. A local,
reviewable pipeline prepares integration without guessing publisher overrides or
changing a tested deployment architecture. Artifact retention, access, signing,
shared-workflow policy and compiler licensing remain company configuration gates.

## ADR-010 - Enforce the documented Windows and production delivery contract

**Status:** Implemented controls; external image, delivery and signing approvals pending.

**Decision:** Require an explicit versioned corporate Windows image for the
documented container runner. Keep optional same-project MR validation separate
from protected-branch team previews and a blocking manual protected-tag production
job declaring `production/windows`. Set explicit artifact access and separate
preview/production retention. Production requires owner approval and an explicit
signing policy. Required signing uses an external runner-managed adapter, checks
the signer/timestamp, signs staged scripts and NSIS setup/uninstaller, and finishes
checksums only afterward. Use the documented corporate Python runtime mirror.

**Reason:** The runner tag does not imply installed workstation tooling. Corporate
rules treat artifacts usable outside the producing team as production deployments.
Neither documentation nor successful unsigned builds establish project approval,
an artifact-retention exception, or access to a signing provider. CI remains
disabled until these external contracts are supplied and validated.

## ADR-011 - Compile Windows setup with the corporate NSIS image

**Status:** Accepted; GitLab compile and signing validation pending.

**Decision:** Use a local `nsis_compile` job on the approved corporate NSIS image
to compile `installer/CanopyExplorationProcessor.nsi`. The package job remains the
source of the versioned Windows ZIP; the compile job extracts that bundle and emits
`CanopyExplorationProcessor-<version>-Setup.exe` as an expiring job artifact. A
protected-tag finalizer combines the EXE with package assets, recalculates hashes,
and smoke-installs and uninstalls both formats. Keep the app's wheel/private-env
deployment, explicit external signer adapter, and disabled-by-default CI policy.

**Reason:** The corporate Windows image provides the approved NSIS compiler. A
local ASCII-named job avoids coupling project configuration to a shared template's
emoji-bearing job key while keeping the compiler, artifact handoff and release
checks within the approved corporate runner. A successful local recipe review is
not a substitute for the pending GitLab compile and protected signing run.

## Presentation Evidence To Capture

- Before/after workflow diagram: three hardcoded MATLAB scripts versus one configurable Python application.
- Screenshot of discovered sweep variables and units.
- Screenshot of metric, filter, baseline, and plot selection controls.
- Example 1D, 2D, and faceted N-dimensional plots.
- Test summary and a representative MATLAB/Python parity comparison.
- A short list of remaining limitations and future work.
