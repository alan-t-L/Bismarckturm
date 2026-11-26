# Bismarckturm 3D - STL model generator

Builds the Bismarckturm as 3D-print-ready STL files from a parametric Python model.

## Files

| File | Purpose |
|---|---|
| `build_bismarckturm_model_scaled.ps1` | PowerShell wrapper: checks Python packages, runs the model script |
| `bismarckturm_model_v4_scaled.py` | The model (signed-distance field sampled on a grid, polygonised with marching cubes) |
| `setup_and_run.ps1` | Setup and run helper |
| User guide | Add the 3D user guide `.md` file to this folder and link it here |

## Quick start

```powershell
# 300 mm tall Birdfeeder, open mode
.\build_bismarckturm_model_scaled.ps1 -Birdfeeder -Scale 0.3 -Open

# 500 mm tall Birdfeeder
.\build_bismarckturm_model_scaled.ps1 -Birdfeeder -Scale 0.5 -Open
```

The Tealight variant is built with its own switch (see the user guide). The script first checks numpy, scipy and scikit-image, then builds parts 1, 2, 3 and the assembly.

## Output

STL files are written to `scaled_output` next to the script. File names contain the variant, scale and mode, for example:

```text
00_full_bismarckturm_assembly_birdfeeder_scale300mm_open.stl
01_base_and_hopper_birdfeeder_scale300mm_open.stl
02_hollow_tower_shaft_birdfeeder_scale300mm_open.stl
03_lift_off_crown_lid_birdfeeder_scale300mm_open.stl
```

Every scale you build stays in the folder side by side. A run takes about 2-3 minutes and needs a few GB of free memory. Each section is checked to be watertight with exactly one shell.

## Notes

- Joint clearance is proportional (0.35 mm x scale).
- The BISMARCK lettering relief is fixed at 2.0 mm. Below about scale 0.32 the letter strokes are narrower than 1.2 mm, which a 0.4 mm nozzle may not print reliably (the build warns about this).
- The 2D laser-cutting workflow uses these STLs as geometric reference: see `..\Bismarckturm 2D`.
