param(
    [string]$Target = "native\launcher\target\release\ShapeYourPhoto.exe"
)

$ErrorActionPreference = "Stop"

$resolvedTarget = Resolve-Path -LiteralPath $Target -ErrorAction SilentlyContinue
if (-not $resolvedTarget) {
    Write-Host "Signing skipped: target was not found: $Target"
    exit 0
}

$signtool = $env:SHAPEYOURPHOTO_SIGNTOOL
if (-not $signtool) {
    $signtool = "signtool.exe"
}

$cert = $env:SHAPEYOURPHOTO_SIGN_CERT
$password = $env:SHAPEYOURPHOTO_SIGN_PASSWORD
$timestamp = $env:SHAPEYOURPHOTO_SIGN_TIMESTAMP
if (-not $timestamp) {
    $timestamp = "http://timestamp.digicert.com"
}

if (-not $cert) {
    Write-Host "Signing skipped: SHAPEYOURPHOTO_SIGN_CERT is not set. This build is unsigned."
    exit 0
}

if (-not (Test-Path -LiteralPath $cert)) {
    Write-Host "Signing skipped: certificate file was not found. This build is unsigned."
    exit 0
}

$args = @(
    "sign",
    "/fd", "SHA256",
    "/f", $cert,
    "/tr", $timestamp,
    "/td", "SHA256",
    $resolvedTarget.Path
)

if ($password) {
    $args = @(
        "sign",
        "/fd", "SHA256",
        "/f", $cert,
        "/p", $password,
        "/tr", $timestamp,
        "/td", "SHA256",
        $resolvedTarget.Path
    )
}

try {
    & $signtool @args
    if ($LASTEXITCODE -ne 0) {
        throw "signtool exited with code $LASTEXITCODE"
    }
    Write-Host "Signed: $($resolvedTarget.Path)"
} catch {
    Write-Host "Signing skipped: $($_.Exception.Message). This build is unsigned."
    exit 0
}
