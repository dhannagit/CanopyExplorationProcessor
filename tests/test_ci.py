import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


ROOT = Path(__file__).parents[1]


def test_pipeline_is_opt_in_protected_and_artifact_only():
    pipeline = yaml.safe_load((ROOT / ".gitlab-ci.yml").read_text())
    assert pipeline["variables"]["CANOPY_CI_ENABLED"] == "false"
    assert pipeline["variables"]["CANOPY_COMPILE_INSTALLER"] == "false"
    assert pipeline["workflow"]["rules"][0]["when"] == "never"
    assert "CI_COMMIT_REF_PROTECTED" in pipeline["workflow"]["rules"][1]["if"]
    assert "include" not in pipeline
    assert pipeline["package_windows"]["needs"][0]["job"] == "test_windows"
    assert pipeline["package_windows"]["artifacts"]["paths"] == ["dist/releases/"]
    assert pipeline["test_windows"]["artifacts"]["reports"]["junit"] == "reports/junit.xml"
    assert not any("push" in name or "publish" in name for name in pipeline if isinstance(pipeline[name], dict))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows CI driver")
def test_ci_helpers_validate_tags_test_selection_and_checksums(tmp_path):
    environment = os.environ.copy()
    environment["CANOPY_CI_SCRIPT"] = str(ROOT / "ci" / "run.ps1")
    environment["CANOPY_CI_TEMP"] = str(tmp_path)
    script = r"""
. $env:CANOPY_CI_SCRIPT
Test-ReleaseVersion '0.1.0' 'v0.1.0'
Test-ReleaseVersion '0.1.0' ''
try { Test-ReleaseVersion '0.1.0' 'v0.2.0'; throw 'Mismatched tag accepted' } catch {
    if ($_.Exception.Message -ne 'CI tag must match the version in pyproject.toml') { throw }
}
if ((Get-TestArguments $false) -notcontains 'tests/test_installer.py') { throw 'Windows deployment checks missing' }
if ((Get-TestArguments $true).Count -ne 2) { throw 'Full-suite selector still excludes tests' }
$asset = Join-Path $env:CANOPY_CI_TEMP 'asset.exe'
Set-Content -LiteralPath $asset -Value 'test bytes'
$digest = (Get-FileHash -LiteralPath $asset -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath (Join-Path $env:CANOPY_CI_TEMP 'SHA256SUMS.txt') -Value "$digest  asset.exe"
Test-ArtifactChecksums $env:CANOPY_CI_TEMP
Add-Content -LiteralPath $asset -Value 'changed'
try { Test-ArtifactChecksums $env:CANOPY_CI_TEMP; throw 'Tampered artifact accepted' } catch {
    if ($_.Exception.Message -ne 'Release checksum mismatch: asset.exe') { throw }
}
Set-Content -LiteralPath (Join-Path $env:CANOPY_CI_TEMP 'SHA256SUMS.txt') -Value ''
try { Test-ArtifactChecksums $env:CANOPY_CI_TEMP; throw 'Empty checksum file accepted' } catch {
    if ($_.Exception.Message -ne 'Release checksum list is incomplete') { throw }
}
exit 0
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        env=environment, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr