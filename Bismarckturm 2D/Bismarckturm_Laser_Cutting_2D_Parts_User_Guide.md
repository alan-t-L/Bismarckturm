# Bismarckturm – Laser-Cutting 2D Parts User Guide

This guide covers the **laser-cutting workflow**: `generate_bismarckturm_laser_parts.ps1` (PowerShell) and
`generate_bismarckturm_laser_parts.py` (Python). They turn the Bismarckturm **STL reference files** into **flat,
interlocking, flat-pack SVG and DXF parts** for a laser cutter. They are separate from the 3D-printing scripts and from the other
user guides, and they never modify the STL files or those scripts. A separate **end-to-end test script**, `test_laser_parts_300mm.ps1`
(Section 6), builds a 300 mm Birdfeeder and runs the whole chain (3D STLs, then 2D parts) with one command.

---

## 1. Overview

| | 3D-printing workflow | Laser-cutting workflow (this guide) |
|---|---|---|
| Scripts | `build_bismarckturm_model_scaled.ps1` / `bismarckturm_model_v4_scaled.py` | `generate_bismarckturm_laser_parts.ps1` / `.py` |
| Output | STL solids for a slicer | 2D **SVG** and/or **DXF** parts, nested sheets, assembly guide, cut list |
| Use of STL | printed directly | **geometric reference only** |

**Why an STL cannot go to a laser cutter.** An STL is a 3D triangle mesh. A laser cutter follows 2D vector paths in a plane and cuts
straight through a sheet. There is nothing in an STL that says what flat shape to cut, where the tabs are, or how thick the sheet is.

**What the scripts do.** They read the STL files, validate them, **cut plane sections through them** (done with numpy) to *measure*
the design (plinth size, door, windows, slits, columns, pediment, inscription panel, tower taper, hopper slope, tea-light seat), and
then build flat panels from those measurements with tab-and-slot joints. The output is **editable 2D geometry** for CAD review, nesting
and laser cutting. It is **not** G-code and not a 3D-printing file; you remain responsible for the final CAD review and the laser
settings.

---

## 2. Prerequisites

