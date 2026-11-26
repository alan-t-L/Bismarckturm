<#
.SYNOPSIS
    Generates a defined set of open Bismarckturm models at multiple scales and
    moves each model's four STL output files into its own folder.

.DESCRIPTION
    This script calls build_bismarckturm_model_scaled.ps1 for each requested
    Birdfeeder or Tealight scale. All models are generated in Open mode, which
    is the default.

    After each build, the four generated STL files are moved from the
    source output folder (default: scaled_output next to this script) to a new,
    appropriately named folder beneath the destination root folder
    (default: model_sets next to this script), for example:
        model_sets\Birdfeeder_open_scale0p3
        model_sets\Tealight_open_scale0p25

    Each destination folder contains:
        00_full_bismarckturm_assembly_*.stl
        01_base_and_hopper_*.stl
        02_hollow_tower_shaft_*.stl
        03_lift_off_crown_lid_*.stl

    Newly generated files are identified by their modification time, so a
    scale that was built before (same file names) is detected correctly.

.PARAMETER BuildScriptPath
    Path to build_bismarckturm_model_scaled.ps1.

.PARAMETER SourceOutputFolder
    Folder where the build script writes its STL files.

.PARAMETER DestinationRootFolder
    Folder under which one sub-folder per model set is created.

.PARAMETER WhatIf
    Show what would be built and moved, without building or moving anything.

.NOTES
    The full assembly STL is for viewing and checking only. For 3D printing,
    print Parts 1, 2, and 3.

    STL files are moved out of the source output folder. Scripts that expect
    them there (for example test_laser_parts_300mm.ps1 -ReuseExistingStlFiles)
    will not find them afterwards.
#>

[CmdletBinding()]
param(
    [string]$BuildScriptPath = "$PSScriptRoot\build_bismarckturm_model_scaled.ps1",

    [string]$SourceOutputFolder = "$PSScriptRoot\scaled_output",

    [string]$DestinationRootFolder = "$PSScriptRoot\model_sets",

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

    if (-not $WhatIf) {
        New-Item -Path $SourceOutputFolder -ItemType Directory -Force | Out-Null
    }
}

# Ensure that the destination root folder exists.
if (-not (Test-Path -LiteralPath $DestinationRootFolder)) {
    if ($WhatIf) {
        Write-Host "WhatIf: Would create destination root folder: $DestinationRootFolder"
    }
    else {
        New-Item -Path $DestinationRootFolder -ItemType Directory -Force | Out-Null
    }
}

Write-Host "Bismarckturm model-set generator" -ForegroundColor Cyan
Write-Host "Build script:            $BuildScriptPath"
Write-Host "Source output folder:    $SourceOutputFolder"
Write-Host "Destination root folder: $DestinationRootFolder"
Write-Host "Model sets requested:    $($modelSets.Count)"
if ($WhatIf) {
    Write-Host "Mode:                    WhatIf (nothing will be built or moved)" -ForegroundColor Cyan
}
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

    # Files written at or after this time belong to this build.
    $buildStartTime = (Get-Date).AddSeconds(-2)

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
            $global:LASTEXITCODE = 0

            & $BuildScriptPath @buildParameters

            if ($LASTEXITCODE -ne 0) {
                throw "Build script returned exit code $LASTEXITCODE for $model at scale $scale."
            }
        }
    }
    catch {
        Write-Host "Failed to build $model at scale $scale. $($_.Exception.Message)" -ForegroundColor Red

        $failedSets += [PSCustomObject]@{
            Model             = $model
            Scale             = $scale
            DestinationFolder = $destinationFolderPath
            Reason            = $_.Exception.Message
        }

        Write-Host ""
        continue
    }

    # In WhatIf mode nothing was built, so there is nothing to move.
    if ($WhatIf) {
        $completedSets += [PSCustomObject]@{
            Model             = $model
            Scale             = $scale
            DestinationFolder = $destinationFolderPath
            STLFileCount      = 0
        }

        Write-Host ""
        continue
    }

    # Identify the STL files newly generated by this build.
    $newFiles = @(
        Get-ChildItem `
            -LiteralPath $SourceOutputFolder `
            -File `
            -Filter "*.stl" |
            Where-Object { $_.LastWriteTime -ge $buildStartTime } |
            Select-Object -ExpandProperty FullName
    )

    if ($newFiles.Count -eq 0) {
        Write-Warning "No newly generated STL files were found for $model at scale $scale."

        $failedSets += [PSCustomObject]@{
            Model             = $model
            Scale             = $scale
            DestinationFolder = $destinationFolderPath
            Reason            = "No newly generated STL files found."
        }

        Write-Host ""
        continue
    }

    # Move the newly generated STL files to the destination folder.
    foreach ($file in $newFiles) {
        $fileName = Split-Path -Path $file -Leaf
        $destinationFile = Join-Path -Path $destinationFolderPath -ChildPath $fileName

        Move-Item -LiteralPath $file -Destination $destinationFile -Force
        Write-Host "Moved: $fileName"
    }

    # Verify that four STL files are present in the destination folder.
    $movedFiles = @(
        Get-ChildItem `
            -LiteralPath $destinationFolderPath `
            -File `
            -Filter "*.stl"
    )

    if ($movedFiles.Count -ne 4) {
        Write-Warning "Expected 4 STL files in '$destinationFolderPath', but found $($movedFiles.Count)."
    }
    else {
        Write-Host "Successfully created 4 STL files in: $destinationFolderPath" -ForegroundColor Green
    }

    $completedSets += [PSCustomObject]@{
        Model             = $model
        Scale             = $scale
        DestinationFolder = $destinationFolderPath
        STLFileCount      = $movedFiles.Count
    }

    Write-Host ""
}

# Summary.
Write-Host "Model-set generation complete." -ForegroundColor Cyan

if ($WhatIf) {
    Write-Host "WhatIf: no models were built and no files were moved."
    Write-Host "Model sets that would be processed: $($completedSets.Count)"
}
else {
    Write-Host "Completed sets: $($completedSets.Count)"
    Write-Host "Failed sets: $($failedSets.Count)"
}

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
