# Bismarckturm

Scripts that turn one parametric model of the Bismarckturm (Bismarck Tower) into files for two kinds of fabrication:

| Folder | Purpose | Output |
|---|---|---|
| [`Bismarckturm 3D`](Bismarckturm%203D/) | Builds the model as watertight 3D-print solids | STL files (base and hopper, hollow tower shaft, lift-off crown lid, full assembly) |
| [`Bismarckturm 2D`](Bismarckturm%202D/) | Turns those STLs into flat, interlocking laser-cut parts | SVG and DXF parts, nested sheets, assembly guide, cut list |

Two variants are supported: **Birdfeeder** (single rear hopper slope, seed outlet door) and **Tealight** (tea-light seat; use an LED tea light or a heat-resistant holder). The tower shaft and crown lid are shared by both.

## Workflow

```text
build_bismarckturm_model_scaled.ps1   (3D)  ->  STL files in "Bismarckturm 3D\scaled_output"
generate_bismarckturm_laser_parts.ps1 (2D)  ->  SVG / DXF in "Bismarckturm 2D\2D CAD output"
```

1. Generate the STLs at the scale you want (for example `-Scale 0.3` gives a model about 300 mm tall).
2. Pass the **full paths** of the three section STLs (`01_base_and_hopper_*`, `02_hollow_tower_shaft_*`, `03_lift_off_crown_lid_*`) to the 2D script. The STLs are not stored in the 2D folder, so relative paths fail with `STL file not found`.
3. Open the SVG or DXF files in Inkscape or your laser software, assign laser settings per layer, and cut.

`Bismarckturm 2D\test_laser_parts_300mm.ps1` runs the whole chain for a 300 mm Birdfeeder as an end-to-end test.

## Requirements

- Windows 10 or later with Windows PowerShell 5.1 or PowerShell 7
- Python 3.8 or newer
- 3D build: numpy, scipy, scikit-image, and a few GB of free memory
- 2D parts: numpy, trimesh, shapely, ezdxf, svgwrite (matplotlib only for `-Preview`)

Details are in each folder's README and user guide.

## Not in the repository

Generated STL, SVG and DXF files are excluded by `.gitignore`. A single section STL is about 60-125 MB, above GitHub's 100 MB file limit. Regenerate them with the scripts, or publish chosen outputs as release assets.

## Safety

Laser cutting: use extraction and air assist, never leave the machine unattended, and never cut PVC or vinyl. Tealight version: prefer an LED tea light, and do not put a real flame directly on printed or laser-cut material. See the 2D user guide for the full list.

## License

Add a LICENSE file before publishing (for example MIT for the scripts).
