param(
    [ValidateSet('Setup', 'Launch', 'Update', 'Rollback', 'Remove', 'CheckIdle')]
    [string]$Mode = 'Launch',
    [string]$InstallDirectory = $PSScriptRoot,
    [string]$IndexUrl = 'https://artifactory.michelin.com/api/pypi/pypi/simple',
    [string]$ReleaseVersion = ''
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
    if (Test-RunningSession) {
        if ($CurrentState) { Write-Log 'Update deferred: an application session is running'; return }
        throw 'Close running Canopy sessions before setup'
    }
    $uv = Find-Uv
    if ($ReleaseVersion -and ($Mode -ne 'Setup' -or $ReleaseVersion -notmatch '^\d+\.\d+\.\d+$')) {
        throw 'An exact stable release version may only be selected during setup'
    }
    $name = 'release-' + [guid]::NewGuid().ToString('N')
    $candidate = Get-EnvironmentPath $name
    $python = Join-Path $candidate 'Scripts\python.exe'
    $activated = $false
    try {
        Invoke-Tool $uv @('venv', $candidate, '--python', '3.13') | Out-Null
        $requirement = $PackageName
        if ($ReleaseVersion) { $requirement += '==' + $ReleaseVersion }
        elseif ($CurrentState) { $requirement += '>=' + $CurrentState.version }
        Invoke-Tool $uv @('pip', 'install', '--python', $python, '--index-url', $IndexUrl,
            '--prerelease', 'disallow', '--no-deps', '--only-binary', ':all:', $requirement) | Out-Null
        $version = (Invoke-Tool $python @('-c', "from importlib.metadata import version; print(version('$PackageName'))")).Trim()
        if ($version -notmatch '^\d+\.\d+\.\d+$') { throw 'Only stable major.minor.patch releases are supported' }
        if ($CurrentState -and ([version]$version -le [version]$CurrentState.version)) {
            if ($Mode -eq 'Update' -and ($CurrentState.PSObject.Properties.Name -contains 'updatesPaused') -and $CurrentState.updatesPaused) {
                $CurrentState.updatesPaused = $false
                Write-State $CurrentState
            }
            Write-Log "Already on stable release $($CurrentState.version)"
            return
        }
        $lock = (Invoke-Tool $python @('-c', "from importlib.metadata import distribution; print(distribution('$PackageName').locate_file('canopy_processor/runtime-requirements.txt'))")).Trim()
        if (-not (Test-Path -LiteralPath $lock)) { throw 'Release wheel is missing its dependency lock' }
        Invoke-Tool $uv @('pip', 'install', '--python', $python, '--index-url', $IndexUrl,
            '--require-hashes', '--only-binary', ':all:', '-r', $lock) | Out-Null
        Invoke-Tool $uv @('pip', 'check', '--python', $python) | Out-Null
        Invoke-Tool $python @('-m', 'canopy_processor.ui.smoke_test') | Out-Null
        $previous = $null
        if ($CurrentState) { $previous = $CurrentState.current }
        Write-State ([ordered]@{current = $name; previous = $previous; version = $version; updatesPaused = $false})
        $activated = $true
        Write-Log "Activated stable release $version"
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
    Write-State ([ordered]@{current = $State.previous; previous = $State.current; version = $version; updatesPaused = $true})
    Write-Log "Rolled back to $version; run the manual updater to resume automatic updates"
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
        'Update' { Install-Release $state }
        'Launch' {
            try {
                if (-not $state -or -not ($state.PSObject.Properties.Name -contains 'updatesPaused') -or -not $state.updatesPaused) {
                    Install-Release $state
                }
            } catch {
                Write-Log "Automatic update failed: $($_.Exception.Message)"
                if (-not $state) { throw }
            }
            Start-Application (Read-State)
        }
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