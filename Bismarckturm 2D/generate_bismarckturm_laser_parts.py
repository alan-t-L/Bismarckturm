#!/usr/bin/env python3
"""
generate_bismarckturm_laser_parts.py  -  flat-pack, interlocking LASER-CUT version of the Bismarckturm model.

Uses the existing 3D-printing STL files (base+hopper, hollow tower shaft, crown lid) as GEOMETRIC REFERENCE and writes
editable 2D SVG and/or DXF files: individual parts, an all-parts overview, nested sheets, an assembly guide (Markdown) and a
cut list (CSV).  It never modifies the STL files or the 3D-printing scripts.

Method (short):
  1. The STL files are validated (closed, watertight, sensible size) and their scale is measured.
  2. Plane sections of the meshes (done here with numpy) give the measured outlines: plinth size, door, windows, slits,
     columns, pediment, inscription panel, tower taper, hopper slope angle, tea-light seat, ...
  3. Flat panels are built from those measurements (FACETED: tab-and-slot panels; STACKED: horizontal layers from sections).
  4. Tabs/slots use a documented kerf/clearance model (see KERF MODEL below); parts are nested onto sheets and validated.

KERF MODEL (all lengths in mm).  K = kerf (total width of material the laser removes), C = finished clearance
(slip: C = JointClearance, snug: C = JointClearance/2, press: C = -0.05), W = tab width, T = material thickness.
  * Nominal ("finished") geometry is built first:   tab width = W,   slot = (W + C) x (T + C).
  * Every cut path is then offset by K/2 with a robust polygon offset (shapely buffer, mitre joins): outer outlines grow by
    K/2, internal openings shrink by K/2.  Drawn tab width = W + K  (finishes at W after the laser removes K/2 per side);
    drawn slot width = W + C - K  (finishes at W + C).  So the FINISHED clearance equals C.
  Engraving, score, construction and label paths are NOT offset.

NOT scaled by --scale: material thickness, kerf, clearance and tab width (they are physical).  Everything measured from the
STL (outlines, openings, positions) IS scaled by --scale.
Requires: numpy, trimesh, shapely, ezdxf, svgwrite  (matplotlib only for --preview).  See requirements-laser-parts.txt.
Python backend of generate_bismarckturm_laser_parts.ps1 (same options).
"""
from __future__ import annotations
import argparse, csv, math, os, re, shutil, sys, time
from dataclasses import dataclass, field
from pathlib import Path

_MISSING = []
try:
    import numpy as np
except ImportError:
    _MISSING.append("numpy")
for _m in ("trimesh", "shapely", "ezdxf", "svgwrite"):
    try:
        __import__(_m)
    except ImportError:
        _MISSING.append(_m)
if _MISSING:
    sys.exit("ERROR: required Python module(s) missing: " + ", ".join(_MISSING) + "\n"
             "       Install them with:  python -m pip install -r requirements-laser-parts.txt\n"
             f"       (interpreter in use: {sys.executable})")
import trimesh
from shapely.geometry import Polygon, Point
from shapely import affinity
import ezdxf
from ezdxf import units as dxf_units
import svgwrite

LAYERS = {   # name: (SVG colour, DXF colour index, DXF linetype)
    "CUT": ("#ff0000", 1, "CONTINUOUS"),
    "ENGRAVE": ("#0000ff", 5, "CONTINUOUS"),
    "SCORE": ("#00a000", 3, "DASHED"),
    "CONSTRUCTION": ("#9a9a9a", 8, "CONTINUOUS"),
    "LABEL": ("#000000", 7, "CONTINUOUS"),
}
LABEL_H = 3.0

class LaserError(Exception):
    """A validation or input error: reported to the user, no files are written."""

WARNINGS: list[str] = []
def warn(msg):
    WARNINGS.append(msg)
    print("WARNING: " + msg, flush=True)
def info(msg):
    print(msg, flush=True)

@dataclass
class Cfg:
    model: str = "birdfeeder"
    T: float = 4.0            # material thickness
    K: float = 0.2            # kerf (total)
    J: float = 0.2            # requested joint clearance
    fit: str = "slip"
    tab_w: float = 10.0
    tab_n: int = 3
    corner_r: float = 0.0
    scale: float = 1.0
    formats: tuple = ("svg", "dxf")
    outdir: str = "2D CAD output"
    method: str = "faceted"
    preview: bool = False
    sheet_w: float = 600.0
    sheet_h: float = 400.0
    margin: float = 10.0
    spacing: float = 3.0
    allow_narrow: bool = False
    allow_open_mesh: bool = False
    @property
    def C(self):              # finished clearance used for the slots
        return {"slip": self.J, "snug": self.J / 2.0, "press": -0.05}[self.fit]
    @property
    def min_edge(self):       # minimum distance slot <-> part edge / other slots / openings
        return 0.75 * self.T

# --------------------------------------------------------------------------------- small math helpers
def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)

def poly_area(pts):
    p = np.asarray(pts, float)
    return 0.5 * float(np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1]))

def ccw(pts):
    return list(pts) if poly_area(pts) > 0 else list(pts)[::-1]

def rect_pts(u0, v0, u1, v1):
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]

def oriented_rect(c, axis, length, width):
    e1 = unit(axis); e2 = np.array([-e1[1], e1[0]]); c = np.asarray(c, float)
    h1, h2 = length / 2.0, width / 2.0
    return [tuple(c - e1 * h1 - e2 * h2), tuple(c + e1 * h1 - e2 * h2), tuple(c + e1 * h1 + e2 * h2), tuple(c - e1 * h1 + e2 * h2)]

def circle_pts(c, r, n=36):
    return [(c[0] + r * math.cos(2 * math.pi * i / n), c[1] + r * math.sin(2 * math.pi * i / n)) for i in range(n)]

def round_polygon(pts, r, n=6):
    """round every (convex) corner of a simple CCW polygon with an arc of radius r (edges must be longer than 2r)"""
    p = [np.array(q, float) for q in pts]; out = []
    for i in range(len(p)):
        a, b, c = p[i - 1], p[i], p[(i + 1) % len(p)]
        d1, d2 = unit(b - a), unit(c - b)
        cross = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(cross) < 1e-9 or r <= 0:
            out.append(tuple(b)); continue
        ang = math.acos(max(-1.0, min(1.0, float(-d1 @ d2))))
        t = r / math.tan(ang / 2.0)
        if t > np.linalg.norm(b - a) / 2 or t > np.linalg.norm(c - b) / 2:
            out.append(tuple(b)); continue
        p1, p2 = b - d1 * t, b + d2 * t
        nrm = np.array([-d1[1], d1[0]]) * (1 if cross > 0 else -1)
        ctr = p1 + nrm * r
        a1 = math.atan2(*(p1 - ctr)[::-1]); a2 = math.atan2(*(p2 - ctr)[::-1])
        da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
        for k in range(n + 1):
            aa = a1 + da * k / n
            out.append((ctr[0] + r * math.cos(aa), ctr[1] + r * math.sin(aa)))
    return out

# --------------------------------------------------------------------------------- STL loading / validation
def load_mesh(path):
    p = Path(path)
    if not p.is_file():
        raise LaserError(f"STL file not found: {p}")
    try:
        m = trimesh.load(str(p), force="mesh")
    except Exception as e:
        raise LaserError(f"STL file cannot be read: {p}  ({e})")
    if not hasattr(m, "faces") or len(m.faces) == 0:
        raise LaserError(f"STL file contains no triangles: {p}")
    return m

def validate_stl(path, role, cfg):
    """Input-STL validation.  Returns (mesh, info dict).  Errors for unusable meshes, warnings for the rest."""
    m = load_mesh(path)
    name = Path(path).name
    ext = np.asarray(m.bounds[1] - m.bounds[0], float)
    inf = dict(path=str(path), name=name, role=role, faces=int(len(m.faces)), bmin=np.asarray(m.bounds[0], float),
               bmax=np.asarray(m.bounds[1], float), extents=ext)
    info(f"  {role}: {name}: {inf['faces']:,} triangles, bounding box {ext[0]:.1f} x {ext[1]:.1f} x {ext[2]:.1f} mm")
    wt = bool(m.is_watertight); wc = bool(m.is_winding_consistent)
    inf["watertight"] = wt
    if not (wt and wc):
        msg = (f"{name}: mesh is not a closed, consistently oriented solid (watertight={wt}, winding consistent={wc}). "
               f"Sections through it cannot be trusted.")
        if cfg.allow_open_mesh:
            warn(msg + " Continuing because --allow-non-watertight was given.")
        else:
            raise LaserError(msg + " Regenerate the STL with the existing 3D-printing script (it checks this), "
                                   "or repair it in a mesh tool. Use --allow-non-watertight to override at your own risk.")
    if float(m.volume) <= 0:
        raise LaserError(f"{name}: the mesh has zero or negative volume (inverted normals?).")
    if ext.min() <= 0 or ext.max() > 5000:
        raise LaserError(f"{name}: implausible bounding box {ext.tolist()} - the STL must be in millimetres.")
    return m, inf

# --------------------------------------------------------------------------------- plane sections (numpy)
class Sectioner:
    """Cuts a triangle mesh with arbitrary planes n.p = c and returns shapely polygons (with holes) in plane coordinates.
    Plane coordinates drop the dominant axis of n:  n~x -> (y, z),  n~y -> (x, z),  n~z -> (x, y)."""
    def __init__(self, mesh, u=1.0):
        self.V = np.asarray(mesh.vertices, float) * u          # the user --scale is applied here, once
        self.F = np.asarray(mesh.faces, np.int64)
        self.bmin, self.bmax = self.V.min(0), self.V.max(0)
        self.volume = float(mesh.volume) * u ** 3
    def _segments(self, n, c):
        V, F = self.V, self.F
        d = V @ n - c
        d = np.where(np.abs(d) < 1e-9, 1e-9, d)
        pos = d > 0
        cross = (pos[F[:, 0]] != pos[F[:, 1]]) | (pos[F[:, 1]] != pos[F[:, 2]])
        Fc = F[cross]
        if len(Fc) == 0:
            return np.zeros((0, 2, 3))
        def edge(a, b):
            lo, hi = np.minimum(a, b), np.maximum(a, b)      # canonical order -> identical points for shared edges
            with np.errstate(divide="ignore", invalid="ignore"):      # edges that do not cross give nan/inf: they are masked out below
                t = d[lo] / (d[lo] - d[hi])
                return V[lo] + t[:, None] * (V[hi] - V[lo]), pos[a] != pos[b]
        pa, ma = edge(Fc[:, 0], Fc[:, 1]); pb, mb = edge(Fc[:, 1], Fc[:, 2]); pc, mc = edge(Fc[:, 2], Fc[:, 0])
        P = np.stack([pa, pb, pc], 1); M = np.stack([ma, mb, mc], 1)
        idx = np.argsort(~M, axis=1, kind="stable")[:, :2]
        return np.take_along_axis(P, idx[:, :, None], axis=1)
    @staticmethod
    def _chain(S, tol=1e-4):
        keys = np.round(S / tol).astype(np.int64)
        adj, pts = {}, {}
        for k0, k1, p0, p1 in zip(map(tuple, keys[:, 0]), map(tuple, keys[:, 1]), S[:, 0], S[:, 1]):
            if k0 == k1:
                continue
            adj.setdefault(k0, []).append(k1); adj.setdefault(k1, []).append(k0)
            pts[k0] = p0; pts[k1] = p1
        used, loops = set(), []
        for start in list(adj):
            for nb in adj[start]:
                e = (start, nb) if start < nb else (nb, start)
                if e in used:
                    continue
                used.add(e); loop = [start]; cur, prev = nb, start
                while cur != start:
                    loop.append(cur); nxt = None
                    for x in adj[cur]:
                        e2 = (cur, x) if cur < x else (x, cur)
                        if e2 not in used:
                            nxt = x; break
                    if nxt is None:
                        break
                    used.add((cur, nxt) if cur < nxt else (nxt, cur)); prev, cur = cur, nxt
                if cur == start and len(loop) >= 3:
                    loops.append([pts[k] for k in loop])
        return loops
    def polys(self, n, c):
        n = unit(n); c = float(c) / 1.0
        dom = int(np.argmax(np.abs(n)))
        ax = [i for i in range(3) if i != dom]
        loops = [np.array(l)[:, ax] for l in self._chain(self._segments(n, c))]
        cand = sorted([(abs(poly_area(l)), l) for l in loops if abs(poly_area(l)) > 1e-6], key=lambda t: -t[0])
        shapes = [Polygon(l) for _, l in cand]
        parent = [-1] * len(cand); depth = [0] * len(cand)
        for i in range(len(cand)):
            pt = shapes[i].representative_point()
            for j in range(i):
                if shapes[j].contains(pt):
                    parent[i] = j
            depth[i] = 0 if parent[i] < 0 else depth[parent[i]] + 1
        res = []
        for i in range(len(cand)):
            if depth[i] % 2 == 0:
                holes = [cand[j][1] for j in range(len(cand)) if parent[j] == i and depth[j] % 2 == 1]
                res.append(Polygon(cand[i][1], holes))
        return res
    def at_x(self, x): return self.polys((1, 0, 0), x)
    def at_y(self, y): return self.polys((0, 1, 0), y)
    def at_z(self, z): return self.polys((0, 0, 1), z)