* **Windows 10 or later**, **Windows PowerShell 5.1** (built in) or PowerShell 7.
* **Python 3.8 or newer** (https://www.python.org/downloads/ – tick *Add python.exe to PATH*).
* A **virtual environment** named `.venv` in the same folder as the scripts:

```powershell
python -m venv .venv
```

* Python packages (listed in `requirements-laser-parts.txt`): **numpy, trimesh, shapely, ezdxf, svgwrite** – and **matplotlib** only
  for `-Preview` (and scipy only if you use the full-assembly STL).

**What the PowerShell script checks.** Before anything else it (1) finds the virtual environment, (2) checks that its Python runs and
is 3.8+, and (3) checks that every required module is installed. **It never installs anything by itself.** If something is missing it
tells you which module, which virtual environment, and the exact command:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\requirements-laser-parts.txt
```

**Installing automatically (optional).** Add `-InstallDependencies`; the script then installs the missing modules from
`requirements-laser-parts.txt` into the virtual environment and checks again:

```powershell
.\generate_bismarckturm_laser_parts.ps1 -InstallDependencies
```

**A different virtual environment.** Use `-PythonVenv`:

```powershell
.\generate_bismarckturm_laser_parts.ps1 -PythonVenv "D:\envs\laser" -InstallDependencies
```

If PowerShell refuses to run scripts: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

Keep these files together: `generate_bismarckturm_laser_parts.ps1`, `generate_bismarckturm_laser_parts.py`,
`requirements-laser-parts.txt`.

**Project folder contents (Bismarckturm 2D).**

| File / folder | Purpose |
|---|---|
| `generate_bismarckturm_laser_parts.ps1` / `.py` | the 2D laser-parts generator (PowerShell wrapper and Python engine) |
| `requirements-laser-parts.txt` | Python modules needed by the generator |
| `check_venv_setup_for_2d_parts.ps1` | checks the `.venv` setup for the 2D scripts |
| `test_laser_parts_300mm.ps1` | end-to-end test: builds 300 mm Birdfeeder STLs, then generates the 2D parts (Section 6) |
| `bismarckturm_model_v4_scaled.py`, `build_bismarckturm_model_scaled.ps1`, `setup_and_run.ps1` | 3D-printing model scripts (copies/helpers; the test script calls the build script in the *Bismarckturm 3D* folder) |
| `2D CAD output\` | generated SVG, DXF and other output |
| `.venv\` | Python virtual environment |
| `Bismarckturm_Laser_Cutting_2D_Parts_User_Guide.md` | this guide |

---

## 3. Input files

**Important: generate the STLs first and give the script their full paths.** The STL files are *not* stored in the
`Bismarckturm 2D` folder. The 3D build script (in the *Bismarckturm 3D* folder) writes them to:

```text
C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output
```

The laser-parts script only reads the files you name. A relative path such as `.\01_base_and_hopper_birdfeeder_scale500mm_open.stl`
is looked up in the **current PowerShell folder**, so running it from `Bismarckturm 2D` fails with
`ERROR: STL file not found`. Always pass **full paths** (or first `cd` into the STL folder).

**Typical workflow (500 mm Birdfeeder)**

```powershell
# 1. Generate the STLs (about 2-3 minutes, several GB of free memory)
& "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\build_bismarckturm_model_scaled.ps1" -Birdfeeder -Scale 0.5 -Open

# 2. Go back to the 2D folder
Set-Location "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 2D"

# 3. Check the exact file names (they contain the scale, e.g. scale500mm)
dir "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output"

# 4. Generate the 2D parts, using full paths to the three section STLs
.\generate_bismarckturm_laser_parts.ps1 `
  -BaseStl "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output\01_base_and_hopper_birdfeeder_scale500mm_open.stl" `
  -TowerStl "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output\02_hollow_tower_shaft_birdfeeder_scale500mm_open.stl" `
  -CrownStl "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output\03_lift_off_crown_lid_birdfeeder_scale500mm_open.stl" `
  -Birdfeeder `
  -MaterialThickness 4 `
  -OutputFormat SVG,DXF `
  -OutputDirectory ".\2D CAD output\birdfeeder_500mm_4mm"
```

* The build folder **accumulates** STLs: a 300 mm and a 500 mm run sit side by side, distinguished only by `scale300mm` / `scale500mm` in the
  file names. Use the three files with the **same** scale. The assembly STL (`00_full_…`) is not needed.
* The output file names do not contain the scale or thickness, so give each run its own `-OutputDirectory` to keep results apart.

You need the three **section STLs** made by the 3D-printing script **at the same scale**:

| Option | File |
|---|---|
| `-BaseStl` | `01_base_and_hopper_birdfeeder_…stl` **or** `01_base_and_hopper_tealight_…stl` |
| `-TowerStl` | `02_hollow_tower_shaft_…stl` (the same for both variants) |
| `-CrownStl` | `03_lift_off_crown_lid_…stl` (the same for both variants) |

* **Birdfeeder vs Tealight:** pick the base STL that matches your choice. The script checks the file name *and* the geometry (a
  tealight base has a tea-light seat, a birdfeeder base has the hopper slope) and stops if they disagree.
* The **tower shaft and crown lid are shared** by both variants; only the base differs.
* **Open or closed STLs:** *open* STLs have real windows and slits, so they are **cut** in the flat parts. *Closed* STLs have only
  recesses, so those outlines are **engraved** instead. The door is always cut.
* **Full assembly STL (`-AssemblyStl`)** can be used when the section STLs are missing, but the script warns that splitting an assembly
  into its sections is **unreliable**. Use the three section STLs whenever you can.

**Checks on every STL.** The file must exist and load; be a closed, consistently oriented, **watertight** solid with positive volume;
have a plausible size in **millimetres** (the bounding box is reported); and all three STLs must share one scale (and agree with the
`scale…mm` in the file name). A non-watertight STL stops the run (override only at your own risk with `-AllowNonWatertight`).

---

## 4. Command-line options

| PowerShell | Python | Default | Meaning |
|---|---|---|---|
| `-Birdfeeder` | `--birdfeeder` | **yes (default)** | Birdfeeder variant |
| `-Tealight` | `--tealight` | | Tealight variant. **`-Birdfeeder` and `-Tealight` are mutually exclusive**: both together = error, no files. (`-Model Birdfeeder\|Tealight` / `--model` also works.) |
| `-BaseStl` | `--base-stl` | – | base and hopper STL |
| `-TowerStl` | `--tower-stl` | – | hollow tower shaft STL |
| `-CrownStl` | `--crown-stl` | – | crown lid STL |
| `-AssemblyStl` | `--assembly-stl` | – | full assembly STL (less reliable) |
| `-MaterialThickness` | `--material-thickness` | 4 | measured sheet thickness, mm (> 0) |
| `-Kerf` | `--kerf` | 0.2 | **total** width of material the laser removes, mm |
| `-JointClearance` | `--joint-clearance` | 0.2 | finished clearance between tab and slot, mm |
| `-Fit` | `--fit` | slip | `slip` (clearance = value), `snug` (half the value), `press` (0.05 mm interference – unreliable) |
| `-TabWidth` | `--tab-width` | 10 | default tab width, mm (never narrower than the material thickness unless allowed) |
| `-TabCount` | `--tab-count` | 3 | tabs per major joint edge; reduced automatically where an edge is too short |
| `-CornerRadius` | `--corner-radius` | 0 | rounds the outer corners of the floor and top frame |
| `-Scale` | `--scale` | 1.0 | scale factor for **everything measured from the STL** (outlines, openings, joint *positions*). Material thickness, kerf, clearance and tab width are physical and are **not** scaled |
| `-ConstructionMethod` | `--construction-method` | Faceted | `Faceted` or `Stacked` (Section 9) |
| `-OutputFormat` | `--output-format` | SVG,DXF | `SVG`, `DXF` or `SVG,DXF` |
| `-OutputDirectory` | `--output-directory` | `.\2D CAD output` | created automatically; if it cannot be created or written, the script stops |
| `-Units` | `--units` | mm | only mm; all files are millimetres at 1:1 |
| `-SheetWidth` / `-SheetHeight` | `--sheet-width/-height` | 600 / 400 | nesting sheet, mm |
| `-SheetMargin` / `-PartSpacing` | `--sheet-margin` / `--part-spacing` | 10 / 3 | sheet margin and extra gap between parts, mm |
| `-TestCoupon` | `--test-coupon` | | write only the joint test coupon (no STL needed) |
| `-Preview` | `--preview` | | also write PNG previews (needs matplotlib) |
| `-AllowNarrowTabs` | `--allow-narrow-tabs` | | allow tabs/slots narrower than the material thickness |
| `-AllowNonWatertight` | `--allow-non-watertight` | | continue with a non-watertight STL (not recommended) |
| `-PythonVenv` | – | `.venv` next to the script | use another virtual environment |
| `-InstallDependencies` | – | | install missing modules from `requirements-laser-parts.txt` |
| `-Help` | `--help` | | usage |

**Defaults when options are left out:** `-Birdfeeder`, 4 mm material, 0.2 mm kerf, 0.2 mm clearance, `slip` fit, Faceted, SVG+DXF,
600 × 400 mm sheets, output in `.\2D CAD output`.

---

## 5. Command examples

The examples use **full paths** to the STLs in `Bismarckturm 3D\scaled_output` (see Section 3). Adjust the file names to the scale you
generated, and check them with `dir`.

```powershell
# Birdfeeder, 4 mm material, SVG and DXF output, default output folder
.\generate_bismarckturm_laser_parts.ps1 `
  -BaseStl "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output\01_base_and_hopper_birdfeeder_scale500mm_open.stl" `
  -TowerStl "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output\02_hollow_tower_shaft_birdfeeder_scale500mm_open.stl" `
  -CrownStl "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output\03_lift_off_crown_lid_birdfeeder_scale500mm_open.stl" `
  -Birdfeeder `
  -MaterialThickness 4 `
  -OutputFormat SVG,DXF
```

```powershell
# Tealight, 3 mm material, SVG only, custom output folder
.\generate_bismarckturm_laser_parts.ps1 `
  -BaseStl "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output\01_base_and_hopper_tealight_scale300mm_open.stl" `
  -TowerStl "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output\02_hollow_tower_shaft_tealight_scale300mm_open.stl" `
  -CrownStl "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output\03_lift_off_crown_lid_tealight_scale300mm_open.stl" `
  -Tealight `
  -MaterialThickness 3 `
  -OutputFormat SVG `
  -OutputDirectory ".\2D CAD output\tealight_3mm"
```

```powershell
# Birdfeeder, 6 mm material, DXF only
.\generate_bismarckturm_laser_parts.ps1 `
  -BaseStl "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output\01_base_and_hopper_birdfeeder_scale500mm_open.stl" `
  -TowerStl "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output\02_hollow_tower_shaft_birdfeeder_scale500mm_open.stl" `
  -CrownStl "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output\03_lift_off_crown_lid_birdfeeder_scale500mm_open.stl" `
  -Birdfeeder `
  -MaterialThickness 6 `
  -OutputFormat DXF
```

```powershell
# Test coupon (no STL needed): five slot/tab pairs with different clearances, for your material
.\generate_bismarckturm_laser_parts.ps1 -TestCoupon -MaterialThickness 4 -Kerf 0.2 -JointClearance 0.2
```

```powershell
# Check or install the Python dependencies
.\generate_bismarckturm_laser_parts.ps1 -InstallDependencies
```

Python equivalents (Windows command prompt):

```bat
python generate_bismarckturm_laser_parts.py ^
  --base-stl "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output\01_base_and_hopper_tealight_scale300mm_open.stl" ^
  --tower-stl "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output\02_hollow_tower_shaft_tealight_scale300mm_open.stl" ^
  --crown-stl "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output\03_lift_off_crown_lid_tealight_scale300mm_open.stl" ^
  --model tealight ^
  --material-thickness 3 ^
  --output-format svg

python generate_bismarckturm_laser_parts.py ^
  --base-stl "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output\01_base_and_hopper_birdfeeder_scale500mm_open.stl" ^
  --tower-stl "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output\02_hollow_tower_shaft_birdfeeder_scale500mm_open.stl" ^
  --crown-stl "C:\Users\atlau\Desktop\SolidCraft Projects\Bismarckturm 3D\scaled_output\03_lift_off_crown_lid_birdfeeder_scale500mm_open.stl" ^
  --model birdfeeder ^
  --material-thickness 4 ^
  --output-format svg,dxf

python generate_bismarckturm_laser_parts.py --test-coupon --material-thickness 4
```

---

## 6. End-to-end test script (300 mm Birdfeeder)

`test_laser_parts_300mm.ps1` checks the whole pipeline in one go: it builds a **300 mm tall Birdfeeder** with the 3D build script, finds
the three section STLs, and then calls `generate_bismarckturm_laser_parts.ps1` with their full paths. Use it after installing or
changing any script, and as a template for your own runs.

**What it does**

1. Prints the configuration (paths, scale, material thickness, kerf, clearance, output formats).
2. **Step 1 – 3D build.** Runs `build_bismarckturm_model_scaled.ps1 -Birdfeeder -Scale 0.3 -Open` in the *Bismarckturm 3D* folder. This writes
   four STLs (assembly, base and hopper, tower shaft, crown lid) to `Bismarckturm 3D\scaled_output`.
3. Selects the three STLs `01_base_and_hopper_…`, `02_hollow_tower_shaft_…` and `03_lift_off_crown_lid_…` (the assembly STL is not needed).
4. **Step 2 – 2D parts.** Runs the laser-parts script with 4 mm material, 0.2 mm kerf, 0.2 mm joint clearance, SVG and DXF output,
   `-ConstructionMethod Faceted`, writing to `2D CAD output\test_birdfeeder_300mm`.

**Run it**

```powershell
# Preview only: shows what would run; builds nothing and writes no STL or 2D files
.\test_laser_parts_300mm.ps1 -WhatIf

# Full test: builds the STLs, then generates the 2D parts
.\test_laser_parts_300mm.ps1

# Reuse STLs that already exist (skips the slow 3D build)
.\test_laser_parts_300mm.ps1 -ReuseExistingStlFiles
```

**Script options**

| Option | Default | Meaning |
|---|---|---|
| `-BuildScriptPath` | `…\Bismarckturm 3D\build_bismarckturm_model_scaled.ps1` | 3D build script |
| `-LaserPartsScriptPath` | `…\Bismarckturm 2D\generate_bismarckturm_laser_parts.ps1` | 2D generator |
| `-SourceOutputFolder` | `…\Bismarckturm 3D\scaled_output` | where the 3D build writes its STLs (note: **underscore**, not hyphen) |
| `-LaserOutputFolder` | `…\2D CAD output\test_birdfeeder_300mm` | where the 2D files are written |
| `-ModelScale` | 0.3 | model scale; 0.3 gives a 300 mm tall model |
| `-MaterialThickness` | 4 | sheet thickness, mm |
| `-Kerf` | 0.2 | laser kerf, mm |
| `-JointClearance` | 0.2 | joint clearance, mm |
| `-WhatIf` | off | preview only; stops after showing the 3D build command |
| `-ReuseExistingStlFiles` | off | reuse existing STLs instead of rebuilding (see below) |

**`-WhatIf`.** Prints the planned 3D build command and then stops with *WhatIf complete*. No STL files are generated and no 2D
generation is attempted. It still creates the output folders it reports.

**`-ReuseExistingStlFiles`.** The 3D build takes about two to three minutes (about 135 s in the reference runs), needs a few GB of free memory and
produces large files (roughly 60–125 MB per section STL, about 300 MB for the assembly). With this switch the script looks in
`-SourceOutputFolder` for these three files:

```text
01_base_and_hopper_birdfeeder_scale300mm_open.stl
02_hollow_tower_shaft_birdfeeder_scale300mm_open.stl
03_lift_off_crown_lid_birdfeeder_scale300mm_open.stl
```

If all three exist, they are used and the 3D build is skipped. If any is missing, the script builds them as normal.
The file names assume `-ModelScale 0.3` (`scale300mm`); if you change the scale, the names change too.

**Expected 3D build messages (not errors).** At scale 0.3 the build prints a warning that the BISMARCK lettering strokes are only
1.14 mm wide. That matters only for 3D printing with a 0.4 mm nozzle; it does not affect the laser-parts test. The build also checks the
Python packages numpy, scipy and scikit-image and reports each section as watertight with one shell.

**Result.** The 2D folder receives the SVG and DXF files described in Section 7. Open the `all_parts` SVG or DXF and the nested
`sheet_01` files to check them (Section 11).

## 7. Output files

All files are in millimetres at 1:1 scale. The name pattern is `bismarckturm_<birdfeeder|tealight>_<part>`.

| File | Content |
|---|---|
| `…_base_floor`, `…_front_wall`, `…_rear_wall`, `…_left_side_wall`, `…_right_side_wall`, `…_base_top_frame` | the base box |
| `…_front_portal`, `…_portal_brace_left`, `…_portal_brace_right` | columned facade with pediment and its two braces |
| `…_seed_slope`, `…_seed_slope_rib_01…03` | birdfeeder only |
| `…_tower_panel_01…04`, `…_tower_ring_01…03` | Faceted tower: 4 tapered panels (2 wide, 2 narrow) and 3 internal rings |
| `…_tower_layers` | Stacked tower: all layers in one file |
| `…_crown_lid` | crown lid: all layers in one file (always stacked) |
| `…_all_parts` | every part, separated and labelled |
| `…_sheet_01`, `_02` … | **nested sheets** ready for cutting (extra sheets are created if the parts do not fit one) |
| `…_assembly_instructions.md` | order of assembly and a table of **every tab-and-slot connection** |
| `…_cut_list.csv` | each part with size, thickness, area, sheet number, and estimated sheet usage |
| `…_preview.png` | with `-Preview` only |
| `bismarckturm_joint_test_coupon.svg/dxf` | with `-TestCoupon` |

Nothing is written unless **all** validation checks pass (the files are prepared in a temporary folder and moved into the output
folder at the end), so you never get partial or invalid output.

**Layers / colours (SVG groups and DXF layers):**

| Layer | Colour | Use |
|---|---|---|
| `CUT` | red | cut through: outlines, tabs, slots, openings |
| `ENGRAVE` | blue | engraving: inscription panel and letters, window/slit outlines on closed models, tea-light seat |
| `SCORE` | green, dashed | score lines (string course, tea-light seat ring) |
| `CONSTRUCTION` | grey | sheet outline and margin |
| `LABEL` | black | part labels (always horizontal and readable) |

---

## 8. How the 2D parts are made

1. **Sections measure the design.** Planes through the STL (0.75 × scale mm inside each outer face, so that recesses and openings
   show as holes) give the door, windows, slits, columns, pediment, inscription panel and letters, tower taper, hopper slope angle and
   tea-light seat. Open/closed is detected from whether the holes persist deeper inside the wall.
2. **Panels** are built from those measurements. Floor, walls and braces are rectangles; the tower panels are tapered trapezoids; the
   portal is a comb shape (legs, entablature, pediment).
3. **Joints.** The tab's centre line is intersected with the mating panel's mid-plane in 3D, so each slot lands exactly where its tab
   passes through.
4. **Kerf compensation**, validation, labelling and nesting.

**Simplifications to know about.** The real podium, steps, tray lip, corbels and corner cylinders are not reproduced as flat parts; the
walls rise straight to the tower start; the columns are flat legs; the top frame is glued onto the walls (no tabs) so the tower sits on
one plate.

---

## 9. Faceted or Stacked construction

| | **Faceted** (default) | **Stacked** |
|---|---|---|
| Tower | 4 tapered flat panels + 3 rings with tab-and-slot joints | many horizontal rings, one per sheet thickness, glued in a stack |
| Look | faceted, flat sides | follows the true rounded outline |
| Assembly | interlocking, quick | glued; line layers up with 3 mm dowel pins where the walls are thick enough |
| Material use | economical | uses much more sheet and many more parts |

The **base** is always panel-built (its walls are flat), and the **crown lid is always stacked** (it is round). Choose Stacked with
`-ConstructionMethod Stacked`; it is a different look and a different assembly method.

---

## 10. Material, kerf and the joint model

**Measure the thickness** with calipers at several places on the sheet (plywood and MDF vary by ±0.3 mm); use the *average*, and use
the same sheet for the test coupon.

**Measure the kerf:** cut a 20 × 20 mm square (or a row of 10 squares of 20 mm), measure the finished size with calipers; **kerf = drawn
size − finished size** (for example 20.00 − 19.80 = 0.20 mm). It is the *total* width removed, not half.

**Formula used (all lengths in mm).** Let *K* = kerf, *T* = thickness, *W* = tab width, *C* = finished clearance
(slip: *C* = JointClearance; snug: *C*/2 of it; press: −0.05).

* Finished tab = **W × T**; finished slot = **(W + C) × (T + C)**.
* Every cut path is offset by *K*/2: outlines grow by *K*/2, openings and slots shrink by *K*/2.
* **Drawn tab width = W + K** (it finishes at *W*); **drawn slot = (W + C − K) × (T + C − K)** (it finishes at *W + C*).
* So the finished clearance equals *C*, whatever the kerf. Example (T = 4, K = 0.2, C = 0.2, W = 10): drawn slot **10.0 × 4.0 mm**,
  drawn tab **10.2 mm** wide.

**Fragile joints are avoided:** tabs and slots are never narrower than the material thickness (unless `-AllowNarrowTabs`); slots stay at
least 0.75 × T from part edges, from each other and from openings; the script warns or stops when the scale and thickness do not fit
together.

### The test coupon

```powershell
.\generate_bismarckturm_laser_parts.ps1 -TestCoupon -MaterialThickness 4 -Kerf 0.2 -JointClearance 0.2
```

1. Cut `bismarckturm_joint_test_coupon` from scrap of the **same material**.
2. The plate has five slots labelled with the clearance (`C=+0.050 … +0.350`) and there are five matching tab pieces with the same
   labels.
3. Try each tab in its slot: it should slide in freely and not fall out when it is glued. Choose the clearance you like and use it as
   `-JointClearance` for the real model. If **all** are too tight/loose, change `-Kerf` (measure it again) and re-cut.

---

## 11. Using the files in CAD / the laser software

1. Open the **SVG** (Inkscape, Illustrator, CorelDRAW, LightBurn…) or **DXF** (any CAD). Units are millimetres.
   **Recommended viewer: Inkscape**, which displays the generated SVG and DXF files correctly. The CADCraft (ArtCraft suite) viewer was
   found to show the generated DXF parts only as dashed outlines on mouse-over, even though layer, colour, linetype and lineweight were
   correct; it appears unsuitable for inspecting these files for now. This was a display problem, not a file problem.
2. Check the scale: the sheet outline (grey) should measure 600 × 400 mm; a tab should measure about *W + K*.
3. Check the layers: **red = cut**, **blue = engrave**, **green dashed = score**, grey = construction, black = labels.
4. Adjust the nesting if you like: parts are separate objects. Keep at least *kerf + a few mm* between parts.
5. Assign laser settings per colour/layer (cut, engrave, score) and send to the laser. **You** set power/speed and decide whether
   your software applies its own kerf offset (do not apply it twice – these files are already kerf-compensated).

---

## 12. Assembly

The generated `…_assembly_instructions.md` lists every step and every joint. In short:

**Faceted:** floor → rear and front walls into the floor slots → left and right side walls (their end tabs go through the front/rear
wall slots) → portal facade on its leg tabs → two braces → *(birdfeeder)* slope ribs, then the slope plate (it falls towards the door)
→ glue the top frame on the walls → tower: narrow panels' tabs through the wide panels' slots, rings slid in, tower on the top frame →
glue the crown layers in numerical order (the first layers form the spigot that slips into the tower top).

* **Dry-fit everything first.** Check squareness before the glue sets; wipe off glue that squeezes into joints. Do not glue the tower
  to the base if you want to lift it off.
* **Birdfeeder:** the door is the seed outlet; the slope angle follows the 3D model (it may be reduced slightly so it fits under the top
  frame – the script tells you).
* **Tealight:** the engraved ring on the floor marks the tea-light seat; the door is the real-proportion door (not enlarged); no seed parts.

---

## 13. Birdfeeder and Tealight differences

| | Birdfeeder | Tealight |
|---|---|---|
| Door | wide seed outlet (80 % of the front width) | real-proportion door |
| Seed parts | `seed_slope` + 3 ribs | none |
| Floor | plain | engraved tea-light seat ring |
| Blind panels beside the door | none | engraved |
| Use | outdoors, with weather-proof material and sealing | indoors only |

The tower shaft and crown lid are **identical** and interchangeable.

---

## 14. Material recommendations and limitations

* **Plywood (birch, poplar) or MDF**, 3–4 mm, is the easiest choice; **cast acrylic** 3–5 mm cuts cleanly (**not** extruded acrylic for
  press fits). For outdoors use exterior plywood sealed with varnish or paint – and expect weathering.
* **Never cut PVC or vinyl** (it releases chlorine gas). Avoid unknown plastics.
* **Thickness versus scale.** The model must be big enough for the tabs. In my tests **500 mm tall with 3, 4 and 6 mm sheet** and
  **250 mm tall with 3 and 4 mm sheet** produced valid parts; the end-to-end test script ran a **300 mm Birdfeeder with 4 mm sheet** successfully, and a
  **500 mm Birdfeeder with 4 mm sheet** produced 51 parts, 42 tab-and-slot connections and 5 nested sheets (56 files), with two warnings (the seed slope reduced from
  35.0° to 32.7°, and crown layers too thin for 3 mm alignment pins), with warnings where the combination is tight (column legs are widened,
  the crown spigot is reduced to seat inside thick tower panels, and the crown layers may be too thin for alignment pins). When the
  material is simply too thick for the scale (for example **8 mm sheet at 250 mm**) the script **stops with a message** and writes
  nothing - use a larger `-Scale` or thinner material.
* The parts are an *approximation* of the 3D model made from flat sheet: curved surfaces are faceted or stacked, and fine details
  (corbels, corner cylinders, ledge) are omitted.
* The software measures the STL; if the STL is unusual (not made by the existing scripts) the measurements may fail – the script then
  stops with a message instead of guessing.

---

## 15. Safety

**Laser cutter.** Use only with the lid closed, extraction and air assist on, and never leave it unattended while it cuts; keep a CO₂
fire extinguisher nearby. Cut only materials approved for your machine. Wood and MDF can flare up – use the correct speed.
**Fumes:** extract them to the outside; MDF glue and acrylic fumes are harmful.

**Tealight version – fire safety.**
* **Prefer an LED tea light.**
* If you use a real flame, use a **heat-resistant glass or metal tea-light holder (insert)** on a heat-resistant tile.
* **Do not place a real flame tea light directly on printed or laser-cut sheet material.** Wood, MDF, acrylic and printed plastics burn
  or soften.
* Never leave a flame unattended; keep away from curtains and paper; leave the tower openings clear for air (a lit tower acts as a
  chimney); extinguish before lifting the lid.

---

## 16. Troubleshooting

| Problem | Cause and remedy |
|---|---|
| "required Python module(s) missing" | install: `.\.venv\Scripts\python.exe -m pip install -r .\requirements-laser-parts.txt`, or add `-InstallDependencies` |
| "Virtual environment not found" | `python -m venv .venv` in the script folder (or give `-PythonVenv`) |
| "Python was not found" | install Python 3.8+ from python.org, then create the venv |
| "mesh is not a closed … solid" / STL cannot be read | regenerate the STL with the 3D-printing script, or repair it; `-AllowNonWatertight` is a last resort |
| "…do not share one scale" | use base, tower and crown STLs made with the same `-Scale` |
| SVG/DXF looks wrong or tiny | check units are millimetres and not "pixels"; SVG size is in mm (viewBox in mm), DXF `$INSUNITS` = 4 |
| Joints too tight | use `-JointClearance` larger by 0.05–0.1; re-measure kerf; test with the coupon |
| Joints too loose | smaller `-JointClearance`; try `-Fit snug`; check the sheet thickness |
| Burnt edges | faster cutting, more air assist, mask the sheet with paper tape; sand lightly |
| Parts overlap or are too close | nested files keep ≥ kerf + spacing apart; if you moved parts, keep a few mm |
| "does not fit on a … sheet" | larger `-SheetWidth/-SheetHeight`, or smaller `-Scale` |
| Parts end up on several sheets | normal: extra numbered sheets are created |
| "validation problem(s) found" | the scale and thickness do not suit each other: larger `-Scale`, thinner material, smaller `-TabWidth` |
| Crown does not seat in the tower | use thinner material or a larger scale (the script warns) |
| `ERROR: STL file not found: .\01_base_and_hopper_…stl` | the STLs are not in the current folder. They are in `Bismarckturm 3D\scaled_output`; give **full paths** to `-BaseStl`, `-TowerStl` and `-CrownStl` (Section 3), and check names with `dir` |
| STL not found although the file exists | check the scale in the name (`scale300mm` vs `scale500mm`) and that you generated that scale |
| Test script: "Required base/hopper STL file was not found" | `-SourceOutputFolder` does not match the folder the 3D build writes to. The build writes to `scaled_output` (underscore); check the path and spelling |
| Test script: parser error "Missing ')' in function parameter list" | a comma is missing after the previous parameter in the `param()` block; every parameter except the last needs a comma |
| Test script `-WhatIf` ends with an error about missing STLs | the script must stop after the "WhatIf: Would run" message; use the current version of `test_laser_parts_300mm.ps1` |
| Test script rebuilds the STLs every time | add `-ReuseExistingStlFiles`; all three `…scale300mm_open.stl` files must exist in `scaled_output` |
| DXF parts appear only as dashed outlines in CADCraft | viewer rendering problem; open the file in Inkscape, or use the SVG |

---

## 17. Validation checklists

**Virtual environment**
- [ ] `.venv` exists; the script prints *Virtual environment … (Python 3.x)*.
- [ ] It prints *All required Python modules are installed*.

**End-to-end test (`test_laser_parts_300mm.ps1`)**
- [ ] `-WhatIf` shows the 3D build command and ends with *WhatIf complete*.
- [ ] A full run (or `-ReuseExistingStlFiles`) selects the three STL inputs and finishes the 2D step.
- [ ] Files appear in `2D CAD output\test_birdfeeder_300mm` and open correctly in Inkscape.

**Input STLs**
- [ ] STLs were generated first and passed with **full paths** (from `Bismarckturm 3D\scaled_output`).
- [ ] Three section STLs at the **same scale**, base STL matches Birdfeeder/Tealight.
- [ ] No "not watertight" message; bounding boxes look right (mm).

**Generated SVG/DXF**
- [ ] The run ended with *all checks passed* and listed the files; read every WARNING.
- [ ] Open the `all_parts` file: every part present, labels readable, tabs and slots in matching numbers (see the joint table).
- [ ] Door, windows and slits where you expect them (cut on open models, engraved on closed models).
- [ ] Opened in Inkscape (or your laser software), not an early-stage CAD viewer.
- [ ] Scale and units: sheet = 600 × 400 mm (or your size), tab = *W + K* wide, slot = *W + C − K* wide.

**Test coupon**
- [ ] Cut from the same material; one clearance gives the fit you want; **use that value**.

**Final nested sheets**
- [ ] Nothing outside the margin; parts at least kerf + spacing apart.
- [ ] Layers assigned the right laser settings; no double kerf offset in the software.
- [ ] Safety: material approved, extraction on, and (tealight) LED or heat-resistant holder.
