<#
.SYNOPSIS
    End-to-end test for generating 300 mm Bismarckturm laser-cut 2D parts.

.DESCRIPTION
    This test script:

    1. Runs build_bismarckturm_model_scaled.ps1 from the Bismarckturm 3D project.
    2. That script calls bismarckturm_model_v4_scaled.py.
    3. It generates the Birdfeeder base/hopper, hollow tower shaft, and
       lift-off crown lid STL files at scale 0.3 (300 mm tall).
    4. It identifies the newly generated STL files.
    5. It passes those STL files to generate_bismarckturm_laser_parts.ps1
       in the Bismarckturm 2D project.
    6. It generates 2D SVG and DXF laser-cutting files for 4 mm material.

    The test uses the Birdfeeder model and Open mode. Open mode is the default.

.NOTES
    Run this script from the Bismarckturm 2D project folder:

        .\test_laser_parts_300mm.ps1

    To preview the commands and file movements without generating anything:

        .\test_laser_parts_300mm.ps1 -WhatIf
#>

[CmdletBinding()]
param(
    [string]$BuildScriptPath = "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\build_bismarckturm_model_scaled.ps1",

    [string]$LaserPartsScriptPath = "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 2D\generate_bismarckturm_laser_parts.ps1",

    [string]$SourceOutputFolder = "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output",

    [string]$LaserOutputFolder = "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 2D\2D CAD output\test_birdfeeder_300mm",

    [double]$ModelScale = 0.3,

    [double]$MaterialThickness = 4.0,

    [double]$Kerf = 0.2,

    [double]$JointClearance = 0.2,

    [switch]$WhatIf,

    [switch]$ReuseExistingStlFiles
)

$ErrorActionPreference = "Stop"

# Display the test configuration.
Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " BISMARCKTURM LASER-PARTS END-TO-END TEST" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Model type:              Birdfeeder"
Write-Host "Model scale:             $ModelScale"
Write-Host "Intended model height:   300 mm"
Write-Host "Open mode:               Enabled (default)"
Write-Host ""
Write-Host "3D project build script: $BuildScriptPath"
Write-Host "Python model script:     bismarckturm_model_v4_scaled.py"
Write-Host "3D STL output folder:    $SourceOutputFolder"
Write-Host ""
Write-Host "Laser-parts script:      $LaserPartsScriptPath"
Write-Host "2D output folder:        $LaserOutputFolder"
Write-Host "Material thickness:      $MaterialThickness mm"
Write-Host "Laser kerf:              $Kerf mm"
Write-Host "Joint clearance:         $JointClearance mm"
Write-Host "Output formats:          SVG and DXF"
Write-Host ""

# Verify that the 3D build script exists.
if (-not (Test-Path -LiteralPath $BuildScriptPath)) {
    throw "3D build script not found: $BuildScriptPath"
}

# Verify that the laser-parts script exists.
if (-not (Test-Path -LiteralPath $LaserPartsScriptPath)) {
    throw "Laser-parts script not found: $LaserPartsScriptPath"
}

# Ensure that the STL output folder exists.
if (-not (Test-Path -LiteralPath $SourceOutputFolder)) {
    Write-Warning "STL output folder does not exist and will be created:"
    Write-Warning $SourceOutputFolder

    if (-not $WhatIf) {
        New-Item -Path $SourceOutputFolder -ItemType Directory -Force | Out-Null
    }
}

# Ensure that the 2D output folder exists.
if (-not (Test-Path -LiteralPath $LaserOutputFolder)) {
    Write-Host "Creating 2D output folder:"
    Write-Host $LaserOutputFolder

    if (-not $WhatIf) {
        New-Item -Path $LaserOutputFolder -ItemType Directory -Force | Out-Null
    }
}

# Record the STL files present before the 3D build.
$stlFilesBeforeBuild = @()