def holes_of(polys):
    """bounding boxes (a0, a1, b0, b1) = (min1, max1, min2, max2) of every interior ring of the given polygons"""
    out = []
    for p in polys:
        for r in p.interiors:
            bb = Polygon(r).bounds; out.append((bb[0], bb[2], bb[1], bb[3]))      # (a0, a1, b0, b1)
    return out

def biggest(polys):
    return max(polys, key=lambda p: p.area) if polys else None

# --------------------------------------------------------------------------------- measuring the model from the STLs
# Design constants of the 3D model at scale 1.0 (used ONLY for plausibility checks and as warned fall-backs).
REF = dict(tray=400.0, plinth=307.0, band_top=250.0, plinth_top=182.0, sill=52.0, shaft_z0=238.0, shaft_z1=760.0,
           crown_z0=748.0, crown_z1=1000.0, front=219.5, slope_deg=35.0)

def scale_from_name(name):
    m = re.search(r"scale(\d+(?:p\d+)?)mm", name)
    return float(m.group(1).replace("p", ".")) / 1000.0 if m else None

def mode_from_name(name):
    n = name.lower()
    return "open" if "_open" in n else ("closed" if "_closed" in n else None)

def model_from_name(name):
    n = name.lower()
    return "birdfeeder" if "birdfeeder" in n else ("tealight" if "tealight" in n else None)

def holes_to_openings(polys, zlo, zhi, latlim, through_polys):
    """interior rings of a section -> openings (lat0, lat1, z0, z1, through)"""
    out = []
    thr = [(b[0] + b[1]) / 2 for b in [(h[0], h[1]) for h in holes_of(through_polys)]]
    thr_c = [((h[0] + h[1]) / 2, (h[2] + h[3]) / 2) for h in holes_of(through_polys)]
    for (a0, a1, b0, b1) in holes_of(polys):
        if b0 < zlo or b1 > zhi or abs(a0) > latlim or abs(a1) > latlim:
            continue
        cx, cz = (a0 + a1) / 2, (b0 + b1) / 2
        through = any(abs(cx - tx) < 3 and abs(cz - tz) < 3 for tx, tz in thr_c)
        out.append((a0, a1, b0, b1, through))
    return sorted(out)

def derive_base(S, s, cfg):
    """Measure the base+hopper STL (coordinates already multiplied by the user --scale; s = overall scale)."""
    d = {}
    b0, b1 = S.bmin, S.bmax
    d["plate"] = (float(b0[0]), float(b1[0]), float(b0[1]), float(b1[1]))
    zm = 70 * s                      # above the podium, below the windows (open-mode windows would split the wall ring)
    big = biggest(S.at_z(zm))
    x0, y0, x1, y1 = big.bounds
    half = (x1 - x0) / 2.0
    d["half"] = half
    if abs(abs(y0) - half) > 0.03 * half:
        warn(f"base STL: the plinth does not look square at Z = {zm:.1f} mm (x {x1 - x0:.1f}, rear y {y0:.1f})")
    # columns: separate islands in front of the plinth
    cols = []
    for p in S.at_z(zm):
        cx0, cy0, cx1, cy1 = p.bounds
        if p.centroid.y > half and (cx1 - cx0) < 45 * s and p.area < 3000 * s * s:
            cols.append(((cx0 + cx1) / 2, cx1 - cx0))
    cols.sort()
    if len(cols) != 4:
        # the two OUTER columns touch the end piers in the mesh and merge into the plinth island: use the design positions
        # for them (the inner pair is measured when it is found separately)
        if len(cols) == 2 and abs(cols[0][0] + cols[1][0]) < 2 * s:
            ci = abs(cols[1][0]); dia = (cols[0][1] + cols[1][1]) / 2
            info(f"  base STL: inner columns measured at x = +/-{ci:.1f} mm; the outer pair touches the end piers, design position used")
            cols = [(-116 * s, dia), cols[0], cols[1], (116 * s, dia)]
        else:
            warn(f"base STL: found {len(cols)} column(s) instead of 4 - using the design positions")
            cols = [(-116 * s, 28 * s), (-70 * s, 28 * s), (70 * s, 28 * s), (116 * s, 28 * s)]
    d["columns"] = cols
    # plinth top (Zt) and tower start (Zc)
    side = biggest(S.at_x(half - 0.75 * s))
    d["Zt"] = float(side.bounds[3])
    band = biggest(S.at_x(145.3 * s))
    d["Zc"] = float(band.bounds[3])
    # windows: sections 0.75*s inside the outer faces; 'through' if the hole persists 3*s inside (open mode)
    def windows(axis_sign, lat):
        res = {}
        for dep, key in ((0.75 * s, "shallow"), (3.0 * s, "deep")):
            if lat == "y":
                res[key] = S.at_x(axis_sign * (half - dep))
            else:
                res[key] = S.at_y(axis_sign * (half - dep))
        return holes_to_openings(res["shallow"], 0.6 * REF["sill"] * s, d["Zt"], half, res["deep"])
    d["win_left"] = windows(+1, "y")      # +X face (viewer's left when facing the front)
    d["win_right"] = windows(-1, "y")     # -X face
    d["win_rear"] = windows(-1, "x")      # -Y face
    # front wall: door (hole containing x ~ 0) and blind panels; section 0.75*s inside the front face
    fr = S.at_y(half - 0.75 * s)
    fholes = holes_of(fr)
    door = None
    for (a0, a1, c0, c1) in sorted(fholes, key=lambda h: abs((h[0] + h[1]) / 2)):
        if abs((a0 + a1) / 2) < 20 * s and c1 - c0 > 20 * s:
            door = (a0, a1, c0, c1); break
    if door is None:
        raise LaserError("base STL: could not find the door opening in the front wall section.")
    d["door"] = door
    d["z_sill"] = door[2]
    d["blind"] = [h for h in fholes if abs((h[0] + h[1]) / 2) > 20 * s and h != door and h[3] - h[2] > 20 * s]
    # portico: entablature + pediment silhouette, front face and inscription panel
    zr = 215 * s
    ent = biggest(S.at_z(zr))
    d["front_y"] = float(ent.bounds[3])
    face_polys = S.at_y(d["front_y"] - 0.75 * s)
    fac = max(face_polys, key=lambda p: p.bounds[3])           # the island that reaches the pediment apex
    upper = [(x, z) for x, z in fac.exterior.coords if z > d["Zt"] + 1]          # entablature + pediment vertices only
    d["Xf"] = max(abs(x) for x, z in upper); d["zA"] = max(z for x, z in upper)
    zE = max(z for x, z in fac.exterior.coords if abs(x) >= 0.95 * d["Xf"] and z > d["Zt"] + 1)
    d["zE"] = zE
    gh = min([abs(x) for x, z in fac.exterior.coords if abs(z - zE) < 0.6 * s and abs(x) < 0.95 * d["Xf"]] or [111 * s])
    d["gh"] = gh
    panel_poly = None; letters = []
    for ring in fac.interiors:               # the inscription panel is the big rectangular hole; the letters are islands in it
        pr = Polygon(ring); bb = pr.bounds
        if (bb[2] - bb[0]) > 60 * s and (bb[3] - bb[1]) > 15 * s:
            panel_poly = pr
    if panel_poly is not None:
        for q in face_polys:
            if q is not fac and panel_poly.contains(q.representative_point()):
                letters.append(q)
    d["panel"] = (panel_poly.bounds[0], panel_poly.bounds[2], panel_poly.bounds[1], panel_poly.bounds[3]) if panel_poly is not None else None   # (x0, x1, z0, z1)
    d["letters"] = letters
    # hopper slope (birdfeeder): fit the sloping top edge in the x = 0 section
    d["slope_deg"] = None
    cx = biggest(S.at_x(0.01))
    pts = np.array([p for p in cx.exterior.coords if -0.84 * half < p[0] < 0.7 * half and d["z_sill"] + 3 * s < p[1] < 0.93 * d["Zc"]])
    if len(pts) >= 8:
        m, b = np.polyfit(pts[:, 0], pts[:, 1], 1)
        if m < -0.3:
            d["slope_deg"] = math.degrees(math.atan(-m)); d["slope_b"] = b
    # tea-light seat: circular hole in the floor just below the sill
    d["seat_d"] = None
    zs_ = d["z_sill"] - 1.5
    if zs_ > 0:
        for a0, a1, c0, c1 in holes_of(S.at_z(zs_)):
            if abs((a0 + a1) / 2) < 5 * s and abs((c0 + c1) / 2) < 5 * s and abs((a1 - a0) - (c1 - c0)) < 1.5:
                d["seat_d"] = a1 - a0
    # open/closed: windows persist deep inside the wall only in open mode
    wins = d["win_left"] + d["win_right"] + d["win_rear"]
    d["open_mode"] = (sum(1 for w in wins if w[4]) > len(wins) / 2) if wins else None
    d["volume_cm3"] = S.volume / 1000.0
    return d

def derive_tower(S, s, cfg):
    d = {}
    b0, b1 = S.bmin, S.bmax
    d["z0"], d["z1"] = float(b0[2]), float(b1[2])
    zb, zt = 260 * s, 740 * s
    wb = biggest(S.at_z(zb)).bounds; wt = biggest(S.at_z(zt)).bounds
    hb, ht = (wb[2] - wb[0]) / 2.0, (wt[2] - wt[0]) / 2.0
    d["zb"], d["zt"], d["hb"], d["ht"] = zb, zt, hb, ht
    d["k"] = (hb - ht) / (zt - zb)                              # taper: half-width lost per mm of height
    outer = biggest(S.at_z(500 * s))
    inner = holes_of([outer])
    d["wall"] = ((outer.bounds[2] - outer.bounds[0]) / 2.0 - (inner[0][1] - inner[0][0]) / 2.0) if inner else None
    core = biggest(S.at_z(700 * s))
    d["core_half"] = max([p[0] for p in core.exterior.coords if abs(p[1]) < 5 * s] or [124 * s])
    # slits: planes parallel to each tapered face, 0.75*s inside (hole = slit or recess) and 3*s inside (through?)
    faces = {"+x": (0, +1), "-x": (0, -1), "+y": (1, +1), "-y": (1, -1)}
    slits = {}
    k = d["k"]
    for name, (ax, sg) in faces.items():
        found = []
        for zone in ("low", "high"):
            res = {}
            for dep, key in ((0.75 * s, "shallow"), (3.0 * s, "deep")):
                n = np.zeros(3); n[ax] = sg
                if zone == "low":
                    n[2] = k; c = hb + k * zb - dep
                else:
                    c = d["core_half"] - dep
                res[key] = S.polys(n, c)
            for (a0, a1, c0, c1, thr) in holes_to_openings(res["shallow"], zb, zt + 5 * s, 1e9, res["deep"]):
                if (a1 - a0) < 40 * s and (c1 - c0) < 80 * s and (a1 - a0) > 3 * s:
                    found.append((a0, a1, c0, c1, thr))
        slits[name] = sorted(set(found), key=lambda t: t[2])
    d["slits"] = slits
    top = biggest(S.at_z(d["z1"] - 2 * s)); hh = holes_of([top])       # clear inside of the real (stacked) tower at its top
    d["inner_top"] = (hh[0][1] - hh[0][0]) / 2.0 if hh else None
    return d

def derive_crown(S, s, cfg):
    b0, b1 = S.bmin, S.bmax
    d = {"z0": float(b0[2]), "z1": float(b1[2])}
    sp = biggest(S.at_z(d["z0"] + 5 * s))
    d["spigot_half"] = (sp.bounds[2] - sp.bounds[0]) / 2.0
    return d

