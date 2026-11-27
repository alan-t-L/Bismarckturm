# Bismarckturm UI Application

A small Windows Forms front end for the Bismarckturm scripts. Choose options, then **copy** the generated PowerShell command or **run** it in a new PowerShell window. It also shows the user guides.

It sits beside the other project folders:

```text
SolidCraft Projects\
  Bismarckturm 3D\                 STL model scripts
  Bismarckturm 2D\                 laser-parts scripts
  Bismarckturm UI Application\     this app
```

## Start it

Double-click **`Start-BismarckturmUI.cmd`**. It starts the app with `-NoProfile`, so your own `$PROFILE` is not loaded.

## Tabs

| Tab | Builds a command for | Options |
|---|---|---|
| 3D model (STL) | `build_bismarckturm_model_scaled.ps1` | variant, open/closed, scale, clearance, parts |
| 2D laser parts | `generate_bismarckturm_laser_parts.ps1` | variant, STL set, thickness, kerf, clearance, fit, construction, formats, output folder, advanced options, test coupon |
| User guides | - | reads the `.md` guides and READMEs |

- **STL set:** the 2D tab scans `Bismarckturm 3D\scaled_output` and `Bismarckturm 3D\model_sets\*` for matching base, tower and crown STLs at the same scale. Click **Rescan** after building new STLs.
- **Output folder:** named automatically, for example `birdfeeder_500mm_4mm`, under `Bismarckturm 2D\2D CAD output`. Edit it, browse for another, or click **Auto name**.
- **Copy command:** copies the command shown. It starts with `Set-Location`, so it works from any folder. Tick **Single-line command** for one pasteable line.
- **Run in new PowerShell window:** opens a new window at the right folder, runs the command and keeps the window open.

## How the run window behaves

`RunSession.ps1` acts as the app's own profile. The run window is started with `-NoProfile`, sets a 120 x 40 character window titled "Bismarckturm - model generator", and then runs the command. Your `$PROFILE` (for example a full-screen setting) is not applied. Resizing may be ignored in some hosts such as Windows Terminal.

## What the app can and cannot do

The app builds commands only for the two project scripts, from fixed paths and validated values (numbers, drop-downs, checkboxes, existing STL files). There is no free-text command box. This limits what the app runs; it is not a PowerShell security boundary, and `-ExecutionPolicy Bypass` applies to the run window only.

## Files

| File | Purpose |
|---|---|
| `Start-BismarckturmUI.cmd` | Launcher |
| `BismarckturmUI.ps1` | The application |
| `RunSession.ps1` | Run-window setup (size, title, working folder) |
| `README.md` | This file |

## Requirements

Windows with Windows PowerShell 5.1 (built in). No extra software. The 3D and 2D scripts have their own requirements (see their READMEs).
