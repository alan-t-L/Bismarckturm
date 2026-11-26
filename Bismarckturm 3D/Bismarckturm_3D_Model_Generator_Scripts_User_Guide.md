# Bismarckturm 3D Model Generator Scripts – User Guide (Birdfeeder and Tealight)

A 3D-printable model of the Bismarckturm in Konstanz (Georg Wickop, 1912).

With a default scale factor (-Scale 1.0) the scripts produce scaled 3D models of the Bismarckturm that are **1m** (1,000 mm) tall using a scale of 1 : 22.8 of the real 22.8 m tower.
One command generates all the required solid model 3D STL files, intended for either of the following two uses:

| Model option | Purpose | Where to use it |
|---|---|---|
| **Birdfeeder** (default) | Seed hopper with a rear slope and a wide front door that delivers seed onto a tray | **Outdoors** |
| **Tealight** | Clean, flat base cavity with a tea-light seat | **Indoors** |

> **Use the right base for the right purpose.** The Birdfeeder base must never be used as a candle holder, and the
> Tealight base must never be used to hold birdseed outdoors. They are different files; the file name tells you which is
> which (`_birdfeeder` / `_tealight`).

The **hollow tower shaft** and the **lift-off crown lid** are *identical* in both versions. Only the base (Part 1)
differs. A Birdfeeder base and a Tealight base are therefore interchangeable on the same shaft and lid (print the shaft and
lid once, if you use the same scale, clearance and Open/Closed setting for both).

---

## 1. Generated parts

Each run produces four STL files (millimetres, Z up, centred on X = Y = 0):

| File prefix | Part | Description |
|---|---|---|
| `01_base_and_hopper` | Part 1 | Tray, podium and steps, plinth, columned portico, pediment with raised "BISMARCK" lettering. **Differs between the two model options** (Section 6 and 7). Has a socket for Part 2. |
| `02_hollow_tower_shaft` | Part 2 | Hollow shaft with corbels, corner cylinders and slits. Has a 12 mm foot that drops into Part 1. Same in both versions. |
| `03_lift_off_crown_lid` | Part 3 | Lantern and crown; a hollow cup with a 12 mm spigot into the top of Part 2. Same in both versions. |
| `00_full_bismarckturm_assembly` | Assembly | All three parts in assembled position, for viewing and checking only. **Print the three parts, not this file.** |

---

## 2. Software prerequisites (Windows)

* Windows 10 or later with **Windows PowerShell 5.1** (built in) or PowerShell 7.
* **Python 3.10 or newer** from python.org (tick *"Add python.exe to PATH"*).
* Python packages **numpy, scipy, scikit-image**, installed automatically into a virtual environment (`.venv`) by
  `setup_and_run.ps1`.
* About **8 GB RAM** (one part needs a few GB while it is meshed – close other programs) and about **0.7 GB free disk
  per run**.
* A slicer (PrusaSlicer, Cura, Bambu Studio …) and a printer whose build volume suits your scale (the tray is 400 mm
  wide at scale 1.0 and 200 mm at 0.5).

Keep these files together in one folder: `setup_and_run.ps1`, `bismarckturm_model_v4_scaled.py`,
`build_bismarckturm_model_scaled.ps1`.

**One-time setup** (creates `.venv` and installs the packages):

```powershell
.\setup_and_run.ps1
```

If PowerShell refuses to run scripts, allow them for the current window only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

---

## 3. Running the PowerShell script (recommended)

Open PowerShell in the folder with the scripts and run, for example:

```powershell
.\build_bismarckturm_model_scaled.ps1 -Birdfeeder -Scale 0.5
```

The script checks your options and the environment, prints what it will build, runs the Python script with progress
messages, and lists the finished files in the **`scaled_output`** folder.

## 4. Running the Python script directly

Use the virtual environment's Python (double-dash options):

```powershell
.\.venv\Scripts\python.exe .\bismarckturm_model_v4_scaled.py --birdfeeder --scale 0.5 --open
.\.venv\Scripts\python.exe .\bismarckturm_model_v4_scaled.py --tealight --scale 0.3 --closed --out my_folder
```

---

## 5. Command-line options