def check_scales(infos, cfg):
    """Cross-check the scale implied by each STL against the other files, the file names and the design constants."""
    est = {}
    est["base"] = (infos["base"]["extents"][0]) / REF["tray"]
    if "tower" in infos:
        est["tower"] = infos["tower"]["extents"][2] / (REF["shaft_z1"] - REF["shaft_z0"])
    if "crown" in infos:
        est["crown"] = infos["crown"]["extents"][2] / (REF["crown_z1"] - REF["crown_z0"])
    vals = list(est.values()); s0 = vals[0]
    for k, v in est.items():
        info(f"  scale measured from {k} STL: {v:.4f}  (model height about {v * 1000:.0f} mm)")
        if abs(v - s0) > 0.03 * s0:
            raise LaserError(f"The STL files do not share one scale ({k}: {v:.3f} vs {s0:.3f}). "
                             f"Use base, tower and crown STLs generated with the same --scale.")
    for k, inf in infos.items():
        nm = scale_from_name(inf["name"])
        if nm is not None and abs(nm - est.get(k, s0)) > 0.03 * s0:
            warn(f"{inf['name']}: the file name says scale {nm:g} but the geometry measures {est.get(k, s0):.3f}")
    if not (0.05 <= s0 <= 3):
        raise LaserError(f"Implausible STL scale {s0:.3f}: the files must be Bismarckturm STLs in millimetres.")
    return s0

# --------------------------------------------------------------------------------- panels, frames, tabs, slots, joints
class Frame:
    """3D placement of a flat panel: local (u, v) -> origin + u*U + v*V.  N = U x V points OUT of the model (outside face)."""
    def __init__(self, origin, U, V):
        self.o = np.asarray(origin, float); self.U = unit(U); self.V = unit(V); self.N = np.cross(self.U, self.V)
    def to3d(self, u, v): return self.o + u * self.U + v * self.V
    def to2d(self, p):
        d = np.asarray(p, float) - self.o
        return float(d @ self.U), float(d @ self.V)

@dataclass
class Hole:
    pts: list
    layer: str = "cut"          # "cut" = through-cut, "engrave" = outline only
    role: str = "opening"       # opening | slot | alignment | seat | panel
    joint: str = ""
    name: str = ""

@dataclass
class Joint:
    name: str; a: str; b: str; edge: int; w: float; depth: float
    tab_polys: list = field(default_factory=list)     # tab rectangles in A's local coordinates (nominal)
    slots: list = field(default_factory=list)         # slot rectangles in B's local coordinates (nominal, finished)
    feet: list = field(default_factory=list)          # tab cross-sections projected into B's plane (for the clearance check)
    @property
    def n(self): return len(self.slots)

class Part:
    def __init__(self, key, label, frame, base=None, shapes=None, group=None, kind="panel", round_r=0.0):
        self.key, self.label, self.frame, self.group, self.kind = key, label, frame, group, kind
        self.base = ccw(base) if base is not None else None
        self.shapes = shapes                  # nominal shapely polygons (stacked layers) instead of base+tabs
        self.tab_specs, self.holes, self.engraves = [], [], []
        self.outline = None; self.round_r = round_r; self.notes = []
    def add_opening(self, rect, through, name=""):
        u0, u1, v0, v1 = rect                                  # callers give (u0, u1, v0, v1)
        self.holes.append(Hole(rect_pts(u0, v0, u1, v1), "cut" if through else "engrave", "opening", name=name))
    def finalize(self):
        """build the outline: the base polygon with every tab inserted on its edge"""
        pts = self.base; n = len(pts); out = []
        by_edge = {}
        for sp in self.tab_specs:
            by_edge.setdefault(sp["edge"], []).extend((t, sp["w"], sp["depth"]) for t in sp["t"])
        for i in range(n):
            p0 = np.array(pts[i], float); p1 = np.array(pts[(i + 1) % n], float)
            d = unit(p1 - p0); nn = np.array([d[1], -d[0]])
            out.append(tuple(p0))
            for t, w, dp in sorted(by_edge.get(i, [])):
                a = p0 + d * (t - w / 2); b = p0 + d * (t + w / 2)
                out += [tuple(a), tuple(a + nn * dp), tuple(b + nn * dp), tuple(b)]
        if self.round_r > 0 and not self.tab_specs:
            out = round_polygon(out, self.round_r)
        self.outline = out

class Registry:
    def __init__(self):
        self.parts = {}; self.joints = []; self.claims = {}; self.required = []
    def add(self, p):
        if p.key in self.parts: raise LaserError(f"internal: duplicate part {p.key}")
        self.parts[p.key] = p; return p

def tab_layout(a, b, n, w_want, cfg, what):
    """Centres (absolute positions) of up to n tabs inside the usable interval [a, b] of an edge.
    Tabs are shrunk to fit but never below the material thickness (unless --allow-narrow-tabs); n is reduced if needed."""
    usable = b - a
    w_min = cfg.T if not cfg.allow_narrow else max(1.0, 0.5 * cfg.T)
    gap = cfg.T
    while n >= 1:
        need = n * w_want + (n - 1) * gap
        ww = w_want if need <= usable else (usable - (n - 1) * gap) / n
        if ww >= w_min - 1e-9:
            ww = min(ww, w_want)
            if n == 1:
                cs = [(a + b) / 2.0]
            else:
                pitch = (usable - ww) / (n - 1); cs = [a + ww / 2 + i * pitch for i in range(n)]
            return cs, ww
        n -= 1
    raise LaserError(f"{what}: the usable edge length ({usable:.1f} mm) is too short for even one tab of at least "
                     f"{w_min:.1f} mm. Use a larger --scale or thinner material (or --allow-narrow-tabs).")

def connect(reg, cfg, A, edge, centers, w, B, name):
    """Add tabs on edge `edge` of panel A at distances `centers` along the edge and the matching slots in panel B.
    The slot position is computed in 3D: where the tab's centre line crosses B's mid-plane.  The tab base must lie on B's
    inner face (T/2 from B's mid-plane) and the tab (length T) must end flush with B's outer face - otherwise the joint is
    reported as misaligned.  Nominal (finished) slot = (w + C) x (T + C); kerf compensation is applied later."""
    T, C = cfg.T, cfg.C
    claim = (A.key, edge)
    if claim in reg.claims:
        raise LaserError(f"assembly check: edge {edge} of '{A.key}' is claimed by two joints ('{reg.claims[claim]}' and '{name}').")
    reg.claims[claim] = name
    pts = A.base; p0 = np.array(pts[edge], float); p1 = np.array(pts[(edge + 1) % len(pts)], float)
    L = float(np.linalg.norm(p1 - p0)); d = (p1 - p0) / L; nn = np.array([d[1], -d[0]])
    A.tab_specs.append(dict(edge=edge, t=list(centers), w=w, depth=T, joint=name))
    j = Joint(name, A.key, B.key, edge, w, T)
    NB = B.frame.N
    for t in centers:
        if t - w / 2 < -1e-6 or t + w / 2 > L + 1e-6:
            raise LaserError(f"joint '{name}': a tab at {t:.1f} mm does not fit on the {L:.1f} mm edge of '{A.key}'.")
        c2 = p0 + d * t
        P = A.frame.to3d(*c2)
        n3 = A.frame.U * nn[0] + A.frame.V * nn[1]; d3 = A.frame.U * d[0] + A.frame.V * d[1]
        den = float(NB @ n3)
        if abs(den) < 0.98:
            raise LaserError(f"joint '{name}': '{A.key}' is not perpendicular to '{B.key}' (cos = {abs(den):.3f}).")
        lam = -float(NB @ (P - B.frame.o)) / den
        if abs(lam - T / 2) > 0.04 * T:
            raise LaserError(f"joint '{name}' is misaligned: the tab base of '{A.key}' is {lam:.3f} mm from the mid-plane of "
                             f"'{B.key}' along the tab direction (expected T/2 = {T / 2:.3f} mm).")
        c3 = P + lam * n3                                    # tab centre line crosses B's mid-plane here
        cu, cv = B.frame.to2d(c3)
        e1 = d3 - NB * (NB @ d3); e1 /= np.linalg.norm(e1)
        e2 = A.frame.N - NB * (NB @ A.frame.N); e2 /= np.linalg.norm(e2)
        e1l = np.array([e1 @ B.frame.U, e1 @ B.frame.V]); e2l = np.array([e2 @ B.frame.U, e2 @ B.frame.V])
        slot = oriented_rect((cu, cv), e1l, w + C, T + C)
        B.holes.append(Hole(slot, "cut", "slot", joint=name))
        j.slots.append(slot)
        foot = oriented_rect((cu, cv), e1l, w, T)
        j.feet.append(foot)
        a_ = p0 + d * (t - w / 2); b_ = p0 + d * (t + w / 2)
        j.tab_polys.append([tuple(a_), tuple(b_), tuple(b_ + nn * T), tuple(a_ + nn * T)])
    reg.joints.append(j)
    reg.required.append((A.key, B.key))
    return j

def edge_centers(length, lo, hi, n, w_want, cfg, what):
    """tab centres (distance from the edge start) inside [lo, hi] along an edge of the given length"""
    cs, w = tab_layout(lo, hi, n, w_want, cfg, what)
    return cs, w

