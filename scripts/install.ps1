#Requires -Version 5.1
<#
.SYNOPSIS
    One-click installer for the Enterprise Desktop Automation Platform.

.DESCRIPTION
    Checks prerequisites, creates a Python virtual environment, installs all
    dependencies, downloads FlaUI assemblies, and validates the installation.

.PARAMETER InstallDir
    Root directory where the platform was cloned. Defaults to the parent of this script.

.PARAMETER PythonVersion
    Minimum Python version required (default: 3.10).

.PARAMETER SkipFlaUI
    Skip downloading FlaUI assemblies (use if you already have them or prefer NuGet).

.PARAMETER SkipTests
    Skip the quick smoke-test run after installation.

.EXAMPLE
    .\scripts\install.ps1
    .\scripts\install.ps1 -SkipFlaUI
    .\scripts\install.ps1 -InstallDir "D:\automation"
#>

[CmdletBinding()]
param(
    [string]  $InstallDir    = (Split-Path $PSScriptRoot -Parent),
    [version] $PythonVersion = "3.10",
    [switch]  $SkipFlaUI,
    [switch]  $SkipTests
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Header { param($msg) Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Write-OK     { param($msg) Write-Host "  [OK]  $msg"  -ForegroundColor Green }
function Write-Warn   { param($msg) Write-Host "  [!!]  $msg"  -ForegroundColor Yellow }
function Write-Fail   { param($msg) Write-Host "  [XX]  $msg"  -ForegroundColor Red }
function Write-Step   { param($msg) Write-Host "  -->   $msg"  -ForegroundColor White }

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Enterprise Desktop Automation Platform" -ForegroundColor Cyan
Write-Host "  Installer" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

Write-Step "Install directory : $InstallDir"
Write-Step "Script started at : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

# --- 1. Prerequisites --------------------------------------------------------
Write-Header "Checking Prerequisites"

# Python
try {
    $pyExe = (Get-Command python -ErrorAction Stop).Source
    $pyVerStr = & python --version 2>&1
    if ($pyVerStr -match "Python (\d+\.\d+)") {
        $installed = [version]$Matches[1]
        if ($installed -lt $PythonVersion) {
            Write-Fail "Python $installed found but $PythonVersion+ required."
            Write-Host "  Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
            exit 1
        }
        Write-OK "Python $installed ($pyExe)"
    }
} catch {
    Write-Fail "Python not found in PATH."
    Write-Host "  Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# Git
try {
    $gitVer = & git --version 2>&1
    Write-OK $gitVer
} catch {
    Write-Warn "Git not found -- OK for installation, but needed for cloning."
}

# .NET (required for FlaUI)
$dotnetOk = $false
try {
    $dotnetInfo = & dotnet --version 2>&1
    Write-OK ".NET $dotnetInfo"
    $dotnetOk = $true
} catch {
    Write-Warn ".NET SDK not found. FlaUI requires .NET 6+ runtime."
    Write-Warn "Download: https://dotnet.microsoft.com/download"
    if (-not $SkipFlaUI) {
        Write-Warn "Continuing with -SkipFlaUI (FlaUI assemblies will not be downloaded)."
        $SkipFlaUI = $true
    }
}

# Admin rights
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if ($isAdmin) {
    Write-OK "Running as Administrator"
} else {
    Write-Warn "Not running as Administrator -- some features may require elevation."
}

# --- 2. Virtual environment --------------------------------------------------
Write-Header "Setting Up Python Virtual Environment"

$venvDir = Join-Path $InstallDir ".venv"

if (Test-Path $venvDir) {
    Write-Step "Existing .venv found -- skipping creation."
} else {
    Write-Step "Creating virtual environment at: $venvDir"
    & python -m venv $venvDir
    Write-OK "Virtual environment created."
}

$pip    = Join-Path $venvDir "Scripts\pip.exe"
$python = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path $pip)) {
    Write-Fail "pip not found in virtual environment: $pip"
    exit 1
}

# --- 3. Upgrade pip / setuptools ---------------------------------------------
Write-Header "Upgrading pip and setuptools"
Write-Step "Upgrading pip..."
& $python -m pip install --upgrade pip setuptools wheel --quiet
Write-OK "pip upgraded."

# --- 4. Install platform dependencies ----------------------------------------
Write-Header "Installing Platform Dependencies"

$reqFile = Join-Path $InstallDir "requirements.txt"
if (-not (Test-Path $reqFile)) {
    Write-Fail "requirements.txt not found at: $reqFile"
    exit 1
}

Write-Step "Installing from requirements.txt (this may take 2-5 minutes)..."
& $pip install -r $reqFile --quiet
Write-OK "Core dependencies installed."

# Ensure setuptools is new enough for editable installs (requires >= 64)
Write-Step "Ensuring setuptools >= 64 ..."
& $pip install "setuptools>=64" --upgrade --quiet
Write-OK "setuptools ready."

Write-Step "Installing platform package (editable)..."
& $pip install -e $InstallDir
if ($LASTEXITCODE -ne 0) {
    Write-Fail "pip install -e failed (exit code $LASTEXITCODE)."
    Write-Warn "Try running manually: .venv\Scripts\pip install -e ."
    exit 1
}
Write-OK "Platform package installed."

# --- 5. FlaUI assemblies -----------------------------------------------------
if (-not $SkipFlaUI) {
    Write-Header "Downloading FlaUI Assemblies"
    $flaUIScript = Join-Path $PSScriptRoot "setup_flaui.ps1"
    if (Test-Path $flaUIScript) {
        Write-Step "Running setup_flaui.ps1..."
        & $flaUIScript -InstallDir $InstallDir
    } else {
        Write-Warn "setup_flaui.ps1 not found -- skipping FlaUI assembly download."
        Write-Warn "Run scripts\setup_flaui.ps1 manually to install FlaUI assemblies."
    }
} else {
    Write-Step "Skipping FlaUI assembly download (-SkipFlaUI specified)."
    Write-Warn "Remember to provide FlaUI DLLs via:"
    Write-Warn "  - Set FLAUI_PATH environment variable, OR"
    Write-Warn "  - Place DLLs in $InstallDir\lib\flaui\"
}

# --- 6. Create example project scaffold --------------------------------------
Write-Header "Creating Example Project Scaffold"

$exampleDir = Join-Path $InstallDir "my_first_test"
if (-not (Test-Path $exampleDir)) {
    New-Item -ItemType Directory -Path $exampleDir | Out-Null

    $configContent = @'
framework:
  adapter_mode: auto
  retry_count: 2
  screenshot_on_failure: true
  logging_level: INFO

application:
  name: Notepad
  executable: C:\Windows\System32\notepad.exe
  launch_timeout_seconds: 10
'@
    Set-Content -Path (Join-Path $exampleDir "config.yaml") -Value $configContent -Encoding utf8

    $locatorsContent = @'
TEXT_AREA:
  primary:
    strategy: class_name
    value: "Edit"
  metadata:
    description: Main text editing area in Notepad
'@
    Set-Content -Path (Join-Path $exampleDir "locators.yaml") -Value $locatorsContent -Encoding utf8

    $robotContent = @'
*** Settings ***
Library    DesktopAutomationLibrary    config_path=${CURDIR}/config.yaml
...                                   locator_path=${CURDIR}/locators.yaml

*** Test Cases ***
Open Notepad And Type Text
    [Documentation]    Verifies Notepad can be launched and text can be typed.
    [Tags]    smoke
    Launch Application
    Input Text    TEXT_AREA    Hello from Desktop Automation Platform!
    ${text}=    Get Text    TEXT_AREA
    Should Contain    ${text}    Hello
    Close Application
'@
    Set-Content -Path (Join-Path $exampleDir "test_notepad.robot") -Value $robotContent -Encoding utf8

    Write-OK "Example project created at: $exampleDir"
    Write-Step "To run: cd $exampleDir && robot test_notepad.robot"
} else {
    Write-Step "Example directory already exists: $exampleDir"
}

# --- 7. Smoke tests ----------------------------------------------------------
if (-not $SkipTests) {
    Write-Header "Running Smoke Tests (Unit Tests Only)"
    $testDir = Join-Path $InstallDir "desktop_automation_platform\tests\unit"
    if (Test-Path $testDir) {
        Write-Step "Running pytest on unit tests..."
        $result = & $python -m pytest $testDir -q --tb=short 2>&1
        $exitCode = $LASTEXITCODE
        if ($exitCode -eq 0) {
            Write-OK "All unit tests passed."
        } else {
            Write-Warn "Some tests failed -- this may be expected if optional dependencies are missing."
            Write-Warn "Run manually: python -m pytest $testDir -v"
            $result | Select-Object -Last 20 | ForEach-Object { Write-Host "    $_" }
        }
    } else {
        Write-Warn "Test directory not found: $testDir"
    }
} else {
    Write-Step "Skipping tests (-SkipTests specified)."
}

# --- 8. Summary --------------------------------------------------------------
Write-Header "Installation Complete"

Write-Host ""
Write-Host "  [OK] Platform installed at : $InstallDir" -ForegroundColor Green
Write-Host "  [OK] Virtual environment   : $venvDir"    -ForegroundColor Green
Write-Host "  [OK] Example project       : $(Join-Path $InstallDir 'my_first_test')" -ForegroundColor Green
Write-Host ""
Write-Host "  NEXT STEPS:" -ForegroundColor White
Write-Host "  -----------" -ForegroundColor White
Write-Host "  1. Activate your virtual environment:" -ForegroundColor White
Write-Host "       .venv\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "  2. Run the example test:" -ForegroundColor White
Write-Host "       cd my_first_test" -ForegroundColor Yellow
Write-Host "       robot test_notepad.robot" -ForegroundColor Yellow
Write-Host ""
Write-Host "  3. Read the full guide: README.md" -ForegroundColor White
Write-Host ""
Write-Host "  TROUBLESHOOTING:" -ForegroundColor White
Write-Host "  - FlaUI errors  : run .\scripts\setup_flaui.ps1" -ForegroundColor White
Write-Host "  - Import errors : ensure .venv is activated" -ForegroundColor White
Write-Host "  - Test failures : check README.md Troubleshooting section" -ForegroundColor White
Write-Host ""
