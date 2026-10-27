# Canopy Exploration Processor

Windows workbench for analyzing Canopy simulation sweeps.

## Install

Download the Windows setup ZIP or EXE from this repository's **Releases** page.
Corporate Windows x64 devices need approved `uv` tooling, Python 3.13 and network
access to corporate Artifactory during setup. The app wheel is bundled with the
release; third-party dependencies come from Artifactory. No company updater or
Artifactory publication of this application is required.

For ZIP, extract into a stable writable folder, run `setup_environment.bat`, then
`CanopyExplorationStart.bat`. For EXE, run setup and use the Start Menu shortcut.
Open **File > Settings** to select the synced folder containing the circuit workbook.
Updates are manual: download and install a newer GitHub Release.

See the [GitHub Release Guide](docs/DISTRIBUTION.md) for prerequisites, building,
GitHub publishing, validation, signing considerations, upgrades and rollback.

## Python Package

Each release also includes a standard wheel for future integration into another
tool. The package remains separate from the Windows installer; no plugin or host
framework integration is imposed on the analysis modules.