# --------------------------------------------------------------------------------- FACETED base + hopper
def build_base(B, tower_top_hb, cfg, reg):
    """Flat-pack base: floor, 4 walls, top frame, portal facade + 2 braces, and (birdfeeder) seed slope + 3 ribs."""
    T, C = cfg.T, cfg.C; model = cfg.model
    half, Zt, Zc, sill = B["half"], B["Zt"], B["Zc"], B["z_sill"]
    Xf, Yf, zE = B["Xf"], B["front_y"], B["zE"]
    wall_top = Zc - T                                        # walls reach the underside of the top frame
    if sill <= T + 1 or wall_top - T < 3 * T:
        raise LaserError(f"scale too small for {T:g} mm material: the base walls would be only {wall_top - T:.1f} mm high.")
    # ---- floor (tray plate)
    x0, x1, y0, y1 = B["plate"]
    floor = reg.add(Part("base_floor", "BASE FLOOR", Frame([0, 0, T / 2], [1, 0, 0], [0, 1, 0]), base=rect_pts(x0, y0, x1, y1),
                         round_r=cfg.corner_r))
    if model == "tealight":
        sd = B.get("seat_d") or 52.0
        floor.engraves.append(dict(pts=circle_pts((0, 0), sd / 2), closed=True, layer="ENGRAVE"))
        floor.engraves.append(dict(pts=circle_pts((0, 0), sd / 2 + 1.5), closed=True, layer="SCORE"))
        floor.notes.append(f"Engraved ring = tea-light seat ({sd:.0f} mm). Use a heat-resistant insert; never a bare flame on the sheet.")
    # ---- four walls (outside face = +N); local u runs to the viewer's right when looking at the outside face
    def wall(key, label, origin, U, u_half, joints_edges):
        p = Part(key, label, Frame(origin, U, [0, 0, 1]), base=rect_pts(-u_half, T, u_half, wall_top))
        return reg.add(p)
    front = wall("front_wall", "FRONT WALL", [0, half - T / 2, 0], [-1, 0, 0], half, None)
    rear = wall("rear_wall", "REAR WALL", [0, -half + T / 2, 0], [1, 0, 0], half, None)
    left = wall("left_side_wall", "LEFT SIDE WALL", [half - 1.5 * T, 0, 0], [0, 1, 0], half - T, None)
    right = wall("right_side_wall", "RIGHT SIDE WALL", [-(half - 1.5 * T), 0, 0], [0, -1, 0], half - T, None)
    # openings (positions measured from the STL; cut when the STL has real openings, otherwise engraved)
    d0, d1, dz0, dz1 = B["door"]
    front.add_opening((-d1, -d0, dz0, dz1), True, "door")
    for (a0, a1, z0_, z1_) in B["blind"]:
        front.add_opening((-a1, -a0, z0_, z1_), False, "blind panel")
    for (a0, a1, z0_, z1_, thr) in B["win_rear"]:
        rear.add_opening((a0, a1, z0_, z1_), thr, "window")
    for (a0, a1, z0_, z1_, thr) in B["win_left"]:
        left.add_opening((a0, a1, z0_, z1_), thr, "window")
    for (a0, a1, z0_, z1_, thr) in B["win_right"]:
        right.add_opening((-a1, -a0, z0_, z1_), thr, "window")
    # ---- joints wall -> floor (bottom tabs); walls stand on the floor with their tabs through floor slots
    for wp, uh in ((front, half), (rear, half), (left, half - T), (right, half - T)):
        cs, w = edge_centers(2 * uh, uh - (half - 3 * T), uh + (half - 3 * T), cfg.tab_n, cfg.tab_w, cfg, f"{wp.key} bottom edge")
        connect(reg, cfg, wp, 0, cs, w, floor, f"{wp.key}_to_floor")
    # ---- corners: side-wall tabs through slots in the front/rear walls
    hv = wall_top - T
    cs, w = edge_centers(hv, 1.5 * T, hv - 1.5 * T, cfg.tab_n, cfg.tab_w, cfg, "side wall vertical edge")
    connect(reg, cfg, left, 1, cs, w, front, "left_wall_to_front_wall")
    connect(reg, cfg, left, 3, cs, w, rear, "left_wall_to_rear_wall")
    connect(reg, cfg, right, 1, cs, w, rear, "right_wall_to_rear_wall")
    connect(reg, cfg, right, 3, cs, w, front, "right_wall_to_front_wall")
    # ---- top frame: sits on the wall tops (glued); the tower panels' tabs lock into it
    o = tower_top_hb - 3 * T - C
    if o < 3 * T:
        raise LaserError(f"scale too small for {T:g} mm material: the top-frame opening would be only {2 * o:.1f} mm wide.")
    frame = reg.add(Part("base_top_frame", "TOP FRAME", Frame([0, 0, Zc - T / 2], [1, 0, 0], [0, 1, 0]),
                         base=rect_pts(-half, -half, half, half), round_r=cfg.corner_r))
    frame.holes.append(Hole(rect_pts(-o, -o, o, o), "cut", "opening", name="tower opening"))
    # ---- portal facade (columns + entablature + pediment), standing on the floor, braced to the floor by two side braces
    cols = B["columns"]; dia = cols[0][1]
    leg_w = max(dia, T + 2 * cfg.min_edge + 0.5)
    if leg_w > dia + 1e-6:
        warn(f"column legs widened from {dia:.1f} to {leg_w:.1f} mm so that a {T:g} mm tab fits (scale/material combination)")
    zl = T
    pts = []; leg_edges = []
    xs = [c[0] for c in cols]
    for i, xc in enumerate(xs):
        xa, xb = xc - leg_w / 2, xc + leg_w / 2
        leg_edges.append(len(pts))
        pts += [(xa, zl), (xb, zl), (xb, Zt)]
        if i + 1 < len(xs):
            pts += [(xs[i + 1] - leg_w / 2, Zt)]
    pts += [(Xf, Zt), (Xf, zE), (B["gh"], zE), (0.0, B["zA"]), (-B["gh"], zE), (-Xf, zE), (-Xf, Zt), (xs[0] - leg_w / 2, Zt)]
    # the polygon above lists points left->right along the bottom, so it is already CCW
    fac = reg.add(Part("front_portal", "FRONT PORTAL", Frame([0, Yf - T / 2, 0], [-1, 0, 0], [0, 0, 1]), base=pts))
    legn = min(cfg.tab_w, leg_w - 2 * cfg.min_edge)
    for i, ei in enumerate(leg_edges):
        a, b = pts[ei], pts[ei + 1]
        L = abs(b[0] - a[0])
        cs, w = edge_centers(L, cfg.min_edge, L - cfg.min_edge, 1, legn, cfg, "column leg")
        connect(reg, cfg, fac, ei, cs, w, floor, f"portal_leg_{i + 1}_to_floor")
    # inscription panel + letters (engraved outlines, mirrored x -> u so the text reads correctly from outside)
    if B.get("panel"):
        px0, px1, pz0, pz1 = B["panel"]
        fac.engraves.append(dict(pts=rect_pts(-px1, pz0, -px0, pz1), closed=True, layer="ENGRAVE"))
        for q in B.get("letters", []):
            fac.engraves.append(dict(pts=[(-x, z) for x, z in q.exterior.coords[:-1]], closed=True, layer="ENGRAVE"))
            for r in q.interiors:
                fac.engraves.append(dict(pts=[(-x, z) for x, z in r.coords[:-1]], closed=True, layer="ENGRAVE"))
    fac.engraves.append(dict(pts=[(-Xf, Zt), (Xf, Zt)], closed=False, layer="SCORE"))
    # braces tie the facade to the floor (not to the front wall: keeps the slots of the walls clear)
    xp = Xf - 1.5 * T
    yb0, yb1 = half, Yf - T
    if yb1 - yb0 < 3 * T:
        raise LaserError(f"scale too small for {T:g} mm material: the portico is only {yb1 - yb0:.1f} mm deep.")
    for key, sg, lab in (("portal_brace_left", +1, "PORTAL BRACE LEFT"), ("portal_brace_right", -1, "PORTAL BRACE RIGHT")):
        # both braces extend towards +Y; the right brace uses U = -Y, so its local u range is mirrored
        u0, u1 = (yb0, yb1) if sg > 0 else (-yb1, -yb0)
        fe = 1 if sg > 0 else 3                                  # the edge facing the facade (+Y)
        br = reg.add(Part(key, lab, Frame([sg * xp, 0, 0], [0, sg, 0], [0, 0, 1]), base=rect_pts(u0, T, u1, zE)))
        cs, w = edge_centers(yb1 - yb0, cfg.T, yb1 - yb0 - cfg.T, 2, cfg.tab_w, cfg, f"{key} bottom edge")
        connect(reg, cfg, br, 0, cs, w, floor, f"{key}_to_floor")
        Lf = zE - T
        lo, hi = Zt, zE - 2 * T                                  # tabs at v in [Zt + T, zE - T]
        if hi - lo < cfg.T:
            raise LaserError(f"{key}: the entablature band is too low ({zE - Zt:.1f} mm) for a {T:g} mm tab.")
        cs, w = edge_centers(Lf, lo, hi, 2, cfg.tab_w, cfg, f"{key} front edge")
        if fe == 3:
            cs = [Lf - c for c in cs]                            # edge 3 runs top -> bottom
        connect(reg, cfg, br, fe, cs, w, fac, f"{key}_to_front_portal")
    return dict(floor=floor, front=front, rear=rear, left=left, right=right, frame=frame, facade=fac, wall_top=wall_top)

def build_hopper(B, cfg, reg, wall_top, floor, half):
    """BIRDFEEDER only: seed slope (flat plate at the measured slope angle) carried by three ribs standing on the floor."""
    T = cfg.T; sill = B["z_sill"]
    theta = B.get("slope_deg")
    if theta is None:
        theta = REF["slope_deg"]; warn("base STL: slope angle not measurable - using 35 degrees")
    y_low = half - T - 0.2
    y_rear = -(half - T) + 0.3
    tan = math.tan(math.radians(theta))
    zmax = wall_top - 0.5 * T
    if sill + tan * (y_low - y_rear) > zmax:
        tan = (zmax - sill) / (y_low - y_rear)
        warn(f"seed slope reduced from {theta:.1f} to {math.degrees(math.atan(tan)):.1f} degrees so that it fits under the top frame "
             f"at this scale/thickness")
    th = math.atan(tan); sn, cs_ = math.sin(th), math.cos(th)
    L = (y_low - y_rear) / cs_
    d = np.array([0, -cs_, sn]); n_up = np.array([0, sn, cs_])
    origin = np.array([0, y_low, sill]) - (T / 2) * n_up
    wp = half - 2 * T - 0.5
    plate = reg.add(Part("seed_slope", "SEED SLOPE", Frame(origin, [1, 0, 0], d), base=rect_pts(-wp, 0, wp, L)))
    plate.notes.append(f"Slope {math.degrees(th):.0f} deg. Low edge (u axis, v = 0) faces the door; ribs support it from below.")
    xr = wp / 2
    for i, x in enumerate((-xr, 0.0, xr), start=1):
        yf = y_low - 3 * T; yr = y_rear
        zu = lambda y: sill + tan * (y_low - y) - T / cs_
        pts = [(yr, T), (yf, T), (yf, zu(yf)), (yr, zu(yr))]
        if zu(yf) < T + 2 * T:
            raise LaserError("seed slope support ribs would be lower than 2 x material thickness - scale too small.")
        rib = reg.add(Part(f"seed_slope_rib_{i:02d}", f"SLOPE RIB {i}", Frame([x, 0, 0], [0, 1, 0], [0, 0, 1]), base=pts))
        c, w = edge_centers(yf - yr, T, yf - yr - T, 2, cfg.tab_w, cfg, f"{rib.key} bottom")
        connect(reg, cfg, rib, 0, c, w, floor, f"{rib.key}_to_floor")
        Le = math.hypot(yf - yr, zu(yr) - zu(yf))
        c, w = edge_centers(Le, T, Le - T, cfg.tab_n, cfg.tab_w, cfg, f"{rib.key} sloped edge")
        connect(reg, cfg, rib, 2, c, w, plate, f"{rib.key}_to_seed_slope")
    return plate

# --------------------------------------------------------------------------------- FACETED tower
def pick_ring_z(pref, avoid, lo, hi, margin):
    """move a ring height away from the slit bands (z0, z1) so ring slots never touch a slit"""
    for step in [0] + [s * k for k in range(1, 400) for s in (1, -1)]:
        z = pref + step * 0.5
        if z < lo or z > hi: continue
        if all(z + margin < a or z - margin > b for a, b in avoid): return z
    raise LaserError("no free height for a tower ring between the slits - use thinner material or a larger scale.")

def build_tower(Tw, Zc, cfg, reg, top_frame):
    """4 tapered wall panels (2 wide with slots, 2 narrow with tabs), tabs into the top frame, 3 internal rings."""
    T, C = cfg.T, cfg.C
    z0, z1 = Zc, Tw["z1"]
    hf = lambda z: Tw["hb"] - Tw["k"] * (z - Tw["zb"])
    hb, ht = hf(z0), hf(z1); dz = z1 - z0
    lean = (ht - hb)
    Lsl = math.hypot(lean, dz); Vy, Vz = lean / Lsl, dz / Lsl
    # wide panels (front +Y, rear -Y): full outer width
    wb_pts = [(-hb, 0), (hb, 0), (ht, Lsl), (-ht, Lsl)]
    yb = hb - T / 2
    wide_front = reg.add(Part("tower_panel_01", "TOWER FRONT", Frame([0, yb, z0], [-1, 0, 0], [0, Vy, Vz]), base=wb_pts))
    wide_rear = reg.add(Part("tower_panel_02", "TOWER REAR", Frame([0, -yb, z0], [1, 0, 0], [0, -Vy, Vz]), base=wb_pts))
    xb = hb - 1.5 * T
    nb_pts = [(-(hb - T), 0), (hb - T, 0), (ht - T, Lsl), (-(ht - T), Lsl)]
    narrow_left = reg.add(Part("tower_panel_03", "TOWER LEFT", Frame([xb, 0, z0], [0, 1, 0], [Vy, 0, Vz]), base=nb_pts))
    narrow_right = reg.add(Part("tower_panel_04", "TOWER RIGHT", Frame([-xb, 0, z0], [0, -1, 0], [-Vy, 0, Vz]), base=nb_pts))
    # slits -> openings in the panels (lateral coordinate -> local u; height -> position along the slope)
    face_map = {"+y": (wide_front, -1), "-y": (wide_rear, +1), "+x": (narrow_left, +1), "-x": (narrow_right, -1)}
    avoid = []
    for face, (panel, sgn) in face_map.items():
        for (a0, a1, c0, c1, thr) in Tw["slits"].get(face, []):
            if c0 < z0 + 1: continue
            u0, u1 = sorted((sgn * a0, sgn * a1))
            panel.add_opening((u0, u1, (c0 - z0) / Vz, (c1 - z0) / Vz), thr, "slit")
            avoid.append((c0, c1))
    # panel corners: narrow panel tabs through slots in the wide panels
    Le = Lsl
    cs, w = edge_centers(Le, 1.5 * T, Le - 1.5 * T, cfg.tab_n, cfg.tab_w, cfg, "tower vertical edge")
    connect(reg, cfg, narrow_left, 1, cs, w, wide_front, "tower_left_to_front")
    connect(reg, cfg, narrow_left, 3, cs, w, wide_rear, "tower_left_to_rear")
    connect(reg, cfg, narrow_right, 1, cs, w, wide_rear, "tower_right_to_rear")
    connect(reg, cfg, narrow_right, 3, cs, w, wide_front, "tower_right_to_front")
    # bottom tabs into the top frame
    for p, uh, key in ((wide_front, hb, "front"), (wide_rear, hb, "rear"), (narrow_left, hb - T, "left"), (narrow_right, hb - T, "right")):
        inset = 3.5 * T if key in ("front", "rear") else 3 * T
        cs, w = edge_centers(2 * uh, uh - (hb - inset), uh + (hb - inset), cfg.tab_n, cfg.tab_w, cfg, f"tower {key} bottom edge")
        connect(reg, cfg, p, 0, cs, w, top_frame, f"tower_{key}_to_top_frame")
    # internal rings (square frames) - keep clear of the slits
    rings = []
    for k in (1, 2, 3):
        zr = pick_ring_z(z0 + dz * k / 4.0, avoid, z0 + 2 * T, z1 - 2 * T, 1.5 * T + 1.0)
        hr = hf(zr); rx, ry = hr - 2 * T, hr - T
        rw = 2 * T
        ring = reg.add(Part(f"tower_ring_{k:02d}", f"TOWER RING {k}", Frame([0, 0, zr], [1, 0, 0], [0, 1, 0]), base=rect_pts(-rx, -ry, rx, ry)))
        ring.holes.append(Hole(rect_pts(-(rx - rw), -(ry - rw), rx - rw, ry - rw), "cut", "opening", name="seed/air passage"))
        for edge, tgt, ln in ((0, wide_rear, 2 * rx), (1, narrow_left, 2 * ry), (2, wide_front, 2 * rx), (3, narrow_right, 2 * ry)):
            cs, w = edge_centers(ln, 1.5 * T, ln - 1.5 * T, 2, cfg.tab_w, cfg, f"{ring.key} edge {edge}")
            connect(reg, cfg, ring, edge, cs, w, tgt, f"{ring.key}_edge{edge}_to_{tgt.key}")
        rings.append(ring)
    return dict(panels=[wide_front, wide_rear, narrow_left, narrow_right], rings=rings, hb=hb, ht=ht, z0=z0, z1=z1)

