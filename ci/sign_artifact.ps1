param(
    [string]$Path,
    [ValidateSet('Script', 'Executable')]
    [string]$Kind = 'Executable',
    [switch]$VerifyOnly,
    [switch]$CheckConfiguration
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Test-SigningConfiguration {
    if (-not $env:CANOPY_SIGNING_SCRIPT -or -not (Test-Path -LiteralPath $env:CANOPY_SIGNING_SCRIPT -PathType Leaf)) {
        throw 'Configure the approved runner-managed CANOPY_SIGNING_SCRIPT adapter before requiring signing'
    }
    if (-not [IO.Path]::IsPathRooted($env:CANOPY_SIGNING_SCRIPT) -or $env:CANOPY_SIGNING_SCRIPT.Contains('"')) {
        throw 'Signing adapter must be an absolute runner-managed path without quotes'
    }
    if ($env:CANOPY_SIGNER_THUMBPRINT -notmatch '^[a-fA-F0-9]{40}$') { throw 'Configure the approved signing certificate thumbprint' }
}

function Test-SignedArtifact([string]$FilePath) {
    $signature = Get-AuthenticodeSignature -LiteralPath $FilePath
    if ($signature.Status -ne 'Valid' -or -not $signature.SignerCertificate -or
        $signature.SignerCertificate.Thumbprint -ne $env:CANOPY_SIGNER_THUMBPRINT -or
        -not $signature.TimeStamperCertificate) {
        throw 'Artifact must have a valid timestamped signature from the approved certificate'
    }
}

if ($MyInvocation.InvocationName -eq '.') { return }

Test-SigningConfiguration
if ($CheckConfiguration) { return }
if (-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw 'Signing target is missing' }
if (-not $VerifyOnly) {
    $global:LASTEXITCODE = 0
    & $env:CANOPY_SIGNING_SCRIPT -Path ([IO.Path]::GetFullPath($Path)) -Kind $Kind
    if ($LASTEXITCODE -ne 0) { throw 'Company signing adapter failed' }
}
Test-SignedArtifact $Path