#Requires -Version 5.1
<#
.SYNOPSIS
    Convenience script for running the Claims Desktop demo test suite.

.DESCRIPTION
    Activates the virtual environment, then runs Robot Framework with
    sensible defaults (timestamped output folder, coloured console).

.PARAMETER Suite
    Which test suite(s) to run:
      all       — all suites (default)
      login     — login_tests.robot only
      claims    — claim_submission_tests.robot only
      supervisor — supervisor_workflow_tests.robot only

.PARAMETER Tags
    Run only tests with this tag, e.g. -Tags smoke

.PARAMETER OutputDir
    Where to save reports (default: ./reports/<timestamp>)

.EXAMPLE
    .\run_tests.ps1
    .\run_tests.ps1 -Suite login
    .\run_tests.ps1 -Tags smoke -Suite claims
#>

param(
    [ValidateSet("all", "login", "claims", "supervisor")]
    [string] $Suite     = "all",
    [string] $Tags      = "",
    [string] $OutputDir = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot

# ── Locate virtual environment ────────────────────────────────────────────────
$projectRoot = Split-Path (Split-Path $ScriptDir -Parent) -Parent
$venvPython  = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Virtual environment not found. Run .\scripts\install.ps1 first." -ForegroundColor Red
    exit 1
}

# ── Output directory ──────────────────────────────────────────────────────────
if (-not $OutputDir) {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $OutputDir = Join-Path $ScriptDir "reports\$timestamp"
}
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

# ── Suite selection ───────────────────────────────────────────────────────────
$testDir = Join-Path $ScriptDir "tests"
$suiteArg = switch ($Suite) {
    "login"      { Join-Path $testDir "login_tests.robot" }
    "claims"     { Join-Path $testDir "claim_submission_tests.robot" }
    "supervisor" { Join-Path $testDir "supervisor_workflow_tests.robot" }
    default      { $testDir }
}

# ── Build robot command ───────────────────────────────────────────────────────
$robotArgs = @(
    "--outputdir", $OutputDir,
    "--log",       "log.html",
    "--report",    "report.html",
    "--output",    "output.xml"
)

if ($Tags) {
    $robotArgs += @("--include", $Tags)
}

$robotArgs += $suiteArg

# ── Run ───────────────────────────────────────────────────────────────────────
Write-Host "`nRunning Claims Demo Tests" -ForegroundColor Cyan
Write-Host "  Suite     : $Suite" -ForegroundColor White
Write-Host "  Tags      : $(if ($Tags) { $Tags } else { '(all)' })" -ForegroundColor White
Write-Host "  Reports   : $OutputDir" -ForegroundColor White
Write-Host ""

& $venvPython -m robot @robotArgs
$exitCode = $LASTEXITCODE

# ── Results ───────────────────────────────────────────────────────────────────
Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "All tests PASSED." -ForegroundColor Green
} else {
    Write-Host "Some tests FAILED (exit code: $exitCode)." -ForegroundColor Red
}

Write-Host "  Report : $OutputDir\report.html"
Write-Host "  Log    : $OutputDir\log.html"

# Open the report in the default browser
try {
    Start-Process (Join-Path $OutputDir "report.html")
} catch {}

exit $exitCode
