param(
    [ValidateSet('Preflight', 'Test', 'Package', 'Finalize')]
    [string]$Phase = 'Preflight'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Test-ReleaseVersion([string]$Version, [string]$Tag) {
    if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw 'Use a stable major.minor.patch project version' }
    if ($Tag -and $Tag -ne "v$Version") { throw 'CI tag must match the version in pyproject.toml' }
}

function Test-RunnerImage([string]$Image) {
    if ($Image -notmatch '^docker\.artifactory\.michelin\.com/[a-z0-9][a-z0-9_./-]*(?::[A-Za-z0-9_][A-Za-z0-9_.-]*|@sha256:[a-fA-F0-9]{64})$' -or $Image -match ':latest$') {
        throw 'Set CANOPY_WINDOWS_IMAGE to an approved versioned Windows image in corporate Artifactory'
    }
}

function Test-ProductionPolicy([string]$Kind, [string]$Tag, [string]$Protected, [string]$Approved, [string]$SigningPolicy) {
    if ($Kind -ne 'production') { return $false }
    if ($Tag -notmatch '^v\d+\.\d+\.\d+$' -or $Protected -ne 'true' -or $Approved -ne 'true') {
        throw 'Production artifacts require an approved protected version tag'
    }
    if ($SigningPolicy -notin @('required', 'not-required')) { throw 'Set the approved production signing policy explicitly' }
    return $SigningPolicy -eq 'required'
}

function Get-TestArguments([bool]$FullSuite) {
    if ($FullSuite) { return @('-m', 'pytest') }
    return @(
        '-m', 'pytest', 'tests/test_ci.py', 'tests/test_cleanup.py', 'tests/test_installer.py', 'tests/test_ui_settings.py',
        'tests/test_ui_discovery.py', 'tests/test_ui_main_window.py', 'tests/test_config.py',
        'tests/test_exporting.py', 'tests/test_plot_data.py', 'tests/test_plotting.py',
        'tests/test_ui_session.py', 'tests/test_ui_worker.py', '-k',
        'not sample_sources and not track_temperature and not populates_discovered and not persists_multiple and not manual_dxpx'
    )
}

function Get-CiUv {
    $command = Get-Command uv.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    foreach ($directory in @('C:\Bib\Prod\Miniforge3', 'C:\Bib\Prod\Miniconda3-64')) {
        foreach ($relative in @('Library\bin\uv.exe', 'Scripts\uv.exe')) {
            $candidate = Join-Path $directory $relative
            if (Test-Path -LiteralPath $candidate) { return $candidate }
        }
    }
    throw 'Provision approved uv tooling for the Windows runner service account'
}

