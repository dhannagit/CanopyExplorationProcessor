# Canopy Exploration Processor

Windows workbench for analyzing Canopy simulation sweeps.

## Install

### 1. Prepare Your Computer

Use a corporate Windows x64 computer connected to the corporate network or VPN.
Setup needs approved `uv` tooling and access to corporate Artifactory to install
Python 3.13 and the application's dependencies. An existing Python 3.11 installation
is not sufficient by itself. Ask your maintainer or IT if the approved tooling is
not installed. No development checkout is needed to install the application.

Before installing, configure PowerShell for your Windows user account using the
following IT-approved command:

1. Open the Windows **Start** menu, search for **Windows PowerShell**, and open it
	normally. **Run as administrator is not required.** Use the same Windows account
	that will install and run Canopy Exploration Processor.
2. Enter this command and press **Enter**:

	```powershell
	Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
	```

3. If asked to confirm the change, enter `Y` and press **Enter**.
4. Check the effective policy:

	```powershell
	Get-ExecutionPolicy
	```

	It should report `RemoteSigned`. This setting persists for your user account;
	you normally only need to configure it once. If it reports another policy,
	the command is denied, or scripts remain blocked, contact IT. Do not bypass
	an enforced corporate policy. Downloaded unsigned scripts can still be blocked
	under `RemoteSigned`; send the exact error to your maintainer if this happens.

### 2. Find The Approved Download In GitLab

GitLab calls files saved by a completed build job **artifacts**. You want the
artifacts from a successful **release_windows** job, not the repository's
**Download source code** button.

The easiest route is to ask the maintainer for a direct link to the approved
`release_windows` job. If you have that link, open it and continue at step 5 below.
Otherwise:

1. Sign in to the Canopy Exploration Processor project in GitLab using your
	corporate account.
2. In the project's left sidebar, open **Build > Pipelines**. Depending on the
	GitLab layout, **Pipelines** may also be available as a pinned sidebar item.
3. Find the pipeline for the release version the maintainer has approved, such as
	**v0.1.1**. Choose the version tag, not a feature branch or a `main` preview.
	Click the pipeline number to open its list or graph of jobs.
4. Find **release_windows** in the **release** stage and click its name. It must
	have a **Passed** status. If it is manual, pending, skipped, or failed, ask the
	maintainer for the completed release; do not start a deployment yourself.
5. On the job page, find **Job artifacts** and select **Download** (sometimes shown
	as **Download artifacts**). This downloads an outer ZIP containing the release
	files. If only **Browse** is visible, use it to inspect the artifact contents
	and locate the download controls.
6. In Windows File Explorer, right-click the downloaded ZIP and choose
	**Extract All...**. Open the extracted folder, then open
	**dist > releases > v0.1.1**, replacing `v0.1.1` with the version you downloaded.
7. Locate **CanopyExplorationProcessor-0.1.1-Setup.exe** for the recommended installer
	or **CanopyExplorationProcessor-0.1.1-Windows-x64.zip** for the extracted-folder
	installation. You only need one installation method. The `.whl`, `.tar.gz`,
	release metadata, and checksum files are not double-click installers.

Do not use `package_windows`, `nsis_compile`, or `nsis_smoke` artifacts for normal
installation unless the maintainer explicitly invites you to test a preview.
If the job or download is inaccessible or expired, ask the maintainer for access
or a current approved download. GitLab project visibility alone does not guarantee
permission to download release artifacts.

### 3. Install And Launch

**Recommended: EXE installer**

1. Double-click the extracted `CanopyExplorationProcessor-<version>-Setup.exe`.
2. Follow the setup wizard. Keep the default per-user installation folder unless
	your maintainer or IT specifies another writable folder. Administrator rights
	are not normally required.
3. Wait for setup to finish successfully, then launch **Canopy Exploration
	Processor** from the Windows Start menu.

**Alternative: ZIP installation**

1. Extract the inner `CanopyExplorationProcessor-<version>-Windows-x64.zip` as well;
	extracting the outer GitLab artifact ZIP alone is not enough.
2. Place the resulting application folder in a stable location where your user
	account has write permission. Do not run setup directly inside the ZIP.
3. Open that application folder and double-click `setup_environment.bat`. Keep
	the window open until setup completes successfully.
4. Double-click `CanopyExplorationStart.bat` to launch the application. Keep the
	installed folder in the same location afterward.

For either method, keep corporate network access available during setup. If setup
fails, report the exact error rather than trying to launch a partial installation.
Once open, use **File > Settings** to select the synced folder containing the
circuit workbook if you need turn-zone preparation. Basic analysis can run without
this setting. Updates are manual: download and install a newer approved release
using the same process.

See the [GitLab Artifact Guide](docs/DISTRIBUTION.md) for prerequisites, local
builds, CI setup, artifact downloads, signing considerations, upgrades and rollback.

## Basic Use: No Filters Or Circuit Workbook

You can analyze a sweep without a circuit workbook, corner-phase filters or turn-zone
filters. Start with a simple plot of one metric against one sweep variable:

1. In the **Analysis** tab, click **Select raw study folder**. Select one study's
	folder containing its numbered job folders, not the parent holding many studies.
2. Check the detected **Raw** and **DXPX** paths. If the matching simulation outputs
	were not found automatically, click **Choose DXPX folder** and select that study's
	output folder.
3. In **Sweep variables**, select the variable's row and set its **Role** to the desired
    input position (x, y, facet). Click **Confirm variables** and wait for the runs to 
    finish loading.
4. Under **Analysis settings**, select a **Metric**. Keep **Plot** on **Suggested
	plot** and **Baseline** on **No baseline** for the simplest starting point.
