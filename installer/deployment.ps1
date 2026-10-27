param(
    [ValidateSet('Setup', 'Launch', 'Rollback', 'Remove', 'CheckIdle')]
    [string]$Mode = 'Launch',
    [string]$InstallDirectory = $PSScriptRoot,
    [string]$IndexUrl = 'https://artifactory.michelin.com/api/pypi/pypi/simple',
    [string]$ReleaseVersion = '',
    [string]$PayloadDirectory = (Join-Path $PSScriptRoot 'payload')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PackageName = 'canopy-exploration-processor'
$InstallDirectory = [IO.Path]::GetFullPath($InstallDirectory)
$EnvironmentDirectory = Join-Path $InstallDirectory 'envs'
$StatePath = Join-Path $InstallDirectory 'active.json'
$LogDirectory = Join-Path $env:LOCALAPPDATA 'CanopyExplorationProcessor\logs'
New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
$LogPath = Join-Path $LogDirectory 'deployment.log'
$env:UV_SYSTEM_CERTS = '1'
$env:UV_HTTP_TIMEOUT = '15'
$env:UV_HTTP_RETRIES = '1'
$env:UV_NO_PROGRESS = '1'
$env:PYTHONUTF8 = '1'

function Write-Log([string]$Message) {
    Add-Content -LiteralPath $LogPath -Value "$(Get-Date -Format o) $Message"
}

function Get-EnvironmentPath([string]$Name) {
    if ($Name -notmatch '^release-[a-f0-9]{32}$') { throw 'Invalid environment identifier' }
    $path = Join-Path $EnvironmentDirectory $Name
    if ((Test-Path -LiteralPath $path) -and ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Application environments must not be links'
    }
    return $path
}

function Read-State {
    if (-not (Test-Path -LiteralPath $StatePath)) { return $null }
    $state = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
    Get-EnvironmentPath $state.current | Out-Null
    return $state
}

function Write-State($State) {
    $temporary = "$StatePath.$([guid]::NewGuid().ToString('N')).tmp"
    [IO.File]::WriteAllText($temporary, ($State | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
    if (Test-Path -LiteralPath $StatePath) {
        [IO.File]::Replace($temporary, $StatePath, "$StatePath.bak")
    } else {
        [IO.File]::Move($temporary, $StatePath)
    }
}

function Test-RunningSession {
    $prefix = $EnvironmentDirectory.TrimEnd('\') + '\'
    $processes = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe' OR Name = 'canopy-exploration.exe'"
    foreach ($process in $processes) {
        if ($process.ExecutablePath -and $process.ExecutablePath.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Find-Uv {
    $command = Get-Command uv.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    foreach ($root in @('C:\Bib\Prod\Miniforge3', 'C:\Bib\Prod\Miniconda3-64')) {
        foreach ($relative in @('Library\bin\uv.exe', 'Scripts\uv.exe')) {
            $candidate = Join-Path $root $relative
            if (Test-Path -LiteralPath $candidate) { return $candidate }
        }
    }
    throw 'uv is unavailable. Install the approved corporate Python tooling, then retry setup.'
}

function Invoke-Tool([string]$Executable, [string[]]$ToolArguments, [int]$TimeoutSeconds = 180) {
    $quoted = $ToolArguments | ForEach-Object {
        if ($_.Contains('"')) { throw 'Unexpected quote in deployment argument' }
        '"' + $_ + '"'
    }
    $info = [Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $Executable
    $info.Arguments = $quoted -join ' '
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.StandardOutputEncoding = [Text.Encoding]::UTF8
    $info.StandardErrorEncoding = [Text.Encoding]::UTF8
    $process = [Diagnostics.Process]::Start($info)
    $output = $process.StandardOutput.ReadToEndAsync()
    $errors = $process.StandardError.ReadToEndAsync()
    try {
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            $process.Kill()
            $process.WaitForExit()
            throw 'Deployment command timed out'
        }
        $process.WaitForExit()
        if ($process.ExitCode -ne 0) {
            throw "Deployment command failed (exit $($process.ExitCode)); verify network, certificates and repository access"
        }
        return $output.GetAwaiter().GetResult()
    } finally {
        $process.Dispose()
    }
}

function Install-Release($CurrentState) {
    $uri = [uri]$IndexUrl
    if ($uri.Scheme -ne 'https' -or $uri.UserInfo) { throw 'Use an HTTPS repository URL without embedded credentials' }
    if (Test-RunningSession) { throw 'Close Canopy sessions before setup' }
    $manifestPath = Join-Path $PayloadDirectory 'release.json'
    if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Release payload is missing release.json; download the complete GitHub Release installer or ZIP' }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $version = $manifest.version
    if ($version -notmatch '^\d+\.\d+\.\d+$') { throw 'Only stable major.minor.patch releases are supported' }
    if ($ReleaseVersion -and $ReleaseVersion -ne $version) { throw 'Installer and bundled release versions do not match' }
    if ($manifest.python -ne '3.13' -or $manifest.platform -ne 'Windows x64') { throw 'Unsupported release platform or Python version' }
    $expectedWheel = "canopy_exploration_processor-$version-py3-none-any.whl"
    if ($manifest.wheel -ne $expectedWheel) { throw 'Release manifest contains an unexpected wheel filename' }
    $wheel = Join-Path $PayloadDirectory $expectedWheel
    if (-not (Test-Path -LiteralPath $wheel)) { throw 'Bundled application wheel is missing' }
    if ($manifest.wheelSha256 -notmatch '^[a-fA-F0-9]{64}$' -or (Get-FileHash -LiteralPath $wheel -Algorithm SHA256).Hash -ne $manifest.wheelSha256) {
        throw 'Bundled application wheel checksum does not match release.json'
    }
    if ($CurrentState) {
        if ([version]$version -lt [version]$CurrentState.version) { throw 'An older release cannot replace the installed version; use Rollback for recovery' }
        if ($version -eq $CurrentState.version) { Write-Log "Already on release $version"; return }
    }
    $uv = Find-Uv
    $name = 'release-' + [guid]::NewGuid().ToString('N')
    $candidate = Get-EnvironmentPath $name
    $python = Join-Path $candidate 'Scripts\python.exe'
    $activated = $false
    try {
        Invoke-Tool $uv @('venv', $candidate, '--python', '3.13') | Out-Null
        Invoke-Tool $uv @('pip', 'install', '--python', $python, '--no-index', '--no-deps', $wheel) | Out-Null
        $installedVersion = (Invoke-Tool $python @('-c', "from importlib.metadata import version; print(version('$PackageName'))")).Trim()
        if ($installedVersion -ne $version) { throw 'Installed wheel version does not match release.json' }
        $lock = (Invoke-Tool $python @('-c', "from importlib.metadata import distribution; print(distribution('$PackageName').locate_file('canopy_processor/runtime-requirements.txt'))")).Trim()
        if (-not (Test-Path -LiteralPath $lock)) { throw 'Release wheel is missing its dependency lock' }
        if ($manifest.lockSha256 -notmatch '^[a-fA-F0-9]{64}$' -or (Get-FileHash -LiteralPath $lock -Algorithm SHA256).Hash -ne $manifest.lockSha256) {
            throw 'Runtime dependency lock checksum does not match release.json'
        }
        Invoke-Tool $uv @('pip', 'install', '--python', $python, '--index-url', $IndexUrl,
            '--require-hashes', '--only-binary', ':all:', '-r', $lock) | Out-Null
        Invoke-Tool $uv @('pip', 'check', '--python', $python) | Out-Null
        Invoke-Tool $python @('-m', 'canopy_processor.ui.smoke_test') | Out-Null
        $previous = $null
        if ($CurrentState) { $previous = $CurrentState.current }
        Write-State ([ordered]@{current = $name; previous = $previous; version = $version})
        $activated = $true
        Write-Log "Activated bundled GitHub release $version"
    } finally {
        if (-not $activated -and (Test-Path -LiteralPath $candidate)) {
            Remove-Item -LiteralPath $candidate -Recurse -Force
        }
    }
}

function Start-Application($State) {
    if (-not $State) { throw 'Application is not installed. Run setup first.' }
    $pythonw = Join-Path (Get-EnvironmentPath $State.current) 'Scripts\pythonw.exe'
    if (-not (Test-Path -LiteralPath $pythonw)) { throw 'Active environment is missing; reinstall or roll back' }
    Start-Process -FilePath $pythonw -ArgumentList @('-m', 'canopy_processor.ui.app') -WorkingDirectory $InstallDirectory | Out-Null
}

function Restore-PreviousRelease($State) {
    if (Test-RunningSession) { throw 'Close Canopy before rolling back' }
    if (-not $State -or -not $State.previous) { throw 'No previous release is available' }
    $python = Join-Path (Get-EnvironmentPath $State.previous) 'Scripts\python.exe'
    $version = (Invoke-Tool $python @('-c', "from importlib.metadata import version; print(version('$PackageName'))")).Trim()
    Invoke-Tool $python @('-m', 'canopy_processor.ui.smoke_test') | Out-Null
    Write-State ([ordered]@{current = $State.previous; previous = $State.current; version = $version})
    Write-Log "Rolled back to $version; launch does not check for updates"
}

function Remove-Releases {
    if (Test-RunningSession) { throw 'Close Canopy before uninstalling' }
    if (Test-Path -LiteralPath $EnvironmentDirectory) {
        foreach ($directory in Get-ChildItem -LiteralPath $EnvironmentDirectory -Directory) {
            if ($directory.Name -match '^release-[a-f0-9]{32}$') {
                $path = Get-EnvironmentPath $directory.Name
                Remove-Item -LiteralPath $path -Recurse -Force
            }
        }
    }
    Remove-Item -LiteralPath $StatePath, "$StatePath.bak" -Force -ErrorAction SilentlyContinue
    Write-Log 'Removed application environments; user settings and data retained'
}

if ($MyInvocation.InvocationName -eq '.') { return }

$guard = $null
try {
    New-Item -ItemType Directory -Force -Path $InstallDirectory | Out-Null
    foreach ($directory in @($InstallDirectory, $EnvironmentDirectory)) {
        if ((Test-Path -LiteralPath $directory) -and ((Get-Item -LiteralPath $directory).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Installation directories must not be links'
        }
    }
    try {
        $guard = [IO.File]::Open((Join-Path $InstallDirectory '.deployment.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    } catch {
        if ($Mode -eq 'Launch') { Start-Application (Read-State); exit 0 }
        throw 'Another setup/update is active, or the installation folder is not writable'
    }
    $state = Read-State
    switch ($Mode) {
        'Setup' { Install-Release $state }
        'Launch' { Start-Application $state }
        'Rollback' { Restore-PreviousRelease $state }
        'CheckIdle' { if (Test-RunningSession) { throw 'Close Canopy before continuing' } }
        'Remove' { Remove-Releases }
    }
} catch {
    Write-Log "Deployment failed: $($_.Exception.Message)"
    [Console]::Error.WriteLine("Canopy deployment failed: $($_.Exception.Message). Logs: $LogPath")
    exit 1
} finally {
    if ($guard) { $guard.Dispose() }
}