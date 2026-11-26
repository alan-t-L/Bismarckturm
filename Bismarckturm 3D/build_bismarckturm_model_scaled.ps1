<#
.SYNOPSIS
  Builds the Bismarckturm model STL files - BIRDFEEDER or TEALIGHT - at a chosen scale (1.0 = 1000 mm tall),
  with open or closed openings.

.DESCRIPTION
  Calls bismarckturm_model_v4_scaled.py inside the existing virtual environment (.venv, created by setup_and_run.ps1).
  Output goes to the "scaled_output" folder next to this script.
  Both model types share the SAME hollow tower shaft and lift-off crown lid; only the base section differs.

.PARAMETER Scale
  Uniform scale of the whole model. 1.0 = 1000 mm tall, 0.7 = 700 mm, 0.5 = 500 mm, 0.3 = 300 mm, 0.25 = 250 mm.

.PARAMETER Birdfeeder
  Outdoor birdfeeder base: single 35 degree rear seed slope and a wide front door (80 % of the front width).
  This is the DEFAULT when neither -Birdfeeder nor -Tealight is given.

.PARAMETER Tealight
  Indoor tea-light base: no seed hardware, flat cavity with a centred tea-light seat, real-proportion door.
  -Birdfeeder and -Tealight cannot be combined.

.PARAMETER Clearance
  Optional. Joint (slip-fit) clearance in FINAL millimetres. Omit to keep it proportional (0.35 mm x Scale).

.PARAMETER Open
  Windows, slits, lantern openings and the door are real openings. DEFAULT when neither -Open nor -Closed is given.

.PARAMETER Closed
  Windows, slits and lantern openings are 1.5 mm recesses only. The door stays a real opening in both model types.
  -Open and -Closed cannot be combined.

.PARAMETER Parts
  Optional. Any of 1, 2, 3, asm. Default: all three parts plus the assembly.

.EXAMPLE
  .\build_bismarckturm_model_scaled.ps1 -Birdfeeder -Scale 1.0              # large open birdfeeder, 1000 mm
  .\build_bismarckturm_model_scaled.ps1 -Birdfeeder -Scale 0.7 -Closed      # closed birdfeeder, 700 mm
  .\build_bismarckturm_model_scaled.ps1 -Birdfeeder -Scale 0.5 -Closed      # closed birdfeeder, 500 mm
  .\build_bismarckturm_model_scaled.ps1 -Tealight -Scale 0.3 -Open          # open tealight, 300 mm
  .\build_bismarckturm_model_scaled.ps1 -Tealight -Scale 0.25 -Open         # open tealight, 250 mm
  .\build_bismarckturm_model_scaled.ps1 -Tealight -Scale 0.2 -Clearance 0.2 # tealight, 200 mm, 0.2 mm joint clearance

  File names: <part>_<birdfeeder|tealight>_scale<height mm>mm[_clr<micrometres>mu]_<open|closed>.stl  (no dots in the names)
  e.g. 01_base_and_hopper_birdfeeder_scale500mm_closed.stl
       00_full_bismarckturm_assembly_tealight_scale200mm_clr200mu_open.stl
  To build -Parts asm separately, use the same -Birdfeeder|-Tealight / -Scale / -Clearance / -Open|-Closed as the part files.
#>
param(
    [Parameter(Mandatory = $true)]
    [double]$Scale,

    [double]$Clearance = 0,

    [switch]$Birdfeeder,
    [switch]$Tealight,

    [switch]$Open,
    [switch]$Closed,

    [ValidateSet("1", "2", "3", "asm")]
    [string[]]$Parts = @("1", "2", "3", "asm")
)

# "Continue" (not "Stop"): Windows PowerShell 5.1 turns harmless native stderr output into terminating errors under "Stop".
# Every failure below is checked explicitly instead.
$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot
$inv = [System.Globalization.CultureInfo]::InvariantCulture    # always pass numbers with a decimal POINT (German locales use a comma)

