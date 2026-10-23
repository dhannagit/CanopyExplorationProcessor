# Windows Distribution

## Deployment Model

Canopy Exploration Processor is distributed as a Python wheel through corporate 
Artifactory. A thin Windows installer provisions an isolated Python 3.13 environment 
using `uv`, adds Start Menu shortcuts, and registers an uninstaller. Recipients do 
not need the source checkout. This is an online installer, not a frozen or offline 
executable.

The application wheel includes `runtime-requirements.txt`: exact runtime package
versions and SHA-256 hashes for Windows x64/Python 3.13, including the GUI extra.
Installing the wheel alone without its dependencies is only a bootstrap step.
The deployment controller reads its lock through distribution metadata without
importing application code, installs the hashed dependencies, runs `uv pip check`,
and constructs the Qt/Matplotlib workbench offscreen before activation.

## Prerequisites

- Managed Windows x64 PC and an approved `uv.exe`, on PATH or inside
  `C:\Bib\Prod\Miniforge3` / `C:\Bib\Prod\Miniconda3-64`.
- Python 3.13 available locally or obtainable through uv's approved runtime
  download route. Corporate Artifactory access alone does not guarantee that
  Python downloads are allowed. Runtime selection currently accepts any 3.13 patch;
  release validation used 3.13.14. Pin a corporate-approved patch in both scripts
  if organizational policy requires one.
- Read access to `https://artifactory.michelin.com/api/pypi/pypi/simple`, including
  the application and every locked dependency. Configure corporate CA trust and
  approved authentication outside scripts. Never add insecure/trusted-host flags
  or embed credentials in scripts, URLs or release artifacts.
- Write permission to the chosen installation folder. Default:
  `C:\Bib\Prod\CanopyExplorationProcessor`. The installer does not request elevation
  or modify global Python/PATH. IT must provision folder permissions if necessary;
  ongoing updates also need write access.
- PowerShell scripts permitted by corporate execution policy. Sign scripts and the
  installer through the approved process as needed; these scripts do not bypass
  execution policy. AppLocker/WDAC restrictions require IT approval.
- Release builders additionally need Python 3.13, `uv`, and Inno Setup 6 to produce
  the installer executable. The existing DataConverter installer source was not
  available; the included recipe uses Inno Setup independently.

## Build A Release

From a PowerShell terminal in the repository root:

```powershell
.\installer\build_release.ps1
```

This uses the committed dependency lock and produces a wheel, source archive and
`dist/release-<version>.json` with wheel/lock hashes. To deliberately resolve a new
dependency set, review the lock diff and rerun all release checks:

```powershell
.\installer\build_release.ps1 -RefreshLock
```

Use a unique stable `major.minor.patch` version in `pyproject.toml` for each release.
Never overwrite an already published wheel, including `0.1.0`. Installer updates
reject prereleases, development versions and unsupported version formats.

