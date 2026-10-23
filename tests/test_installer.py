import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).parents[1] / "installer" / "deployment.ps1"
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows deployment controller")


def run_powershell(tmp_path: Path, body: str):
    environment = os.environ.copy()
    environment["LOCALAPPDATA"] = str(tmp_path / "user")
    environment["CANOPY_TEST_ROOT"] = str(tmp_path / "installation with spaces \u00e9")
    environment["CANOPY_TEST_SCRIPT"] = str(SCRIPT)
    environment["CANOPY_TEST_PYTHON"] = sys.executable
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", body + "\nexit 0"],
        env=environment, capture_output=True, text=True, timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


BOOTSTRAP = r"""
. $env:CANOPY_TEST_SCRIPT -InstallDirectory $env:CANOPY_TEST_ROOT
New-Item -ItemType Directory -Path $InstallDirectory -Force | Out-Null
$global:versions = @{}
$global:nextVersion = '0.2.0'
$global:failSmoke = $false
$global:running = $false
$global:toolCalls = @()
function Test-RunningSession { return $global:running }
function Find-Uv { return 'fake-uv.exe' }
function Invoke-Tool([string]$Executable, [string[]]$ToolArguments, [int]$TimeoutSeconds = 180) {
    $global:toolCalls += ,$ToolArguments
    if ($ToolArguments[0] -eq 'venv') {
        $directory = $ToolArguments[1]
        New-Item -ItemType Directory -Path (Join-Path $directory 'Scripts') -Force | Out-Null
        New-Item -ItemType File -Path (Join-Path $directory 'Scripts\python.exe') | Out-Null
        $global:versions[$directory] = $global:nextVersion
        return
    }
    if ($ToolArguments[0] -eq '-c') {
        $directory = Split-Path (Split-Path $Executable -Parent) -Parent
        if ($ToolArguments[1].Contains('locate_file')) {
            $lock = Join-Path $directory 'runtime-requirements.txt'
            Set-Content -LiteralPath $lock -Value 'fake-lock'
            return $lock
        }
        return $global:versions[$directory]
    }
    if ($ToolArguments[0] -eq '-m' -and $global:failSmoke) { throw 'simulated Qt failure' }
}
function Assert-True($Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}
"""


def test_install_no_update_and_failed_update_preserve_state(tmp_path):
	run_powershell(tmp_path, BOOTSTRAP + r"""
Install-Release $null
$first = Read-State
Assert-True ($first.version -eq '0.2.0') 'Initial install not activated'
Assert-True ($first.previous -eq $null) 'Initial previous pointer incorrect'
Install-Release $first
Assert-True ((Read-State).current -eq $first.current) 'No-op update changed active environment'
Assert-True (@(Get-ChildItem $EnvironmentDirectory -Directory).Count -eq 1) 'Candidate leaked'
$global:nextVersion = '0.3.0'
$global:failSmoke = $true
try { Install-Release $first; throw 'Expected failed validation' } catch {
    if ($_.Exception.Message -ne 'simulated Qt failure') { throw }
}
Assert-True ((Read-State).current -eq $first.current) 'Failed update changed active environment'
Assert-True (@(Get-ChildItem $EnvironmentDirectory -Directory).Count -eq 1) 'Failed candidate leaked'
$global:failSmoke = $false
Install-Release $first
$second = Read-State
Assert-True ($second.previous -eq $first.current) 'Previous release was not retained'
Assert-True ($second.version -eq '0.3.0') 'New release not activated'
$calls = $global:toolCalls | ForEach-Object { $_ -join ' ' }
Assert-True ([bool]($calls -match '--prerelease disallow')) 'Prereleases not excluded'
Assert-True ([bool]($calls -match '--require-hashes')) 'Lock hashes not required'
""")


def test_running_session_defers_updates_and_rejects_unsafe_paths(tmp_path):
	run_powershell(tmp_path, BOOTSTRAP + r"""
Install-Release $null
$first = Read-State
$global:running = $true
$global:nextVersion = '0.3.0'
Install-Release $first
Assert-True ((Read-State).current -eq $first.current) 'Active session was updated'
try { Get-EnvironmentPath '..\other-app'; throw 'Traversal accepted' } catch {
    if ($_.Exception.Message -ne 'Invalid environment identifier') { throw }
}
$global:running = $false
$global:nextVersion = '0.3.0rc1'
try { Install-Release $first; throw 'Prerelease accepted' } catch {
    if ($_.Exception.Message -ne 'Only stable major.minor.patch releases are supported') { throw }
}
Assert-True ((Read-State).current -eq $first.current) 'Prerelease changed installation'
""")


def test_tool_execution_captures_output_and_handles_failure(tmp_path):
	run_powershell(tmp_path, r"""
. $env:CANOPY_TEST_SCRIPT -InstallDirectory $env:CANOPY_TEST_ROOT
$output = Invoke-Tool $env:CANOPY_TEST_PYTHON @('-c', 'print(123)')
if ($output.Trim() -ne '123') { throw 'Output capture failed' }
try {
    Invoke-Tool $env:CANOPY_TEST_PYTHON @('-c', 'raise SystemExit(5)')
    throw 'Failure ignored'
} catch {
    if ($_.Exception.Message -notmatch 'exit 5') { throw }
}
""")


def test_rollback_and_removal_preserve_external_files(tmp_path):
	run_powershell(tmp_path, BOOTSTRAP + r"""
Install-Release $null
$first = Read-State
$global:nextVersion = '0.3.0'
Install-Release $first
$second = Read-State
Restore-PreviousRelease $second
$restored = Read-State
Assert-True ($restored.current -eq $first.current) 'Rollback did not restore previous release'
Assert-True $restored.updatesPaused 'Rollback did not pause automatic updates'
$external = Join-Path $InstallDirectory 'team-data.txt'
Set-Content -LiteralPath $external -Value 'keep'
$global:running = $true
try { Remove-Releases; throw 'Removed active installation' } catch {
    if ($_.Exception.Message -ne 'Close Canopy before uninstalling') { throw }
}
$global:running = $false
Remove-Releases
Assert-True (Test-Path -LiteralPath $external) 'Unrelated file was removed'
Assert-True (-not (Test-Path -LiteralPath $StatePath)) 'Active state was not removed'
Assert-True (-not (Test-Path -LiteralPath "$StatePath.bak")) 'Backup state was not removed'
Assert-True (@(Get-ChildItem $EnvironmentDirectory -Directory).Count -eq 0) 'Environment was not removed'
""")


def test_deployment_scripts_parse(tmp_path):
	run_powershell(tmp_path, r"""
$errors = $null
$tokens = $null
Get-ChildItem (Split-Path $env:CANOPY_TEST_SCRIPT -Parent) -Filter '*.ps1' | ForEach-Object {
    [Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$tokens, [ref]$errors) | Out-Null
    if ($errors) { throw ($errors | Out-String) }
}
""")