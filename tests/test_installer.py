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
. $env:CANOPY_TEST_SCRIPT -InstallDirectory $env:CANOPY_TEST_ROOT -PayloadDirectory (Join-Path $env:CANOPY_TEST_ROOT 'payload')
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
function Set-TestRelease([string]$Version) {
    $global:nextVersion = $Version
    New-Item -ItemType Directory -Path $PayloadDirectory -Force | Out-Null
    $wheelName = "canopy_exploration_processor-$Version-py3-none-any.whl"
    $wheel = Join-Path $PayloadDirectory $wheelName
    Set-Content -LiteralPath $wheel -Value 'test wheel'
    $lock = Join-Path $PayloadDirectory 'test-lock.txt'
    Set-Content -LiteralPath $lock -Value 'fake-lock'
    [ordered]@{
        version = $Version; python = '3.13'; platform = 'Windows x64'; wheel = $wheelName
        wheelSha256 = (Get-FileHash $wheel -Algorithm SHA256).Hash
        lockSha256 = (Get-FileHash $lock -Algorithm SHA256).Hash
    } | ConvertTo-Json | Set-Content (Join-Path $PayloadDirectory 'release.json')
}
Set-TestRelease '0.2.0'
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
Set-TestRelease '0.3.0'
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
Assert-True ([bool]($calls -match '--no-index --no-deps')) 'Application must be installed from the bundled wheel without an index'
Assert-True ([bool]($calls -match '--require-hashes')) 'Lock hashes not required'
Assert-True ([bool]($calls -match '--index-url https://artifactory.michelin.com/')) 'Dependencies must use corporate Artifactory'
""")


def test_running_session_blocks_setup_and_rejects_unsafe_paths(tmp_path):
	run_powershell(tmp_path, BOOTSTRAP + r"""
Install-Release $null
$first = Read-State
$global:running = $true
Set-TestRelease '0.3.0'
try { Install-Release $first; throw 'Running session did not block setup' } catch {
    if ($_.Exception.Message -ne 'Close Canopy sessions before setup') { throw }
}
Assert-True ((Read-State).current -eq $first.current) 'Active session was updated'
try { Get-EnvironmentPath '..\other-app'; throw 'Traversal accepted' } catch {
    if ($_.Exception.Message -ne 'Invalid environment identifier') { throw }
}
$global:running = $false
Set-TestRelease '0.3.0rc1'
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
Set-TestRelease '0.3.0'
Install-Release $first
$second = Read-State
Restore-PreviousRelease $second
$restored = Read-State
Assert-True ($restored.current -eq $first.current) 'Rollback did not restore previous release'
Assert-True ($restored.version -eq '0.2.0') 'Rollback did not restore previous version'
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


def test_launch_only_starts_installed_application(tmp_path):
    run_powershell(tmp_path, r"""
$errors = $null
$tokens = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($env:CANOPY_TEST_SCRIPT, [ref]$tokens, [ref]$errors)
$switch = $ast.Find({ param($node) $node -is [Management.Automation.Language.SwitchStatementAst] }, $true)
$launch = $switch.Clauses | Where-Object { $_.Item1.Value -eq 'Launch' }
if ($launch.Item2.Extent.Text.Trim() -ne '{ Start-Application $state }') {
    throw 'Launch must only start the installed application, without a network or update check'
}
""")


def test_setup_rejects_invalid_release_payload(tmp_path):
    run_powershell(tmp_path, BOOTSTRAP + r"""
Install-Release $null
$first = Read-State
Set-TestRelease '0.3.0'
$wheel = Join-Path $PayloadDirectory 'canopy_exploration_processor-0.3.0-py3-none-any.whl'
Add-Content -LiteralPath $wheel -Value 'tampered'
try { Install-Release $first; throw 'Tampered wheel accepted' } catch {
    if ($_.Exception.Message -ne 'Bundled application wheel checksum does not match release.json') { throw }
}
Set-TestRelease '0.3.0'
$ReleaseVersion = '0.4.0'
try { Install-Release $first; throw 'Wrong installer version accepted' } catch {
    if ($_.Exception.Message -ne 'Installer and bundled release versions do not match') { throw }
}
$ReleaseVersion = ''
Set-TestRelease '0.1.0'
try { Install-Release $first; throw 'Downgrade accepted' } catch {
    if ($_.Exception.Message -notmatch 'older release cannot replace') { throw }
}
Set-TestRelease '0.3.0'
Remove-Item -LiteralPath (Join-Path $PayloadDirectory 'release.json')
try { Install-Release $first; throw 'Missing manifest accepted' } catch {
    if ($_.Exception.Message -notmatch 'Release payload is missing release.json') { throw }
}
Assert-True ((Read-State).current -eq $first.current) 'Invalid payload changed active environment'
""")


def test_installer_bundles_application_and_removes_updater():
    recipe = (SCRIPT.parent / "CanopyExplorationProcessor.iss").read_text()
    assert 'Source: "{#MyPayloadDir}\\release.json"' in recipe
    assert 'Source: "{#MyPayloadDir}\\canopy_exploration_processor-{#MyAppVersion}-py3-none-any.whl"' in recipe
    assert 'OutputDir=..\\dist\\releases\\v{#MyAppVersion}' in recipe
    assert 'Source: "CanopyExplorationUpdate.bat"' not in recipe
    assert 'Name: "{group}\\Update Canopy Exploration Processor";' not in recipe
    assert 'Type: files; Name: "{app}\\CanopyExplorationUpdate.bat"' in recipe


def test_release_builder_keeps_generated_files_outside_source():
    builder = (SCRIPT.parent / "build_release.ps1").read_text()
    assert 'Join-Path $PSScriptRoot \'payload\'' not in builder
    assert 'Join-Path $PSScriptRoot "output\\' not in builder
    assert '"/DMyPayloadDir=$(Join-Path $bundle \'payload\')"' in builder
    assert '"/O$assets"' in builder


def test_setup_rejects_mismatched_metadata_and_lock(tmp_path):
    run_powershell(tmp_path, BOOTSTRAP + r"""
Install-Release $null
$first = Read-State
Set-TestRelease '0.3.0'
$global:nextVersion = '0.4.0'
try { Install-Release $first; throw 'Wrong wheel metadata accepted' } catch {
    if ($_.Exception.Message -ne 'Installed wheel version does not match release.json') { throw }
}
Set-TestRelease '0.3.0'
$manifestPath = Join-Path $PayloadDirectory 'release.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$manifest.lockSha256 = '0' * 64
$manifest | ConvertTo-Json | Set-Content -LiteralPath $manifestPath
try { Install-Release $first; throw 'Wrong lock checksum accepted' } catch {
    if ($_.Exception.Message -ne 'Runtime dependency lock checksum does not match release.json') { throw }
}
Assert-True ((Read-State).current -eq $first.current) 'Mismatch changed active environment'
Assert-True (@(Get-ChildItem $EnvironmentDirectory -Directory).Count -eq 1) 'Mismatch leaked candidate environment'
""")