# --------------------------------------------------------------------------------- STACKED layers (tower / crown)
def make_layers(S, zlo, zhi, cfg, reg, prefix, label, group):
    T = cfg.T
    n = int(((zhi - zlo) + 0.05) / T)                     # 0.05 mm tolerance: 126.0 / 6 must give 21 layers, not 20
    if n < 1:
        raise LaserError(f"{label}: only {zhi - zlo:.1f} mm high - less than one {T:g} mm layer.")
    rem = (zhi - zlo) - n * T
    if rem > 0.5 * T:
        warn(f"{label}: the last {rem:.1f} mm of height does not fill a {T:g} mm layer and is omitted")
    layers = []
    for i in range(n):
        zm = zlo + (i + 0.5) * T
        polys = [p.simplify(0.05) for p in S.at_z(zm) if p.area > 1.0]
        if not polys:
            raise LaserError(f"{label}: empty section at Z = {zm:.1f} mm.")
        p = reg.add(Part(f"{prefix}_{i + 1:03d}", f"{label} {i + 1}", Frame([0, 0, zm], [1, 0, 0], [0, 1, 0]), shapes=polys, group=group, kind="layer"))
        layers.append(p)
    return layers

def add_pins(layers, cfg, what):
    """alignment pin holes (3 mm dowel) at the same two positions in every layer where possible"""
    pin_d = 3.0; r = pin_d / 2 + cfg.C / 2; margin = 3.0 + r
    def valid(shapes, x, y):
        pt = Point(x, y)
        for pl in shapes:
            if pl.contains(pt):
                if pl.exterior.distance(pt) < margin: return False
                return all(ring.distance(pt) >= margin for ring in pl.interiors)
        return False
    bs = [s.bounds for l in layers for s in l.shapes]
    x0 = min(b[0] for b in bs); x1 = max(b[2] for b in bs); y0 = min(b[1] for b in bs); y1 = max(b[3] for b in bs)
    good = [(x, y) for x in np.arange(x0, x1, 2.0) for y in np.arange(y0, y1, 2.0) if all(valid(l.shapes, x, y) for l in layers)]
    if len(good) >= 2:
        a = min(good, key=lambda c: c[0] + c[1]); b = max(good, key=lambda c: c[0] + c[1])
        if math.hypot(a[0] - b[0], a[1] - b[1]) > 4 * pin_d:
            for l in layers:
                for c in (a, b):
                    l.holes.append(Hole(circle_pts(c, r), "cut", "alignment"))
            return
    warn(f"{what}: the walls are too thin for 3 mm alignment pins at this scale/thickness - align the layers with a jig or glue")

# --------------------------------------------------------------------------------- kerf compensation, labels, validation
def ring_ok(coords, what):
    pts = list(coords)
    if len(pts) > 1 and tuple(pts[0]) == tuple(pts[-1]): pts = pts[:-1]
    if len(pts) < 3:
        raise LaserError(f"{what}: a path has fewer than 3 points")
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        if math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-6:
            raise LaserError(f"{what}: zero-length (duplicate point) segment at ({a[0]:.2f}, {a[1]:.2f})")

def nominal_polys(p):
    """finished (nominal) geometry of a part as shapely polygons: outline with tabs, minus the cut-through holes"""
    if p.shapes is not None:
        res = []
        for shp in p.shapes:
            holes = [list(r.coords)[:-1] for r in shp.interiors]
            extra = [h.pts for h in p.holes if h.layer == "cut" and shp.contains(Point(*np.mean(np.array(h.pts), axis=0)))]
            res.append(Polygon(list(shp.exterior.coords)[:-1], holes + extra))
        return res
    if p.outline is None:
        p.finalize()
    return [Polygon(p.outline, [h.pts for h in p.holes if h.layer == "cut"])]

def drawn_part(p, cfg):
    """kerf-compensated cut polygons (drawn) + engrave/score paths + label, all in the part's local coordinates"""
    nom = nominal_polys(p)
    out = []
    for q in nom:
        if not q.is_valid:
            raise LaserError(f"{p.key}: the outline is not a valid simple polygon (self-intersection) - check the openings.")
        ring_ok(q.exterior.coords, p.key)
        for r in q.interiors: ring_ok(r.coords, f"{p.key} opening")
        d = q.buffer(cfg.K / 2.0, join_style=2, mitre_limit=3.0) if cfg.K > 0 else q
        if getattr(d, "geom_type", "") != "Polygon" or d.is_empty:
            raise LaserError(f"{p.key}: kerf compensation of {cfg.K:g} mm split or erased the part - an opening or tab is too small.")
        if len(d.interiors) != len(q.interiors):
            raise LaserError(f"{p.key}: an opening or slot vanished after kerf compensation ({cfg.K:g} mm) - it is smaller than the kerf.")
        out.append(d)
    engr = [dict(pts=list(e["pts"]), closed=e["closed"], layer=e["layer"]) for e in p.engraves]
    for h in p.holes:
        if h.layer == "engrave":
            engr.append(dict(pts=list(h.pts), closed=True, layer="ENGRAVE"))
    text = p.label
    pos, outside = place_label(out, engr, text)
    return dict(part=p, nominal=nom, drawn=out, engr=engr, label=(text, pos, outside))

def place_label(drawn, engr, text):
    """Find a spot for the part label inside the part (not touching cut lines, openings or engraving); otherwise below it."""
    w = 0.62 * LABEL_H * len(text) + 1.0; h = LABEL_H + 1.0
    big = max(drawn, key=lambda q: q.area)
    x0, y0, x1, y1 = big.bounds
    obstacles = []
    for e in engr:
        if e["closed"] and len(e["pts"]) > 2:
            obstacles.append(Polygon(e["pts"]))
        else:
            xs = [q[0] for q in e["pts"]]; ys = [q[1] for q in e["pts"]]
            obstacles.append(Polygon(rect_pts(min(xs) - 0.5, min(ys) - 0.5, max(xs) + 0.5, max(ys) + 0.5)))
    if x1 - x0 > w + 2 and y1 - y0 > h + 2:
        step = max(2.0, max(x1 - x0, y1 - y0) / 14.0)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        cand = [(x, y) for x in np.arange(x0 + 1, x1 - w, step) for y in np.arange(y0 + 1, y1 - h, step)]
        cand.sort(key=lambda c: (c[0] + w / 2 - cx) ** 2 + (c[1] + h / 2 - cy) ** 2)
        for (x, y) in cand[:250]:
            b = Polygon(rect_pts(x, y, x + w, y + h))
            if big.contains(b) and not any(b.intersects(o) for o in obstacles):
                return (x + 0.5, y + 0.5), False
    return (x0, y0 - 2.0 - LABEL_H), True

def validate_part(dr, cfg):
    """per-part checks of the finished (nominal) geometry; returns a list of problem strings"""
    p = dr["part"]; errs = []; key = p.key; ms = cfg.min_edge
    if p.shapes is not None:                       # stacked layers: outlines come straight from the STL sections
        return errs
    body = Polygon(p.outline)
    nom = dr["nominal"][0]
    slots = [h for h in p.holes if h.role == "slot"]
    ops = [h for h in p.holes if h.role in ("opening", "seat", "alignment")]
    sp = [Polygon(h.pts) for h in slots]; op = [(h, Polygon(h.pts)) for h in ops]
    for h, s_ in zip(slots, sp):
        if not body.contains(s_):
            errs.append(f"{key}: slot of joint '{h.joint}' lies outside the part")
        elif body.exterior.distance(s_) < ms - 0.05:
            errs.append(f"{key}: slot of joint '{h.joint}' is only {body.exterior.distance(s_):.2f} mm from the part edge (minimum {ms:.2f} mm)")
    for i in range(len(sp)):
        for j in range(i + 1, len(sp)):
            if sp[i].intersects(sp[j]):
                errs.append(f"{key}: slots of joints '{slots[i].joint}' and '{slots[j].joint}' overlap")
            elif sp[i].distance(sp[j]) < ms - 0.05:
                errs.append(f"{key}: slots of '{slots[i].joint}' and '{slots[j].joint}' are only {sp[i].distance(sp[j]):.2f} mm apart (minimum {ms:.2f} mm)")
    for h, o in op:
        if h.layer == "cut" and not body.contains(o):
            errs.append(f"{key}: opening '{h.name or h.role}' is not completely inside the part")
        for k, s_ in zip(slots, sp):
            if o.intersects(s_):
                errs.append(f"{key}: slot of joint '{k.joint}' intersects opening '{h.name or h.role}'")
            elif o.distance(s_) < ms - 0.05:
                errs.append(f"{key}: slot of joint '{k.joint}' is only {o.distance(s_):.2f} mm from opening '{h.name or h.role}'")
    for e in dr["engr"]:                           # engraving must lie on solid sheet and never touch a cut path
        if e["closed"] and len(e["pts"]) > 2 and not nom.contains(Polygon(e["pts"])):
            errs.append(f"{key}: an engraved outline crosses a cut path or leaves the part")
    return errs

def validate_joints(reg, cfg):
    errs = []
    for j in reg.joints:
        A, B = reg.parts.get(j.a), reg.parts.get(j.b)
        if A is None or B is None:
            errs.append(f"joint '{j.name}': missing part"); continue
        if len(j.tab_polys) != len(j.slots) or len(j.slots) == 0:
            errs.append(f"joint '{j.name}': tab count ({len(j.tab_polys)}) differs from slot count ({len(j.slots)})")
        if j.w < cfg.T - 1e-9 and not cfg.allow_narrow:
            errs.append(f"joint '{j.name}': tab width {j.w:.2f} mm is narrower than the material thickness {cfg.T:g} mm")
        holes_a = [Polygon(h.pts) for h in A.holes]
        for tp in j.tab_polys:
            tpoly = Polygon(tp)
            for h in holes_a:
                if tpoly.intersects(h):
                    errs.append(f"joint '{j.name}': a tab on '{A.key}' intersects an opening or slot")
        for i in range(len(j.tab_polys)):
            for k in range(i + 1, len(j.tab_polys)):
                if Polygon(j.tab_polys[i]).intersects(Polygon(j.tab_polys[k])):
                    errs.append(f"joint '{j.name}': two tabs on '{A.key}' overlap")
        for sl, ft in zip(j.slots, j.feet):
            s_, f_ = Polygon(sl), Polygon(ft)
            ws = max(abs(np.array(sl)[:, 0].max() - np.array(sl)[:, 0].min()), abs(np.array(sl)[:, 1].max() - np.array(sl)[:, 1].min()))
            if abs(s_.area - (f_.area + cfg.C * (j.w + cfg.T) + cfg.C * cfg.C)) > 1e-6 * max(1.0, f_.area):
                errs.append(f"joint '{j.name}': slot size does not equal tab size + clearance ({cfg.C:+.3f} mm)")
            if abs(s_.centroid.x - f_.centroid.x) > 1e-6 or abs(s_.centroid.y - f_.centroid.y) > 1e-6:
                errs.append(f"joint '{j.name}': tab and slot are not centred on each other")
            if cfg.C >= 0 and not s_.contains(f_):
                errs.append(f"joint '{j.name}': the tab does not fit inside its slot")
            body = Polygon(B.outline) if B.outline else None
            if body is not None and not body.contains(s_):
                errs.append(f"joint '{j.name}': a slot lies outside '{B.key}'")
    return errs

def expected_parts(model, method):
    base = {"base_floor", "front_wall", "rear_wall", "left_side_wall", "right_side_wall", "base_top_frame", "front_portal",
            "portal_brace_left", "portal_brace_right"}
    if model == "birdfeeder":
        base |= {"seed_slope", "seed_slope_rib_01", "seed_slope_rib_02", "seed_slope_rib_03"}
    return base

def validate_assembly(reg, cfg, ctx):
    errs = []
    keys = {k for k, p in reg.parts.items() if p.kind == "panel" and not k.startswith("tower_")}
    exp = expected_parts(cfg.model, cfg.method)
    if keys != exp:
        errs.append(f"assembly check: base parts do not match the {cfg.model} variant (missing {sorted(exp - keys)}, unexpected {sorted(keys - exp)})")
    if cfg.model == "tealight" and any(k.startswith("seed_") for k in reg.parts):
        errs.append("assembly check: a tealight assembly must not contain seed-flow parts")
    if cfg.method == "faceted":
        tk = {k for k in reg.parts if k.startswith("tower_panel_") or k.startswith("tower_ring_")}
        if len(tk) != 7:
            errs.append(f"assembly check: expected 4 tower panels + 3 rings, found {len(tk)} tower parts")
    # every part must be tied into the assembly by at least one joint (or be glued stock: frame / layers)
    tied = {j.a for j in reg.joints} | {j.b for j in reg.joints}
    for k, p in reg.parts.items():
        if p.kind == "panel" and k not in tied and k != "base_top_frame":
            errs.append(f"assembly check: part '{k}' has no tab-and-slot joint")
    # assembled extent against the STL
    zs, xs, ys = [], [], []
    for p in reg.parts.values():
        if p.kind == "panel":
            for (u, v) in p.outline or p.base:
                q = p.frame.to3d(u, v); xs.append(q[0]); ys.append(q[1]); zs.append(q[2])
        else:
            for sh in p.shapes:
                x0, y0, x1, y1 = sh.bounds
                xs += [x0, x1]; ys += [y0, y1]; zs.append(p.frame.o[2] + cfg.T / 2)
    ztop = max(zs)
    if abs(ztop - ctx["z_top"]) > 1.5 * cfg.T + 1.0:
        errs.append(f"assembly check: the assembled height {ztop:.1f} mm differs from the STL height {ctx['z_top']:.1f} mm")
    ctx["assembled_height"] = ztop
    # crown spigot must fit inside the tower top
    if ctx.get("spigot_half") and ctx.get("tower_top_inner"):
        if ctx["spigot_half"] + cfg.C > ctx["tower_top_inner"] + 1e-6:
            warn(f"the crown spigot ({2 * ctx['spigot_half']:.1f} mm wide) is wider than the inside of the tower top "
                 f"({2 * ctx['tower_top_inner']:.1f} mm) with {cfg.T:g} mm panels - the crown will not seat; use thinner material or a larger scale.")
    return errs

# --------------------------------------------------------------------------------- nesting
@dataclass
class Item:
    key: str; label: str; group: str | None; drawn: list; engr: list; label_text: str; label_pos: tuple; label_out: bool
    w: float = 0.0; h: float = 0.0; x0: float = 0.0; y0: float = 0.0
    extra: list = field(default_factory=list)      # more labels: (text, (x, y))
    def bounds(self):
        bs = [q.bounds for q in self.drawn]
        x0 = min(b[0] for b in bs); y0 = min(b[1] for b in bs); x1 = max(b[2] for b in bs); y1 = max(b[3] for b in bs)
        if self.label_out:
            lw = 0.62 * LABEL_H * len(self.label_text) + 1.0
            x0 = min(x0, self.label_pos[0]); y0 = min(y0, self.label_pos[1]); x1 = max(x1, self.label_pos[0] + lw)
        return x0, y0, x1, y1

def make_item(dr):
    it = Item(dr["part"].key, dr["part"].label, dr["part"].group, dr["drawn"], dr["engr"], dr["label"][0], dr["label"][1], dr["label"][2])
    x0, y0, x1, y1 = it.bounds(); it.x0, it.y0, it.w, it.h = x0, y0, x1 - x0, y1 - y0
    return it

def transform(it, dx, dy, rot):
    """item -> sheet coordinates: optional 90 degree rotation (text stays horizontal), then shift so the bbox starts at (dx, dy)"""
    def rp(x, y):
        return (-y, x) if rot else (x, y)
    bx0, by0 = (-(it.y0 + it.h), it.x0) if rot else (it.x0, it.y0)
    ox, oy = dx - bx0, dy - by0
    polys = []
    for q in it.drawn:
        r = affinity.rotate(q, 90, origin=(0, 0)) if rot else q
        polys.append(affinity.translate(r, ox, oy))
    engr = [dict(pts=[(rp(x, y)[0] + ox, rp(x, y)[1] + oy) for x, y in e["pts"]], closed=e["closed"], layer=e["layer"]) for e in it.engr]
    lp = rp(*it.label_pos)
    labs = [(it.label_text, (lp[0] + ox, lp[1] + oy))]
    for text, (lx, ly) in it.extra:
        q = rp(lx, ly); labs.append((text, (q[0] + ox, q[1] + oy)))
    return polys, engr, labs

def nest(items, cfg):
    """shelf packing; parts are never closer than kerf + spacing to each other (cut lines are kerf/2 each) or the sheet margin"""
    gap = cfg.K + cfg.spacing
    W, H = cfg.sheet_w - 2 * cfg.margin, cfg.sheet_h - 2 * cfg.margin
    for it in items:
        if not ((it.w <= W and it.h <= H) or (it.h <= W and it.w <= H)):
            raise LaserError(f"part '{it.key}' ({it.w:.0f} x {it.h:.0f} mm) does not fit on a {cfg.sheet_w:g} x {cfg.sheet_h:g} mm sheet "
                             f"with {cfg.margin:g} mm margins. Use a larger --sheet-width/--sheet-height or a smaller --scale.")
    sheets = []
    def try_place(sh, it):
        for rot in (False, True):
            w, h = (it.h, it.w) if rot else (it.w, it.h)
            if w > W or h > H: continue
            for row in sh["rows"]:
                if h <= row["h"] + 1e-9 and row["x"] + w <= W + 1e-9:
                    sh["pl"].append((it, cfg.margin + row["x"], cfg.margin + row["y"], rot)); row["x"] += w + gap; return True
            ytop = (sh["rows"][-1]["y"] + sh["rows"][-1]["h"] + gap) if sh["rows"] else 0.0
            if ytop + h <= H + 1e-9:
                sh["rows"].append(dict(y=ytop, h=h, x=w + gap)); sh["pl"].append((it, cfg.margin, cfg.margin + ytop, rot)); return True
        return False
    for it in sorted(items, key=lambda i: -max(i.w, i.h)):
        if not any(try_place(sh, it) for sh in sheets):
            sh = dict(rows=[], pl=[]); sheets.append(sh)
            if not try_place(sh, it):
                raise LaserError(f"internal: cannot place '{it.key}' on an empty sheet")
    return [sh["pl"] for sh in sheets]

def validate_sheet(placements, cfg, idx):
    errs = []; gap = cfg.K + cfg.spacing
    placed = []
    for it, dx, dy, rot in placements:
        polys, engr, lab = transform(it, dx, dy, rot)
        placed.append((it, polys))
        for q in polys:
            x0, y0, x1, y1 = q.bounds
            if x0 < cfg.margin - 1e-6 or y0 < cfg.margin - 1e-6 or x1 > cfg.sheet_w - cfg.margin + 1e-6 or y1 > cfg.sheet_h - cfg.margin + 1e-6:
                errs.append(f"sheet {idx}: part '{it.key}' lies outside the sheet or inside the {cfg.margin:g} mm margin")
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            for a in placed[i][1]:
                for b in placed[j][1]:
                    if a.distance(b) < gap - 1e-6:
                        errs.append(f"sheet {idx}: '{placed[i][0].key}' and '{placed[j][0].key}' are closer than {gap:g} mm (kerf + spacing)")
    return errs

def grid_layout(items, cfg, max_w=1200.0, gap=8.0):
    """all-parts overview: items in rows, no rotation"""
    pl = []; x = y = 0.0; rowh = 0.0
    for it in items:
        if x > 0 and x + it.w > max_w:
            x = 0.0; y += rowh + gap; rowh = 0.0
        pl.append((it, x + 5.0, y + 5.0, False)); x += it.w + gap; rowh = max(rowh, it.h)
    return pl, max_w + 10.0, y + rowh + 10.0

# --------------------------------------------------------------------------------- writers (SVG / DXF / CSV / preview)
def collect(placements):
    polys, engr, labels = [], [], []
    for it, dx, dy, rot in placements:
        p, e, l = transform(it, dx, dy, rot)
        polys += p; engr += e; labels += l
    return polys, engr, labels

def write_svg(path, W, H, polys, engr, labels, extra_lines):
    dwg = svgwrite.Drawing(str(path), size=(f"{W:.3f}mm", f"{H:.3f}mm"), viewBox=f"0 0 {W:.3f} {H:.3f}")
    fy = lambda y: H - y                                      # SVG y points down, model y points up
    def d_of(coords):
        c = list(coords)
        if len(c) > 1 and tuple(c[0]) == tuple(c[-1]): c = c[:-1]
        return "M " + " L ".join(f"{x:.4f} {fy(y):.4f}" for x, y in c) + " Z"
    groups = {n: dwg.g(id=n, stroke=LAYERS[n][0], fill="none", stroke_width=0.1,
                       **({"stroke_dasharray": "2,1"} if n == "SCORE" else {})) for n in LAYERS}
    for n in ("CONSTRUCTION", "CUT", "ENGRAVE", "SCORE", "LABEL"):
        dwg.add(groups[n])
    for (a, b, c, e) in extra_lines:                         # construction rectangle(s)
        groups["CONSTRUCTION"].add(dwg.path(d=d_of(rect_pts(a, b, c, e) + [rect_pts(a, b, c, e)[0]])))
    for q in polys:
        groups["CUT"].add(dwg.path(d=d_of(q.exterior.coords)))
        for r in q.interiors:
            groups["CUT"].add(dwg.path(d=d_of(r.coords)))
    for e in engr:
        pts = e["pts"]
        if e["closed"]:
            groups[e["layer"]].add(dwg.path(d=d_of(pts + [pts[0]])))
        else:
            groups[e["layer"]].add(dwg.path(d="M " + " L ".join(f"{x:.4f} {fy(y):.4f}" for x, y in pts)))
    for text, (x, y) in labels:
        groups["LABEL"].add(dwg.text(text, insert=(round(x, 4), round(fy(y), 4)), font_size=LABEL_H, fill=LAYERS["LABEL"][0], stroke="none"))
    dwg.save()

def write_dxf(path, W, H, polys, engr, labels, extra_lines):
    doc = ezdxf.new("R2010", setup=True)
    doc.units = dxf_units.MM
    doc.header["$INSUNITS"] = 4; doc.header["$MEASUREMENT"] = 1
    for n, (_, col, lt) in LAYERS.items():
        doc.layers.add(n, color=col, linetype=lt)
    msp = doc.modelspace()
    pl = lambda pts, layer, close: msp.add_lwpolyline([(float(x), float(y)) for x, y in pts], close=close, dxfattribs={"layer": layer})
    for (a, b, c, e) in extra_lines:
        pl(rect_pts(a, b, c, e), "CONSTRUCTION", True)
    for q in polys:
        pl(list(q.exterior.coords)[:-1], "CUT", True)
        for r in q.interiors:
            pl(list(r.coords)[:-1], "CUT", True)
    for e in engr:
        pl(e["pts"], e["layer"], e["closed"])
    for text, (x, y) in labels:
        msp.add_text(text, dxfattribs={"layer": "LABEL", "height": LABEL_H, "insert": (float(x), float(y))})
    doc.saveas(str(path))

def export(basepath, cfg, W, H, placements, extra_lines=None, written=None):
    polys, engr, labels = collect(placements)
    extra = [(0, 0, W, H)] + list(extra_lines or [])
    out = []
    if "svg" in cfg.formats:
        write_svg(f"{basepath}.svg", W, H, polys, engr, labels, extra); out.append(f"{basepath}.svg")
    if "dxf" in cfg.formats:
        write_dxf(f"{basepath}.dxf", W, H, polys, engr, labels, extra); out.append(f"{basepath}.dxf")
    return out

def write_preview(path, W, H, placements):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        warn("matplotlib is not installed - preview images skipped (pip install matplotlib)")
        return None
    polys, engr, labels = collect(placements)
    fig, ax = plt.subplots(figsize=(max(4, W / 60), max(3, H / 60)), dpi=110)
    ax.set_aspect("equal"); ax.add_patch(plt.Rectangle((0, 0), W, H, fill=False, ec="#999999", lw=0.8))
    for q in polys:
        x, y = zip(*q.exterior.coords); ax.plot(x, y, color="red", lw=0.7)
        for r in q.interiors:
            x, y = zip(*r.coords); ax.plot(x, y, color="red", lw=0.7)
    for e in engr:
        x, y = zip(*(e["pts"] + ([e["pts"][0]] if e["closed"] else []))); ax.plot(x, y, color=LAYERS[e["layer"]][0], lw=0.5)
    for t, (x, y) in labels:
        ax.text(x, y, t, fontsize=5)
    ax.set_xlim(-2, W + 2); ax.set_ylim(-2, H + 2); ax.set_xticks([]); ax.set_yticks([])
    fig.savefig(path, bbox_inches="tight"); plt.close(fig)
    return str(path)

