#Requires -Version 5.1
<#
.SYNOPSIS
    Downloads and installs FlaUI NuGet assemblies for the Desktop Automation Platform.

.DESCRIPTION
    Uses the NuGet CLI (downloaded automatically if absent) to fetch:
      FlaUI.Core and FlaUI.UIA3 (and optionally FlaUI.UIA2).
    Assemblies are extracted to <InstallDir>\lib\flaui\ so the platform
    automation_factory.py can find them via the project-local search path.

.PARAMETER InstallDir
    Root directory of the platform project. Defaults to the parent of this script.

.PARAMETER FlaUIVersion
    NuGet version of FlaUI packages to install (default: 4.0.0).

.PARAMETER IncludeUIA2
    Also download FlaUI.UIA2 (older automation API, needed for legacy apps).

.PARAMETER Force
    Re-download even if assemblies are already present.

.EXAMPLE
    .\scripts\setup_flaui.ps1
    .\scripts\setup_flaui.ps1 -FlaUIVersion 3.2.0 -IncludeUIA2
#>

[CmdletBinding()]
param(
    [string] $InstallDir   = (Split-Path $PSScriptRoot -Parent),
    [string] $FlaUIVersion = "4.0.0",
    [switch] $IncludeUIA2,
    [switch] $Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Header { param($msg) Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Write-OK     { param($msg) Write-Host "  [OK]  $msg"  -ForegroundColor Green }
function Write-Warn   { param($msg) Write-Host "  [!!]  $msg"  -ForegroundColor Yellow }
function Write-Fail   { param($msg) Write-Host "  [XX]  $msg"  -ForegroundColor Red }
function Write-Step   { param($msg) Write-Host "  -->   $msg"  -ForegroundColor White }

Write-Host ""
Write-Host "FlaUI Assembly Installer" -ForegroundColor Cyan
Write-Host "========================" -ForegroundColor Cyan
Write-Host ""

$libDir = Join-Path $InstallDir "lib\flaui"

# --- Already installed? ------------------------------------------------------
if ((Test-Path $libDir) -and (-not $Force)) {
    $existing = Get-ChildItem $libDir -Filter "FlaUI.Core.dll" -Recurse -ErrorAction SilentlyContinue
    if ($existing) {
        Write-OK "FlaUI assemblies already present at: $libDir"
        Write-Step "Use -Force to re-download."
        exit 0
    }
}

# --- 1. Verify dotnet CLI available ------------------------------------------
Write-Header "Checking Prerequisites"

try {
    $dotnetVer = & dotnet --version 2>&1
    Write-OK "dotnet $dotnetVer"
} catch {
    Write-Fail "dotnet CLI not found. Install .NET 6+ SDK from https://dotnet.microsoft.com/download"
    exit 1
}

# --- 2. Build dependency list ------------------------------------------------
$uia3Ref  = "<PackageReference Include=`"FlaUI.UIA3`"  Version=`"$FlaUIVersion`" />"
$uia2Ref  = if ($IncludeUIA2) { "<PackageReference Include=`"FlaUI.UIA2`"  Version=`"$FlaUIVersion`" />" } else { "" }

# --- 3. Use dotnet publish to resolve ALL transitive dependencies -------------
Write-Header "Resolving FlaUI Dependencies via dotnet publish"

$tempDir   = Join-Path $env:TEMP ("flaui_nuget_" + (Get-Random).ToString())
$pubDir    = Join-Path $tempDir "publish"
$csprojPath = Join-Path $tempDir "flaui_resolve.csproj"
$csPath     = Join-Path $tempDir "Program.cs"
New-Item -ItemType Directory -Path $tempDir | Out-Null

$csprojContent = @"
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net6.0-windows</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
  <ItemGroup>
    $uia3Ref
    $uia2Ref
  </ItemGroup>
</Project>
"@

Set-Content -Path $csprojPath -Value $csprojContent -Encoding utf8
Set-Content -Path $csPath     -Value 'using System; Console.WriteLine("ok");' -Encoding utf8

Write-Step "Running dotnet publish (resolves all transitive deps)..."
try {
    $output = & dotnet publish $csprojPath -o $pubDir --nologo 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "dotnet publish failed (exit $LASTEXITCODE):"
        $output | ForEach-Object { Write-Host "  $_" }
        Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
        exit 1
    }
    Write-OK "dotnet publish succeeded."
} catch {
    Write-Fail "dotnet publish threw: $_"
    Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    exit 1
}

# --- 4. Copy required DLLs to lib/flaui --------------------------------------
Write-Header "Copying Assemblies"

if (-not (Test-Path $libDir)) {
    New-Item -ItemType Directory -Path $libDir | Out-Null
}

$copiedFiles = @()

# Copy FlaUI assemblies and their direct NuGet dependencies from publish output
$dllsToCopy = Get-ChildItem $pubDir -Filter "*.dll" | Where-Object {
    $_.Name -like "FlaUI.*" -or
    $_.Name -like "Interop.*" -or
    $_.Name -eq "System.Management.dll"
}

foreach ($dll in $dllsToCopy) {
    Copy-Item $dll.FullName $libDir -Force
    $copiedFiles += $dll.Name
    Write-Step "Copied: $($dll.Name)"
}

# System.Drawing.Common requires the WindowsDesktop runtime — copy from there.
# (It's NOT in the publish output because it's a framework-provided assembly.)
$wdaDir = "C:\Program Files\dotnet\shared\Microsoft.WindowsDesktop.App"
if (Test-Path $wdaDir) {
    $latestWda = Get-ChildItem $wdaDir | Sort-Object Name -Descending | Select-Object -First 1
    if ($latestWda) {
        $drawingDll = Join-Path $latestWda.FullName "System.Drawing.Common.dll"
        if (Test-Path $drawingDll) {
            Copy-Item $drawingDll $libDir -Force
            $copiedFiles += "System.Drawing.Common.dll"
            Write-Step "Copied: System.Drawing.Common.dll  [WindowsDesktop $($latestWda.Name)]"
        }
    }
}

# --- 4b. Write runtimeconfig so pythonnet loads the WindowsDesktop framework -
$runtimeconfigPath = Join-Path $libDir "flaui.runtimeconfig.json"
$runtimeconfigContent = @"
{
  "runtimeOptions": {
    "tfm": "net6.0-windows",
    "rollForward": "latestMajor",
    "frameworks": [
      {
        "name": "Microsoft.NETCore.App",
        "version": "6.0.0"
      },
      {
        "name": "Microsoft.WindowsDesktop.App",
        "version": "6.0.0"
      }
    ]
  }
}
"@
Set-Content -Path $runtimeconfigPath -Value $runtimeconfigContent -Encoding utf8
Write-Step "Wrote: flaui.runtimeconfig.json"

# --- 5. Cleanup --------------------------------------------------------------
Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue

# --- 6. Write README in lib/flaui --------------------------------------------
$readmePath = Join-Path $libDir "README.txt"
$readmeLines = @(
    "FlaUI Assemblies",
    "================",
    ("Downloaded by setup_flaui.ps1 on " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    ("FlaUI version : " + $FlaUIVersion),
    "",
    "Files here:"
)
foreach ($f in $copiedFiles) {
    $readmeLines += "  $f"
}
$readmeLines += ""
$readmeLines += "To update, re-run: .\scripts\setup_flaui.ps1 -Force -FlaUIVersion <new-version>"
$readmeLines += "The platform automation_factory.py automatically searches this directory."
$readmeLines += "Do NOT add this folder to git (it is already in .gitignore)."
Set-Content -Path $readmePath -Value ($readmeLines -join "`r`n") -Encoding utf8

# --- 7. Verify ---------------------------------------------------------------
Write-Header "Verification"

$corePresent = Test-Path (Join-Path $libDir "FlaUI.Core.dll")
$uia3Present = Test-Path (Join-Path $libDir "FlaUI.UIA3.dll")

if ($corePresent) { Write-OK "FlaUI.Core.dll  found" } else { Write-Warn "FlaUI.Core.dll  NOT found" }
if ($uia3Present) { Write-OK "FlaUI.UIA3.dll  found" } else { Write-Warn "FlaUI.UIA3.dll  NOT found" }

Write-Host ""
Write-Host "  FlaUI assemblies installed to: $libDir" -ForegroundColor Green
Write-Host "  Files copied: $($copiedFiles.Count)" -ForegroundColor Green
Write-Host "  No environment variable needed -- platform finds them automatically." -ForegroundColor Green
Write-Host ""
