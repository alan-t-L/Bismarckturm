#!/usr/bin/env python3
"""
Bismarckturm Konstanz model v4 (scalable): BIRDFEEDER or TEALIGHT base, open or closed openings.
Reference size 1:22.8 = 1000 mm tall, 3 pull-apart parts + assembly.

Two model types share the SAME hollow tower shaft (part 2) and lift-off crown lid (part 3); only the base (part 1) differs:
    --birdfeeder   (DEFAULT) outdoor birdfeeder: single 35 degree rear seed slope, wide front door (80 % of the front width)
    --tealight     indoor tea-light holder: clean flat cavity, centred tea-light seat, real-proportion door, no seed hardware

Geometry is described as exact signed-distance fields (boxes / rounded squares / cylinders / planes combined
with min / max = union / subtract) and polygonised with marching cubes -> closed, welded, manifold single-shell
triangle meshes written as binary STL.  Z-up, millimetres, X=Y=0 centred.

Usage (PowerShell wrapper: build_bismarckturm_model_scaled.ps1):
    python bismarckturm_model_v4_scaled.py --birdfeeder --scale 1.0
    python bismarckturm_model_v4_scaled.py --birdfeeder --scale 0.7 --closed
    python bismarckturm_model_v4_scaled.py --tealight --scale 0.3 --open
    python bismarckturm_model_v4_scaled.py --tealight --scale 0.2 --clearance 0.2
    python bismarckturm_model_v4_scaled.py --scale 0.25 --parts 1 2    (only some parts; add asm for the assembly)

Options:
    --birdfeeder    outdoor birdfeeder base (DEFAULT when neither --birdfeeder nor --tealight is given)
    --tealight      indoor tea-light base.  --birdfeeder and --tealight cannot be combined.
    --scale S       uniform scale of the whole model (1.0 = 1000 mm tall, 0.25 = 250 mm tall)
    --clearance MM  optional joint clearance in FINAL millimetres (default: 0.35 mm x scale)
    --open          all windows, slits, lantern openings and the door are real openings (DEFAULT)
    --closed        windows, slits and lantern openings are 1.5 mm recesses only; the door stays open
    --out DIR       output folder (default: scaled_output next to this script)
    --parts ...     any of 1 2 3 asm (default: all)

File names: <part>_<birdfeeder|tealight>_scale<height>mm[_clr<clearance>mu]_<open|closed>.stl
    e.g. 01_base_and_hopper_birdfeeder_scale250mm_clr200mu_open.stl   (no dots in the names; non-whole values use 'p')

NOT scaled (fixed physical sizes): the 2 mm relief of the raised BISMARCK lettering and the tea-light seat
(a real tea light is 38 mm wide whatever the model scale).
Needs: numpy, scipy, scikit-image
"""
import argparse, os, sys, struct, time, shutil

try:                                                  # friendly message instead of a traceback if the venv is wrong
    import numpy as np
    from skimage.measure import marching_cubes
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
except ImportError as _e:
    sys.exit(f"ERROR: a required Python package is missing ({_e}).\n"
             f"       Run .\\setup_and_run.ps1 once to create the virtual environment and install numpy, scipy and scikit-image.")

f32 = np.float32

# ------------------------------------------------------------------ run-time settings (set once in configure())
CLR = 0.35          # radial slip-fit clearance of the two pull-apart joints, in full-size model units
REC = 1.5           # depth of a "recessed only" opening, in full-size model units (scales with the model)
SCALE = 1.0         # model scale factor (1.0 = 1000 mm tall)
OPEN_MODE = True    # True: windows/slits/lantern openings cut through;  False: 1.5 mm recesses only
MODEL = "birdfeeder"  # "birdfeeder" (seed hopper base) or "tealight" (tea-light base); only part 1 differs
RELIEF_MM = 2.0     # raised-lettering relief height in FINAL millimetres - deliberately NOT scaled
OUTLET_W = OUTLET_H = RELIEF = HW = SEAT_D = SEAT_DEPTH = 0.0   # derived in configure()

# ---- door proportions measured from the three portal photographs (full-size model mm)
DOOR_W, DOOR_H = 43.0, 91.0        # door leaf: about 0.98 m x 2.07 m real  (width : height = 0.47)
MIN_OUTLET_H_MM = 25.0             # practical minimum door/outlet HEIGHT for the birdfeeder, in FINAL mm
MAX_OUTLET_H = 110.0               # keep a sensible wall above the door (plinth top is at Z 182)
DOOR_WIDTH_FRACTION = 0.80         # BIRDFEEDER door width = 80 % (= full front width minus 20 %) of the available front width
# "available front width" = clear internal width of the hopper at the front wall (the cavity, 2 x CAV_HALF)

# ---- plinth window positions, measured from the photographs of the real tower (full-size model mm; size/depth unchanged)
# Side faces: centres at 29.5 % and 43.2 % of the plinth depth measured from the FRONT corner (Y = 153.5 - f x 307).
# Rear face: centres 28.5 % of the plinth width either side of the centre line (X = +/- 0.285 x 307).
# Height: window centre at 112 mm (window 42 mm tall) on the plinth that spans Z 52..182.
WIN_SIDE_Y = (21.0, 63.0)
WIN_REAR_X = (-87.5, 87.5)
WIN_Z0, WIN_Z1 = 91.0, 133.0

# ---- tea-light seat (TEALIGHT model). A real tea light is a fixed physical size, so these are FINAL millimetres, not scaled.
TEA_CUP_D_MM = 38.0                # standard tea light: metal cup 38 mm wide, 14-16 mm tall
SEAT_PREF_D_MM = 52.0              # preferred seat for a heat-resistant insert (glass/metal holder base up to ~50 mm)
SEAT_MIN_D_MM = 41.0               # smallest acceptable seat (38 mm cup + 1.5 mm each side)
SEAT_DEPTH_MM = 3.0                # recess depth of the seat
SEAT_EDGE_MARGIN_MM = 5.0          # keep at least this much floor between the seat and the cavity wall

# ------------------------------------------------------------------ SDF primitives
def _ext(d2, z, z0, z1):
    """extrude a 2-D sdf d2 between z0 and z1 (exact extrusion formula; also used along Y for the lettering)"""
    zc, hz = (z0 + z1) / 2.0, (z1 - z0) / 2.0
    dz = np.abs(z - zc) - hz
    a = np.maximum(d2, 0); b = np.maximum(dz, 0)
    return (np.minimum(np.maximum(d2, dz), 0) + np.sqrt(a * a + b * b)).astype(f32)

def rrect2d(x, y, hx, hy, r):
    qx = np.abs(x) - (hx - r); qy = np.abs(y) - (hy - r)
    ox = np.maximum(qx, 0); oy = np.maximum(qy, 0)
    return np.sqrt(ox * ox + oy * oy) + np.minimum(np.maximum(qx, qy), 0) - r

def rrect(x, y, z, hx, hy, r, z0, z1, cx=0.0, cy=0.0):
    return _ext(rrect2d(x - cx, y - cy, hx, hy, r), z, z0, z1)

def box(x, y, z, x0, x1, y0, y1, z0, z1):
    return rrect(x, y, z, (x1 - x0) / 2, (y1 - y0) / 2, 0, z0, z1, (x0 + x1) / 2, (y0 + y1) / 2)

def cyl(x, y, z, cx, cy, r, z0, z1):
    return _ext(np.sqrt((x - cx) ** 2 + (y - cy) ** 2) - r, z, z0, z1)

def union(*a):
    r = a[0]
    for k in a[1:]: r = np.minimum(r, k)
    return r
def sub(a, *b):
    for k in b: a = np.maximum(a, -k)
    return a
def inter(a, b): return np.maximum(a, b)
def lerp(z, za, zb, va, vb): return va + (vb - va) * (z - za) / (zb - za)

def depth_of(through):
    """MODE SWITCH: depth of a window/slit/lantern opening. Open mode = cut right through (depth 'through'),
    closed mode = shallow recess of REC."""
    return through if OPEN_MODE else REC

def recess_x(x, y, z, face, yc, w, z0, z1, sign, depth):
    """rectangular pocket/opening on a face normal to +/-X ('face' = wall half-width, 'depth' measured inwards)"""
    if sign > 0: return box(x, y, z, face - depth, face + 6, yc - w / 2, yc + w / 2, z0, z1)
    return box(x, y, z, -face - 6, -face + depth, yc - w / 2, yc + w / 2, z0, z1)

def recess_y(x, y, z, face, xc, w, z0, z1, sign, depth):
    if sign > 0: return box(x, y, z, xc - w / 2, xc + w / 2, face - depth, face + 6, z0, z1)
    return box(x, y, z, xc - w / 2, xc + w / 2, -face - 6, -face + depth, z0, z1)

# ------------------------------------------------------------------ shared tower geometry
Z_BAND_TOP = 250.0          # Part 1 / Part 2 joint plane
Z_SHAFT_TOP = 760.0         # Part 2 / Part 3 joint plane
Z_LEDGE = 632.0             # corbel ledge: shaft steps in, corner cylinders emerge
H_BOT, H_TOP = 139.1, 130.5 # half-width of shaft outline at Z=250 / Z=760 (278.2 / 261 sq)
R_BOT, R_TOP = 40.0, 36.0
H_CORE, R_CORE = 124.0, 50.0
LOBE_R, LOBE_C = 35.0, H_TOP - 35.0
WALL = 6.0
H_BORE_UP, R_BORE_UP = H_CORE - WALL, R_CORE - WALL
CAV_HALF = H_BOT - WALL     # hopper cavity half-width = shaft bore (133.1)

def h_shaft(z): return lerp(z, Z_BAND_TOP, Z_SHAFT_TOP, H_BOT, H_TOP)
def r_shaft(z): return lerp(z, Z_BAND_TOP, Z_SHAFT_TOP, R_BOT, R_TOP)

