<#
.SYNOPSIS
    Checks and updates the existing Python virtual environment for the
    Bismarckturm 2D laser-parts generation workflow.

.DESCRIPTION
    This script assumes that a Python virtual environment already exists at:

        .\.venv

    It:
    1. Verifies that the virtual environment and requirements file exist.
    2. Upgrades pip inside the virtual environment.
    3. Installs or upgrades the packages listed in requirements-laser-parts.txt.
    4. Reports the installed version of each required package.

    The requirements file must contain:

        numpy>=1.22
        trimesh>=3.23
        shapely>=2.0
        ezdxf>=1.0
        svgwrite>=1.4
        matplotlib>=3.5
        scipy>=1.8

.NOTES
    Run this script from the Bismarckturm project folder:

        .\check_venv_setup_for_2d_parts.ps1

    To check the environment without installing or upgrading anything:

        .\check_venv_setup_for_2d_parts.ps1 -CheckOnly
#>

[CmdletBinding()]
param(
    [string]$VenvFolder = ".venv",

    [string]$RequirementsFile = "requirements-laser-parts.txt",

    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"

# Move to the folder containing this script.
Set-Location -Path $PSScriptRoot

# Resolve the virtual-environment Python executable.
$venvPython = Join-Path -Path $PSScriptRoot -ChildPath (Join-Path -Path $VenvFolder -ChildPath "Scripts\python.exe")

# Resolve the requirements file.
$requirementsPath = Join-Path -Path $PSScriptRoot -ChildPath $RequirementsFile

Write-Host "Bismarckturm 2D laser-parts virtual-environment check" -ForegroundColor Cyan
Write-Host "Project folder:        $PSScriptRoot"
Write-Host "Virtual environment:   $VenvFolder"
Write-Host "Python executable:     $venvPython"
Write-Host "Requirements file:     $requirementsPath"
Write-Host ""

# Verify that the virtual environment exists.
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Python virtual environment not found or is incomplete: $venvPython"
}

# Verify that the requirements file exists.
if (-not (Test-Path -LiteralPath $requirementsPath)) {
    throw "Requirements file not found: $requirementsPath"
}

# Packages required for the 2D laser-parts workflow.
$requiredPackages = @(
    "numpy",
    "trimesh",
    "shapely",
    "ezdxf",
    "svgwrite",
    "matplotlib",
    "scipy"
)

# Minimum versions required by requirements-laser-parts.txt.
$minimumVersions = @{
    "numpy"      = "1.22"
    "trimesh"    = "3.23"
    "shapely"    = "2.0"
    "ezdxf"      = "1.0"
    "svgwrite"   = "1.4"
    "matplotlib" = "3.5"
    "scipy"      = "1.8"
}

# Display the Python and pip versions used by the virtual environment.
Write-Host "Virtual-environment Python and pip versions:" -ForegroundColor Yellow

& $venvPython --version
& $venvPython -m pip --version

Write-Host ""

if ($CheckOnly) {
    Write-Host "Check-only mode: no packages will be installed or upgraded." -ForegroundColor Yellow
}
else {
    # Upgrade pip first.
    Write-Host "Upgrading pip..." -ForegroundColor Yellow
    & $venvPython -m pip install --upgrade pip

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upgrade pip."
    }

    # Install or upgrade all packages listed in the requirements file.
    Write-Host ""
    Write-Host "Installing or upgrading packages from:" -ForegroundColor Yellow
    Write-Host $requirementsPath

    & $venvPython -m pip install --upgrade -r $requirementsPath

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install or upgrade packages from $requirementsPath."
    }
}

# Check and display installed versions.
Write-Host ""
Write-Host "Installed package versions:" -ForegroundColor Yellow

$missingPackages = @()
$versionWarnings = @()

foreach ($packageName in $requiredPackages) {
    # Temporarily allow pip's stderr warning for a missing package.
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    $packageInfo = & $venvPython -m pip show $packageName 2>&1

    $ErrorActionPreference = $previousErrorActionPreference

    $packageNotFound = $packageInfo | Where-Object {
        $_ -like "*WARNING: Package(s) not found*"
    }

    if ($LASTEXITCODE -ne 0 -or $packageNotFound) {
        $missingPackages += $packageName
        Write-Host ("{0,-12}: NOT INSTALLED" -f $packageName) -ForegroundColor Red
        continue
    }

    # Extract the version from pip show output.
    $versionLine = $packageInfo | Where-Object {
        $_ -like "Version:*"
    } | Select-Object -First 1

    if (-not $versionLine) {
        $missingPackages += $packageName
        Write-Host ("{0,-12}: VERSION UNKNOWN" -f $packageName) -ForegroundColor Red
        continue
    }

    $installedVersion = ($versionLine -replace "^Version:\s*", "").Trim()
    $minimumVersion = $minimumVersions[$packageName]

    # Compare versions using .NET version parsing where possible.
    $versionOk = $true

    try {
        $installed = [version]$installedVersion
        $minimum = [version]$minimumVersion

        if ($installed -lt $minimum) {
            $versionOk = $false
        }
    }
    catch {
        # If the version cannot be parsed as a standard .NET version,
        # treat it as acceptable but record a warning.
        $versionWarnings += "$packageName has a non-standard version string: $installedVersion"
    }

    if ($versionOk) {
        Write-Host (
            "{0,-12}: {1} (minimum {2})" -f `
                $packageName, $installedVersion, $minimumVersion
        ) -ForegroundColor Green
    }
    else {
        Write-Host (
            "{0,-12}: {1} is below the required minimum {2}" -f `
                $packageName, $installedVersion, $minimumVersion
        ) -ForegroundColor Red

        $missingPackages += $packageName
    }
}

# Report warnings for non-standard version strings.
if ($versionWarnings.Count -gt 0) {
    Write-Host ""
    Write-Host "Version warnings:" -ForegroundColor Yellow

    foreach ($warning in $versionWarnings) {
        Write-Host $warning
    }
}

# Final result.
Write-Host ""

if ($missingPackages.Count -eq 0) {
    Write-Host "SUCCESS: The virtual environment contains all required packages." -ForegroundColor Green
    exit 0
}
else {
    Write-Host "ACTION REQUIRED: One or more required packages are missing or below the minimum version." -ForegroundColor Red
    Write-Host "Missing or unsuitable packages:"
    $missingPackages | ForEach-Object { Write-Host " - $_" }

    Write-Host ""
    Write-Host "To install or upgrade them, run:" -ForegroundColor Yellow
    Write-Host ".\check_venv_setup_for_2d_parts.ps1"

    exit 1
}
