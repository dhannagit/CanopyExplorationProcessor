param(
    [string]$IndexUrl = 'https://artifactory.michelin.com/api/pypi/pypi/simple',
    [switch]$RefreshLock,
    [switch]$SignRelease
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$env:UV_SYSTEM_CERTS = '1'
if (-not $env:UV_PYTHON_INSTALL_MIRROR) {
    $env:UV_PYTHON_INSTALL_MIRROR = 'https://artifactory.michelin.com/artifactory/github-generic/astral-sh/python-build-standalone/releases/download'
}
$index = [uri]$IndexUrl
if ($index.Scheme -ne 'https' -or $index.UserInfo) { throw 'Use an HTTPS dependency index without embedded credentials' }
$root = Split-Path $PSScriptRoot -Parent
$signingWrapper = Join-Path $root 'ci\sign_artifact.ps1'
if ($SignRelease) { & $signingWrapper -CheckConfiguration }
$lock = Join-Path $root 'src\canopy_processor\runtime-requirements.txt'
$uvCommand = Get-Command uv.exe -ErrorAction SilentlyContinue
$uv = if ($uvCommand) { $uvCommand.Source } else { $null }
if (-not $uv) {
    foreach ($directory in @('C:\Bib\Prod\Miniforge3', 'C:\Bib\Prod\Miniconda3-64')) {
        foreach ($relative in @('Library\bin\uv.exe', 'Scripts\uv.exe')) {
            $candidate = Join-Path $directory $relative
            if (-not $uv -and (Test-Path -LiteralPath $candidate)) { $uv = $candidate }
        }
    }
}
if (-not $uv) { throw 'uv is unavailable. Install the approved corporate Python tooling before building.' }
$staging = $null
Push-Location $root
try {
    if ($RefreshLock) {
        & $uv pip compile pyproject.toml --extra gui --python-version 3.13 --python-platform x86_64-pc-windows-msvc `
            --generate-hashes --no-emit-index-url --no-header --output-file $lock --index-url $IndexUrl
        if ($LASTEXITCODE -ne 0) { throw 'Dependency locking failed' }
    }
    if (-not (Test-Path -LiteralPath $lock)) { throw 'Generate the dependency lock with -RefreshLock first' }
    $python = (& $uv python find 3.13).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Install approved Python 3.13 before building' }
    $version = (& $python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])").Trim()
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^\d+\.\d+\.\d+$') { throw 'Use a stable major.minor.patch release version' }
    $staging = Join-Path $root ('dist\.release-' + [guid]::NewGuid().ToString('N'))
    $buildOutput = Join-Path $staging 'packages'
    $buildSource = Join-Path $staging 'source'
    New-Item -ItemType Directory -Force -Path (Join-Path $buildSource 'src') | Out-Null
    foreach ($file in @('pyproject.toml', 'MANIFEST.in', 'README.md', 'uv.lock', '.gitlab-ci.yml')) {
        Copy-Item -LiteralPath (Join-Path $root $file) -Destination $buildSource
    }
    Copy-Item -LiteralPath (Join-Path $root 'src\canopy_processor') -Destination (Join-Path $buildSource 'src') -Recurse
    foreach ($directory in @('docs', 'installer', 'tests', 'ci')) {
        New-Item -ItemType Directory -Path (Join-Path $buildSource $directory) | Out-Null
    }
    foreach ($file in @('DISTRIBUTION.md', 'DECISIONS.md', 'BUILD_LOG.md')) {
        Copy-Item -LiteralPath (Join-Path $root "docs\$file") -Destination (Join-Path $buildSource 'docs')
    }
    Get-ChildItem -LiteralPath $PSScriptRoot -File | Where-Object Extension -In '.ps1', '.bat', '.nsi', '.py' |
        Copy-Item -Destination (Join-Path $buildSource 'installer')
    Copy-Item -Path (Join-Path $root 'ci\*.ps1') -Destination (Join-Path $buildSource 'ci')
    Get-ChildItem -Path (Join-Path $root 'tests\test_*.py') -File |
        Copy-Item -Destination (Join-Path $buildSource 'tests')
    if ($SignRelease) {
        foreach ($directory in @('installer', 'ci')) {
            Get-ChildItem -LiteralPath (Join-Path $buildSource $directory) -Filter '*.ps1' -File | ForEach-Object {
                & $signingWrapper -Path $_.FullName -Kind Script
            }
        }
    }
    & $uv build $buildSource --index-url $IndexUrl --out-dir $buildOutput
    if ($LASTEXITCODE -ne 0) { throw 'Wheel/sdist build failed' }
    $wheel = Join-Path $buildOutput "canopy_exploration_processor-$version-py3-none-any.whl"
    & $python -c "import sys,zipfile,pathlib; archive=zipfile.ZipFile(sys.argv[1]); assert archive.read('canopy_processor/runtime-requirements.txt') == pathlib.Path(sys.argv[2]).read_bytes()" $wheel $lock
    if ($LASTEXITCODE -ne 0) { throw 'Wheel runtime dependency lock differs from the release lock' }
    $manifest = [ordered]@{
        version = $version
        platform = 'Windows x64'
        python = '3.13'
        wheel = [IO.Path]::GetFileName($wheel)
        wheelSha256 = (Get-FileHash -LiteralPath $wheel -Algorithm SHA256).Hash.ToLowerInvariant()
        lockSha256 = (Get-FileHash -LiteralPath $lock -Algorithm SHA256).Hash.ToLowerInvariant()
        applicationSource = 'bundled-wheel'
        dependencyIndex = $IndexUrl
    }
    $manifestPath = Join-Path $buildOutput "release-$version.json"
    $manifest | ConvertTo-Json | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    $assets = Join-Path $root "dist\releases\v$version"
    if (Test-Path -LiteralPath $assets) { Remove-Item -LiteralPath $assets -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $assets | Out-Null
    $bundleName = "CanopyExplorationProcessor-$version-Windows-x64"
    $bundle = Join-Path $staging $bundleName
    New-Item -ItemType Directory -Force -Path $bundle | Out-Null
    foreach ($file in @('deployment.ps1', 'cleanup.py', 'setup_environment.bat', 'CanopyExplorationStart.bat', 'remove_environment.bat')) {
        Copy-Item -LiteralPath (Join-Path $buildSource "installer\$file") -Destination $bundle
    }
    Copy-Item -LiteralPath (Join-Path $root 'docs\DISTRIBUTION.md') -Destination $bundle
    New-Item -ItemType Directory -Path (Join-Path $bundle 'payload') | Out-Null
    Copy-Item -LiteralPath $wheel -Destination (Join-Path $bundle 'payload')
    Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $bundle 'payload\release.json')
    $zip = Join-Path $assets "$bundleName.zip"
    Compress-Archive -LiteralPath $bundle -DestinationPath $zip
    $sdist = Join-Path $buildOutput "canopy_exploration_processor-$version.tar.gz"
    Copy-Item -LiteralPath $wheel, $sdist, $manifestPath -Destination $assets
    $checksums = Get-ChildItem -LiteralPath $assets -File | Sort-Object Name | ForEach-Object {
        (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() + '  ' + $_.Name
    }
    $checksums | Set-Content -LiteralPath (Join-Path $assets 'SHA256SUMS.txt') -Encoding ASCII
    Write-Output "Release artifacts ready in $assets. Test before distributing; nothing has been published."
} finally {
    if ($staging -and (Test-Path -LiteralPath $staging)) { Remove-Item -LiteralPath $staging -Recurse -Force }
    Pop-Location
}