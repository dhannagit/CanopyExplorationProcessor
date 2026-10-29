import os
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest
import yaml


ROOT = Path(__file__).parents[1]


def test_public_commands_use_full_product_name():
    configuration = tomllib.loads((ROOT / "pyproject.toml").read_text())
    project = configuration["project"]
    assert set(project["scripts"]) == {"canopy-exploration-processor-gui"}
    assert set(project["gui-scripts"]) == {"canopy-exploration-processor"}
    assert any(
        marker.startswith("local_data:")
        for marker in configuration["tool"]["pytest"]["ini_options"]["markers"]
    )

    entry_points = (ROOT / "src" / "canopy_exploration_processor.egg-info" / "entry_points.txt").read_text()
    assert "canopy-exploration-processor-gui = canopy_processor.ui.app:main" in entry_points
    assert "canopy-exploration-processor = canopy_processor.ui.app:main" in entry_points
    metadata = (ROOT / "src" / "canopy_exploration_processor.egg-info" / "PKG-INFO").read_text()
    assert "Summary: Canopy Exploration Processor for analyzing Canopy simulation sweeps." in metadata


def test_local_sample_roots_are_present_but_their_contents_are_ignored():
    ignore_rules = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for directory in ("DATA_Raw", "DATA_dXpx", "BaselineExample"):
        assert f"/{directory}/*" in ignore_rules
        assert f"!/{directory}/.gitkeep" in ignore_rules
        assert (ROOT / directory / ".gitkeep").is_file()
    assert "*.xlsx" in ignore_rules