# ------------------------------------------------------------------ raised "BISMARCK" lettering (stroke font)
# Each glyph = (width in glyph units, list of centre-line segments (x0,z0,x1,z1) in a 0..width x 0..1 cell).
GLYPHS = {
    "B": (0.85, [(0, 0, 0, 1), (0, 1, .8, 1), (.8, 1, .8, .5), (0, .5, .85, .5), (.85, .5, .85, 0), (0, 0, .85, 0)]),
    "I": (0.45, [(.225, 0, .225, 1), (0, 1, .45, 1), (0, 0, .45, 0)]),
    "S": (0.85, [(0, 1, .85, 1), (0, 1, 0, .5), (0, .5, .85, .5), (.85, .5, .85, 0), (0, 0, .85, 0)]),
    "M": (1.10, [(0, 0, 0, 1), (0, 1, .55, .35), (.55, .35, 1.1, 1), (1.1, 1, 1.1, 0)]),
    "A": (1.00, [(0, 0, .5, 1), (.5, 1, 1, 0), (.2, .4, .8, .4)]),
    "R": (0.90, [(0, 0, 0, 1), (0, 1, .8, 1), (.8, 1, .8, .5), (0, .5, .8, .5), (.35, .5, .9, 0)]),
    "C": (0.85, [(.85, 1, 0, 1), (0, 1, 0, 0), (0, 0, .85, 0)]),
    "K": (0.95, [(0, 0, 0, 1), (.85, 1, 0, .45), (.2, .6, .95, 0)]),
}
TEXT = "BISMARCK"
GLYPH_GAP = 0.30
# Inscription panel measured from the photographs: ~107 mm wide x 30.7 mm high, centred on the pediment,
# sitting across the base of the gable (full-size model mm).
PANEL_X, PANEL_Z0, PANEL_Z1 = 53.5, 226.0, 257.0
FRONT_Y = 219.5                       # front face of the portico entablature / pediment
LETTER_H = 18.0                       # physical letter height (incl. stroke) in full-size model mm