| PowerShell | Python | Meaning |
|---|---|---|
| `-Birdfeeder` | `--birdfeeder` | Birdfeeder base (see Section 6). **This is the default** if neither `-Birdfeeder` nor `-Tealight` is given. |
| `-Tealight` | `--tealight` | Tealight base (see Section 7). |
| `-Scale 0.5` (required) | `--scale 0.5` | Uniform scale of everything. `1.0` = 1000 mm tall, `0.7` = 700 mm, `0.5` = 500 mm, `0.3` = 300 mm, `0.25` = 250 mm. Must be > 0. |
| `-Clearance 0.2` (optional) | `--clearance 0.2` | Slip-fit clearance of the two pull-apart joints in **final millimetres**. Without it the clearance is proportional: 0.35 mm × scale. Only the two joints are affected. |
| `-Open` | `--open` | Windows, slits, lantern openings and the door are real openings. **Default** if neither `-Open` nor `-Closed` is given. |
| `-Closed` | `--closed` | Windows, slits and lantern openings are 1.5 mm × scale recesses only. **The door stays a real opening** in both model types. |
| `-Parts 1,2` (optional) | `--parts 1 2` | Build only some of `1`, `2`, `3`, `asm`. Default: all. `asm` needs parts 1–3 built with the same options. |
| – | `--out DIR` | Output folder (the PowerShell script always uses `scaled_output`). |

**Defaults:** with no `-Birdfeeder`/`-Tealight` you get the **Birdfeeder**; with no `-Open`/`-Closed` you get **Open**.

**Mutually exclusive options.** `-Birdfeeder` and `-Tealight` cannot be used together, and `-Open` and `-Closed` cannot be
used together. If you supply a conflicting pair the script prints an explanation and stops **without generating any
files**.

**Retained options:** `-Scale`, `-Clearance`, `-Open`, `-Closed`, `-Parts`, `--out` work exactly as before. **Renamed:**
the scripts are now `build_bismarckturm_model_scaled.ps1` and `bismarckturm_model_v4_scaled.py` (the old names
`build_bismarck_feeder_scaled.ps1` and `bismarck_feeder_v3_scaled.py` are no longer used).

### What "open" and "closed" mean

| Feature | `-Open` | `-Closed` |
|---|---|---|
| Door | real opening | real opening |
| Plinth windows (sides and rear) | **Tealight:** cut through the wall (light shows through). **Birdfeeder:** deep pockets that stop 6.4 mm (× scale) short of the cavity, so no seed can leak | 1.5 mm recess |
| Slits in the shaft | cut through the 6 mm wall | 1.5 mm recess |
| 16 lantern openings | cut through the drum wall into the lid cavity | 1.5 mm recess |
| Blind panels beside the door (Tealight only), BISMARCK panel | recess | recess |

> **Birdfeeder in Open mode:** the shaft slits are 15 mm wide, so seed **will pour out of them** if the shaft is filled
> above them. Keep the seed below the lowest slit (about **300 mm × scale** above the base), glue clear acrylic or PETG
> strips behind the slits, or use `-Closed`.

---

## 6. The Birdfeeder base

**Seed path.** You fill the feeder from the top → seed falls down the hollow shaft → slides down a **single 35° solid
slope** that runs from the rear wall to the front → leaves through the **wide front door** → lands on the portico floor
and spills down the two steps onto the surrounding **seed tray**.