def test_pipeline_is_opt_in_protected_and_artifact_only():
    pipeline_path = ROOT / ".gitlab-ci.yml"
    pipeline_bytes = pipeline_path.read_bytes()
    assert all(byte < 128 for byte in pipeline_bytes)
    pipeline = yaml.safe_load(pipeline_bytes.decode("ascii"))
    assert pipeline["variables"]["CANOPY_CI_ENABLED"] == "false"
    assert pipeline["variables"]["CANOPY_COMPILE_INSTALLER"] == "false"
    assert "CANOPY_FULL_TESTS" not in pipeline["variables"]
    assert pipeline["workflow"]["rules"][0]["when"] == "never"
    assert any("CI_COMMIT_REF_PROTECTED" in rule.get("if", "") for rule in pipeline["workflow"]["rules"])
    workflow_rules = pipeline["workflow"]["rules"]
    mr_rule = next(rule for rule in workflow_rules if "merge_request_event" in rule.get("if", ""))
    push_rule = next(rule for rule in workflow_rules if "CI_PIPELINE_SOURCE == \"push\"" in rule.get("if", ""))
    web_rule = next(rule for rule in workflow_rules if "CI_PIPELINE_SOURCE == \"web\"" in rule.get("if", ""))
    tag_rule = next(rule for rule in workflow_rules if "CI_COMMIT_TAG =~" in rule.get("if", ""))
    expected_pipeline_paths = {
        ".gitlab-ci.yml", ".gitignore", "MANIFEST.in", "pyproject.toml", "uv.lock",
        "ci/**/*", "installer/**/*", "src/**/*", "tests/**/*",
    }
    assert set(mr_rule["changes"]["paths"]) == expected_pipeline_paths
    assert set(push_rule["changes"]["paths"]) == expected_pipeline_paths
    assert "README.md" not in push_rule["changes"]["paths"]
    assert not any(path.startswith("docs/") for path in push_rule["changes"]["paths"])
    assert "changes" not in tag_rule
    assert "changes" not in web_rule
    assert pipeline["variables"]["CANOPY_WINDOWS_IMAGE"] == ""
    assert pipeline["default"]["image"]["name"] == "$CANOPY_WINDOWS_IMAGE"
    assert pipeline["variables"]["CANOPY_RELEASE_APPROVED"] == "false"
    assert pipeline["variables"]["CANOPY_SIGNING_POLICY"] == "unset"
    assert pipeline["variables"]["CANOPY_MR_VALIDATION_ENABLED"] == "false"
    assert pipeline["release_windows"]["environment"]["name"] == "production/windows"
    assert pipeline["release_windows"]["rules"][0]["when"] == "manual"
    assert "CI_COMMIT_TAG" in pipeline["release_windows"]["rules"][0]["if"]
    assert "CANOPY_RELEASE_APPROVED" in pipeline["release_windows"]["rules"][0]["if"]
    assert "merge_request_event" not in pipeline["package_windows"]["rules"][0]["if"]
    assert pipeline["release_windows"]["artifacts"]["access"] == "developer"
    assert pipeline["package_windows"]["artifacts"]["expire_in"] == "7 days"
    assert "environment" not in pipeline["package_windows"]
    nsis_job = pipeline["nsis_compile"]
    assert [need["job"] for need in pipeline["release_windows"]["needs"]] == [
        "package_windows", "nsis_compile", "nsis_smoke"
    ]
    assert pipeline["release_windows"]["rules"][0]["allow_failure"] is False
    assert pipeline["include"][0]["file"] == ["global-settings.yml"]
    assert pipeline["stages"].index("installer") < pipeline["stages"].index("release")
    assert pipeline["stages"].index(nsis_job["stage"]) < pipeline["stages"].index("release")
    assert nsis_job["image"]["name"] == "docker.artifactory.michelin.com/rdxp/windows/build:1.0.0"
    assert nsis_job["needs"][0]["job"] == "package_windows"
    assert nsis_job["script"]
    assert "makensis.exe" in nsis_job["script"][0]
    assert '"/DPRODUCT_VERSION=$env:PRODUCT_VERSION"' in nsis_job["script"][0]
    assert '"/DCANOPY_BUNDLE_DIR=$env:CANOPY_BUNDLE_DIR"' in nsis_job["script"][0]
    assert '"/DCANOPY_NSIS_OUTPUT=$env:CANOPY_NSIS_OUTPUT"' in nsis_job["script"][0]
    assert nsis_job["artifacts"]["paths"] == [
        "nsis_compile_files/*.exe"
    ]
    smoke_job = pipeline["nsis_smoke"]
    assert smoke_job["stage"] == "installer_smoke"
    assert "environment" not in smoke_job
    assert smoke_job["variables"]["CANOPY_BUILD_KIND"] == "preview"
    assert [need["job"] for need in smoke_job["needs"]] == ["package_windows", "nsis_compile"]
    assert "PreviewSmoke" in smoke_job["script"][0]
    assert smoke_job["artifacts"]["paths"] == ["dist/releases/"]
    assert pipeline["release_windows"]["needs"][2] == {
        "job": "nsis_smoke", "artifacts": False, "optional": True
    }
    assert pipeline["package_windows"]["needs"][0]["job"] == "test_windows"
    assert pipeline["package_windows"]["artifacts"]["paths"] == ["dist/releases/"]
    assert pipeline["test_windows"]["artifacts"]["reports"]["junit"] == "reports/junit.xml"
    for job in pipeline.values():
        if not isinstance(job, dict):
            continue
        artifact_paths = job.get("artifacts", {}).get("paths", [])
        assert not any(
            protected_name in path
            for path in artifact_paths
            for protected_name in ("DATA_Raw", "DATA_dXpx", "BaselineExample", "CircuitsData_Canopy_Hypercar.xlsx")
        )
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
Test-RunnerImage 'docker.artifactory.michelin.com/example/windows-ci:1.0.0'
Test-RunnerImage ('docker.artifactory.michelin.com/example/windows-ci@sha256:' + ('a' * 64))
foreach ($image in @('', 'python:3.13', 'docker.artifactory.michelin.com/example/windows-ci:latest')) {
    try { Test-RunnerImage $image; throw 'Unsafe image accepted' } catch {
        if ($_.Exception.Message -notmatch 'approved versioned Windows image') { throw }
    }
}
if (-not (Test-ProductionPolicy 'production' 'v0.1.0' 'true' 'true' 'required')) { throw 'Signing requirement lost' }
if (Test-ProductionPolicy 'production' 'v0.1.0' 'true' 'true' 'not-required') { throw 'Signing waiver ignored' }
try { Test-ProductionPolicy 'production' '' 'true' 'true' 'not-required'; throw 'Branch production accepted' } catch {
    if ($_.Exception.Message -notmatch 'approved protected version tag') { throw }
}
try { Test-ProductionPolicy 'production' 'v0.1.0' 'true' 'true' 'unset'; throw 'Unset signing policy accepted' } catch {
    if ($_.Exception.Message -notmatch 'signing policy explicitly') { throw }
}
try { Test-ReleaseVersion '0.1.0' 'v0.2.0'; throw 'Mismatched tag accepted' } catch {
    if ($_.Exception.Message -ne 'CI tag must match the version in pyproject.toml') { throw }
}
$testArguments = @(Get-TestArguments)
if (($testArguments -join ' ') -ne '-m pytest -m not local_data') { throw 'CI must run all tests except the local-data profile' }
if ($testArguments -contains '-k' -or $testArguments -contains 'tests/test_installer.py') { throw 'CI test selector still uses a filename allowlist' }
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


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Authenticode validation")
@pytest.mark.parametrize(
    "status,matching_signer,timestamp,accepted",
    [("Valid", True, True, True), ("NotSigned", True, True, False),
     ("Valid", False, True, False), ("Valid", True, False, False)],
)
def test_signing_requires_valid_approved_timestamped_signature(tmp_path, status, matching_signer, timestamp, accepted):
    environment = os.environ.copy()
    environment["CANOPY_SIGNING_WRAPPER"] = str(ROOT / "ci" / "sign_artifact.ps1")
    environment["CANOPY_SIGNER_THUMBPRINT"] = "a" * 40
    environment["TEST_SIGNATURE_STATUS"] = status
    environment["TEST_SIGNATURE_THUMBPRINT"] = ("a" if matching_signer else "b") * 40
    environment["TEST_SIGNATURE_TIMESTAMP"] = "true" if timestamp else "false"
    environment["TEST_SIGNATURE_ACCEPTED"] = "true" if accepted else "false"
    script = r"""
. $env:CANOPY_SIGNING_WRAPPER
function Get-AuthenticodeSignature {
    $stamp = $null
    if ($env:TEST_SIGNATURE_TIMESTAMP -eq 'true') { $stamp = 'test timestamp' }
    return [PSCustomObject]@{
        Status = $env:TEST_SIGNATURE_STATUS
        SignerCertificate = [PSCustomObject]@{Thumbprint = $env:TEST_SIGNATURE_THUMBPRINT}
        TimeStamperCertificate = $stamp
    }
}
try {
    Test-SignedArtifact 'test.exe'
    if ($env:TEST_SIGNATURE_ACCEPTED -ne 'true') { throw 'Invalid signature accepted' }
} catch {
    if ($env:TEST_SIGNATURE_ACCEPTED -eq 'true' -or $_.Exception.Message -notmatch 'valid timestamped signature') { throw }
}
$env:CANOPY_SIGNING_SCRIPT = $null
try { Test-SigningConfiguration; throw 'Missing company signer accepted' } catch {
    if ($_.Exception.Message -notmatch 'approved runner-managed CANOPY_SIGNING_SCRIPT') { throw }
}
exit 0
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        env=environment, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(sys.platform != "win32", reason="Windows release builder")
def test_required_signing_stops_before_build_without_company_adapter():
    environment = os.environ.copy()
    environment.pop("CANOPY_SIGNING_SCRIPT", None)
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-File",
         str(ROOT / "installer" / "build_release.ps1"), "-SignRelease"],
        env=environment, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "CANOPY_SIGNING_SCRIPT" in result.stdout + result.stderr