if (Test-Path -LiteralPath $SourceOutputFolder) {
    $stlFilesBeforeBuild = Get-ChildItem `
        -LiteralPath $SourceOutputFolder `
        -File `
        -Filter "*.stl" |
        Select-Object -ExpandProperty FullName
}

Write-Host "STL files present before build: $($stlFilesBeforeBuild.Count)"
Write-Host ""

# Build the Birdfeeder model at scale 0.3, unless existing STL files are reused.
Write-Host "----------------------------------------------------------------------" -ForegroundColor Yellow
Write-Host " STEP 1: GENERATING 300 mm BIRDFEEDER STL FILES" -ForegroundColor Yellow
Write-Host "----------------------------------------------------------------------" -ForegroundColor Yellow
Write-Host ""

$expectedScaleText = "300mm"

$baseStlFile = Join-Path `
    -Path $SourceOutputFolder `
    -ChildPath "01_base_and_hopper_birdfeeder_scale${expectedScaleText}_open.stl"

$towerStlFile = Join-Path `
    -Path $SourceOutputFolder `
    -ChildPath "02_hollow_tower_shaft_birdfeeder_scale${expectedScaleText}_open.stl"

$crownStlFile = Join-Path `
    -Path $SourceOutputFolder `
    -ChildPath "03_lift_off_crown_lid_birdfeeder_scale${expectedScaleText}_open.stl"

$allExpectedFilesExist = (
    (Test-Path -LiteralPath $baseStlFile) -and
    (Test-Path -LiteralPath $towerStlFile) -and
    (Test-Path -LiteralPath $crownStlFile)
)

if ($ReuseExistingStlFiles -and $allExpectedFilesExist) {
    Write-Host "Reusing existing STL files:" -ForegroundColor Green
    Write-Host "Base/hopper STL:  $baseStlFile"
    Write-Host "Tower shaft STL:  $towerStlFile"
    Write-Host "Crown lid STL:    $crownStlFile"
    Write-Host ""
}
else {
    # Record the STL files present before the 3D build.
    $stlFilesBeforeBuild = @()

    if (Test-Path -LiteralPath $SourceOutputFolder) {
        $stlFilesBeforeBuild = Get-ChildItem `
            -LiteralPath $SourceOutputFolder `
            -File `
            -Filter "*.stl" |
            Select-Object -ExpandProperty FullName
    }

    Write-Host "STL files present before build: $($stlFilesBeforeBuild.Count)"
    Write-Host ""

    $buildParameters = @{
        Birdfeeder = $true
        Scale      = $ModelScale
        Open       = $true
    }

    $buildDisplayArguments = "-Birdfeeder -Scale $ModelScale -Open"

    Write-Host "Running: $BuildScriptPath $buildDisplayArguments"
    Write-Host ""

    try {
        if ($WhatIf) {
            Write-Host "WhatIf: Would run:"
            Write-Host "$BuildScriptPath $buildDisplayArguments"

            Write-Host ""
            Write-Host "WhatIf complete." -ForegroundColor Cyan
            Write-Host "No STL files were generated and no 2D laser-parts generation was attempted."
            Write-Host ""
            return
        }
        else {
            & $BuildScriptPath @buildParameters

            if ($LASTEXITCODE -ne 0) {
                throw "The 3D build script returned exit code $LASTEXITCODE."
            }
        }
    }
    catch {
        Write-Error "Failed to generate the 300 mm Birdfeeder STL files."
        Write-Error $_.Exception.Message
        throw
    }

    # Identify the newly generated STL files.
    $newStlFiles = @()

    if (Test-Path -LiteralPath $SourceOutputFolder) {
        $stlFilesAfterBuild = Get-ChildItem `
            -LiteralPath $SourceOutputFolder `
            -File `
            -Filter "*.stl" |
            Select-Object -ExpandProperty FullName

        $newStlFiles = $stlFilesAfterBuild | Where-Object {
            $stlFilesBeforeBuild -notcontains $_
        }
    }

    Write-Host ""
    Write-Host "Newly generated STL files: $($newStlFiles.Count)"

    foreach ($stlFile in $newStlFiles) {
        Write-Host " - $(Split-Path -Path $stlFile -Leaf)"
    }

    # Identify the three required input STL files.
    $baseStlFile = $newStlFiles | Where-Object {
        (Split-Path -Path $_ -Leaf) -like "01_base_and_hopper_*"
    } | Select-Object -First 1

    $towerStlFile = $newStlFiles | Where-Object {
        (Split-Path -Path $_ -Leaf) -like "02_hollow_tower_shaft_*"
    } | Select-Object -First 1

    $crownStlFile = $newStlFiles | Where-Object {
        (Split-Path -Path $_ -Leaf) -like "03_lift_off_crown_lid_*"
    } | Select-Object -First 1
}

# Verify that all required STL inputs were found.
if (-not $baseStlFile -or -not (Test-Path -LiteralPath $baseStlFile)) {
    throw "Required base/hopper STL file was not found: $baseStlFile"
}

if (-not $towerStlFile -or -not (Test-Path -LiteralPath $towerStlFile)) {
    throw "Required tower shaft STL file was not found: $towerStlFile"
}

if (-not $crownStlFile -or -not (Test-Path -LiteralPath $crownStlFile)) {
    throw "Required crown lid STL file was not found: $crownStlFile"
}

Write-Host ""
Write-Host "Selected STL inputs for laser-parts generation:" -ForegroundColor Green
Write-Host "Base/hopper STL:  $baseStlFile"
Write-Host "Tower shaft STL:  $towerStlFile"
Write-Host "Crown lid STL:    $crownStlFile"
Write-Host ""
# Generate the 2D laser-cutting parts.
Write-Host "----------------------------------------------------------------------" -ForegroundColor Yellow
Write-Host " STEP 2: GENERATING 2D LASER-CUT SVG AND DXF PARTS" -ForegroundColor Yellow
Write-Host "----------------------------------------------------------------------" -ForegroundColor Yellow
Write-Host ""

$laserParameters = @{
    BaseStl            = $baseStlFile
    TowerStl           = $towerStlFile
    CrownStl           = $crownStlFile
    Birdfeeder         = $true
    MaterialThickness  = $MaterialThickness
    Kerf               = $Kerf
    JointClearance     = $JointClearance
    OutputFormat       = "SVG,DXF"
    OutputDirectory    = $LaserOutputFolder
    Units              = "mm"
    ConstructionMethod = "Faceted"
}

$laserDisplayArguments = @"
-BaseStl "$baseStlFile"
-TowerStl "$towerStlFile"
-CrownStl "$crownStlFile"
-Birdfeeder
-MaterialThickness $MaterialThickness
-Kerf $Kerf
-JointClearance $JointClearance
-OutputFormat SVG,DXF
-OutputDirectory "$LaserOutputFolder"
-Units mm
-ConstructionMethod Faceted
"@

Write-Host "Running:"
Write-Host $LaserPartsScriptPath
Write-Host $laserDisplayArguments
Write-Host ""

try {
    if ($WhatIf) {
        Write-Host "WhatIf: Would run the laser-parts generation script with the parameters shown above."
    }
    else {
        & $LaserPartsScriptPath @laserParameters

        if ($LASTEXITCODE -ne 0) {
            throw "The laser-parts script returned exit code $LASTEXITCODE."
        }
    }
}
catch {
    Write-Error "Failed to generate the 2D laser-cutting parts."
    Write-Error $_.Exception.Message
    throw
}

# Inspect the generated 2D output files.
Write-Host ""
Write-Host "----------------------------------------------------------------------" -ForegroundColor Yellow
Write-Host " STEP 3: CHECKING GENERATED 2D OUTPUT FILES" -ForegroundColor Yellow
Write-Host "----------------------------------------------------------------------" -ForegroundColor Yellow
Write-Host ""

if ($WhatIf) {
    Write-Host "WhatIf: Would inspect SVG and DXF files in:"
    Write-Host $LaserOutputFolder
}
else {
    $svgFiles = Get-ChildItem `
        -LiteralPath $LaserOutputFolder `
        -File `
        -Filter "*.svg" `
        -ErrorAction SilentlyContinue

    $dxfFiles = Get-ChildItem `
        -LiteralPath $LaserOutputFolder `
        -File `
        -Filter "*.dxf" `
        -ErrorAction SilentlyContinue

    Write-Host "SVG files generated: $($svgFiles.Count)"

    foreach ($svgFile in $svgFiles) {
        Write-Host " - $($svgFile.Name)"
    }

    Write-Host ""
    Write-Host "DXF files generated: $($dxfFiles.Count)"

    foreach ($dxfFile in $dxfFiles) {
        Write-Host " - $($dxfFile.Name)"
    }

    Write-Host ""

    if ($svgFiles.Count -eq 0 -and $dxfFiles.Count -eq 0) {
        Write-Warning "No SVG or DXF files were found in the 2D output folder."
        Write-Warning "Check the output from generate_bismarckturm_laser_parts.ps1."
    }
    else {
        Write-Host "SUCCESS: 2D laser-cutting output files were generated." -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " TEST COMPLETE" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "3D STL files remain in:"
Write-Host $SourceOutputFolder
Write-Host ""
Write-Host "2D SVG and DXF files are in:"
Write-Host $LaserOutputFolder
Write-Host ""