5. Leave every checkbox in **Phases** and **Turn zones** unchecked. An empty filter
	selection means no restriction, not an empty result. Skip track/zone preparation.
6. Click **Apply / Analyze**, then view the plot and per-run values in **Results**.

With no filters, time-series metrics are reduced over all available samples in each
run. Scalar metrics, such as a precomputed lap-time value, are used as supplied.
Change a metric or plot setting and click **Apply / Analyze** again to recalculate.

## More Detailed Use

### Sweep Variables And Plots

Select additional variable rows before **Confirm variables** when analyzing more
than one swept input. Assign **x** and **y** for a two-variable view, or use the
other available roles for higher-dimensional plots. **Suggested plot** chooses a
view from your assignments; use **Plot** to select a compatible view explicitly.
Variable **Display name** and **Units** can be adjusted for presentation.

### Corner-Phase Filters

Corner-phase filtering uses the phase flags already present in the loaded DXPX
data and does **not** require a circuit workbook. Available checkboxes depend on
the source data.

1. Load and confirm the study as in Basic Use.
2. In **Phases**, check the corner phase or phases you want to include.
3. Keep **Phase logic** on **or** to include samples belonging to any selected
	phase. Use **and** only when samples must satisfy every selected phase; phases
	that do not overlap can produce no selected samples.
4. Leave **Turn zones** unchecked to filter by phase alone, then click
	**Apply / Analyze**.

Uncheck every phase to return to unfiltered analysis. Filters act on time-series
samples; they do not recalculate scalar metrics such as a precomputed lap time.

### Turn-Zone Filters And The Circuit Workbook

Preparing turn-zone filters currently depends on the circuit workbook
`CircuitsData_Canopy_Hypercar.xlsx`, which you can **request from the repository
maintainer**. It is not included in the installer download. Runs that already contain
turn-zone masks can use those existing masks without generating them again.

1. Place the workbook in a locally accessible folder, such as your synced
	SharePoint/OneDrive resource folder.
2. Open **File > Settings**, select the folder containing the workbook directly,
	and save. Load or reload your study so it uses this location.
3. In **Turn zones**, check the **Detected track**, select the correct **Track for
	zones**, and click **Confirm track and add zones** when zone preparation is
	offered. Verify the track rather than assuming the detected name is correct.
4. Check the zones to include. **Zone logic: or** includes any selected zone;
	**and** requires their overlap.
5. If phases are also selected, **Category logic: and** restricts the analysis to
	those phases within the selected zones. **or** includes samples matching either
	category. Click **Apply / Analyze** to update the results.

Leave all zones unchecked when you do not want a location restriction. For offline
access, make sure OneDrive has downloaded the workbook rather than leaving only a
cloud placeholder.

### Saving And Reloading An Analysis

An analysis file is a small JSON recipe containing source locations and your
analysis settings. It is **not** a copy of the simulation data, computed results
or plot images. Keep the original raw study and DXPX files available.

1. Configure the analysis, then choose **File > Save As...** and select a JSON
	filename. Use **File > Save** to update that file after later changes.
2. To return to it later, choose **File > Open Analysis...** and select the JSON.
3. Wait for the source data to reload. If a saved data folder or external baseline
	has moved, the app asks you to locate it.
4. Review the restored variables, metric, filters and plot settings, then click
	**Apply / Analyze**. Opening an analysis does not automatically run it.

The circuit workbook comes from the current user's **File > Settings** location.
Turn-zone analyses may require track confirmation again if the source track or
workbook has changed. When sharing an analysis JSON, the recipient also needs
access to its source data and, if required, the workbook. Use **Export Figure** in
**Results** to save plot images separately.

## Python Package

Each release also includes a standard wheel for future integration into another
tool. The package remains separate from the Windows installer; no plugin or host
framework integration is imposed on the analysis modules.

## Developer Tests And Local Data

Run the non-local suite before committing. It covers all synthetic and
fixture-independent tests across the test modules:

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not local_data" -q --basetemp (Join-Path $env:TEMP ('canopy-exploration-processor-ci-tests-' + [guid]::NewGuid().ToString('N')))
```

To run the real-data integration tests as well, ask a maintainer for an approved
sample or use compatible Canopy data you are authorized to access. Place the
contents, not archives, in the ignored `DATA_Raw`, `DATA_dXpx`, and
`BaselineExample` folders at the repository root. The test data must include a
raw exploration with metadata, at least two numeric sweep variables, its paired
numbered DXPX runs, `gCarPotential`, phase data for GUI filter coverage, a
multi-lap baseline, and a circuit workbook containing the paired run's track.
Keep the workbook at the repository root as
`CircuitsData_Canopy_Hypercar.xlsx`.

These folders and workbook are ignored by Git. Keep their contents local: do not
force-add, commit, package, or upload them to GitLab. Check the ignore behavior
before staging changes. Run the local-data profile, then the combined suite, before
committing:

```powershell
.\.venv\Scripts\python.exe -m pytest -m local_data -q --basetemp (Join-Path $env:TEMP ('canopy-exploration-processor-local-data-' + [guid]::NewGuid().ToString('N')))
.\.venv\Scripts\python.exe -m pytest -q --basetemp (Join-Path $env:TEMP ('canopy-exploration-processor-full-tests-' + [guid]::NewGuid().ToString('N')))
```

GitLab runs the complete test suite except `local_data`; protected samples are
never required or uploaded in CI. On a protected default branch, the optional
`nsis_smoke` job validates the preview installer without creating a production
release. Production release remains a separate approved, protected-tag action.
