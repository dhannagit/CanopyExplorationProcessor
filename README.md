# Canopy Exploration Processor

Windows workbench for analyzing Canopy simulation sweeps.

## Install

Download the Windows setup ZIP or EXE from a successful GitLab **package_windows**
job's artifacts. Ask the maintainer for the approved pipeline/job link.
Corporate Windows x64 devices need approved `uv` tooling, Python 3.13 and network
access to corporate Artifactory during setup. The app wheel is bundled with the
release; third-party dependencies come from Artifactory. No company updater or
Artifactory publication of this application is required.

For ZIP, extract into a stable writable folder, run `setup_environment.bat`, then
`CanopyExplorationStart.bat`. For EXE, run setup and use the Start Menu shortcut.
Open **File > Settings** to select the synced folder containing the circuit workbook.
This is optional for basic analysis: leave it unconfigured if you are not preparing
turn-zone filters.
Updates are manual: download and install a newer approved job artifact.

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