def lettering(x, y, z):
    """Raised BISMARCK letters on the floor of the inscription panel.
    2-D stroke SDF is evaluated only on the (x, z) plane (cheap) and extruded along Y by RELIEF."""
    hw = HW
    total_units = sum(GLYPHS[c][0] for c in TEXT) + GLYPH_GAP * (len(TEXT) - 1)
    avail = 2 * PANEL_X - 6.0                         # keep 3 mm clear of the recess walls
    ux = (avail - 2 * hw) / total_units               # glyph unit width (mm)
    hz = LETTER_H - 2 * hw                            # centre-line height of a letter
    zc = (PANEL_Z0 + PANEL_Z1) / 2.0
    xcur = -avail / 2.0 + hw
    d2 = None
    for ch in TEXT:
        gw, segs = GLYPHS[ch]
        for (a, b, c, d) in segs:
            # xcur/a/c run in READING direction (left to right as seen from OUTSIDE). The panel faces +Y, so a viewer
            # standing outside looking at it has their right-hand side on -X: reading coordinate u maps to X = -u.
            ax, az = -(xcur + a * ux), zc - hz / 2 + b * hz
            bx, bz = -(xcur + c * ux), zc - hz / 2 + d * hz
            dx, dz = bx - ax, bz - az
            t = np.clip(((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz), 0.0, 1.0)
            d = np.sqrt((x - (ax + t * dx)) ** 2 + (z - (az + t * dz)) ** 2) - hw     # capsule = rounded stroke
            d2 = d if d2 is None else np.minimum(d2, d)
        xcur += (gw + GLYPH_GAP) * ux
    floor_y = FRONT_Y - REC                           # panel floor
    return _ext(d2, y, floor_y - 1.0, floor_y + RELIEF)   # starts 1 unit inside the wall so it fuses to the panel

# ------------------------------------------------------------------ PART 1  base + hopper
def part1(x, y, z):
    # ---- seed tray 400x400 R12: floor 12, lip 16 high x 8 thick
    floor = rrect(x, y, z, 200, 200, 12, 0, 12)
    lip = sub(rrect(x, y, z, 200, 200, 12, 12, 28), rrect(x, y, z, 192, 192, 4, 11, 29))
    ext = box(x, y, z, -162, 162, 190, 276, 0, 12)                     # tray extension in front of the steps
    ext_lip = sub(box(x, y, z, -162, 162, 190, 276, 12, 28), box(x, y, z, -154, 154, 150, 268, 11, 29))
    lip = sub(lip, box(x, y, z, -154, 154, 188, 203, 11, 29))
    tray = union(floor, lip, ext, ext_lip)
    for sx in (-1, 1):                                                  # 4 mm drain holes
        for sy in (-1, 1):
            tray = sub(tray, cyl(x, y, z, sx * 172, sy * 172, 2.0, -1, 13))
    # ---- podium + 2 front steps
    podium = box(x, y, z, -162, 162, -162, 236, 12, 52)
    steps = union(box(x, y, z, -87, 87, 236, 250, 12, 38.7), box(x, y, z, -87, 87, 250, 264, 12, 25.3))
    # ---- plinth 307 sq (Z 52..182) + stepped band 292 sq (Z 181..250)
    body = union(box(x, y, z, -153.5, 153.5, -153.5, 153.5, 52, 182),
                 box(x, y, z, -146, 146, -146, 146, 181, Z_BAND_TOP))
    # the front OUTLET is the real DOOR: door-proportioned opening through the front wall (open in both modes)
    outlet = box(x, y, z, -OUTLET_W / 2, OUTLET_W / 2, 120, 160, 52, 52 + OUTLET_H)
    body = sub(body,
               rrect(x, y, z, H_BOT + CLR, H_BOT + CLR, R_BOT + CLR, Z_BAND_TOP - 12, Z_BAND_TOP + 1),  # socket for Part 2
               rrect(x, y, z, CAV_HALF, CAV_HALF, R_BOT - WALL, 52, Z_BAND_TOP + 1),                    # hopper cavity
               outlet)
    # ---- blind panels beside the door (tealight only): recesses.  Plinth windows: open = cut through the wall, closed = recess.
    rec = []
    if MODEL == "tealight":      # (the wide birdfeeder door would swallow these panels, so only the tealight base has them)
        for sx in (-1, 1):
            rec.append(box(x, y, z, min(sx * 78, sx * 108), max(sx * 78, sx * 108), 153.5 - REC, 160, 52, 160))
    # Open mode: tealight windows go right through the wall (they glow); BIRDFEEDER windows stop 6.4 mm short of the cavity
    # (blind pockets) so no seed can leak out of them now that the side guides are gone.
    wd = depth_of(26.0 if MODEL == "tealight" else 14.0)
    # Window POSITIONS (size 15 x 42 and depth unchanged) follow the photographs - see WIN_* constants:
    for yc in WIN_SIDE_Y:       # side faces (+X and -X): close together, towards the FRONT; identical on both sides
        rec += [recess_x(x, y, z, 153.5, yc, 15, WIN_Z0, WIN_Z1, +1, wd), recess_x(x, y, z, 153.5, yc, 15, WIN_Z0, WIN_Z1, -1, wd)]
    for xc in WIN_REAR_X:       # rear face (-Y): the two windows far apart
        rec += [recess_y(x, y, z, 153.5, xc, 15, WIN_Z0, WIN_Z1, -1, wd)]
    body = sub(body, *rec)
    # ---- portico: 4 plain columns D28, entablature, end piers, pediment with inscription panel + raised lettering
    cols = [cyl(x, y, z, cx, 201.5, 14.0, 52, 183) for cx in (-116, -70, 70, 116)]
    entab = box(x, y, z, -146, 146, 146, FRONT_Y, 182, 248)
    piers = union(box(x, y, z, 130, 146, 146, FRONT_Y, 52, 183), box(x, y, z, -146, -130, 146, FRONT_Y, 52, 183))
    gable = inter(box(x, y, z, -111, 111, 146, FRONT_Y, 247, 295),
                  (np.abs(x) * 47 + (z - 248) * 111 - 111 * 47) / np.hypot(47, 111))
    panel = box(x, y, z, -PANEL_X, PANEL_X, FRONT_Y - REC, FRONT_Y + 6, PANEL_Z0, PANEL_Z1)   # recessed panel
    front = union(sub(union(entab, gable), panel), lettering(x, y, z))                           # + raised letters
    if MODEL == "birdfeeder":
        # BIRDFEEDER seed flow: ONE rear slope - a solid 35 degree ramp falling from the rear wall to the front apron and the
        # wide door (no side guides).  Solid fill, so nothing overhangs.
        t = np.tan(np.radians(35.0))
        main = 52.0 + t * np.maximum(0.0, 115.0 - y)                                # slope height (flat apron for Y > 115)
        hopper_fill = inter(box(x, y, z, -134, 134, -134, 134, 51, 260), z - main)
        return union(tray, podium, steps, body, hopper_fill, front, piers, *cols)
    # TEALIGHT: no seed hardware.  The cavity floor is the flat, level top of the podium (Z 52).  A shallow circular seat,
    # centred in the cavity, takes a heat-resistant insert (glass / metal holder) so a tea light never sits on the plastic.
    # SEAT_D / SEAT_DEPTH are fixed physical sizes (final mm) converted to model units in configure().
    seat = cyl(x, y, z, 0, 0, SEAT_D / 2.0, 52.0 - SEAT_DEPTH, 53.0)
    return sub(union(tray, podium, steps, body, front, piers, *cols), seat)

# ------------------------------------------------------------------ PART 2  hollow shaft
def part2(x, y, z):
    zc = np.maximum(z, Z_BAND_TOP)                 # the 12 mm foot (Z 238..250) keeps the Z=250 section
    h = h_shaft(zc); r = r_shaft(zc)
    low = _ext(rrect2d(x, y, h, h, r), z, Z_BAND_TOP - 12, Z_LEDGE)
    core = rrect(x, y, z, H_CORE, H_CORE, R_CORE, Z_LEDGE - 1, Z_SHAFT_TOP)
    lobes = [cyl(x, y, z, sx * LOBE_C, sy * LOBE_C, LOBE_R, Z_LEDGE - 1, Z_SHAFT_TOP)
             for sx in (-1, 1) for sy in (-1, 1)]
    hl = float(h_shaft(614.0))                     # corbel ledges: lintel bar + 2 corbel blocks per face
    cb = []
    for s in (-1, 1):
        a, b = (120, hl + 8) if s > 0 else (-(hl + 8), -120)
        cb.append(box(x, y, z, a, b, -68, 68, 606, 624)); cb.append(box(x, y, z, -68, 68, a, b, 606, 624))
        for yc in (-55, 55):
            a, b = (120, hl + 17) if s > 0 else (-(hl + 17), -120)
            cb.append(box(x, y, z, a, b, yc - 13, yc + 13, 602, 626))
            cb.append(box(x, y, z, yc - 13, yc + 13, a, b, 602, 626))
    body = union(low, core, *lobes, *cb)
    # bore narrows over a 45 deg internal chamfer just below the ledge so the 6 mm wall stays one solid
    tt = np.clip((z - (Z_LEDGE - 9.0)) / 9.0, 0.0, 1.0)
    hb = (h - WALL) * (1 - tt) + H_BORE_UP * tt
    rb = (r - WALL) * (1 - tt) + R_BORE_UP * tt
    body = sub(body, _ext(rrect2d(x, y, hb, hb, rb), z, Z_BAND_TOP - 13, Z_SHAFT_TOP + 1))   # open both ends
    # slits (15 wide): MODE SWITCH - open = cut through the 6 mm wall, closed = 1.5 mm recess.
    # Lower single slit only on the two side faces and the rear (not the portico face).
    sd = depth_of(WALL + 3.0)
    cuts = []
    for sg in (-1, 1):
        for xc in (-16.0, 16.0):                   # pair under the ledge, all faces
            f = float(h_shaft(561.0))
            cuts += [recess_x(x, y, z, f, xc, 15, 542, 580, sg, sd), recess_y(x, y, z, f, xc, 15, 542, 580, sg, sd)]
        cuts += [recess_x(x, y, z, H_CORE, 0, 15, 675, 715, sg, sd), recess_y(x, y, z, H_CORE, 0, 15, 675, 715, sg, sd)]
    f = float(h_shaft(320.0))
    cuts += [recess_x(x, y, z, f, 0, 15, 300, 340, +1, sd), recess_x(x, y, z, f, 0, 15, 300, 340, -1, sd),
             recess_y(x, y, z, f, 0, 15, 300, 340, -1, sd)]
    return sub(body, *cuts)

# ------------------------------------------------------------------ PART 3  lantern + crown lid
R_DRUM, R_BORE3 = 120.5, 108.0
def part3(x, y, z):
    rho = np.sqrt(x * x + y * y)
    spigot = rrect(x, y, z, H_BORE_UP - CLR, H_BORE_UP - CLR, R_BORE_UP, Z_SHAFT_TOP - 12, Z_SHAFT_TOP + 0.5)
    plate = union(rrect(x, y, z, H_CORE, H_CORE, R_CORE, Z_SHAFT_TOP, 770),
                  *[cyl(x, y, z, sx * LOBE_C, sy * LOBE_C, LOBE_R, Z_SHAFT_TOP, 770) for sx in (-1, 1) for sy in (-1, 1)])
    drum = cyl(x, y, z, 0, 0, R_DRUM, 769, 830)
    q1 = rho - (125.5 - 10); q2 = np.abs(z - 857) - (28 - 10)                 # bulging ring-dome Z 829..885
    dome = (np.sqrt(np.maximum(q1, 0) ** 2 + np.maximum(q2, 0) ** 2) + np.minimum(np.maximum(q1, q2), 0) - 10).astype(f32)
    lantern = union(spigot, plate, drum, dome)
    lantern = sub(lantern, cyl(x, y, z, 0, 0, R_BORE3, Z_SHAFT_TOP - 13, 841))   # hollow cup, open underneath
    # 16 lantern openings: MODE SWITCH - open = through the drum wall into the lid cavity, closed = 1.5 mm recess
    uh = 13.5 if OPEN_MODE else REC * 4.0          # half extent along the radius (outer face is at r = 120.5)
    uc = 131.0 - uh
    for k in range(16):
        a = np.radians(22.5 * k)
        u = x * np.cos(a) + y * np.sin(a); v = -x * np.sin(a) + y * np.cos(a)
        lantern = sub(lantern, _ext(rrect2d(u - uc, v, uh, 11.0, 0), z, 783, 820))
    cap = union(cyl(x, y, z, 0, 0, 112, 884, 897), cyl(x, y, z, 0, 0, 104, 896, 907),
                cyl(x, y, z, 0, 0, 55.5, 906, 950), cyl(x, y, z, 0, 0, 50, 949, 978))
    Rs = (46.5 ** 2 + 22.0 ** 2) / (2 * 22.0)
    top = np.maximum(np.sqrt(x * x + y * y + (z - (1000 - Rs)) ** 2) - Rs, 977 - z).astype(f32)  # shallow dome, apex 1000
    return union(lantern, cap, top)

# ------------------------------------------------------------------ meshing / IO
def axis_nodes(lo, hi, step, fine=None):
    """Grid nodes along one axis; 'fine' = (lo, hi, step) adds a finer band (used around the lettering)."""
    if fine is None:
        return np.arange(lo, hi + 1e-6, step)
    fl, fh, fs = fine
    return np.concatenate([np.arange(lo, fl, step), np.arange(fl, fh, fs), np.arange(fh, hi + 1e-6, step)])

def build(fn, ax, ay, az, name):
    """Sample the SDF on a (possibly non-uniform) grid, polygonise with marching cubes, map back to millimetres."""
    t0 = time.time()
    xs = (ax + 0.0371).astype(f32); ys = (ay + 0.0529).astype(f32); zs = (az + 0.0613).astype(f32)   # nodes never sit on a feature plane
    nx, ny, nz = len(xs), len(ys), len(zs)
    print(f"  {name}: sampling {nx}x{ny}x{nz} = {nx * ny * nz / 1e6:.0f} M grid points ...", flush=True)
    try:
        vol = np.empty((nx, ny, nz), f32)
    except MemoryError:
        sys.exit(f"ERROR: not enough memory for {name} ({nx * ny * nz * 4 / 1e9:.1f} GB needed). Close other programs and retry.")
    X = xs[:, None, None]; Y = ys[None, :, None]
    nchunk = (nz + 23) // 24
    for ci, i in enumerate(range(0, nz, 24)):
        vol[:, :, i:i + 24] = fn(X, Y, zs[None, None, i:i + 24])
        if nchunk >= 4 and ci % max(1, nchunk // 4) == 0:
            print(f"    field evaluation {100 * (ci + 1) // nchunk}%", flush=True)
    for face in (vol[0], vol[-1], vol[:, 0], vol[:, -1], vol[:, :, 0], vol[:, :, -1]):
        if face.min() <= 0:
            sys.exit(f"INTERNAL ERROR: grid padding too small for {name} (the model touches the grid edge).")
    print(f"  {name}: polygonising (marching cubes) ...", flush=True)
    v, f, _, _ = marching_cubes(vol, 0.0, spacing=(1.0, 1.0, 1.0), allow_degenerate=False)
    del vol
    v = np.stack([np.interp(v[:, 0], np.arange(nx), xs),               # index space -> millimetres (axes may be non-uniform)
                  np.interp(v[:, 1], np.arange(ny), ys),
                  np.interp(v[:, 2], np.arange(nz), zs)], axis=1)
    f = f[:, ::-1]
    if signed_volume(v, f) < 0: f = f[:, ::-1]
    print(f"  {name}: {len(f):,} triangles ({time.time() - t0:.0f} s)", flush=True)
    return v, f

def signed_volume(v, f):
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0

def check(v, f, name):
    """Mesh validation: every directed edge appears once and has an opposite twin (closed, consistently oriented),
    and the mesh is a single connected shell."""
    n = len(v) + 1
    d = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]).astype(np.int64)
    key = d[:, 0] * n + d[:, 1]; rkey = d[:, 1] * n + d[:, 0]
    manifold = len(np.unique(key)) == len(key) and np.array_equal(np.sort(key), np.sort(rkey))
    g = coo_matrix((np.ones(len(d)), (d[:, 0], d[:, 1])), shape=(len(v), len(v)))
    shells = connected_components(g, directed=False)[0]
    ok = manifold and shells == 1
    print(f"  {name}: manifold/watertight = {manifold}, separate shells = {shells} (must be 1), "
          f"volume {signed_volume(v, f) / 1000:.1f} cm3", flush=True)
    print(f"  {name}: bounding box {np.round(v.min(0), 1).tolist()} .. {np.round(v.max(0), 1).tolist()} mm", flush=True)
    return ok