function Test-ArtifactChecksums([string]$Directory) {
    $checksumFile = Join-Path $Directory 'SHA256SUMS.txt'
    if (-not (Test-Path -LiteralPath $checksumFile)) { throw 'Release checksums are missing' }
    $lines = @(Get-Content -LiteralPath $checksumFile | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($lines.Count -eq 0) { throw 'Release checksum list is incomplete' }
    $names = @()
    foreach ($line in $lines) {
        if ($line -notmatch '^([a-f0-9]{64})  ([^\\/]+)$') { throw 'Invalid release checksum entry' }
        $digest = $Matches[1]
        $name = $Matches[2]
        if ($name -eq '.' -or $name -eq '..') { throw 'Invalid release asset name' }
        if ($names -contains $name) { throw 'Duplicate release checksum entry' }
        $names += $name
        $actual = (Get-FileHash -LiteralPath (Join-Path $Directory $name) -Algorithm SHA256).Hash
        if ($actual -ne $digest) { throw "Release checksum mismatch: $name" }
    }
    $actualNames = @(Get-ChildItem -LiteralPath $Directory -File | Where-Object Name -ne 'SHA256SUMS.txt' | ForEach-Object Name)
    if (Compare-Object $names $actualNames) { throw 'Release checksum list is incomplete' }
}

function Test-InstalledBundle([string]$Archive, [string]$Version) {
    $smokeRoot = if ($env:CI -eq 'true') {
    Join-Path $env:SystemDrive 'cs'
    } else {
    [IO.Path]::GetTempPath()
    }
    $temporary = Join-Path $smokeRoot ([guid]::NewGuid().ToString('N'))
    $install = Join-Path $temporary 'app'
    $oldLocalAppData = $env:LOCALAPPDATA
    $oldFindLinks = $env:UV_FIND_LINKS
    $operationFailed = $false

    try {
        $env:LOCALAPPDATA = Join-Path $temporary 'user'
        $env:UV_FIND_LINKS = $null
        Expand-Archive -LiteralPath $Archive -DestinationPath $temporary
        $bundle = Join-Path $temporary "CanopyExplorationProcessor-$Version-Windows-x64"

        & (Join-Path $bundle 'deployment.ps1') -Mode Setup -InstallDirectory $install
        if ($LASTEXITCODE -ne 0) {
            throw 'Installed-bundle dependency/Qt smoke check failed'
        }

        if (-not (Test-Path -LiteralPath (Join-Path $install 'active.json'))) {
            throw 'Smoke installation was not activated'
        }

        & (Join-Path $bundle 'deployment.ps1') -Mode Remove -InstallDirectory $install
        if ($LASTEXITCODE -ne 0) {
            throw 'Smoke installation removal failed'
        }
    } catch {
        $operationFailed = $true
        throw
    } finally {
        $env:LOCALAPPDATA = $oldLocalAppData
        $env:UV_FIND_LINKS = $oldFindLinks

        try {
            if (Test-Path -LiteralPath $temporary) {
                Remove-Item -LiteralPath $temporary -Recurse -Force -ErrorAction Stop
            }
        } catch {
            if ($operationFailed) {
                Write-Warning "Temporary-folder cleanup also failed: $($_.Exception.Message)"
            } else {
                throw
            }
        }
    }
}

function Test-InstalledNsis([string]$Installer, [string]$Version, [string]$Python) {
    $smokeRoot = if ($env:CI -eq 'true') { Join-Path $env:SystemDrive 'cs' } else { [IO.Path]::GetTempPath() }
    $temporary = Join-Path $smokeRoot ([guid]::NewGuid().ToString('N'))
    $install = Join-Path $temporary 'app'
    $oldLocalAppData = $env:LOCALAPPDATA
    $operationFailed = $false
    try {
        New-Item -ItemType Directory -Force -Path $install | Out-Null
        $env:LOCALAPPDATA = Join-Path $temporary 'user'
        $process = Start-Process -FilePath $Installer -ArgumentList @('/S', "/D=$install") -PassThru -Wait
        if ($process.ExitCode -ne 0) { throw "NSIS setup failed (exit $($process.ExitCode))" }
        $state = Join-Path $install 'active.json'
        if (-not (Test-Path -LiteralPath $state)) { throw 'NSIS setup did not activate the installed application' }
        $saved = Get-Content -LiteralPath $state -Raw | ConvertFrom-Json
        if ($saved.version -ne $Version) { throw 'NSIS installed a different application version' }
        $sentinel = Join-Path $install 'retain-this-user-file.txt'
        Set-Content -LiteralPath $sentinel -Value 'preserve'
        $uninstaller = Join-Path $install 'uninst.exe'
        if (-not (Test-Path -LiteralPath $uninstaller)) { throw 'NSIS uninstaller was not created' }
        $process = Start-Process -FilePath $uninstaller -ArgumentList '/S' -PassThru -Wait
        if ($process.ExitCode -ne 0) { throw "NSIS uninstall failed (exit $($process.ExitCode))" }
        if (Test-Path -LiteralPath $state) { throw 'NSIS uninstall left the application state behind' }
        if (-not (Test-Path -LiteralPath $sentinel)) { throw 'NSIS uninstall deleted a file it did not install' }
    } catch {
        $operationFailed = $true
        throw
    } finally {
        $env:LOCALAPPDATA = $oldLocalAppData
        try {
            $environmentDirectory = Join-Path $install 'envs'
            if (Test-Path -LiteralPath $environmentDirectory) {
                foreach ($environment in Get-ChildItem -LiteralPath $environmentDirectory -Directory) {
                    if ($environment.Name -match '^release-[a-f0-9]{32}$') {
                        & $Python -I (Join-Path $PSScriptRoot '..\installer\cleanup.py') `
                            --install-directory $install --release-name $environment.Name
                        if ($LASTEXITCODE -ne 0) { throw "Smoke cleanup failed for $($environment.Name)" }
                    }
                }
            }
            if (Test-Path -LiteralPath $temporary) {
                Remove-Item -LiteralPath $temporary -Recurse -Force -ErrorAction Stop
            }
        } catch {
            if ($operationFailed) { Write-Warning "NSIS smoke cleanup also failed: $($_.Exception.Message)" }
            else { throw }
        }
    }
}

function Finalize-Release([string]$ReleaseDirectory, [string]$Version, [string]$Python, [bool]$SignRelease) {
    $executableName = "CanopyExplorationProcessor-$Version-Setup.exe"
    $candidate = Join-Path $root "nsis_compile_files\$executableName"
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { throw 'NSIS job artifact is missing the expected setup executable' }
    if ($SignRelease) {
        & (Join-Path $PSScriptRoot 'sign_artifact.ps1') -Path $candidate -Kind Executable -VerifyOnly
        if ($LASTEXITCODE -ne 0) { throw 'NSIS setup signature verification failed' }
    }
    Copy-Item -LiteralPath $candidate -Destination (Join-Path $ReleaseDirectory $executableName) -Force
    $checksums = Get-ChildItem -LiteralPath $ReleaseDirectory -File | Where-Object Name -ne 'SHA256SUMS.txt' | Sort-Object Name | ForEach-Object {
        (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() + '  ' + $_.Name
    }
    $checksums | Set-Content -LiteralPath (Join-Path $ReleaseDirectory 'SHA256SUMS.txt') -Encoding ASCII
    Test-ArtifactChecksums $ReleaseDirectory
    Test-InstalledBundle (Join-Path $ReleaseDirectory "CanopyExplorationProcessor-$Version-Windows-x64.zip") $Version
    Test-InstalledNsis (Join-Path $ReleaseDirectory $executableName) $Version $Python
}

if ($MyInvocation.InvocationName -eq '.') { return }

$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitProcess) { throw 'CI requires a Windows x64 PowerShell runner' }
    if ($env:UV_INSECURE_HOST) { throw 'CI must use approved certificate trust, not UV_INSECURE_HOST' }
    if ($env:CI -eq 'true') {
        Test-RunnerImage $env:CANOPY_WINDOWS_IMAGE
        if ($env:CI_JOB_IMAGE -and $env:CI_JOB_IMAGE -ne $env:CANOPY_WINDOWS_IMAGE) { throw 'Runner image differs from the configured Windows image' }
        Get-CimInstance Win32_Process -Filter "ProcessId = $PID" -ErrorAction Stop | Out-Null
    }
    $env:UV_SYSTEM_CERTS = '1'
    if (-not $env:UV_PYTHON_INSTALL_MIRROR) {
        $env:UV_PYTHON_INSTALL_MIRROR = 'https://artifactory.michelin.com/artifactory/github-generic/astral-sh/python-build-standalone/releases/download'
    }
    $uv = Get-CiUv
    $pythonOutput = & $uv python find --offline 3.13
    if ($LASTEXITCODE -ne 0) { throw 'Provision approved Python 3.13 for the runner before enabling CI' }
    $python = ($pythonOutput | Out-String).Trim()
    $version = (& $python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])").Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Could not read the project version' }
    Test-ReleaseVersion $version $env:CI_COMMIT_TAG
    $buildKind = $env:CANOPY_BUILD_KIND
    if ($env:CI -eq 'true' -and $env:CI_ENVIRONMENT_TIER -eq 'production') { $buildKind = 'production' }
    $signRelease = Test-ProductionPolicy $buildKind $env:CI_COMMIT_TAG $env:CI_COMMIT_REF_PROTECTED $env:CANOPY_RELEASE_APPROVED $env:CANOPY_SIGNING_POLICY
    if ($signRelease) { & (Join-Path $PSScriptRoot 'sign_artifact.ps1') -CheckConfiguration }
    $compileInstaller = $env:CANOPY_COMPILE_INSTALLER -eq 'true'
    New-Item -ItemType Directory -Force -Path reports | Out-Null
    switch ($Phase) {
        'Preflight' {
            @(
                "version=$version", "commit=$env:CI_COMMIT_SHA", "phase=$Phase",
                "compile_installer=$compileInstaller", "full_tests=$($env:CANOPY_FULL_TESTS -eq 'true')",
                "build_kind=$buildKind", "signing_required=$signRelease"
            ) | Set-Content -LiteralPath reports/ci-context.txt -Encoding UTF8
            Write-Output 'Windows, uv, Python, tag/version and release-policy preflight passed. Corporate index access is checked during dependency installation.'
        }
        'Test' {
            $env:QT_QPA_PLATFORM = 'offscreen'
            if (-not $env:UV_PROJECT_ENVIRONMENT) { $env:UV_PROJECT_ENVIRONMENT = Join-Path $root '.ci-venv' }
            & $uv sync --locked --extra gui --extra test --group dev --python $python
            if ($LASTEXITCODE -ne 0) { throw 'Locked CI dependency installation failed; check approved index authentication and certificates' }
            $testPython = Join-Path $env:UV_PROJECT_ENVIRONMENT 'Scripts\python.exe'
            $fullSuite = $env:CANOPY_FULL_TESTS -eq 'true'
            if (-not $fullSuite) { Write-Warning 'Running fixture-independent tests only; full dataset/numerical parity is not validated by this job' }
            $arguments = @(Get-TestArguments $fullSuite) + @(
                '-q', '--junitxml=reports/junit.xml', '--basetemp',
                (Join-Path ([IO.Path]::GetTempPath()) ('canopy-exploration-processor-ci-pytest-' + [guid]::NewGuid().ToString('N')))
            )
            & $testPython @arguments
            if ($LASTEXITCODE -ne 0) { throw 'CI test suite failed' }
        }
        'Package' {
            & (Join-Path $root 'installer\build_release.ps1') -SignRelease:$signRelease
            if ($LASTEXITCODE -ne 0) { throw 'CI release build failed' }
            $assets = Join-Path $root "dist\releases\v$version"
            Test-ArtifactChecksums $assets
            Test-InstalledBundle (Join-Path $assets "CanopyExplorationProcessor-$version-Windows-x64.zip") $version
            Write-Output "Verified release artifacts: $assets"
        }
        'Finalize' {
            if (-not $compileInstaller) { throw 'NSIS installer compilation must be enabled before finalizing a release' }
            $assets = Join-Path $root "dist\releases\v$version"
            Finalize-Release $assets $version $python $signRelease
            Write-Output "Verified NSIS release artifacts: $assets"
        }
    }
} finally {
    Pop-Location
}