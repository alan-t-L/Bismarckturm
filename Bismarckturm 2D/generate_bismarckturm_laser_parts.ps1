<#
.SYNOPSIS
  Flat, interlocking LASER-CUT parts (SVG / DXF) for the Bismarckturm model, derived from the 3D-printing STL files.

.DESCRIPTION
  This script is a front end: it checks your Python virtual environment and then runs
  generate_bismarckturm_laser_parts.py (which must be in the same folder as this script) with the same options.
  The Python script does all the geometry work. The 3D-printing scripts and STL files are never modified.

  Environment checks (nothing is installed unless you add -InstallDependencies):
    1. the virtual environment (default: .venv next to this script; or -PythonVenv <path>) and its Python 3.8+;
    2. the Python modules numpy, trimesh, shapely, ezdxf, svgwrite (and matplotlib with -Preview).

.PARAMETER Birdfeeder / Tealight   Select the base variant (mutually exclusive). Default: Birdfeeder. (-Model also accepted.)
.PARAMETER BaseStl / TowerStl / CrownStl   The three section STL files (preferred input).
.PARAMETER AssemblyStl     Full assembly STL, used alone if the section STLs are unavailable (less reliable).
.PARAMETER MaterialThickness  Sheet thickness in mm (default 4).
.PARAMETER Kerf            Total laser kerf in mm (default 0.2).
.PARAMETER JointClearance  Finished tab/slot clearance in mm (default 0.2).
.PARAMETER Fit             slip (default), snug or press.
.PARAMETER TabWidth / TabCount   Default tab width (10 mm) and tabs per joint edge (3).
.PARAMETER CornerRadius    Corner rounding of the floor and top frame in mm (default 0).
.PARAMETER Scale           Scale factor for everything measured from the STL (default 1.0).
.PARAMETER ConstructionMethod  Faceted (default, tab-and-slot panels) or Stacked (horizontal layers).
.PARAMETER OutputFormat    SVG, DXF or SVG,DXF (default both).
.PARAMETER OutputDirectory Default ".\2D CAD output".
.PARAMETER Units           mm only.
.PARAMETER SheetWidth / SheetHeight / SheetMargin / PartSpacing   Nesting sheet (default 600 x 400 mm, margin 10, spacing 3).
.PARAMETER TestCoupon      Only write the joint test coupon (no STL needed).
.PARAMETER Preview         Also write PNG previews (needs matplotlib).
.PARAMETER PythonVenv      Use a virtual environment in another folder.
.PARAMETER InstallDependencies  Install missing packages from requirements-laser-parts.txt into the venv.
.PARAMETER Help            Show this help.

.EXAMPLE
  .\generate_bismarckturm_laser_parts.ps1 -BaseStl ".\01_base_and_hopper_birdfeeder_scale500mm_open.stl" -TowerStl ".\02_hollow_tower_shaft_birdfeeder_scale500mm_open.stl" -CrownStl ".\03_lift_off_crown_lid_birdfeeder_scale500mm_open.stl" -Birdfeeder -MaterialThickness 4 -OutputFormat SVG,DXF
.EXAMPLE
  .\generate_bismarckturm_laser_parts.ps1 -TestCoupon -MaterialThickness 3
.EXAMPLE
  .\generate_bismarckturm_laser_parts.ps1 -InstallDependencies
#>
[CmdletBinding()]
param(
    [string]$BaseStl, [string]$TowerStl, [string]$CrownStl, [string]$AssemblyStl,
    [ValidateSet("Birdfeeder", "Tealight")][string]$Model,
    [switch]$Birdfeeder, [switch]$Tealight,
    [double]$MaterialThickness = 4, [double]$Kerf = 0.2, [double]$JointClearance = 0.2,
    [ValidateSet("slip", "snug", "press")][string]$Fit = "slip",
    [double]$TabWidth = 10, [int]$TabCount = 3, [double]$CornerRadius = 0, [double]$Scale = 1.0,
    [string[]]$OutputFormat = @("SVG", "DXF"),
    [string]$OutputDirectory = ".\2D CAD output",
    [string]$Units = "mm",
    [ValidateSet("Faceted", "Stacked")][string]$ConstructionMethod = "Faceted",
    [double]$SheetWidth = 600, [double]$SheetHeight = 400, [double]$SheetMargin = 10, [double]$PartSpacing = 3,
    [switch]$AllowNarrowTabs, [switch]$AllowNonWatertight, [switch]$TestCoupon, [switch]$Preview, [switch]$Help,
    [string]$PythonVenv, [switch]$InstallDependencies
)