* **Rear seed-flow guide.** A solid 35° ramp falling from the rear wall to the front. There are **no side guides** any more.
* **Door / outlet.** Width = **80 % of the available front width** (the hopper's internal width, 266 mm at scale 1.0), i.e.
  **213 mm wide at scale 1.0**. The height keeps the previous proportional value: **91 mm at scale 1.0** (never below 25 mm in
  the finished model, and limited so a solid wall remains above the door). The door is centred on the front face and
  leaves 47 mm of wall on each side (× scale).
* **Windows** in Open mode are blind pockets (see Section 5), so they never leak seed.
* **Blind panels** beside the door are omitted in this version because the wide door takes their place.

**Filling.** Lift off Part 3 and pour seed down the shaft. In Open mode keep the seed below the lowest slit.

**Seed tray.** Seed lands on the portico floor and runs down the two steps onto the tray (400 mm × scale square, with a
16 mm × scale lip and four drain holes in the corners so rain drains away).

**Cleaning.** Lift off the lid and the shaft. Brush the slope and the two small corners beside the door (a little seed can
rest there), wash with warm water and mild detergent, rinse, and **dry completely** before refilling. No dishwasher or boiling
water.

**Weather protection.** Print in PETG or ASA; place the feeder under a roof or eaves; keep seed dry (damp seed jams and
spoils). Do not mount it where rain can run into the open slits.

---

## 7. The Tealight base

* **No seed hardware:** no slope and no guides. The cavity floor is **flat and level** (the top of the podium).
* **Tea-light seat:** a shallow circular recess **centred** in the cavity, **3 mm deep and 52 mm wide**, sized for a
  heat-resistant **glass or metal holder / insert** (or a ≤ 50 mm heat-resistant disc or tile). A standard tea light is
  **about 38 mm wide and 14–16 mm tall**, so it stands comfortably on the insert. **The tea-light seat is a real-world
  size and is NOT scaled.**
* **Small scales:** if the cavity is too small for the full 52 mm seat the seat shrinks to fit (never below 41 mm); the
  script then tells you. Below about **scale 0.19** a standard tea light does not fit and the script stops with an error.

| Scale | Model height | Base cavity width | Seat width |
|---|---|---|---|
| 0.30 | 300 mm | 80 mm | 52 mm |
| 0.25 | 250 mm | 67 mm | 52 mm |
| 0.20 | 200 mm | 53 mm | 43 mm |
| below 0.19 | – | too small | error |

* **Door:** the realistic door, **43 mm × 91 mm at scale 1.0** (× scale), **not enlarged**, a real opening in both modes.
  The two blind recessed panels beside it are retained.
* **Windows:** in Open mode the plinth windows go through the wall (the glow shows); in Closed mode they are recesses.

### Safety – please read before using a flame

* **Prefer LED tea lights.** They are the safe choice for a printed plastic model.
* If you use a real flame: use a standard **metal or glass tea-light holder/insert** on the seat, **never** a bare tea
  light directly on the printed floor, and never a tea light on PLA. A ceramic or metal tile under the holder is a good extra
  precaution.
* **Use Open mode only** for a real flame. The slits and lantern openings let air in and heat out; in Closed mode the shaft and
  lid are sealed and heat and soot build up.
* The hollow shaft acts as a **chimney**: hot air rises into the lid. Printed plastics soften at low temperatures (PLA about
  55–60 °C, PETG about 70–80 °C). **Never leave a lit model unattended**, keep it on a stable, level, heat-resistant surface
  away from curtains, paper and other flammable material, and out of reach of children and pets. Extinguish before moving or
  lifting the lid.
* Do not use a tea light taller than about 16 mm, do not stack tea lights, and do not use scented/gel candles.
* If any part feels warm, discolours or deforms: **stop immediately** and switch to an LED tea light.
* **You use a real flame at your own risk.** The model is a decorative object, not a certified candle holder.

---

## 8. File naming rules

```
<part>_<birdfeeder|tealight>_scale<height mm>mm[_clr<micrometres>mu]_<open|closed>.stl
```

* The model type (`_birdfeeder` or `_tealight`) comes straight after the part name, on **every** file, including the shared shaft and
  lid, so Birdfeeder and Tealight files can never be confused.
* Height = 1000 × scale, whole millimetres (a non-whole value uses **`p`** instead of a dot, e.g. `255p5mm`).
* `_clr…mu` appears **only** when you pass `-Clearance`; the value is in **micrometres** (0.2 mm = `200mu`).
* `_open` or `_closed` appears **exactly once, immediately before `.stl`**.
* There is no dot in a name apart from the one before `stl`.

| Command | Base file produced |
|---|---|
| `-Birdfeeder -Scale 0.25` | `01_base_and_hopper_birdfeeder_scale250mm_open.stl` |
| `-Birdfeeder -Scale 0.25 -Clearance 0.2` | `01_base_and_hopper_birdfeeder_scale250mm_clr200mu_open.stl` |
| `-Birdfeeder -Scale 0.5` | `01_base_and_hopper_birdfeeder_scale500mm_open.stl` |
| `-Birdfeeder -Scale 0.7 -Closed` | `01_base_and_hopper_birdfeeder_scale700mm_closed.stl` |
| `-Tealight -Scale 0.3` | `01_base_and_hopper_tealight_scale300mm_open.stl` |
| `-Tealight -Scale 0.2 -Clearance 0.2` | `01_base_and_hopper_tealight_scale200mm_clr200mu_open.stl` |

The other parts follow the same pattern, e.g. `02_hollow_tower_shaft_tealight_scale250mm_open.stl`,
`03_lift_off_crown_lid_birdfeeder_scale250mm_open.stl` and
`00_full_bismarckturm_assembly_birdfeeder_scale250mm_open.stl`. A new run with identical settings overwrites the earlier
files with the same names (the script says so).

---

## 9. Printing recommendations

| Topic | Recommendation |
|---|---|
| **Material** | **Birdfeeder:** PETG or ASA (outdoors; PLA softens in the sun and degrades in rain). **Tealight:** PETG or ASA is preferable to PLA even with LED lights; see Section 7 for flames. |
| **Nozzle / layers** | 0.4 mm nozzle, 0.16–0.20 mm layers (0.12 mm for crisp lettering on small models). |
| **Walls / infill** | ≥ 3 perimeters. The 6 mm shaft wall is only 1.5 mm at scale 0.25. The Birdfeeder base contains a large solid slope (about 19 L at scale 1.0): use 10–15 % infill. The Tealight base is much lighter. |
| **Orientation** | Part 1: flat on the tray (as modelled), with supports under the portico roof (tree supports are easiest). Part 2: upright; corbel blocks overhang about 17 mm × scale, so use supports. Part 3: **upside-down** (spigot up) so the cavity opens upward; the shallow dome apex needs a raft or a few mm of support. |
| **Birdfeeder door** | The wide door has a flat top about 213 mm × scale across: print it with supports, or bridge slowly. |
| **Small scales** | Below scale ~0.32 the BISMARCK strokes are under 1.2 mm; the 2 mm relief height is fixed (not scaled). At scale 0.25 the shaft wall is 1.5 mm; the default joint clearance is only 0.087 mm, so use `-Clearance 0.2` to `0.3`. |
| **Elephant foot** | Use about 0.1–0.2 mm compensation; the joints are tight. |
| **Test the joints first** | Print one joint sample (foot/socket or spigot) before the full set. |

---

## 10. Assembly (both versions)

1. Place Part 1 (the Birdfeeder or the Tealight base) on a level, stable surface. For the Birdfeeder, orient the door the way you
   want the seed to flow; for the Tealight, place the insert/tea light on the seat first.
2. Lower Part 2 straight down into the socket of Part 1. The 12 mm foot should drop in with a small gap all round and sit flat.
   **Do not glue it** – the model must be able to be pulled apart.
3. Lower Part 3 straight onto Part 2 so the spigot slips into the shaft; the lantern rests on the shaft rim.
4. Check that nothing wobbles. If a joint is too tight, sand gently or reprint with a larger `-Clearance`.

To refill (Birdfeeder) or change the tea light (Tealight), lift off Part 3 (for the Tealight you can also reach the seat through
the door at larger scales).

---

## 11. Troubleshooting

| Problem | Likely cause and fix |
|---|---|
| **Poor seed flow** | Damp, sticky or dusty seed. Use dry seed; tap the feeder. A larger scale gives a wider shaft and door. |
| **Seed bridging** | The door is 80 % of the front width, so bridging is unlikely at the door. If seed hangs in the shaft use a larger scale or smaller seed. |
| **Too much seed dispensed** | The wide door has no sill, so seed keeps running onto the tray. Fill the shaft less, or add a low removable sill or lip at the door threshold (see the design notes below). |
| **Seed leaks from the shaft** | You are in `-Open` mode and the seed is above a slit. Use `-Closed`, fill lower, or glue clear strips behind the slits. |
| **Tea light does not fit** | The Tealight seat is 52 mm wide (smaller at scales below about 0.23). Use a standard 38 mm tea light, or a holder with a base ≤ the seat width. Below scale ~0.19 it cannot fit. |
| **Heat concerns** | Use an LED tea light; for a flame use a metal/glass holder, Open mode only, and never leave it lit unattended (Section 7). |
| **Parts too tight or loose** | The clearance is proportional (0.35 mm × scale). Use `-Clearance` (real mm): larger if tight, smaller if loose. |
| **Thin or fragile features** | Walls are 6 mm × scale, so they thin out at small scales. Use ≥ 3 perimeters or a larger scale. The lettering needs scale ≥ ~0.32. |
| **"-Birdfeeder and -Tealight cannot be used together"** | You gave both. Choose one. |
| **"-Open and -Closed cannot be used together"** | You gave both. Choose one. |
| **"Virtual environment not found"** | Run `.\setup_and_run.ps1` first. |
| **"Out of memory"** | Close other programs; the largest part needs a few GB of free RAM. |

### Design notes: seed-flow assessment (Birdfeeder)

The 35° rear slope and the wide door should work for dry sunflower hearts, black-oil sunflower, safflower and similar free-flowing
seed. The door is far wider than any seed, so it will not bridge, and 35° is steeper than the friction angle of seed on smooth plastic
(about 20–27°). It is **marginal for damp or dusty mixes**. Two things to be aware of: the door is **not self-limiting** (seed keeps
running onto the tray), and a little seed can rest in the two front corners beside the door. Possible improvements, *not
implemented*: a low sill lip at the door threshold; a shallow central V-shaped floor; or small corner fillets at the front. Ask before
adopting any of them.

---

## 12. Command examples

```powershell
# Large Open Birdfeeder, 1000 mm tall, windows/slits/openings open (default)
.\build_bismarckturm_model_scaled.ps1 -Birdfeeder -Scale 1.0

# Medium Closed Birdfeeder, 700 mm tall, windows/slits/openings recessed only; door remains open
.\build_bismarckturm_model_scaled.ps1 -Birdfeeder -Scale 0.7 -Closed

# Small Closed Birdfeeder, 500 mm tall, windows/slits/openings recessed only; door remains open
.\build_bismarckturm_model_scaled.ps1 -Birdfeeder -Scale 0.5 -Closed

# Large Open Tealight, 300 mm tall, open
.\build_bismarckturm_model_scaled.ps1 -Tealight -Scale 0.3 -Open

# Large Open Tealight, 250 mm tall, open
.\build_bismarckturm_model_scaled.ps1 -Tealight -Scale 0.25 -Open

# Small Open Tealight, 200 mm tall, joint clearance fixed at 0.2 mm; Open is the default
.\build_bismarckturm_model_scaled.ps1 -Tealight -Scale 0.2 -Clearance 0.2
```

Python equivalents (from the folder containing the scripts):

```powershell
.\.venv\Scripts\python.exe .\bismarckturm_model_v4_scaled.py --birdfeeder --scale 1.0
.\.venv\Scripts\python.exe .\bismarckturm_model_v4_scaled.py --birdfeeder --scale 0.7 --closed
.\.venv\Scripts\python.exe .\bismarckturm_model_v4_scaled.py --tealight --scale 0.2 --clearance 0.2
```

---

## 13. Pre-print checklist

1. The script printed **"manifold/watertight = True, separate shells = 1"** for all three parts, and no warnings scrolled past.
2. The file names show the right model type (`_birdfeeder` / `_tealight`), scale and mode (`_open` / `_closed`).
3. In the slicer each part is **one solid**.
4. **Birdfeeder:** one rear slope, no side guides, wide door clear, lettering reads **BISMARCK left to right** from the front.
   **Tealight:** flat floor with a shallow round seat in the centre, the narrow realistic door.
5. Open mode: slits and windows cut through (Birdfeeder windows are blind pockets); Closed mode: shallow recesses only.
6. Print a joint sample and test the fit before printing everything.
7. Slice Part 1 with supports under the portico roof (and under the Birdfeeder door); Part 3 upside-down.
8. **Tealight:** decide LED or insert-and-flame, and re-read the safety section before use.
