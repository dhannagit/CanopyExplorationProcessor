# GitHub Release Guide

This guide explains how to turn the source code into downloads your teammates can
install. It does not publish anything automatically.

**Maintainers:** follow Prerequisites, Build A Release, then Publish On GitHub.
**Teammates installing the app:** skip to User Setup.

Examples use version `0.1.0`. Replace that number with your actual release version.
Run maintainer commands in PowerShell from the repository folder unless stated
otherwise. Do not copy angle-bracket placeholders into commands without replacing
them with real values.

## Deployment Model

GitHub provides the app download. Corporate Artifactory provides its third-party
Python packages during installation. There is no company updater, and the app
does not check GitHub or Artifactory when it starts.

| Term | What It Means Here |
| --- | --- |
| Release | A named version on GitHub, such as `v0.1.0`, with attached downloads. |
| EXE | Setup program that installs the app, adds Start Menu shortcuts and registers an uninstaller. |
| Windows ZIP | Alternative setup bundle: extract it and run its batch files. No shortcuts or uninstaller registration are added. |
| Wheel (`.whl`) | The Python app package inside both setup options; also supplied separately for future tool integration. |
| Dependency lock | Exact third-party package versions and hashes, stored in the app wheel. |
| Manifest (`.json`) | Version, platform and wheel/dependency-lock hashes used by setup. It is not an installer. |
| Checksum | A file fingerprint used to detect damaged or changed downloads. |

The EXE and ZIP are both **GitHub Release assets**, not separate distribution
systems. Both contain the exact app wheel. Neither contains Python or all its
dependencies, so initial installation is not fully offline. The app itself does
not need to be uploaded to Artifactory.

### Project Layout

```text
src/canopy_processor/       Application code and dependency lock
tests/                     Automated checks
installer/                 GitHub build, setup and launcher source files
docs/                      Release instructions and engineering records
pyproject.toml             App name, version and package requirements
MANIFEST.in                Additional files included in the source archive
README.md                  Short project and installation introduction
dist/github-release/       Generated downloads, grouped by release version
```

Only `dist/github-release/v<version>/` is used for uploads. Temporary build files
are generated under `dist` and removed after the build. Do not commit generated
archives, `.egg-info`, copied source trees, `.venv`, or installed environments.
Local study data and workbooks are not part of the release.

## Prerequisites

### For The Person Building A Release

1. Use a corporate Windows x64 PC with access to the repository and Artifactory.
2. Have approved `uv` tooling and Python 3.13 installed. The build script finds
   `uv.exe` on PATH or in corporate Miniforge/Miniconda locations.
3. Use the existing development `.venv` with the GUI and test dependencies for
   automated tests. Recipients do not need this development environment.
4. To include an EXE, install approved Inno Setup 6.3 or later within version 6.
   Confirm its licence covers the intended corporate use. A compiler reporting
   "Non-commercial use only" needs review by IT before corporate distribution.
5. Confirm whether IT requires signed PowerShell scripts, the setup EXE or the
   generated uninstaller. Local scripts working unsigned is not proof that
   downloaded scripts will be allowed on teammates' PCs.

Build inside the corporate network. Ordinary GitHub-hosted runners are not assumed
to reach internal Artifactory. Self-hosted CI can be considered separately later.

### For Anyone Installing The App

- Corporate Windows x64, approved `uv`, and Python 3.13 already available or
  obtainable through the approved uv runtime download route. Artifactory access
  alone does not guarantee that Python downloads are allowed.
- Read access to `https://artifactory.michelin.com/api/pypi/pypi/simple` for every
  locked dependency. Authentication and corporate certificate trust must be
  configured through approved tooling, not embedded in this release.
- Permission to write to the install folder. The EXE defaults to
  `C:\Bib\Prod\CanopyExplorationProcessor` and does not request admin elevation.
  IT may need to provision that folder. A stable folder under `%LOCALAPPDATA%`
  can be chosen instead. Later upgrades also need write access.
- PowerShell scripts allowed by corporate execution policy and application-control
  rules. Do not disable certificate checks or bypass IT policy to install.

The scripts accept Python 3.13 patch releases; validation has used 3.13.14. If IT
requires an exact patch, coordinate changes to build/setup scripts and retest.
The app does not change global Python or PATH settings.

## Build A Release

### Step 1: Open The Project

Open PowerShell and enter the repository folder:

```powershell
Set-Location C:\Bib\Git\CanopyExplorationProcessor
```

You should see `pyproject.toml`, `installer`, `src` and `tests`. A successful command
is not always enough: stop if a command prints a failure, and resolve it before
continuing.

### Step 2: Choose A Version

Open `pyproject.toml` and check `version` under `[project]`. Use a stable
`major.minor.patch` number, such as `0.1.0` or `0.1.1`. Prerelease/development
formats are not supported by this installer.