# ---------------------------------------------------------------- 1. validate the arguments (nothing is generated if one is wrong)
if ($Birdfeeder -and $Tealight) {
    Write-Host "ERROR: -Birdfeeder and -Tealight cannot be used together." -ForegroundColor Red
    Write-Host "       -Birdfeeder : outdoor seed-feeder base (default)."
    Write-Host "       -Tealight   : indoor tea-light base."
    Write-Host "       Choose one of them, or neither (= -Birdfeeder). No files were generated."
    exit 1
}
if ($Open -and $Closed) {
    Write-Host "ERROR: -Open and -Closed cannot be used together." -ForegroundColor Red
    Write-Host "       -Open   : windows, slits, lantern openings and the door are real openings (default)."
    Write-Host "       -Closed : windows, slits and lantern openings are recesses only; the door stays open."
    Write-Host "       Choose one of them, or neither (= -Open). No files were generated."
    exit 1
}
if ($Scale -le 0) {
    Write-Host "ERROR: -Scale must be greater than 0 (for example 0.5 for a 500 mm tall model)." -ForegroundColor Red
    exit 1
}
if ($PSBoundParameters.ContainsKey("Clearance") -and $Clearance -le 0) {
    Write-Host "ERROR: -Clearance must be greater than 0 (millimetres, for example 0.2)." -ForegroundColor Red
    exit 1
}
$model = if ($Tealight) { "tealight" } else { "birdfeeder" }     # default: birdfeeder
$mode  = if ($Closed)   { "closed" }   else { "open" }           # default: open

# ---------------------------------------------------------------- 2. check the environment
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "ERROR: virtual environment not found at $venvPy" -ForegroundColor Red
    Write-Host "       Run .\setup_and_run.ps1 first to create it."
    exit 1
}
$script = Join-Path $PSScriptRoot "bismarckturm_model_v4_scaled.py"
if (-not (Test-Path $script)) {
    Write-Host "ERROR: bismarckturm_model_v4_scaled.py not found in $PSScriptRoot" -ForegroundColor Red
    exit 1
}
Write-Host "Checking Python packages (numpy, scipy, scikit-image) ..."
& $venvPy -c "import numpy, scipy, skimage" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: numpy / scipy / scikit-image are missing from .venv. Run .\setup_and_run.ps1 again." -ForegroundColor Red
    exit 1
}

$outDir = Join-Path $PSScriptRoot "scaled_output"
try { New-Item -ItemType Directory -Force -Path $outDir -ErrorAction Stop | Out-Null }
catch { Write-Host "ERROR: cannot create the output folder $outDir : $_" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------- 3. build the argument list for Python
$argList = @($script, "--scale", $Scale.ToString($inv), "--out", $outDir, "--parts") + $Parts
if ($Clearance -gt 0) { $argList += @("--clearance", $Clearance.ToString($inv)) }
$argList += "--$model"                                           # --birdfeeder | --tealight
$argList += $(if ($Closed) { "--closed" } else { "--open" })

$height = ([math]::Round(1000 * $Scale, 1)).ToString($inv)
Write-Host ""
Write-Host "Building the Bismarckturm model" -ForegroundColor Cyan
Write-Host "  model     : $model"
Write-Host "  scale     : $($Scale.ToString($inv))  (model about $height mm tall)"
Write-Host "  mode      : $mode"
if ($Clearance -gt 0) { Write-Host "  clearance : $($Clearance.ToString($inv)) mm (fixed)" } else { Write-Host "  clearance : proportional (0.35 mm x scale)" }
Write-Host "  parts     : $($Parts -join ', ')"
Write-Host "  output    : $outDir"
Write-Host "This can take a few minutes and needs a few GB of free memory. Progress follows ..."
Write-Host ""

# ---------------------------------------------------------------- 4. run Python and report
$sw = [System.Diagnostics.Stopwatch]::StartNew()
& $venvPy @argList
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: bismarckturm_model_v4_scaled.py failed (exit code $LASTEXITCODE). See the messages above." -ForegroundColor Red
    exit $LASTEXITCODE
}
$sw.Stop()

Write-Host ""
Write-Host ("Done in {0:N0} s. Files for this run:" -f $sw.Elapsed.TotalSeconds) -ForegroundColor Green
$tag = "_${model}_scale*mm*_$mode.stl"
Get-ChildItem -Path $outDir -Filter "*$tag" | Sort-Object Name |
    ForEach-Object { Write-Host ("  {0}  ({1:N0} MB)" -f $_.Name, ($_.Length / 1MB)) }
Write-Host "Output folder: $outDir"