Validate before publishing:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m pytest tests/test_installer.py tests/test_ui_settings.py
```

Run the remaining regression suite with its required `DATA_Raw`, `DATA_dXpx` and
`BaselineExample` fixtures provisioned. Several existing tests cannot even collect
without these external datasets; do not interpret focused tests as full analysis
parity validation.

Create a disposable Python 3.13 environment in its final temporary path. Install
the built wheel with `uv pip install --no-deps`, then install the embedded lock with
`uv pip install --require-hashes --only-binary :all: -r <installed-lock>` using the
corporate index. Run `uv pip check` and
`python -m canopy_processor.ui.smoke_test` outside the repository. Test a real study,
turn-zone generation, baseline analysis and plotting on a representative team PC.

Only after those gates pass, publish the wheel and source archive to the approved
Artifactory upload repository. The simple/install URL above is **not** an upload
URL; obtain the upload endpoint and permissions from the repository owner.

```powershell
uv pip install --python .venv\Scripts\python.exe ".[release]" --index-url https://artifactory.michelin.com/api/pypi/pypi/simple
.\.venv\Scripts\python.exe -m twine check dist\canopy_exploration_processor-<version>*
.\.venv\Scripts\python.exe -m twine upload --repository-url <approved-upload-endpoint> dist\canopy_exploration_processor-<version>*
```

Use approved keyring/credential tooling or direct terminal prompts, never command
line secrets. Archive the release JSON with the artifacts in the release record.
Stable publication makes a version eligible for automatic updates immediately;
use a separate staging repository to validate candidates before promoting them.

Once the stable wheel is readable from the install index, compile the installer:

```powershell
.\installer\build_release.ps1 -CompileInstaller
```

Output: `installer/output/CanopyExplorationProcessor-<version>-Setup.exe`.
Initial setup selects that exact package version; subsequent launches check for
newer stable versions. The default Windows installer/shortcut icon is used until
an approved product icon is supplied. Sign and pilot the resulting installer
before distributing it through the team channel. Do not share a copied `.venv`.

## User Setup

1. Install the signed setup executable while connected to the corporate network.
2. Open **Canopy Exploration Processor** from the Start Menu.
3. Open **File > Settings** and enter or browse to the locally synced
   SharePoint/OneDrive folder containing `CircuitsData_Canopy_Hypercar.xlsx` directly.
4. Save settings, then select and load the study.

This is filesystem access, not a SharePoint URL/API integration. Use OneDrive's
**Always keep on this device** for the workbook when offline availability matters.
Each teammate configures their own local sync path; paths differ between users.
The workbook must be readable and have a `Turns` sheet with circuit names. Full
numeric turn-zone validation still happens when generating zones.

Settings use Windows per-user QSettings under the Canopy-specific namespace
`canopy-exploration-processor/canopy-exploration-ui`, key
`paths/circuit_resource_dir`. They are separate from DataConverter's settings and
survive app updates. Cancel does not save changes. Clearing the setting is allowed.
Startup does not require a workbook; dependent operations report missing resources.
Folder changes apply to the next study load, not to an already loaded dataset.
External edits to the workbook are not snapshotted or versioned by the application.

## Updates And Recovery

The launcher checks for stable updates automatically. It creates a candidate
environment at `envs/release-<unique-id>` and only replaces `active.json` after
dependency and GUI checks pass. The old active environment is retained, and no
environment is renamed or copied after creation. Network calls have short HTTP
timeouts/retries and each deployment subprocess has a 180-second time limit;
a failed update can delay launch but must not invalidate the installed version.

A running Canopy Python process defers updates. A file lock serializes deployment
operations; another launcher can use the existing release while an update runs.
No analysis process is forcibly terminated. The Start Menu update shortcut performs
the same stable-update operation on demand. On launch, a failed update is logged
and the existing release is started. First installation has no fallback and reports
failure if the environment cannot be prepared.

Close all Canopy windows before rolling back:

```powershell
& 'C:\Bib\Prod\CanopyExplorationProcessor\deployment.ps1' -Mode Rollback
```

Rollback revalidates the previous release and pauses automatic updates. Run the
manual updater to install a corrected release and resume them. Retained environments
consume disk space; this initial implementation retains old successful releases
until uninstall, rather than risk removing an environment another session needs.

Logs are under `%LOCALAPPDATA%\CanopyExplorationProcessor\logs`: `deployment.log`
for activation/errors and rotating `application.log` files for GUI exceptions.
Tool stdout/stderr is captured privately and discarded rather than copying possible
repository credentials into logs. Use approved tooling interactively to diagnose
detailed repository/runtime provisioning errors. Console-free GUI errors show a
message pointing to the application log.

Uninstall removes only application-owned environments, state and installed files.
It refuses to remove a running application and leaves user settings, logs, shared
workbooks, study data and exports alone.

## Release Acceptance Checklist

- Fresh managed PC: install, shortcuts, first settings save, real study analysis.
- Settings: valid/empty/missing folder, Cancel, corrupt or missing `Turns` workbook,
  spaces/non-ASCII in sync paths, cloud-only and offline files, next-study behavior.
- Update: newer stable release, no update, unavailable network, failed installation,
  interrupted candidate preparation, current session open, simultaneous launchers.
- Recovery: previous environment retained, failed smoke check leaves active state
  unchanged, manual rollback and subsequent manual update.
- Uninstall: app closed, app running, external resources and user settings retained.
- Corporate validation: trusted certificates, authenticated repository, runtime
  provisioning, signing, ordinary-user install/update permissions and antivirus.