Use a new number for every published release. Never replace an already published
version with different files. You can rebuild an unpublished draft while testing.

Set these variables for the commands below, matching the version in the file:

```powershell
$version = '0.1.0'
$assets = Join-Path $PWD "dist\github-release\v$version"
```

### Step 3: Run Automated Tests

Start with the setup and preferences tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_installer.py tests/test_ui_settings.py -q --basetemp (Join-Path $env:TEMP ('canopy-release-tests-' + [guid]::NewGuid().ToString('N')))
```

The final line should report tests passed, with no error traceback. The unique
temporary folder avoids conflicts with older admin-created test directories.

For full analysis/GUI regression testing, provide the `DATA_Raw`, `DATA_dXpx` and
`BaselineExample` sample datasets, then run the full suite. Some tests cannot even
be collected without these external fixtures:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp (Join-Path $env:TEMP ('canopy-full-tests-' + [guid]::NewGuid().ToString('N')))
```

Focused setup tests do not establish numerical parity. Record any unavailable
fixtures or untested workflows in the release notes.

### Step 4: Build The Downloads

To create both the EXE and the ZIP:

```powershell
.\installer\build_release.ps1 -CompileInstaller
```

For ZIP and Python-package assets only, without Inno:

```powershell
.\installer\build_release.ps1
```

The build uses the committed dependency lock. Do not use `-RefreshLock` for an
ordinary release: that option deliberately selects a new dependency set, requiring
lock-file review and renewed regression testing.

Each build replaces the upload folder for that version. A ZIP-only build removes
an EXE from an earlier build of the same version. Do not rebuild after signing or
after uploading the final assets without repeating verification.

On success, the script prints the upload directory. Inspect it:

```powershell
$assets = Join-Path $PWD "dist\github-release\v$version"
Get-ChildItem -LiteralPath $assets
```

| File | Who Needs It |
| --- | --- |
| `CanopyExplorationProcessor-<version>-Setup.exe` | Most Windows users; present only with `-CompileInstaller`. |
| `CanopyExplorationProcessor-<version>-Windows-x64.zip` | Users who prefer extracted-folder setup. |
| `canopy_exploration_processor-<version>-py3-none-any.whl` | Python integration; not a double-click installer. |
| `canopy_exploration_processor-<version>.tar.gz` | Source archive for developers. |
| `release-<version>.json` | Release metadata for verification/support. |
| `SHA256SUMS.txt` | Expected hashes of all the other assets. |

No Artifactory app upload, `UV_FIND_LINKS` setting, or GitHub token is needed to
build or test these downloads. The wheel remains a normal Python package for
future integration; no host-tool/plugin framework is implemented now.

### Step 5: Apply Required Signing

If IT requires script signing, sign the final scripts **before Step 4** so signed
copies enter both the ZIP and EXE. Sign the compiled EXE afterward using the
approved certificate/service and timestamp server. Editing signed files breaks
their signatures. Signing setup does not automatically sign its generated
uninstaller; that requires separate Inno signing configuration.

If an EXE changes after the build, regenerate checksums in the upload folder:

```powershell
Get-ChildItem -LiteralPath $assets -File |
    Where-Object Name -ne 'SHA256SUMS.txt' |
    Sort-Object Name |
    ForEach-Object { (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() + '  ' + $_.Name } |
    Set-Content -LiteralPath (Join-Path $assets 'SHA256SUMS.txt') -Encoding ASCII
```

Do not put signing certificates, passwords, tokens or private keys in the repository.

### Step 6: Verify The Files

This checks that every asset still matches its recorded fingerprint:

```powershell
foreach ($line in Get-Content -LiteralPath (Join-Path $assets 'SHA256SUMS.txt')) {
    $expected, $name = $line -split '  ', 2
    $actual = (Get-FileHash -LiteralPath (Join-Path $assets $name) -Algorithm SHA256).Hash
    if ($actual -ne $expected) { throw "Checksum mismatch: $name" }
}
Write-Output 'All release checksums match.'
```

Checksums detect changed files; they do not prove publisher identity or replace
trusted GitHub access and signing requirements.

### Step 7: Test What A Teammate Will Install

Open a **non-administrator** PowerShell window, return to the project folder, and
set `$version` and `$assets` again as in Step 2. Admin testing can hide permission
problems. Stay connected to the corporate network for installation.

To test the EXE, run:

```powershell
Start-Process -FilePath (Join-Path $assets "CanopyExplorationProcessor-$version-Setup.exe") -Wait
```

Choose a separate test folder, not an existing production installation. Confirm
the Start Menu launch works, configure the workbook folder, and analyze a real
study. Then uninstall and check that shared data and preferences were preserved.

To test the ZIP, extract it into a new stable test folder:

```powershell
$testRoot = Join-Path $env:LOCALAPPDATA ('CanopyZipTest-' + [guid]::NewGuid().ToString('N'))
Expand-Archive -LiteralPath (Join-Path $assets "CanopyExplorationProcessor-$version-Windows-x64.zip") -DestinationPath $testRoot
$bundle = Join-Path $testRoot "CanopyExplorationProcessor-$version-Windows-x64"
& (Join-Path $bundle 'setup_environment.bat')
& (Join-Path $bundle 'CanopyExplorationStart.bat')
```

Do not move this folder after setup; its Python environment contains absolute
paths. Setup verifies the bundled wheel/version/lock, installs dependencies with
hash checking from Artifactory, checks compatibility, and constructs the GUI
offscreen before activating it. This is a fresh-environment check, independent
of your source checkout. It is not a substitute for testing the visible app.

Close the app and disconnect from the corporate network. Launch again: the
installed app should open without an update check. Study data and the workbook
must also be physically available locally. Reconnect after this test.

Before a team release, repeat installation on a teammate's PC. Use the Release
Acceptance Checklist below to record exactly what was tested.

## Publish On GitHub

### Step 8: Commit And Tag The Tested Source

Review changes in VS Code Source Control, commit the intended source/documentation
changes, and push that commit. Do not commit local datasets, credentials, `.venv`
or generated release files. Confirm the repository visibility is appropriate for
company code and that the assets match the source being tagged.

A tag names the exact commit behind a release. After pushing the tested commit:

```powershell
git tag "v$version"
git push origin "v$version"
```

If the tag already exists, investigate rather than moving it. Use a new version
and rebuild if the existing version was published.

### Step 9: Create A Draft Release

1. Open the GitHub repository in your browser.
2. Select **Releases**, then **Draft a new release**.
3. Select the matching tag, for example `v0.1.0`.
4. Give it a title such as **Canopy Exploration Processor 0.1.0**.
5. Explain changes, prerequisites, known limitations and what was tested.
6. Attach **every file** from `dist/github-release/v<version>/`.
7. Save the draft and review its downloads before publishing.

Tell teammates to download the Windows EXE or Windows setup ZIP. GitHub also adds
automatic source-code archives; those are not the Windows setup bundle. Do not
upload the whole working directory, corporate dependencies, workbooks or secrets.

Suggested installation note for the release description:

> Windows x64. Requires approved corporate uv tooling, Python 3.13 and access to
> corporate Artifactory during setup. Download the Setup EXE or Windows-x64 ZIP.
> Configure the circuit folder in File > Settings. Upgrades are manual.

Optional: with approved GitHub CLI access, create the same draft from PowerShell:

```powershell
$assetPaths = Get-ChildItem -LiteralPath $assets -File | ForEach-Object FullName
gh release create "v$version" @assetPaths --verify-tag --draft --title "Canopy Exploration Processor $version" --notes 'Windows x64; corporate uv, Python 3.13 and Artifactory access required. Download the Windows setup ZIP or EXE. Upgrades are manual.'
```

### Step 10: Publish After Approval

Finish the checklist, confirm licensing/signing requirements and review the draft.
Then select **Publish release** on GitHub. Share the release page, not your local
build folder. The build scripts never commit, tag, upload or publish for you.
No GitHub token is stored in the app.

## User Setup

These are the steps to give teammates who are not building the app:

1. Open the GitHub Release page and download the Windows EXE or Windows-x64 ZIP,
   plus `SHA256SUMS.txt`. Compare the download's `Get-FileHash -Algorithm SHA256`
   result with its line in that file.
2. Connect to the corporate network so setup can retrieve Python dependencies.
3. For EXE: run setup, select a writable install folder and use the Start Menu
   shortcut. For ZIP: extract into a stable writable folder, run
   `setup_environment.bat`, then `CanopyExplorationStart.bat`.
4. In the app, open **File > Settings**. Select the locally synced
   SharePoint/OneDrive folder containing `CircuitsData_Canopy_Hypercar.xlsx` directly.
   Select a local folder, not a SharePoint web URL.
5. Save, select a study and begin analysis.

The workbook must be readable and have circuit names in its `Turns` sheet. Full
numeric turn-zone validation occurs when generating zones. For offline use, mark
the workbook **Always keep on this device** in OneDrive. Each teammate chooses
their own local sync path; it may differ between users.

Preferences are stored per Windows user with QSettings, under
`canopy-exploration-processor/canopy-exploration-ui`, key `paths/circuit_resource_dir`.
They survive upgrades and are separate from DataConverter. Cancel leaves settings
unchanged; clearing the folder is allowed. Startup works without a workbook, but
features needing it report missing resources. Folder changes apply to the next
study load. The app does not make an immutable copy of the external workbook.