def write_stl(path, v, f, label):
    tri = v[f].astype(np.float32)
    nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
    rec = np.zeros(len(f), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"] = nrm; rec["v"] = tri
    with open(path, "wb") as fh:
        fh.write(label.encode()[:80].ljust(80, b" ")); fh.write(struct.pack("<I", len(f))); fh.write(rec.tobytes())
    # verify the file really is a valid binary STL (size must equal 84 + 50 x triangles)
    if os.path.getsize(path) != 84 + 50 * len(f):
        sys.exit(f"ERROR: {path} was not written completely (disk full?).")

# part 1 uses finer grid bands around the lettering (X, Z) and relief (Y); everything else stays coarse
PARTS = {
    "1": (part1, (-204, 204, 1.2, (-90, 90, 0.6)), (-204, 282, 1.2, (212, 232, 0.4)), (-2, 300, 1.0, (205, 250, 0.6)), "01_base_and_hopper"),
    "2": (part2, (-156, 156, 1.0, None), (-156, 156, 1.0, None), (234, 762, 1.0, None), "02_hollow_tower_shaft"),
    "3": (part3, (-134, 134, 0.8, None), (-134, 134, 0.8, None), (746, 1002, 0.8, None), "03_lift_off_crown_lid"),
}
ASM_NAME = "00_full_bismarckturm_assembly"
FULL_HEIGHT = 1000.0

def nodot(x):
    """number -> text without a dot: whole numbers as-is, otherwise one decimal with 'p' (255.5 -> 255p5)"""
    r = round(x, 1)
    if abs(r - round(r)) < 1e-9:
        return str(int(round(r)))
    return f"{r:.1f}".replace(".", "p")

def name_suffix(sc, clearance_mm, open_mode, model):
    """FILENAME SUFFIX: _<birdfeeder|tealight> + _scale<height mm>mm [+ _clr<micrometres>mu] + _open|_closed
    (applied to every file, exactly once, immediately before .stl)"""
    suf = f"_{model}_scale{nodot(FULL_HEIGHT * sc)}mm"
    if clearance_mm is not None:
        suf += f"_clr{nodot(clearance_mm * 1000.0)}mu"
    return suf + ("_open" if open_mode else "_closed")

def make_assembly(out_dir, suffix):
    """Concatenate the three part STLs into one assembly STL (they are modelled in their final positions)."""
    paths = [os.path.join(out_dir, PARTS[k][4] + suffix + ".stl") for k in "123"]
    counts = []
    for p in paths:
        if not os.path.isfile(p):
            sys.exit(f"ERROR: {os.path.basename(p)} not found in {out_dir} - build parts 1 2 3 first "
                     f"(with the same --birdfeeder/--tealight, --scale, --clearance and --open/--closed).")
        with open(p, "rb") as fh:
            fh.seek(80); n = struct.unpack("<I", fh.read(4))[0]
        if os.path.getsize(p) != 84 + 50 * n:
            sys.exit(f"ERROR: {os.path.basename(p)} is not a complete binary STL - rebuild that part.")
        counts.append(n)
    asm = ASM_NAME + suffix + ".stl"
    print(f"  assembling {asm} from 3 parts ...", flush=True)
    with open(os.path.join(out_dir, asm), "wb") as out:
        out.write(asm.encode().ljust(80, b" ")); out.write(struct.pack("<I", sum(counts)))
        for p, n in zip(paths, counts):
            with open(p, "rb") as src:
                src.seek(84); left = n * 50
                while left:
                    b = src.read(min(left, 5_000_000)); out.write(b); left -= len(b)
    print(f"  {asm}: {sum(counts):,} triangles", flush=True)

def configure(sc, clearance_mm, open_mode, model):
    """Set the run-time globals and derive the scale-dependent sizes (door/outlet, tea-light seat, lettering)."""
    global CLR, SCALE, OPEN_MODE, MODEL, OUTLET_W, OUTLET_H, RELIEF, HW, SEAT_D, SEAT_DEPTH
    SCALE, OPEN_MODE, MODEL = sc, open_mode, model
    if clearance_mm is not None:
        CLR = clearance_mm / sc                    # joint clearance is built in full-size units, then scaled with everything
    if model == "birdfeeder":
        # BIRDFEEDER door/outlet: 80 % of the available front width (the hopper's internal width), existing proportional height
        # (never shorter than the practical minimum in FINAL mm, and limited so a solid wall stays above the door).
        OUTLET_W = DOOR_WIDTH_FRACTION * 2 * CAV_HALF
        OUTLET_H = min(max(DOOR_H, MIN_OUTLET_H_MM / sc), MAX_OUTLET_H)
        if OUTLET_H * sc < MIN_OUTLET_H_MM - 1e-6:
            print(f"WARNING: at scale {sc:g} the door/outlet is only {OUTLET_H * sc:.1f} mm tall (wall limit) - "
                  f"seed may flow poorly; use a larger scale.", flush=True)
    else:
        # TEALIGHT door: exactly the photo-measured door proportions (not enlarged, no seed-flow minimum)
        OUTLET_W, OUTLET_H = DOOR_W, DOOR_H
        # tea-light seat: fixed physical size, shrunk only if the cavity is too small at this scale
        SEAT_DEPTH = SEAT_DEPTH_MM / sc
        avail = 2 * CAV_HALF * sc - 2 * SEAT_EDGE_MARGIN_MM          # final mm available for the seat
        seat_mm = min(SEAT_PREF_D_MM, avail)
        if seat_mm < SEAT_MIN_D_MM:
            min_sc = (SEAT_MIN_D_MM + 2 * SEAT_EDGE_MARGIN_MM) / (2 * CAV_HALF)
            sys.exit(f"ERROR: scale {sc:g} is too small for a standard 38 mm tea light (the base cavity is only "
                     f"{2 * CAV_HALF * sc:.0f} mm wide). Use --scale {min_sc:.2f} or larger. No files were generated.")
        SEAT_D = seat_mm / sc
        if seat_mm < SEAT_PREF_D_MM - 1e-6:
            print(f"NOTE: at scale {sc:g} the tea-light seat is {seat_mm:.1f} mm wide (preferred {SEAT_PREF_D_MM:.0f} mm): "
                  f"it takes a bare tea-light cup or a thin insert. Prefer an LED tea light at this size.", flush=True)
    # lettering: 2 mm relief is a FIXED physical height; stroke is thickened (up to a limit) at small scales
    RELIEF = RELIEF_MM / sc
    HW = min(max(1.3, 0.6 / sc), 1.9)
    stroke_mm = 2 * HW * sc
    if stroke_mm < 1.2 - 1e-6:
        print(f"WARNING: at scale {sc:g} the BISMARCK letter strokes are only {stroke_mm:.2f} mm wide "
              f"(letters {LETTER_H * sc:.1f} mm tall). They are below the ~1.2 mm a 0.4 mm nozzle prints reliably; "
              f"use scale >= {0.6 / 1.9:.2f} for dependable lettering.", flush=True)

def main():
    global CLR
    ap = argparse.ArgumentParser(description="Bismarckturm model (BIRDFEEDER or TEALIGHT base), uniformly scalable "
                                             "(1.0 = 1000 mm tall), open or closed openings.")
    ap.add_argument("--scale", type=float, required=True,
                    help="uniform scale factor: 1.0 = 1000 mm tall, 0.7 = 700 mm, 0.5 = 500 mm, 0.25 = 250 mm")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "scaled_output"),
                    help="output folder (default: scaled_output next to this script)")
    ap.add_argument("--parts", nargs="+", default=["1", "2", "3", "asm"], choices=["1", "2", "3", "asm"],
                    help="which parts to build (default: 1 2 3 asm)")
    ap.add_argument("--clearance", type=float, default=None,
                    help="OPTIONAL: slip-fit clearance of the two joints in FINAL millimetres. "
                         "Default keeps it proportional (0.35 mm x scale).")
    ap.add_argument("--birdfeeder", "-birdfeeder", dest="birdfeeder_", action="store_true",
                    help="outdoor birdfeeder base: single 35 degree rear seed slope + wide front door (DEFAULT)")
    ap.add_argument("--tealight", "-tealight", dest="tealight_", action="store_true",
                    help="indoor tea-light base: clean cavity, centred tea-light seat, real-proportion door")
    ap.add_argument("--open", "-open", dest="open_", action="store_true",
                    help="windows, slits, lantern openings and the door are real openings (DEFAULT)")
    ap.add_argument("--closed", "-closed", dest="closed_", action="store_true",
                    help="windows, slits and lantern openings are 1.5 mm recesses only; the door/outlet stays open")
    args = ap.parse_args()

    # ---- argument validation (nothing is generated if anything is wrong)
    if args.birdfeeder_ and args.tealight_:
        sys.exit("ERROR: --birdfeeder and --tealight cannot be used together.\n"
                 "       --birdfeeder = outdoor seed feeder base (default).\n"
                 "       --tealight   = indoor tea-light base.\n"
                 "       Choose one (or neither for --birdfeeder). No files were generated.")
    model = "tealight" if args.tealight_ else "birdfeeder"
    if args.open_ and args.closed_:
        sys.exit("ERROR: --open and --closed cannot be used together.\n"
                 "       --open  = windows, slits and openings are cut through (default).\n"
                 "       --closed = they are recessed only. Choose one (or neither for --open). No files were generated.")
    open_mode = not args.closed_
    sc = args.scale
    if not (sc > 0 and np.isfinite(sc)):
        ap.error("--scale must be a number greater than 0")
    if sc < 0.05 or sc > 3:
        print(f"WARNING: scale {sc:g} gives a {FULL_HEIGHT * sc:.0f} mm tall model - unusual, continuing.", flush=True)
    if args.clearance is not None and not (args.clearance > 0 and np.isfinite(args.clearance)):
        ap.error("--clearance must be a number greater than 0")
    out_dir = os.path.abspath(args.out)
    try:
        os.makedirs(out_dir, exist_ok=True)
        free = shutil.disk_usage(out_dir).free
    except OSError as e:
        sys.exit(f"ERROR: cannot use output folder {out_dir}: {e}")
    need = 700e6 * len([p for p in args.parts if p != "asm"]) / 3 + (270e6 if "asm" in args.parts else 0)
    if free < need:
        sys.exit(f"ERROR: only {free / 1e6:.0f} MB free in {out_dir}; about {need / 1e6:.0f} MB needed.")

    configure(sc, args.clearance, open_mode, model)
    suffix = name_suffix(sc, args.clearance, open_mode, model)
    print("=" * 72, flush=True)
    print(f"Bismarckturm {model.upper()}  scale {sc:g}  ->  model height {FULL_HEIGHT * sc:.1f} mm", flush=True)
    print(f"  mode               : {'OPEN (windows, slits, lantern openings and door are real openings)' if open_mode else 'CLOSED (windows, slits, lantern openings are recesses; door open)'}", flush=True)
    print(f"  joint clearance    : {CLR * sc:.3f} mm ({'proportional' if args.clearance is None else 'fixed by --clearance'})", flush=True)
    if model == "birdfeeder":
        print(f"  base               : BIRDFEEDER - single 35 deg rear slope; door/outlet {OUTLET_W * sc:.1f} x {OUTLET_H * sc:.1f} mm (80 % of front width)", flush=True)
    else:
        print(f"  base               : TEALIGHT - flat cavity, door {OUTLET_W * sc:.1f} x {OUTLET_H * sc:.1f} mm (real proportions), "
              f"tea-light seat {SEAT_D * sc:.1f} mm wide x {SEAT_DEPTH_MM:.0f} mm deep (fixed size)", flush=True)
    print(f"  BISMARCK lettering : relief {RELIEF_MM:.1f} mm (fixed, not scaled), stroke {2 * HW * sc:.2f} mm, letters {LETTER_H * sc:.1f} mm tall", flush=True)
    print(f"  output folder      : {out_dir}", flush=True)
    print("=" * 72, flush=True)

    done = 0
    for k in [a for a in args.parts if a in PARTS]:
        fn, (xl, xh, xs_, xf), (yl, yh, ys_, yf), (zl, zh, zs_, zf), name = PARTS[k]
        print(f"[{name}]", flush=True)
        try:
            v, f = build(fn, axis_nodes(xl, xh, xs_, xf), axis_nodes(yl, yh, ys_, yf), axis_nodes(zl, zh, zs_, zf), name)
        except MemoryError:
            sys.exit(f"ERROR: out of memory while building {name}. Close other programs and retry.")
        v = v * sc                                     # uniform scale of the finished part about the origin
        if not check(v, f, name):
            sys.exit(f"ERROR: {name} failed the manifold / single-shell check - not writing it.")
        path = os.path.join(out_dir, name + suffix + ".stl")
        if os.path.exists(path): print(f"  (overwriting existing {os.path.basename(path)})", flush=True)
        write_stl(path, v, f, name + suffix)
        print(f"  wrote {os.path.basename(path)} ({os.path.getsize(path) / 1e6:.0f} MB)", flush=True)
        done += 1
    if "asm" in args.parts:
        print("[assembly]", flush=True)
        make_assembly(out_dir, suffix)
    print("All done.", flush=True)

if __name__ == "__main__":
    main()