# "Continue" (not "Stop"): Windows PowerShell 5.1 turns harmless native stderr text into terminating errors under "Stop".
# Every failure below is checked explicitly instead.
$ErrorActionPreference = "Continue"
$inv = [System.Globalization.CultureInfo]::InvariantCulture      # numbers with a decimal POINT whatever the Windows locale
function Fail([string]$msg, [int]$code = 1) { Write-Host "ERROR: $msg" -ForegroundColor Red; exit $code }

if ($Help) { Get-Help $PSCommandPath -Detailed; exit 0 }

# ---------------------------------------------------------------- 1. validate the options (before anything runs)
if ($Birdfeeder -and $Tealight) {
    Fail ("-Birdfeeder and -Tealight cannot be used together.`n       -Birdfeeder = outdoor seed-feeder base (default).`n" +
          "       -Tealight   = indoor tea-light base.`n       Choose one of them, or neither (= -Birdfeeder). No files were generated.")
}
$modelName = if ($Tealight) { "tealight" } elseif ($Birdfeeder) { "birdfeeder" } elseif ($Model) { $Model.ToLower() } else { "birdfeeder" }
if ($Model -and ($Birdfeeder -or $Tealight) -and $Model.ToLower() -ne $modelName) {
    Fail "-Model $Model conflicts with -$(if ($Tealight) {'Tealight'} else {'Birdfeeder'}). No files were generated."
}
if ($Units.ToLower() -ne "mm") { Fail "only -Units mm is supported (all output is millimetres at 1:1 scale)." }
$haveInputs = $AssemblyStl -or ($BaseStl -and $TowerStl -and $CrownStl)
$partial = ($BaseStl -or $TowerStl -or $CrownStl) -and -not ($BaseStl -and $TowerStl -and $CrownStl) -and -not $AssemblyStl
if ($partial) { Fail "supply all three of -BaseStl, -TowerStl and -CrownStl (or -AssemblyStl alone)." }
foreach ($p in @($BaseStl, $TowerStl, $CrownStl, $AssemblyStl)) {
    if ($p -and -not (Test-Path -LiteralPath $p -PathType Leaf)) { Fail "STL file not found: $p" 2 }
}

# ---------------------------------------------------------------- 2. locate and validate the virtual environment
$venv = if ($PythonVenv) { $PythonVenv } else { Join-Path $PSScriptRoot ".venv" }
$py = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) {
    $alt = Join-Path $venv "bin/python"
    if (Test-Path -LiteralPath $alt) { $py = $alt }
}
if (-not (Test-Path -LiteralPath $py)) {
    $sys = Get-Command python -ErrorAction SilentlyContinue
    if (-not $sys) { $sys = Get-Command py -ErrorAction SilentlyContinue }
    if (-not $sys) {
        Fail ("Python was not found on this computer.`n       Install Python 3.8 or newer from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'),`n" +
              "       then create the virtual environment in this folder:   python -m venv .venv")
    }
    Fail ("Virtual environment not found: $venv`n       (expected $py)`n       Create it in this folder with:   python -m venv .venv`n" +
          "       then install the packages:   .\.venv\Scripts\python.exe -m pip install -r .\requirements-laser-parts.txt")
}
$ver = & $py -c "import sys; sys.stdout.write('%d.%d' % sys.version_info[:2])" 2>$null
if ($LASTEXITCODE -ne 0 -or -not $ver) {
    Fail "The Python in '$venv' cannot be run - the virtual environment looks broken.`n       Recreate it with:   python -m venv `"$venv`""
}
$vp = $ver.Split("."); if ([int]$vp[0] -lt 3 -or ([int]$vp[0] -eq 3 -and [int]$vp[1] -lt 8)) {
    Fail "Python $ver found in '$venv', but 3.8 or newer is required."
}
Write-Host "Virtual environment: $venv  (Python $ver)"

# ---------------------------------------------------------------- 3. check the required modules (no automatic installation)
$required = @("numpy", "trimesh", "shapely", "ezdxf", "svgwrite")
if ($Preview) { $required += "matplotlib" }
function Get-MissingModules {
    $out = & $py -c "import importlib.util as u, sys; sys.stdout.write(','.join(m for m in sys.argv[1:] if u.find_spec(m) is None))" @required 2>$null
    if ($LASTEXITCODE -ne 0) { Fail "could not query the installed Python modules in '$venv'." }
    if ($out) { return @($out.Split(",") | Where-Object { $_ }) } else { return @() }
}
$req = Join-Path $PSScriptRoot "requirements-laser-parts.txt"
$missing = Get-MissingModules
if ($missing.Count -gt 0 -and $InstallDependencies) {
    if (-not (Test-Path -LiteralPath $req)) { Fail "requirements file not found: $req" }
    Write-Host "Installing the missing modules ($($missing -join ', ')) from requirements-laser-parts.txt ..." -ForegroundColor Cyan
    & $py -m pip install -r $req
    if ($LASTEXITCODE -ne 0) { Fail "pip could not install the requirements (exit code $LASTEXITCODE). See the messages above." }
    $missing = Get-MissingModules
}
if ($missing.Count -gt 0) {
    Write-Host "ERROR: required Python module(s) missing: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "       Virtual environment: $venv"
    Write-Host "       Install them with:   `"$py`" -m pip install -r `"$req`""
    Write-Host "       or run this script again with -InstallDependencies."
    exit 1
}
Write-Host "All required Python modules are installed: $($required -join ', ')" -ForegroundColor Green
if ($InstallDependencies -and -not $haveInputs -and -not $TestCoupon) { exit 0 }
if (-not $haveInputs -and -not $TestCoupon) {
    Write-Host "No STL files were given, so nothing was generated. Use -BaseStl/-TowerStl/-CrownStl, or -TestCoupon, or -Help."
    exit 0
}

