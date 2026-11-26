# setup_and_run.ps1 - create a venv, install dependencies, build all STL files (v2)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
if (-not (Test-Path "bismarck_feeder_v2.py")) { throw "bismarck_feeder_v2.py not found in $PSScriptRoot" }

if (Get-Command py -ErrorAction SilentlyContinue)         { $py = @("py", "-3") }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = @("python") }
else { throw "Python 3 not found. Install it from python.org (tick 'Add to PATH')." }

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    & $py[0] $py[1..($py.Length)] -m venv .venv
}
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $venvPy -m pip install --upgrade pip
& $venvPy -m pip install numpy scipy scikit-image

# Builds the 3 parts + the assembly into .\output  (about 3-6 GB RAM peak for part 1 or 2; close other apps)
& $venvPy bismarck_feeder_v2.py
Write-Host "Done. Files are in $PSScriptRoot\output"