# --------------------------------------------------------------------------------- joint test coupon
def drawn_from_nominal(key, label, poly, cfg, extra=None):
    """kerf-compensate a hand-made nominal polygon and wrap it as a nestable Item"""
    d = poly.buffer(cfg.K / 2.0, join_style=2, mitre_limit=3.0) if cfg.K > 0 else poly
    if len(d.interiors) != len(poly.interiors):
        raise LaserError(f"{key}: a slot vanished after kerf compensation ({cfg.K:g} mm).")
    pos, outside = place_label([d], [], label)
    it = Item(key, label, None, [d], [], label, pos, outside)
    x0, y0, x1, y1 = it.bounds(); it.x0, it.y0, it.w, it.h = x0, y0, x1 - x0, y1 - y0
    it.extra = list(extra or [])
    return it

def build_coupon(cfg):
    """A plate with 5 slots and 5 matching tab pieces for clearances J-0.15 ... J+0.15: cut it from scrap and pick the best fit."""
    T = cfg.T; W = max(cfg.tab_w, T)
    Cs = [cfg.J - 0.15, cfg.J - 0.075, cfg.J, cfg.J + 0.075, cfg.J + 0.15]
    pitch = W + 22.0
    plate = Polygon(rect_pts(0, 0, 12 + pitch * len(Cs), 46),
                    [oriented_rect((12 + W / 2 + 6 + i * pitch, 26), (1, 0), W + c, T + c) for i, c in enumerate(Cs)])
    extra = [(f"C={c:+.3f}", (12 + W / 2 + 6 + i * pitch - 8, 8)) for i, c in enumerate(Cs)]
    items = [drawn_from_nominal("coupon_plate", f"JOINT TEST PLATE  T={T:g}  K={cfg.K:g}  W={W:g}", plate, cfg, extra)]
    for i, c in enumerate(Cs):
        bw = W + 14
        pts = [(0, 0), (bw, 0), (bw, 14), (bw / 2 + W / 2, 14), (bw / 2 + W / 2, 14 + T), (bw / 2 - W / 2, 14 + T), (bw / 2 - W / 2, 14), (0, 14)]
        items.append(drawn_from_nominal(f"coupon_tab_{i + 1}", f"C={c:+.3f}", Polygon(pts), cfg))
    return items

# --------------------------------------------------------------------------------- documents
STEPS_FACETED = {
 "common": [
  "Lay **base_floor** flat on the bench.",
  "Stand the **rear_wall** and the **front_wall** on the floor: push their bottom tabs through the floor slots.",
  "Fit the **left_side_wall** and **right_side_wall**: their bottom tabs go through the floor slots and their two end tabs go through the "
  "slots near the ends of the front and rear walls.",
  "Stand the **front_portal** (columns and pediment) in front of the front wall: its four column-leg tabs go through the floor slots.",
  "Push the two **portal_brace** plates: bottom tabs through the floor, front tabs through the slots in the portal's entablature band.",
 ],
 "birdfeeder": [
  "Seed slope: stand the three **seed_slope_rib** plates in their floor slots, then lower the **seed_slope** plate so that the rib tabs pass "
  "through its slots. The sloping plate must fall towards the door (front wall).",
 ],
 "tealight": [
  "The engraved ring on the floor marks the tea-light seat. Put a heat-resistant insert there; never a bare flame tea light on the sheet.",
 ],
 "top": [
  "Lay the **base_top_frame** on the tops of the four walls (glue it; the square opening is the passage for the tower).",
  "Tower: join the four **tower_panel** parts - the two narrow panels (left/right) have tabs on their long edges that go through the slots "
  "in the two wide panels (front/rear). Slide the three **tower_ring** frames in from above and push their tabs through the panel slots.",
  "Stand the tower on the top frame: the bottom tabs of the four panels go through the frame slots.",
  "Crown: glue the **crown_lid** layers in numerical order (lowest layer first); the first layers form the spigot that slips into the tower top.",
 ],
}

def write_instructions(path, cfg, reg, items, ctx):
    L = []
    title = "Birdfeeder" if cfg.model == "birdfeeder" else "Tealight"
    L += [f"# Bismarckturm {title} - laser-cut flat-pack assembly instructions", "",
          f"* Construction method: **{cfg.method}**  |  material thickness **{cfg.T:g} mm**  |  kerf **{cfg.K:g} mm**  |  "
          f"fit **{cfg.fit}** (finished clearance {cfg.C:+.3f} mm)  |  scale factor {cfg.scale:g}",
          f"* Assembled height about **{ctx.get('assembled_height', 0):.0f} mm**.", "",
          "## Before you start", "",
          "1. Cut the joint **test coupon** first (`--test-coupon`) and choose the clearance that gives the fit you want.",
          "2. Dry-fit every joint before gluing. Slip fits are meant to be glued (wood glue or solvent cement for acrylic).",
          "3. Keep the sheet-nesting file names: every part is engraved with its label.", ""]
    if cfg.model == "tealight":
        L += ["> **Safety:** use an LED tea light, or a real tea light in a glass or metal holder placed on a heat-resistant tile. "
              "Wood, MDF and acrylic burn or soften. Never leave a flame unattended. Burn only with the top openings left clear for air.", ""]
    L += ["## Parts", "", "| Part | Label | Size (mm) |", "|---|---|---|"]
    for it in items:
        L.append(f"| `{it.key}` | {it.label} | {it.w:.0f} x {it.h:.0f} |")
    L += ["", "## Assembly order", ""]
    steps = []
    if cfg.method == "faceted":
        steps = STEPS_FACETED["common"] + STEPS_FACETED[cfg.model] + STEPS_FACETED["top"]
    else:
        steps = STEPS_FACETED["common"][:5] + STEPS_FACETED[cfg.model] + [
            STEPS_FACETED["top"][0],
            "Tower: stack the **tower_layer** parts in numerical order (lowest first), aligning them with 3 mm dowels in the pin holes if present, and glue.",
            STEPS_FACETED["top"][3]]
    for i, s in enumerate(steps, 1):
        L.append(f"{i}. {s}")
    if reg.joints:
        L += ["", "## Every tab-and-slot connection", "",
              "| Joint | Tabs on | Edge | Slots in | Number | Tab width (finished) | Slot (finished) |", "|---|---|---|---|---|---|---|"]
        for j in reg.joints:
            L.append(f"| {j.name} | `{j.a}` | {j.edge} | `{j.b}` | {j.n} | {j.w:.2f} | {j.w + cfg.C:.2f} x {cfg.T + cfg.C:.2f} |")
    L += ["", "## Notes", ""]
    for p in reg.parts.values():
        for n in p.notes:
            L.append(f"* `{p.key}`: {n}")
    L += ["* The **base_top_frame** is glued onto the walls (no tabs) so that the tower sits on one solid plate.",
          "* Engrave / score layers show the door and window outlines that are only marked (closed model), the inscription panel and letters, "
          "and the string-course line. They are not cut."]
    Path(path).write_text("\n".join(L) + "\n", encoding="utf-8")

def write_cutlist(path, cfg, items, sheet_of):
    area_sheet = cfg.sheet_w * cfg.sheet_h
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["part", "label", "group", "quantity", "width_mm", "height_mm", "thickness_mm", "area_cm2", "sheet"])
        tot = 0.0
        for it in items:
            a = sum(q.area for q in it.drawn) / 100.0; tot += a
            w.writerow([it.key, it.label, it.group or "", 1, f"{it.w:.1f}", f"{it.h:.1f}", f"{cfg.T:g}", f"{a:.1f}", sheet_of.get(it.key, "")])
        nsheets = len(set(sheet_of.values())) or 1
        w.writerow([]); w.writerow(["TOTAL", f"{len(items)} parts", "", "", "", "", f"{cfg.T:g}", f"{tot:.1f}", f"{nsheets} sheet(s)"])
        w.writerow(["estimated sheet usage", f"{100 * tot * 100 / (area_sheet * nsheets):.1f} % of {nsheets} sheet(s) of {cfg.sheet_w:g} x {cfg.sheet_h:g} mm"])

# --------------------------------------------------------------------------------- inputs
def split_assembly(mesh):
    """split a full-assembly STL into base / tower / crown by connected shells (may be imperfect)"""
    try:
        comps = mesh.split(only_watertight=False)
    except Exception as e:
        raise LaserError(f"cannot split the assembly STL into its three sections ({e}). Supply the separate base, tower and crown STLs instead.")
    comps = [c for c in comps if len(c.faces) > 100]
    if len(comps) != 3:
        raise LaserError(f"the assembly STL contains {len(comps)} separate shells instead of 3 (base, tower, crown). "
                         f"Supply the separate section STLs instead.")
    comps.sort(key=lambda c: float(c.bounds[0][2] + c.bounds[1][2]))
    return comps

def load_inputs(cfg, args):
    metas = {}
    meshes = {}
    if args.assembly_stl and not (args.base_stl and args.tower_stl and args.crown_stl):
        warn("the full assembly STL was supplied: automatic extraction of the individual sections can be imperfect. "
             "The separate section STLs give more reliable results.")
        m, inf = validate_stl(args.assembly_stl, "assembly", cfg)
        base, tower, crown = split_assembly(m)
        for role, mesh in (("base", base), ("tower", tower), ("crown", crown)):
            meshes[role] = mesh
            metas[role] = dict(name=f"{Path(args.assembly_stl).name} [{role}]", extents=np.asarray(mesh.bounds[1] - mesh.bounds[0], float), path=args.assembly_stl)
        return meshes, metas
    for role, path in (("base", args.base_stl), ("tower", args.tower_stl), ("crown", args.crown_stl)):
        if not path:
            raise LaserError(f"--{role}-stl is required (or supply --assembly-stl alone).")
        meshes[role], metas[role] = validate_stl(path, role, cfg)
    return meshes, metas

# --------------------------------------------------------------------------------- main flow
def run(cfg, args):
    t0 = time.time()
    outdir = Path(cfg.outdir)
    created = not outdir.exists()
    try:
        outdir.mkdir(parents=True, exist_ok=True)
        probe = outdir / f".write_test_{os.getpid()}"; probe.write_text("x"); probe.unlink()
    except OSError as e:
        raise LaserError(f"cannot create or write the output directory '{outdir}': {e}")
    stage = outdir / f".tmp_laser_{os.getpid()}"
    stage.mkdir(exist_ok=True)
    written = []
    try:
        info("=" * 72)
        info(f"Bismarckturm laser parts - {cfg.model.upper()} - {cfg.method} - material {cfg.T:g} mm, kerf {cfg.K:g} mm, "
             f"clearance {cfg.C:+.3f} mm ({cfg.fit})")
        info("=" * 72)
        stem = f"bismarckturm_{cfg.model}"
        if args.test_coupon:
            items = build_coupon(cfg)
            pls = nest(items, cfg)
            errs = []
            for i, pl in enumerate(pls, 1):
                errs += validate_sheet(pl, cfg, i)
            if errs: raise LaserError("coupon layout invalid:\n  " + "\n  ".join(errs))
            for i, pl in enumerate(pls, 1):
                nm = "bismarckturm_joint_test_coupon" + (f"_{i:02d}" if len(pls) > 1 else "")
                written += export(str(stage / nm), cfg, cfg.sheet_w, cfg.sheet_h, pl)
            info("Cut the coupon from scrap of the SAME material. The tab piece whose label matches the slot you want should slide in\n"
                 "with the feel you need (slip = free, snug = light friction). Use that value as --joint-clearance.")
        else:
            written += run_model(cfg, args, stage, stem)
        # all checks passed: move the staged files into the output folder
        final = []
        for f in written:
            dst = outdir / Path(f).name
            if dst.exists(): dst.unlink()
            shutil.move(f, dst); final.append(dst)
        info("")
        info(f"Done in {time.time() - t0:.0f} s - {len(final)} file(s) written to {outdir.resolve()}")
        for f in final: info("  " + f.name)
        if WARNINGS:
            info(f"{len(WARNINGS)} warning(s) were reported above - please read them before cutting.")
        return 0
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        if created:
            try: outdir.rmdir()                                  # remove the folder again if the run failed before writing anything
            except OSError: pass

