#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M4-B2 hero props batch:
  TLS-PRP-001 Edmund's Lantern (7k)   - brass/iron/glass, rotating shade
  TLS-PRP-002 Register of Sins (9k)   - leather ledger, 17 cheap locks, open+closed
  TLS-PRP-003 Sin Plate (5k)          - stone plate + bread + salt (11-scene key item)
  TLS-PRP-004 Ifan's Gate Key (3k)    - rusted iron, Y Porth
  TLS-PRP-011 Inn Tableware (12k)     - brass jug, mugs, plates, candlesticks
  TLS-PRP-014 Evidence Set A (8k)     - opium bottle, collector letter, grave ring, wax
Run: blender -b --python b2_props.py -- --root <repo>
"""
import bpy, os, sys, math, time
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import tls_lib as L
import tls_mats as M

OPTS = L.parse_args()
ROOT = OPTS.get("root", "/home/z/my-project/work/lastsin-repo")
SRC = os.path.join(ROOT, "02_Art", "blender", "source", "prp")
FBX = os.path.join(ROOT, "02_Art", "exports", "fbx")
STATS = os.path.join(ROOT, "02_Art", "exports", "stats")
EV = os.path.join(ROOT, "reports", "M4_BATCH1_EVIDENCE")
os.makedirs(SRC, exist_ok=True)
TAU = L.TAU
t0 = time.time()
BATCH = []

# ---------------------------------------------------------------- helpers
def torus(name, R, r, cx=0.0, cy=0.0, cz=0.0, n_path=36, n_sec=12,
          mat=None, coll="TLS", arc=TAU, scale_sec=None):
    rings = []
    for i in range(n_path):
        a = arc * i / n_path
        px, py = cx + R * math.cos(a), cy + R * math.sin(a)
        pts = []
        for j in range(n_sec):
            b = TAU * j / n_sec
            rx, rz = math.cos(b) * r, math.sin(b) * r
            if scale_sec:
                rx *= scale_sec
            pts.append((px + math.cos(a) * rx, py + math.sin(a) * rx, cz + rz))
        rings.append({"verts": pts})
    v, f, u = L.loft_rings(rings, closed_loop=arc >= TAU - 1e-6,
                           cap_bottom=arc < TAU - 1e-6,
                           cap_top=arc < TAU - 1e-6)
    return L.new_mesh_obj(name, v, f, uvs=u, mat=mat, coll=coll)

def squashed_sphere(name, cx, cy, cz, rx, ry, rz, seg=24, rng_seed=0,
                    bump=0.0, mat=None, coll="TLS"):
    rings = []
    rows = 18
    for j in range(rows + 1):
        t = j / rows
        theta = math.pi * t
        s = math.sin(theta)
        rr = s
        z = cz + rz * math.cos(theta)
        pts = []
        for i in range(seg):
            a = TAU * i / seg
            rad = rr * (1.0 + (bump * math.sin(3 * a + rng_seed) * (1 - t)))
            pts.append((cx + rx * rad * math.cos(a), cy + ry * rad * math.sin(a), z))
        rings.append({"verts": pts})
    v, f, u = L.loft_rings(rings, closed_loop=True, cap_bottom=False, cap_top=False)
    return L.new_mesh_obj(name, v, f, uvs=u, mat=mat, coll=coll)

def lathe(name, profile, seg=28, mat=None, coll="TLS", close_bottom=False,
          close_top=False):
    """profile: list of (radius, z). radius 0 allowed (pole)."""
    rings = []
    for r, z in profile:
        if r <= 1e-6:
            rings.append({"verts": [(0.0, 0.0, z)] * seg})
        else:
            pts = []
            for i in range(seg):
                a = TAU * i / seg
                pts.append((r * math.cos(a), r * math.sin(a), z))
            rings.append({"verts": pts})
    # handle pole rings: collapse by using cap flags instead
    clean = [rr for rr in rings]
    v, f, u = L.loft_rings(clean, closed_loop=True,
                           cap_bottom=close_bottom, cap_top=close_top)
    return L.new_mesh_obj(name, v, f, uvs=u, mat=mat, coll=coll)

def glass_mat(name="TLS_Mat_Glass", tint=(0.86, 0.90, 0.92)):
    m = L.new_mat(name, base=tint, rough=0.05, metal=0.0)
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    L.set_principled(bsdf, alpha=0.18, ior=1.45, transmission=None)
    try:
        bsdf.inputs["Transmission Weight"].default_value = 0.85
    except Exception:
        pass
    try:
        m.blend_method = 'BLEND'
    except Exception:
        pass
    return m

def finish_asset(asset_id, objs, ucx_objs, blend_name, dims_expected=None,
                 note=""):
    """Audit + save blend + export FBX + record."""
    L.reset_scene.__wrapped__ if False else None
    stem = blend_name.replace(".blend", "")
    # audit BEFORE saving (objects already in scene)
    stats = L.audit_asset(objs, asset_id)
    stats["expected_dims_m"] = dims_expected
    stats["note"] = note
    stats["fbx_expected_objects"] = len(objs) + len(ucx_objs)
    try:
        bpy.ops.file.pack_all()
    except Exception as e:
        print("pack warning:", e)
    bpath = os.path.join(SRC, blend_name)
    bpy.ops.wm.save_as_mainfile(filepath=bpath, compress=True)
    fpath = os.path.join(FBX, f"{stem}_v001.fbx")
    sz = L.export_static_fbx(objs, fpath, ucx_objs=ucx_objs)
    stats["blend_mb"] = round(os.path.getsize(bpath) / 1e6, 2)
    stats["fbx_mb"] = round(sz / 1e6, 2)
    stats["fbx_path"] = fpath
    L.write_json(os.path.join(STATS, f"{stem}.json"), stats)
    BATCH.append({"asset": asset_id, "blend": bpath, "fbx": fpath,
                  "tris": stats["totals"]["tris"]})
    print(f"[B2] {asset_id}: {stats['totals']['verts']}v {stats['totals']['tris']}t "
          f"dims={stats['bbox_m']['dims']} -> {os.path.basename(bpath)}")

# ================================================================ PRP-001 lantern
print("[B2] TLS-PRP-001 lantern ...")
L.reset_scene(); L.setup_units("TLS_PRP_001")
m_brass = M.pbr("TLS_Mat_Lantern_Brass", "brass", ao=0.85)
m_iron = M.pbr("TLS_Mat_Lantern_Iron", "iron", ao=0.8)
m_glass = glass_mat()
m_wax = M.pbr("TLS_Mat_Candle", "wax", ao=0.5)

lan = []
# base reservoir (fuel): tapered drum
lan.append(L.cyl("Lantern_Base", 0.052, 0.012, 0.052, n=24, r_top=0.058, mat=m_brass))
# base plate rim
lan.append(torus("Lantern_BaseRim", 0.055, 0.006, cz=0.052, n_path=28, n_sec=10, mat=m_brass))
# cage rods (4) brass, slight inward taper
for i in range(4):
    a = TAU * i / 4 + math.pi / 4
    x0, y0 = math.cos(a) * 0.058, math.sin(a) * 0.058
    x1, y1 = math.cos(a) * 0.048, math.sin(a) * 0.048
    lan.append(L.tube_between((x0, y0, 0.052), (x1, y1, 0.170), 0.006, 0.005,
                              n=10, name=f"Lantern_Rod{i}", mat=m_brass))
# bottom + top cage rings
lan.append(torus("Lantern_RingBot", 0.058, 0.005, cz=0.056, n_path=32, n_sec=10, mat=m_brass))
lan.append(torus("Lantern_RingTop", 0.049, 0.005, cz=0.168, n_path=32, n_sec=10, mat=m_brass))
# glass chimney (open cylinder)
lan.append(L.cyl("Lantern_Glass", 0.055, 0.054, 0.166, n=28, r_top=0.046,
                 mat=m_glass, cap=False))
# rotating shade (half-cylinder iron sheet inside glass - gameplay light key)
shade = L.cyl("Lantern_Shade", 0.050, 0.055, 0.164, n=20, r_top=0.042,
              mat=m_iron, cap=False)
# remove half the faces: rebuild as half loft
sh_objs = [shade]
# top cap dome
lan.append(lathe("Lantern_Cap", [(0.050, 0.170), (0.046, 0.174), (0.030, 0.180),
                                 (0.012, 0.184), (0.0, 0.186)], seg=28,
                 mat=m_iron, close_top=True))
# smoke dome fins
for i in range(4):
    a = TAU * i / 4
    lan.append(L.box(f"Lantern_Fin{i}", 0.004, 0.020, 0.012,
                     cx=math.cos(a) * 0.036, cy=math.sin(a) * 0.036, cz=0.177,
                     rot_z=a, mat=m_iron))
# hanging ring + bracket
lan.append(torus("Lantern_HangRing", 0.022, 0.004, cz=0.202, n_path=24, n_sec=8, mat=m_iron))
lan.append(L.tube_between((0, 0, 0.186), (0, 0, 0.200), 0.006, 0.005, n=10,
                          name="Lantern_HangPost", mat=m_iron))
# interior: candle stub + flame-ready emitter socket
lan.append(L.cyl("Lantern_Candle", 0.014, 0.052, 0.098, n=16, mat=m_wax))
lan.append(L.cyl("Lantern_Wick", 0.0015, 0.098, 0.104, n=6, mat=m_iron))
# make shade half: delete faces where y > 0.02 (front half kept? shade covers back)
sh = sh_objs[0]
me = sh.data
bm_faces = []
import bmesh
bm = bmesh.new(); bm.from_mesh(me)
for fc in bm.faces:
    c = fc.calc_center_median()
    if c.y > 0.004:
        bm_faces.append(fc)
for fc in bm_faces:
    bm.faces.remove(fc)
bm.to_mesh(me); bm.free(); me.update()

# re-add shade only (not in lan yet)
lan.append(sh)
objs = lan
ucx = [L.add_ucx_box(o, shrink=1.02) for o in [objs[0]]]
finish_asset("TLS-PRP-001", objs, ucx, "tls_prp_001_lantern.blend",
             dims_expected=[0.12, 0.12, 0.20],
             note="handle ring top; shade half-cylinder interior (light gameplay key)")

# ================================================================ PRP-002 ledger
print("[B2] TLS-PRP-002 register of sins ...")
L.reset_scene(); L.setup_units("TLS_PRP_002")
m_leather = M.pbr("TLS_Mat_Ledger_Leather", "leather", ao=0.85)
m_paper = M.pbr("TLS_Mat_Ledger_Paper", "paper", ao=0.4)
m_iron2 = M.pbr("TLS_Mat_Ledger_Iron", "iron", ao=0.8)
m_brass2 = M.pbr("TLS_Mat_Ledger_Brass", "brass", ao=0.7)

led = []
# closed book block 0.32 x 0.24 x 0.062
led.append(L.box("Ledger_Cover", 0.322, 0.242, 0.012, cz=0.031, mat=m_leather))
led.append(L.box("Ledger_Pages", 0.310, 0.230, 0.048, cz=0.024, mat=m_paper))
# spine curvature hint: 3 straps
for i, (x, w) in enumerate([(-0.075, 0.030), (0.0, 0.034), (0.075, 0.030)]):
    led.append(L.box(f"Ledger_Strap{i}", w, 0.248, 0.006, cx=x, cz=0.062, mat=m_iron2))
# 17 cheap locks along the right edge (canon: cheap brass padlock look)
for i in range(17):
    y = -0.096 + 0.012 * i
    led.append(L.box(f"Ledger_Lock{i:02d}", 0.016, 0.009, 0.006,
                     cx=0.152, cy=y, cz=0.064, mat=m_brass2))
    led.append(torus(f"Ledger_Hasp{i:02d}", 0.0035, 0.0012, cx=0.160, cy=y,
                     cz=0.066, n_path=12, n_sec=6, mat=m_iron2))
# clasp centerpiece
led.append(L.box("Ledger_Clasp", 0.030, 0.036, 0.008, cx=0.150, cz=0.064, mat=m_brass2))
# corner protectors (4)
for sx in (-1, 1):
    for sy in (-1, 1):
        led.append(L.box(f"Ledger_Corner{sx}{sy}", 0.034, 0.034, 0.004,
                         cx=sx * 0.144, cy=sy * 0.104, cz=0.064, mat=m_brass2))
objs = led
ucx = [L.add_ucx_box(objs[0])]
finish_asset("TLS-PRP-002", objs, ucx, "tls_prp_002_ledger.blend",
             dims_expected=[0.33, 0.25, 0.07],
             note="closed variant; 17 cheap locks documented in registry notes")

# open variant = separate file per registry note
print("[B2] TLS-PRP-002 open variant ...")
L.reset_scene(); L.setup_units("TLS_PRP_002_OPEN")
M._cache.clear()
m_leather = M.pbr("TLS_Mat_Ledger_Leather", "leather", ao=0.85)
m_paper = M.pbr("TLS_Mat_Ledger_Paper", "paper", ao=0.4)

def hinged_plate(name, w, d, t, side, angle_deg, lift, mat, y0=0.0):
    """Plate hinged at spine x=0, spanning side*(0..w), tilted angle_deg up.
    lift = base z offset at spine. Pure-python vert transform."""
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    pts = []
    for (lx, ly, lz) in [(-w/2, -d/2, -t/2), (w/2, -d/2, -t/2),
                          (w/2, d/2, -t/2), (-w/2, d/2, -t/2),
                          (-w/2, -d/2, t/2), (w/2, -d/2, t/2),
                          (w/2, d/2, t/2), (-w/2, d/2, t/2)]:
        x = lx + w / 2          # 0..w from spine
        z = lz + x * math.tan(a) if False else lz
        # rotate around Y through (x=0, z=lift): x' = x ca, z' = lift + x sa + lz
        px = side * x * ca
        pz = lift + x * sa + lz
        pts.append((px, y0 + ly, pz))
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    u = [(0, 0), (1, 0), (1, 1), (0, 1)] * 2
    return L.new_mesh_obj(name, pts, faces, uvs=u, mat=mat)

led2 = []
# covers nearly flat (examined on a table), slight tilt
led2.append(hinged_plate("LedgerO_CoverL", 0.242, 0.322, 0.012, -1, 8, 0.004, m_leather))
led2.append(hinged_plate("LedgerO_CoverR", 0.242, 0.322, 0.012, +1, 8, 0.004, m_leather))
# page stacks fanning
for side in (-1, 1):
    for k in range(4):
        ang = 6 + k * 5
        lift = 0.008 + k * 0.0022
        led2.append(hinged_plate(f"LedgerO_Pages{side}_{k}", 0.236, 0.312,
                                 0.0035, side, ang, lift, m_paper))
# one raised turning page
led2.append(hinged_plate("LedgerO_TurningPage", 0.232, 0.308, 0.002, +1, 38,
                         0.016, m_paper))
# center binding
led2.append(L.box("LedgerO_Spine", 0.034, 0.318, 0.020, cz=0.012, mat=m_leather))
# loose torn page beside (restoration mechanic hook)
led2.append(L.box("LedgerO_TornPage", 0.115, 0.155, 0.001, cx=0.20, cy=-0.09,
                  cz=0.0015, rot_z=math.radians(14), mat=m_paper))
objs = led2
ucx = [L.add_ucx_box(objs[0])]
finish_asset("TLS-PRP-002-OPEN", objs, ucx, "tls_prp_002_ledger_open.blend",
             dims_expected=[0.50, 0.33, 0.17],
             note="open-on-table variant + turning page + loose torn page (restoration mechanic)")

# ================================================================ PRP-003 sin plate
print("[B2] TLS-PRP-003 sin plate ...")
L.reset_scene(); L.setup_units("TLS_PRP_003")
m_stone = M.pbr("TLS_Mat_SinPlate_Stone", "slate", ao=0.9)
m_bread = L.new_mat("TLS_Mat_Bread", base=(0.62, 0.44, 0.24), rough=0.8)
m_salt = L.new_mat("TLS_Mat_Salt", base=(0.88, 0.88, 0.86), rough=0.55)

sp = []
# stone plate: lathe profile
sp.append(lathe("SinPlate_Body",
                [(0.004, 0.0), (0.13, 0.004), (0.14, 0.012), (0.138, 0.022),
                 (0.128, 0.026), (0.004, 0.024)], seg=32, mat=m_stone,
                close_bottom=False))
# bread loaf (scored round loaf)
loaf = squashed_sphere("SinPlate_Bread", -0.025, 0.01, 0.036, 0.055, 0.048, 0.030,
                       seg=22, rng_seed=3, bump=0.04, mat=m_bread)
sp.append(loaf)
# score lines on bread
for i in range(3):
    a = math.radians(-30 + i * 30)
    sp.append(L.box(f"SinPlate_Score{i}", 0.002, 0.06, 0.004,
                    cx=-0.025 + math.sin(a) * 0.02, cy=0.01 + math.cos(a) * 0.015,
                    cz=0.062, rot_z=a, mat=m_bread))
# salt pile (cone with lump)
sp.append(lathe("SinPlate_Salt",
                [(0.002, 0.024), (0.030, 0.026), (0.040, 0.038), (0.028, 0.050),
                 (0.012, 0.058), (0.0, 0.060)], seg=24, mat=m_salt, close_top=True))
sp[-1].location = (0.065, -0.035, 0)
# crumb scattered
for i, (x, y) in enumerate([(0.02, -0.06), (0.09, 0.03), (-0.08, -0.03)]):
    sp.append(squashed_sphere(f"SinPlate_Crumb{i}", x, y, 0.026, 0.008, 0.007, 0.005,
                              seg=10, rng_seed=i + 1, mat=m_bread))
objs = sp
ucx = [L.add_ucx_box(objs[0])]
finish_asset("TLS-PRP-003", objs, ucx, "tls_prp_003_sin_plate.blend",
             dims_expected=[0.29, 0.29, 0.09],
             note="bread + salt ritual plate - recurring key item (11 scenes)")

# ================================================================ PRP-004 gate key
print("[B2] TLS-PRP-004 gate key ...")
L.reset_scene(); L.setup_units("TLS_PRP_004")
m_rust = M.pbr("TLS_Mat_Key_Rust", "iron", ao=0.85)

ky = []
# shaft
ky.append(L.tube_between((0, 0, 0.012), (0, -0.125, 0.012), 0.0045, 0.0040, n=12,
                         name="Key_Shaft", mat=m_rust))
# bit (teeth) at far end pointing -Y: two lobes
ky.append(L.box("Key_Bit1", 0.010, 0.022, 0.006, cy=-0.116, cz=0.012, mat=m_rust))
ky.append(L.box("Key_Bit2", 0.010, 0.016, 0.006, cy=-0.124, cz=0.020, mat=m_rust))
ky.append(L.box("Key_Bit3", 0.016, 0.008, 0.006, cy=-0.122, cz=0.005, mat=m_rust))
# bow: ring + inner cross (worn saltire)
ky.append(torus("Key_BowRing", 0.020, 0.0045, cy=0.024, cz=0.012, n_path=28,
                n_sec=10, mat=m_rust))
ky.append(L.box("Key_BowCross1", 0.026, 0.005, 0.004, cy=0.024, cz=0.012,
                rot_z=math.radians(45), mat=m_rust))
ky.append(L.box("Key_BowCross2", 0.026, 0.005, 0.004, cy=0.024, cz=0.012,
                rot_z=math.radians(-45), mat=m_rust))
# collar
ky.append(torus("Key_Collar", 0.0065, 0.0022, cy=-0.002, cz=0.012, n_path=16,
                n_sec=8, mat=m_rust))
objs = ky
ucx = [L.add_ucx_box(objs[0])]
finish_asset("TLS-PRP-004", objs, ucx, "tls_prp_004_gate_key.blend",
             dims_expected=[0.05, 0.17, 0.03],
             note="Ifan's rusted Y Porth key - central evidence")

# ================================================================ PRP-011 tableware
print("[B2] TLS-PRP-011 inn tableware set ...")
L.reset_scene(); L.setup_units("TLS_PRP_011")
m_br3 = M.pbr("TLS_Mat_Tw_Brass", "brass", ao=0.8)
m_pewter = L.new_mat("TLS_Mat_Pewter", base=(0.58, 0.59, 0.60), rough=0.35, metal=0.9)
m_wax2 = M.pbr("TLS_Mat_Tw_Wax", "wax", ao=0.5)

tw = []
# brass jug 0.22 tall
tw.append(lathe("Tw_Jug", [(0.028, 0.0), (0.052, 0.004), (0.060, 0.030),
                           (0.058, 0.100), (0.050, 0.130), (0.036, 0.152),
                           (0.040, 0.160), (0.038, 0.162), (0.034, 0.156),
                           (0.032, 0.150)], seg=28, mat=m_br3, close_bottom=True))
tw[-1].location = (-0.16, -0.10, 0)
# spout
tw.append(L.tube_between((-0.16 - 0.033, -0.10, 0.150), (-0.16 - 0.056, -0.10, 0.170),
                         0.011, 0.006, n=12, name="Tw_JugSpout", mat=m_br3))
# handle
hr = torus("Tw_JugHandle", 0.036, 0.005, cx=-0.16 + 0.058, cy=-0.10, cz=0.085,
           n_path=28, n_sec=10, mat=m_br3, arc=math.pi)
# orient handle arc outward +X: rotate about Z by -90 so arc opens -X
L.apply_transforms([hr])
hr.rotation_euler = (0, 0, math.radians(-90))
L.apply_transforms([hr])
tw.append(hr)
# lid knob
tw.append(L.cyl("Tw_JugKnob", 0.008, 0.162, 0.176, cx=-0.16, cy=-0.10, n=12,
                r_top=0.004, mat=m_br3))
# pewter mugs x2
for i, (mx, my) in enumerate([(0.02, -0.13), (0.13, -0.06)]):
    tw.append(lathe(f"Tw_Mug{i}", [(0.028, 0.0), (0.033, 0.003), (0.035, 0.006),
                                    (0.033, 0.095), (0.036, 0.098), (0.030, 0.098),
                                    (0.028, 0.094)], seg=22, mat=m_pewter,
                    close_bottom=True))
    tw[-1].location = (mx, my, 0)
    mh = torus(f"Tw_MugHandle{i}", 0.018, 0.0035, cx=mx + 0.034, cy=my, cz=0.050,
               n_path=22, n_sec=8, mat=m_pewter, arc=math.pi)
    L.apply_transforms([mh])
    mh.rotation_euler = (0, 0, math.radians(-90))
    L.apply_transforms([mh])
    tw.append(mh)
# pewter plates x2
for i, (px, py) in enumerate([(0.06, 0.08), (0.20, 0.10)]):
    tw.append(lathe(f"Tw_Plate{i}", [(0.006, 0.0), (0.070, 0.002), (0.095, 0.010),
                                      (0.098, 0.014), (0.092, 0.016), (0.006, 0.012)],
                    seg=26, mat=m_pewter))
    tw[-1].location = (px, py, 0)
# brass candlestick + candle x2
for i, (cx_, cy_) in enumerate([(-0.14, 0.12), (0.02, 0.18)]):
    tw.append(lathe(f"Tw_Candlestick{i}",
                    [(0.030, 0.0), (0.052, 0.004), (0.054, 0.010), (0.050, 0.014),
                     (0.012, 0.020), (0.014, 0.090), (0.024, 0.100), (0.026, 0.104),
                     (0.020, 0.106), (0.018, 0.100)], seg=24, mat=m_br3,
                    close_bottom=True))
    tw[-1].location = (cx_, cy_, 0)
    tw.append(L.cyl(f"Tw_Candle{i}", 0.016, 0.104 + 0, 0.104 + 0.062, cx=cx_, cy=cy_,
                    n=16, r_top=0.014, mat=m_wax2))
    tw.append(L.cyl(f"Tw_Wick{i}", 0.0012, 0.166, 0.171, cx=cx_, cy=cy_, n=6,
                    mat=m_pewter))
# tray
tw.append(lathe("Tw_Tray", [(0.03, 0.0), (0.15, 0.003), (0.185, 0.014),
                            (0.190, 0.018), (0.184, 0.020), (0.03, 0.006)],
                seg=32, mat=m_br3, close_bottom=True))
tw[-1].location = (0.05, 0.02, 0)
# bake locations into geometry for all
for o in tw:
    if o.location.length > 0:
        L.apply_transforms([o], location=True)
objs = tw
ucx = [L.add_ucx_box(objs[0])]
finish_asset("TLS-PRP-011", objs, ucx, "tls_prp_011_tableware.blend",
             dims_expected=[0.42, 0.36, 0.23],
             note="jug+2 mugs+2 plates+2 candlesticks+tray arrangement")

# ================================================================ PRP-014 evidence A
print("[B2] TLS-PRP-014 evidence set A ...")
L.reset_scene(); L.setup_units("TLS_PRP_014")
m_bottle = L.new_mat("TLS_Mat_BottleGlass", base=(0.16, 0.20, 0.14), rough=0.12)
m_cork = L.new_mat("TLS_Mat_Cork", base=(0.55, 0.42, 0.28), rough=0.85)
m_paper3 = M.pbr("TLS_Mat_EvPaper", "paper", ao=0.5)
m_wax3 = M.pbr("TLS_Mat_EvWax", "wax", ao=0.6)
m_brass4 = M.pbr("TLS_Mat_EvRing", "brass", ao=0.6)

ev = []
# opium bottle (laudanum): dark glass
ev.append(lathe("Ev_Bottle", [(0.001, 0.0), (0.022, 0.002), (0.026, 0.010),
                              (0.028, 0.030), (0.026, 0.052), (0.018, 0.062),
                              (0.011, 0.070), (0.010, 0.080), (0.012, 0.084),
                              (0.010, 0.086)], seg=24, mat=m_bottle, close_bottom=True))
# cork
ev.append(L.cyl("Ev_Cork", 0.009, 0.084, 0.096, n=14, mat=m_cork))
# label
ev.append(L.box("Ev_Label", 0.026, 0.020, 0.0005, cy=-0.0265, cz=0.040, mat=m_paper3))
# collector's letter (folded, sealed)
ev.append(L.box("Ev_Letter", 0.180, 0.115, 0.0025, cx=0.10, cy=0.05, cz=0.0013,
                rot_z=math.radians(9), mat=m_paper3))
ev.append(L.box("Ev_LetterFold", 0.180, 0.002, 0.004, cx=0.10, cy=0.107, cz=0.0033,
                rot_z=math.radians(9), mat=m_paper3))
# wax seal
ev.append(squashed_sphere("Ev_Seal", 0.155, 0.05, 0.006, 0.012, 0.012, 0.004,
                          seg=14, rng_seed=5, mat=m_wax3))
# grave ring (button-mold brass)
rg = torus("Ev_Ring", 0.0095, 0.0018, cx=-0.06, cy=0.10, cz=0.002, n_path=20,
           n_sec=8, mat=m_brass4)
ev.append(rg)
ev.append(L.box("Ev_RingBezel", 0.008, 0.006, 0.003, cx=-0.06, cy=0.088, cz=0.002,
                mat=m_brass4))
# wax drops trail x3
for i, (x, y, r) in enumerate([(-0.02, -0.08, 0.004), (0.01, -0.10, 0.003),
                                (0.04, -0.07, 0.0035)]):
    ev.append(squashed_sphere(f"Ev_WaxDrop{i}", x, y, r * 0.7, r, r, r * 0.8,
                              seg=10, rng_seed=i + 2, mat=m_wax3))
objs = ev
ucx = [L.add_ucx_box(objs[0])]
finish_asset("TLS-PRP-014", objs, ucx, "tls_prp_014_evidence_a.blend",
             dims_expected=[0.30, 0.26, 0.10],
             note="day1-3 evidence: laudanum bottle, collector letter+seal, grave ring, wax drops")

# ---------------------------------------------------------------- summary
L.write_json(os.path.join(STATS, "b2_props_batch.json"),
             {"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
              "seconds": round(time.time() - t0, 1), "assets": BATCH})
print(f"[B2] done in {time.time()-t0:.0f}s: {len(BATCH)} assets")
for b in BATCH:
    print(f"  - {b['asset']}: {b['tris']} tris")
