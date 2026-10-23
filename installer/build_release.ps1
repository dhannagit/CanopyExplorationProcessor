param(
    [string]$IndexUrl = 'https://artifactory.michelin.com/api/pypi/pypi/simple',
    [switch]$RefreshLock,
    [switch]$CompileInstaller
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$env:UV_SYSTEM_CERTS = '1'
$root = Split-Path $PSScriptRoot -Parent
$lock = Join-Path $root 'src\canopy_processor\runtime-requirements.txt'
Push-Location $root
try {
    if ($RefreshLock) {
        uv pip compile pyproject.toml --extra gui --python-version 3.13 --python-platform x86_64-pc-windows-msvc `
            --generate-hashes --no-emit-index-url --no-header --output-file $lock --index-url $IndexUrl
        if ($LASTEXITCODE -ne 0) { throw 'Dependency locking failed' }
    }
    if (-not (Test-Path -LiteralPath $lock)) { throw 'Generate the dependency lock with -RefreshLock first' }
    $python = (uv python find 3.13).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Install approved Python 3.13 before building' }
    $version = (& $python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])").Trim()
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^\d+\.\d+\.\d+$') { throw 'Use a stable major.minor.patch release version' }
    uv build --index-url $IndexUrl
    if ($LASTEXITCODE -ne 0) { throw 'Wheel/sdist build failed' }
    $wheel = Join-Path $root "dist\canopy_exploration_processor-$version-py3-none-any.whl"
    & $python -c "import sys,zipfile; archive=zipfile.ZipFile(sys.argv[1]); assert archive.read('canopy_processor/runtime-requirements.txt')" $wheel
    if ($LASTEXITCODE -ne 0) { throw 'Wheel has no runtime dependency lock' }
    $manifest = [ordered]@{
        version = $version
        platform = 'Windows x64'
        python = '3.13'
        wheel = [IO.Path]::GetFileName($wheel)
        wheelSha256 = (Get-FileHash -LiteralPath $wheel -Algorithm SHA256).Hash.ToLowerInvariant()
        lockSha256 = (Get-FileHash -LiteralPath $lock -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root "dist\release-$version.json") -Encoding UTF8
    if ($CompileInstaller) {
        $compiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
        $compilerPath = if ($compiler) { $compiler.Source } else { Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe' }
        if (-not (Test-Path -LiteralPath $compilerPath)) { throw 'Install approved Inno Setup 6 to compile the Windows installer' }
        & $compilerPath "/DMyAppVersion=$version" (Join-Path $PSScriptRoot 'CanopyExplorationProcessor.iss')
        if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed' }
    }
    Write-Output "Built release $version. Validate the wheel in a clean environment before publishing."
} finally {
    Pop-Location
}