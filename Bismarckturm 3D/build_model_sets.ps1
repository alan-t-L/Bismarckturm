<#
.SYNOPSIS
    Generates a defined set of open Bismarckturm models at multiple scales and
    moves each model's four STL output files into its own folder.

.DESCRIPTION
    This script calls build_bismarckturm_model_scaled.ps1 for each requested
    Birdfeeder or Tealight scale. All models are generated in Open mode, which
    is the default.

    After each build, the four generated STL files are moved from:
        C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm\scaled-output

    to a new, appropriately named folder beneath:
        C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm

    Each destination folder contains:
        00_full_bismarckturm_assembly_*.stl
        01_base_and_hopper_*.stl
        02_hollow_tower_shaft_*.stl
        03_lift_off_crown_lid_*.stl

.NOTES
    The full assembly STL is for viewing and checking only. For 3D printing,
    print Parts 1, 2, and 3.
#>

[CmdletBinding()]
param(
    [string]$BuildScriptPath = "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm\build_bismarckturm_model_scaled.ps1",

    [string]$SourceOutputFolder = "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm\scaled-output",

    [string]$DestinationRootFolder = "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm",

    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

# Define the requested model sets.
# The duplicate Tealight scale 0.25 request has been removed.
$modelSets = @(
    @{ Model = "Birdfeeder"; Scale = 1.0  },
    @{ Model = "Birdfeeder"; Scale = 0.7  },
    @{ Model = "Birdfeeder"; Scale = 0.5  },
    @{ Model = "Birdfeeder"; Scale = 0.3  },
    @{ Model = "Birdfeeder"; Scale = 0.25 },
    @{ Model = "Birdfeeder"; Scale = 0.2  },
    @{ Model = "Birdfeeder"; Scale = 0.1  },
    @{ Model = "Birdfeeder"; Scale = 0.05 },
    @{ Model = "Birdfeeder"; Scale = 0.04 },
    @{ Model = "Birdfeeder"; Scale = 0.03 },

    @{ Model = "Tealight"; Scale = 0.3  },
    @{ Model = "Tealight"; Scale = 0.25 },
    @{ Model = "Tealight"; Scale = 0.2  },
    @{ Model = "Tealight"; Scale = 0.1  }
)

# Convert a scale value into a folder-friendly name.
function Get-ScaleFolderName {
    param(
        [double]$Scale
    )

    $scaleText = $Scale.ToString(
        "0.##",
        [System.Globalization.CultureInfo]::InvariantCulture
    )

    # Replace the decimal point with "p" to avoid folder-name ambiguity.
    return $scaleText.Replace(".", "p")
}

# Build the destination folder name.
function Get-DestinationFolderName {
    param(
        [string]$Model,
        [double]$Scale
    )

    $scaleFolder = Get-ScaleFolderName -Scale $Scale

    return "${Model}_open_scale${scaleFolder}"
}

# Verify that the build script exists.
if (-not (Test-Path -LiteralPath $BuildScriptPath)) {
    throw "Build script not found: $BuildScriptPath"
}

# Ensure that the source output folder exists.
if (-not (Test-Path -LiteralPath $SourceOutputFolder)) {
    Write-Warning "Source output folder does not exist and will be created: $SourceOutputFolder"
    New-Item -Path $SourceOutputFolder -ItemType Directory -Force | Out-Null
}

# Ensure that the destination root folder exists.
if (-not (Test-Path -LiteralPath $DestinationRootFolder)) {
    New-Item -Path $DestinationRootFolder -ItemType Directory -Force | Out-Null
}

Write-Host "Bismarckturm model-set generator" -ForegroundColor Cyan
Write-Host "Build script:            $BuildScriptPath"
Write-Host "Source output folder:    $SourceOutputFolder"
Write-Host "Destination root folder: $DestinationRootFolder"
Write-Host ""

$completedSets = @()
$failedSets = @()

foreach ($modelSet in $modelSets) {
    $model = $modelSet.Model
    $scale = [double]$modelSet.Scale

    $destinationFolderName = Get-DestinationFolderName -Model $model -Scale $scale
    $destinationFolderPath = Join-Path -Path $DestinationRootFolder -ChildPath $destinationFolderName

    Write-Host "Processing: $model at scale $scale" -ForegroundColor Yellow
    Write-Host "Destination: $destinationFolderPath"

    # Create the destination folder before generation.
    if (-not (Test-Path -LiteralPath $destinationFolderPath)) {
        if ($WhatIf) {
            Write-Host "WhatIf: Would create destination folder: $destinationFolderPath"
        }
        else {
            New-Item -Path $destinationFolderPath -ItemType Directory -Force | Out-Null
        }
    }

    # Record the STL files present before this build.
    $filesBeforeBuild = @()

    if (Test-Path -LiteralPath $SourceOutputFolder) {
        $filesBeforeBuild = Get-ChildItem `
            -LiteralPath $SourceOutputFolder `
            -File `
            -Filter "*.stl" |
            Select-Object -ExpandProperty FullName
    }

    # Build the model in Open mode using named parameters.
    $buildParameters = @{
        Scale = $scale
        Open  = $true
    }

    if ($model -eq "Birdfeeder") {
        $buildParameters.Birdfeeder = $true
    }
    elseif ($model -eq "Tealight") {
        $buildParameters.Tealight = $true
    }
    else {
        throw "Unknown model type: $model"
    }

    $displayArguments = "-$model -Scale $scale -Open"
    Write-Host "Running: $BuildScriptPath $displayArguments"

    try {
        if ($WhatIf) {
            Write-Host "WhatIf: Would run: $BuildScriptPath $displayArguments"
        }
        else {
            & $BuildScriptPath @buildParameters

            if ($LASTEXITCODE -ne 0) {
                throw "Build script returned exit code $LASTEXITCODE for $model at scale $scale."
            }
        }
    }
    catch {
        Write-Error "Failed to build $model at scale $scale. $($_.Exception.Message)"

        $failedSets += [PSCustomObject]@{
            Model             = $model
            Scale             = $scale
            DestinationFolder = $destinationFolderPath
            Reason            = $_.Exception.Message
        }

        continue
    }

    # Identify the STL files newly generated by this build.
    $filesAfterBuild = @()

    if (Test-Path -LiteralPath $SourceOutputFolder) {
        $filesAfterBuild = Get-ChildItem `
            -LiteralPath $SourceOutputFolder `
            -File `
            -Filter "*.stl" |
            Select-Object -ExpandProperty FullName
    }

    $newFiles = $filesAfterBuild | Where-Object {
        $filesBeforeBuild -notcontains $_
    }

    if (-not $newFiles -or $newFiles.Count -eq 0) {
        Write-Warning "No newly generated STL files were found for $model at scale $scale."

        $failedSets += [PSCustomObject]@{
            Model             = $model
            Scale             = $scale
            DestinationFolder = $destinationFolderPath
            Reason            = "No newly generated STL files found."
        }

        continue
    }

    # Move the newly generated STL files to the destination folder.
    foreach ($file in $newFiles) {
        $fileName = Split-Path -Path $file -Leaf
        $destinationFile = Join-Path -Path $destinationFolderPath -ChildPath $fileName

        if ($WhatIf) {
            Write-Host "WhatIf: Would move '$file' to '$destinationFile'"
        }
        else {
            Move-Item -LiteralPath $file -Destination $destinationFile -Force
            Write-Host "Moved: $fileName"
        }
    }

    # Verify that four STL files are present in the destination folder.
    if (-not $WhatIf) {
        $movedFiles = Get-ChildItem `
            -LiteralPath $destinationFolderPath `
            -File `
            -Filter "*.stl"

        if ($movedFiles.Count -ne 4) {
            Write-Warning "Expected 4 STL files in '$destinationFolderPath', but found $($movedFiles.Count)."
        }
        else {
            Write-Host "Successfully created 4 STL files in: $destinationFolderPath" -ForegroundColor Green
        }
    }

    $completedSets += [PSCustomObject]@{
        Model             = $model
        Scale             = $scale
        DestinationFolder = $destinationFolderPath
        STLFileCount      = if ($WhatIf) {
            0
        }
        else {
            (Get-ChildItem `
                -LiteralPath $destinationFolderPath `
                -File `
                -Filter "*.stl").Count
        }
    }

    Write-Host ""
}

# Summary.
Write-Host "Model-set generation complete." -ForegroundColor Cyan
Write-Host "Completed sets: $($completedSets.Count)"
Write-Host "Failed sets: $($failedSets.Count)"

if ($completedSets.Count -gt 0) {
    Write-Host ""
    Write-Host "Completed model sets:" -ForegroundColor Green
    $completedSets | Format-Table -AutoSize
}

if ($failedSets.Count -gt 0) {
    Write-Host ""
    Write-Host "Failed model sets:" -ForegroundColor Red
    $failedSets | Format-Table -AutoSize
}