# ---------------------------------------------------------------- 4. build the argument list for the Python backend
$script = Join-Path $PSScriptRoot "generate_bismarckturm_laser_parts.py"
if (-not (Test-Path -LiteralPath $script)) { Fail "generate_bismarckturm_laser_parts.py not found next to this script ($PSScriptRoot)." }
$a = New-Object System.Collections.Generic.List[string]
$a.Add($script)
$a.Add("--model"); $a.Add($modelName)
foreach ($pair in @(@("--base-stl", $BaseStl), @("--tower-stl", $TowerStl), @("--crown-stl", $CrownStl), @("--assembly-stl", $AssemblyStl))) {
    if ($pair[1]) { $a.Add($pair[0]); $a.Add((Resolve-Path -LiteralPath $pair[1]).Path) }
}
function N([double]$v) { $v.ToString($inv) }
$a.AddRange([string[]]@("--material-thickness", (N $MaterialThickness), "--kerf", (N $Kerf), "--joint-clearance", (N $JointClearance),
    "--fit", $Fit, "--tab-width", (N $TabWidth), "--tab-count", "$TabCount", "--corner-radius", (N $CornerRadius), "--scale", (N $Scale),
    "--construction-method", $ConstructionMethod.ToLower(), "--output-format", (($OutputFormat -join ",").ToLower()),
    "--output-directory", $OutputDirectory, "--units", $Units.ToLower(),
    "--sheet-width", (N $SheetWidth), "--sheet-height", (N $SheetHeight), "--sheet-margin", (N $SheetMargin), "--part-spacing", (N $PartSpacing)))
foreach ($sw in @(@($AllowNarrowTabs, "--allow-narrow-tabs"), @($AllowNonWatertight, "--allow-non-watertight"), @($TestCoupon, "--test-coupon"), @($Preview, "--preview"))) {
    if ($sw[0]) { $a.Add($sw[1]) }
}

# ---------------------------------------------------------------- 5. run the Python backend; show its output; keep its exit code
Write-Host ""
Write-Host "Running the Python backend (model: $modelName, thickness $(N $MaterialThickness) mm) ..." -ForegroundColor Cyan
$env:PYTHONIOENCODING = "utf-8"
$argArray = $a.ToArray()
& $py @argArray                                                   # splatted: every option is passed as its own argument
$code = $LASTEXITCODE
if ($code -ne 0) {
    Write-Host ""
    Write-Host "The laser-parts generation FAILED (exit code $code). No output files were written. See the messages above." -ForegroundColor Red
    exit $code
}
Write-Host "Finished. Output folder: $OutputDirectory" -ForegroundColor Green
exit 0