## Upgrades And Recovery

### Upgrade To A New Release

1. Close every Canopy window and download a newer GitHub Release.
2. For EXE, run it against the same install folder. Existing user settings remain.
3. For ZIP, the simplest approach is a new stable folder and fresh setup. Keep
   the old folder until the new version is accepted; settings are shared per user.

For an in-place ZIP upgrade, extract the new ZIP separately and run its
`deployment.ps1 -Mode Setup -InstallDirectory <existing-folder>`. Its adjacent
payload supplies the new wheel. Only after setup succeeds, copy the new scripts,
documentation and payload into the existing folder. Do not copy or replace
`active.json` or `envs`. Never move an installed environment to another location.

Setup builds a candidate in `envs/release-<unique-id>`, validates it, then atomically
changes `active.json` to select it. Failed installation leaves the current release
selected. A deployment lock prevents concurrent setup changes. Running Canopy
blocks setup; processes are never forcibly killed. Old successful environments
are retained until uninstall, which uses more disk space but permits recovery.

An older installer is rejected. Installing the same version does nothing; it is
not a repair of damaged environment files. First installation has no previous
working version to fall back to. Normal launch performs no network/version checks.

### Roll Back After An Upgrade

Rollback means returning to the previous successfully installed version in the
same install folder. It requires a previous environment; a fresh installation has
none. Close the app and run, adjusting the path if you chose another folder:

```powershell
& 'C:\Bib\Prod\CanopyExplorationProcessor\deployment.ps1' -Mode Rollback
```

The previous version is checked and selected. It stays selected until you explicitly
install another release. Separate ZIP installations are switched by launching the
desired folder instead. Test an actual two-version upgrade/rollback before claiming
that workflow has been validated for users.

### Uninstall

For EXE, close Canopy and use Windows Installed Apps or its Start Menu uninstaller.
For ZIP, close Canopy and run `remove_environment.bat`, then delete the remaining
extracted bundle if no longer needed. Removal refuses to proceed while Canopy is
running. It preserves per-user preferences/logs, shared workbooks, studies and exports.

## Troubleshooting

Logs are in `%LOCALAPPDATA%\CanopyExplorationProcessor\logs`. `deployment.log` records
setup/activation failures; rotating `application.log` files record GUI exceptions.
Deployment subprocesses have 180-second limits plus short HTTP timeouts/retries.
Detailed tool output is discarded to avoid logging possible credentials; use
approved corporate tooling interactively if IT needs detailed repository errors.

| Symptom | Next Step |
| --- | --- |
| `uv` is not recognized | Use the corporate Python prompt or check approved Miniforge/Miniconda tooling. Build/setup also search the standard corporate locations. |
| Inno compiler missing | Install approved Inno Setup 6, or build without `-CompileInstaller` for ZIP-only assets. |
| Access denied | Use a writable test/install folder and ask IT about permissions. Admin success does not establish normal-user readiness. |
| Script blocked | Check `Get-ExecutionPolicy -List` and ask IT about signing/application-control policy. Do not bypass it. |
| Repository/certificate failure | Reconnect to the corporate network and check approved authentication/CA configuration. Do not add trusted-host or insecure flags. |
| Missing manifest/checksum mismatch | Download the complete release again. Do not edit the manifest to hide an error. |
| Workbook unavailable offline | Confirm OneDrive has downloaded it and verify File > Settings. Network-drive data may also be unavailable. |
| Test cleanup permission error | Use the unique `--basetemp` command in Step 3, not an older admin-created temp directory. |

## Release Acceptance Checklist

Record results before publishing. Mark anything not tested explicitly; do not
describe the release as fully validated when a required scenario is outstanding.

- [ ] Correct version, matching source commit/tag, final assets and valid checksums.
- [ ] Automated setup/settings tests and available full regression suites passed.
- [ ] Fresh EXE and/or ZIP setup tested as a normal user on a corporate device.
- [ ] Visible app, shortcuts where applicable, real study, zones, baseline and plots tested.
- [ ] Preferences save/cancel, empty/invalid folder, corrupt/missing workbook and cloud/offline files tested.
- [ ] Spaces/non-ASCII paths and locally synced folder differences tested.
- [ ] Ordinary launch works disconnected; setup dependency/network failure is handled.
- [ ] New-version upgrade, same-version no-op, downgrade rejection and tampered/missing payload tested.
- [ ] Failed candidate leaves active version unchanged; two-version rollback tested.
- [ ] Setup/removal with a running session and competing setup attempts handled.
- [ ] Uninstall preserves external resources, studies, exports and per-user settings.
- [ ] Corporate runtime provisioning, certificates, authentication, signing, licence and antivirus requirements confirmed.
- [ ] Teammate pilot completed; prerequisites, limitations and test results included in release notes.