def run_model(cfg, args, stage, stem):
    u = cfg.scale
    info("Reading and validating the STL files ...")
    meshes, metas = load_inputs(cfg, args)
    s0 = check_scales(metas, cfg)
    s = s0 * u
    if scale_from_name(metas["base"]["name"]) is None and u == 1.0:
        pass
    Sb, St, Sc = (Sectioner(meshes[k], u) for k in ("base", "tower", "crown"))
    info("Measuring the base ...")
    Bd = derive_base(Sb, s, cfg)
    name_model = model_from_name(metas["base"]["name"])
    if name_model and name_model != cfg.model:
        raise LaserError(f"the base STL file name says '{name_model}' but {cfg.model} was selected. Select the matching model "
                         f"(--birdfeeder / --tealight) or supply the right base STL.")
    geo_model = "tealight" if Bd.get("seat_d") else ("birdfeeder" if Bd.get("slope_deg") else None)
    if geo_model and geo_model != cfg.model:
        raise LaserError(f"the base STL geometry looks like the {geo_model} base (seat={'yes' if Bd.get('seat_d') else 'no'}, "
                         f"slope={'yes' if Bd.get('slope_deg') else 'no'}) but {cfg.model} was selected.")
    nm_mode = mode_from_name(metas["base"]["name"]); geo_open = Bd.get("open_mode")
    if nm_mode and geo_open is not None and (nm_mode == "open") != bool(geo_open):
        warn(f"the file name says _{nm_mode} but the geometry looks {'open' if geo_open else 'closed'}; the geometry is used")
    info(f"  plinth {2 * Bd['half']:.1f} mm, door {Bd['door'][1] - Bd['door'][0]:.1f} x {Bd['door'][3] - Bd['door'][2]:.1f} mm, "
         f"{'OPEN' if geo_open else 'CLOSED'} windows/slits, tower start Z {Bd['Zc']:.1f} mm")
    info("Measuring the tower and crown ...")
    Tw = derive_tower(St, s, cfg); Cr = derive_crown(Sc, s, cfg)
    hf = lambda z: Tw["hb"] - Tw["k"] * (z - Tw["zb"])
    reg = Registry()
    info(f"Building the flat parts ({cfg.method}) ...")
    base = build_base(Bd, hf(Bd["Zc"]), cfg, reg)
    if cfg.model == "birdfeeder":
        build_hopper(Bd, cfg, reg, base["wall_top"], base["floor"], Bd["half"])
    if cfg.method == "faceted":
        build_tower(Tw, Bd["Zc"], cfg, reg, base["frame"])
    else:
        lay = make_layers(St, Bd["Zc"], Tw["z1"], cfg, reg, "tower_layer", "TOWER LAYER", "tower_layers")
        add_pins(lay, cfg, "tower layers")
    cl = make_layers(Sc, Cr["z0"], Cr["z1"], cfg, reg, "crown_layer", "CROWN LAYER", "crown_lid")
    spigot = Cr["spigot_half"]
    if cfg.method == "faceted":
        # inside the flat-panel tower: narrow panels sit T inside the wide ones, so the opening is (h - 2T) wide on each side
        inner = hf(Tw["z1"]) - 2 * cfg.T - cfg.C
        if spigot > inner:
            f = inner / spigot
            for l in cl:                                     # only the layers that go INTO the tower (the spigot)
                if l.frame.o[2] < Tw["z1"]:
                    l.shapes = [affinity.scale(sh, f, f, origin=(0, 0)) for sh in l.shapes]
            spigot *= f
            info(f"  crown spigot layers scaled to {100 * f:.1f} % so that the crown seats inside the {cfg.T:g} mm tower panels")
            if f < 0.85:
                warn(f"the crown spigot had to be reduced to {100 * f:.0f} % for {cfg.T:g} mm panels at this scale; consider thinner material")
    add_pins(cl, cfg, "crown layers")
    ctx = dict(z_top=Cr["z1"], spigot_half=spigot,
               tower_top_inner=(hf(Tw["z1"]) - 2 * cfg.T) if cfg.method == "faceted" else Tw.get("inner_top"))
    info("Applying kerf compensation and validating every part ...")
    drs, errs = [], []
    for p in reg.parts.values():
        dr = drawn_part(p, cfg); drs.append(dr); errs += validate_part(dr, cfg)
    errs += validate_joints(reg, cfg)
    errs += validate_assembly(reg, cfg, ctx)
    if errs:
        raise LaserError(f"{len(errs)} validation problem(s) found - nothing was written:\n  " + "\n  ".join(errs[:30]) +
                         ("\n  ..." if len(errs) > 30 else "") +
                         "\n  Likely cause: the scale and material thickness do not suit each other (tabs/slots need room). "
                         "Try a larger --scale, thinner material or a smaller --tab-width.")
    info(f"  {len(drs)} parts, {len(reg.joints)} tab-and-slot connections, all checks passed")
    items = [make_item(dr) for dr in drs]
    written = []
    # ---- individual part files (stacked groups are written as one file per group)
    done_groups = set()
    for it in items:
        if it.group:
            if it.group in done_groups: continue
            done_groups.add(it.group)
            members = [i for i in items if i.group == it.group]
            pl, W, H = grid_layout(members, cfg)
            written += export(str(stage / f"{stem}_{it.group}"), cfg, W, H, pl)
        else:
            written += export(str(stage / f"{stem}_{it.key}"), cfg, it.w + 10, it.h + 10, [(it, 5.0, 5.0, False)])
    pl, W, H = grid_layout(items, cfg)
    written += export(str(stage / f"{stem}_all_parts"), cfg, W, H, pl)
    # ---- nested sheets
    sheets = nest(items, cfg)
    sheet_of = {}
    for i, pl in enumerate(sheets, 1):
        e = validate_sheet(pl, cfg, i)
        if e: raise LaserError("nesting produced an invalid sheet:\n  " + "\n  ".join(e))
        for it, *_ in pl: sheet_of[it.key] = i
        m = cfg.margin
        written += export(str(stage / f"{stem}_sheet_{i:02d}"), cfg, cfg.sheet_w, cfg.sheet_h, pl, [(m, m, cfg.sheet_w - m, cfg.sheet_h - m)])
        if cfg.preview:
            pth = write_preview(stage / f"{stem}_sheet_{i:02d}_preview.png", cfg.sheet_w, cfg.sheet_h, pl)
            if pth: written.append(pth)
    if len(sheets) > 1:
        info(f"The parts do not fit on one {cfg.sheet_w:g} x {cfg.sheet_h:g} mm sheet: {len(sheets)} sheets were created.")
    if cfg.preview:
        pth = write_preview(stage / f"{stem}_all_parts_preview.png", W, H, grid_layout(items, cfg)[0])
        if pth: written.append(pth)
    write_instructions(stage / f"{stem}_assembly_instructions.md", cfg, reg, items, ctx)
    write_cutlist(stage / f"{stem}_cut_list.csv", cfg, items, sheet_of)
    written += [str(stage / f"{stem}_assembly_instructions.md"), str(stage / f"{stem}_cut_list.csv")]
    return written

# --------------------------------------------------------------------------------- command line
def build_parser():
    ap = argparse.ArgumentParser(
        prog="generate_bismarckturm_laser_parts.py",
        description="Flat, interlocking laser-cut parts (SVG/DXF) derived from the Bismarckturm STL files.",
        epilog="PowerShell front end: generate_bismarckturm_laser_parts.ps1 (same options).")
    g = ap.add_argument_group("model")
    g.add_argument("--birdfeeder", "-birdfeeder", action="store_true", help="birdfeeder base (default)")
    g.add_argument("--tealight", "-tealight", action="store_true", help="tealight base")
    g.add_argument("--model", choices=["birdfeeder", "tealight"], type=str.lower, help="alternative to --birdfeeder/--tealight")
    g = ap.add_argument_group("input STL files")
    g.add_argument("--base-stl"); g.add_argument("--tower-stl"); g.add_argument("--crown-stl")
    g.add_argument("--assembly-stl", help="full assembly STL (less reliable than the three section STLs)")
    g = ap.add_argument_group("material and joints (millimetres)")
    g.add_argument("--material-thickness", type=float, default=4.0, help="sheet thickness (default 4)")
    g.add_argument("--kerf", type=float, default=0.2, help="TOTAL laser kerf (default 0.2)")
    g.add_argument("--joint-clearance", type=float, default=0.2, help="finished tab/slot clearance (default 0.2)")
    g.add_argument("--fit", choices=["slip", "snug", "press"], default="slip", help="slip: clearance = value; snug: half; press: -0.05 interference")
    g.add_argument("--tab-width", type=float, default=10.0, help="default tab width (default 10)")
    g.add_argument("--tab-count", type=int, default=3, help="default tabs per major joint edge (default 3)")
    g.add_argument("--corner-radius", type=float, default=0.0, help="outer corner rounding of floor and top frame (default 0)")
    g.add_argument("--allow-narrow-tabs", action="store_true", help="allow tabs/slots narrower than the material thickness")
    g = ap.add_argument_group("geometry and output")
    g.add_argument("--scale", type=float, default=1.0, help="scale factor for everything measured from the STL (default 1.0)")
    g.add_argument("--construction-method", choices=["faceted", "stacked"], type=str.lower, default="faceted")
    g.add_argument("--output-format", default="svg,dxf", help="svg, dxf or svg,dxf (default both)")
    g.add_argument("--output-directory", default="2D CAD output", help='default ".\\2D CAD output"')
    g.add_argument("--units", default="mm", help="only mm is supported")
    g.add_argument("--sheet-width", type=float, default=600.0); g.add_argument("--sheet-height", type=float, default=400.0)
    g.add_argument("--sheet-margin", type=float, default=10.0); g.add_argument("--part-spacing", type=float, default=3.0)
    g.add_argument("--preview", action="store_true", help="also write PNG previews (needs matplotlib)")
    g.add_argument("--test-coupon", action="store_true", help="write only the joint test coupon (no STL needed)")
    g.add_argument("--allow-non-watertight", action="store_true", help="continue with an STL that is not watertight (not recommended)")
    return ap

def make_cfg(args, ap):
    if args.birdfeeder and args.tealight:
        raise LaserError("--birdfeeder and --tealight cannot be used together.\n       Choose one (or neither for --birdfeeder). No files were generated.")
    model = "tealight" if args.tealight else "birdfeeder" if args.birdfeeder else (args.model or "birdfeeder")
    if args.model and (args.birdfeeder or args.tealight) and args.model != model:
        raise LaserError(f"--model {args.model} conflicts with --{'tealight' if args.tealight else 'birdfeeder'}. No files were generated.")
    if args.units.lower() != "mm":
        raise LaserError("only --units mm is supported (all output is millimetres at 1:1 scale).")
    fm = tuple(sorted({x.strip().lower() for x in re.split(r"[,\s;]+", args.output_format) if x.strip()}))
    if not fm or not set(fm) <= {"svg", "dxf"}:
        raise LaserError(f"--output-format must be svg, dxf or svg,dxf (got '{args.output_format}').")
    chk = [(args.material_thickness > 0, "--material-thickness must be greater than 0"),
           (args.material_thickness <= 25, "--material-thickness above 25 mm is not supported"),
           (args.kerf >= 0 and args.kerf < args.material_thickness / 2, "--kerf must be 0 or more and smaller than half the thickness"),
           (args.joint_clearance >= 0 and args.joint_clearance <= 1, "--joint-clearance must be between 0 and 1 mm"),
           (args.tab_width >= 1, "--tab-width must be at least 1 mm"), (1 <= args.tab_count <= 8, "--tab-count must be 1..8"),
           (args.corner_radius >= 0, "--corner-radius must be 0 or more"), (args.scale > 0 and math.isfinite(args.scale), "--scale must be greater than 0"),
           (args.sheet_margin >= 0 and args.part_spacing >= 0, "--sheet-margin and --part-spacing must be 0 or more"),
           (args.sheet_width > 2 * args.sheet_margin + 10 and args.sheet_height > 2 * args.sheet_margin + 10, "the sheet is too small for the margins")]
    for ok, msg in chk:
        if not ok: raise LaserError(msg)
    if not args.test_coupon:
        if not (args.assembly_stl or (args.base_stl and args.tower_stl and args.crown_stl)):
            raise LaserError("supply --base-stl, --tower-stl and --crown-stl (or --assembly-stl), or use --test-coupon.")
    return Cfg(model=model, T=args.material_thickness, K=args.kerf, J=args.joint_clearance, fit=args.fit, tab_w=args.tab_width,
               tab_n=args.tab_count, corner_r=args.corner_radius, scale=args.scale, formats=fm, outdir=args.output_directory,
               method=args.construction_method, preview=args.preview, sheet_w=args.sheet_width, sheet_h=args.sheet_height,
               margin=args.sheet_margin, spacing=args.part_spacing, allow_narrow=args.allow_narrow_tabs,
               allow_open_mesh=args.allow_non_watertight)

def main(argv=None):
    ap = build_parser(); args = ap.parse_args(argv)
    try:
        cfg = make_cfg(args, ap)
        if cfg.fit == "press":
            warn("fit 'press' is an interference fit: laser-cut press fits are unreliable - test with the coupon first")
        return run(cfg, args)
    except LaserError as e:
        print("\nERROR: " + str(e), file=sys.stderr)
        print("No output files were written.", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
