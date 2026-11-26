# Bismarckturm 2D - laser-cutting parts generator

Converts the section STLs from `Bismarckturm 3D` into flat, interlocking, flat-pack **SVG and DXF** parts for a laser cutter, with kerf compensation, nested sheets, an assembly guide and a cut list. The output is editable 2D geometry, not G-code; you set laser power and speed.

Full details: **[Bismarckturm_Laser_Cutting_2D_Parts_User_Guide.md](Bismarckturm_Laser_Cutting_2D_Parts_User_Guide.md)**

## Files

| File | Purpose |
|---|---|
| `generate_bismarckturm_laser_parts.ps1` / `.py` | Generator (PowerShell wrapper and Python engine) |
| `requirements-laser-parts.txt` | Python dependencies |
| `check_venv_setup_for_2d_parts.ps1` | Checks the `.venv` setup |
| `test_laser_parts_300mm.ps1` | End-to-end test: builds 300 mm Birdfeeder STLs, then generates 2D parts |

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements-laser-parts.txt
```

Or add `-InstallDependencies` to the generator command. If PowerShell blocks scripts: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

## Usage

Generate the STLs first, then pass **full paths** (the STLs live in `Bismarckturm 3D\scaled_output`, not in this folder):

```powershell
$stl = "C:\path\to\Bismarckturm 3D\scaled_output"

.\generate_bismarckturm_laser_parts.ps1 `
  -BaseStl  "$stl\01_base_and_hopper_birdfeeder_scale500mm_open.stl" `
  -TowerStl "$stl\02_hollow_tower_shaft_birdfeeder_scale500mm_open.stl" `
  -CrownStl "$stl\03_lift_off_crown_lid_birdfeeder_scale500mm_open.stl" `
  -Birdfeeder `
  -MaterialThickness 4 `
  -OutputFormat SVG,DXF `
  -OutputDirectory ".\2D CAD output\birdfeeder_500mm_4mm"
```

Use `-Tealight` with the tealight base STL for the other variant. Use a separate `-OutputDirectory` per run: file names do not contain the scale or thickness.

Test the pipeline end to end:

```powershell
.\test_laser_parts_300mm.ps1 -WhatIf               # preview, builds nothing
.\test_laser_parts_300mm.ps1                       # build STLs, then 2D parts
.\test_laser_parts_300mm.ps1 -ReuseExistingStlFiles # skip the slow 3D build
```

Cut a joint test coupon from your actual material before the real parts:

```powershell
.\generate_bismarckturm_laser_parts.ps1 -TestCoupon -MaterialThickness 4 -Kerf 0.2 -JointClearance 0.2
```

## Verified runs

| Model | Scale | Material | Parts | Joints | Sheets |
|---|---|---|---|---|---|
| Birdfeeder | 500 mm | 4 mm | 51 | 42 | 5 |
| Tealight | 300 mm | 3 mm | 41 | 36 | 2 |

Both runs passed all validation checks. Read every WARNING before cutting (for example, crown layers may be too thin for alignment pins at small scales).

## Viewing the output

Inkscape displays the generated SVG and DXF files correctly. The CADCraft viewer showed the DXF parts only as dashed outlines on mouse-over, so it is not recommended for inspection.

## Layers

`CUT` red, `ENGRAVE` blue, `SCORE` green dashed, `CONSTRUCTION` grey, `LABEL` black. Files are in millimetres at 1:1 and already kerf-compensated; do not apply kerf offset again in your laser software.
