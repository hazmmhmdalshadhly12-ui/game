#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M4-B4 village green + nature batch:
  TLS-ENV-040 Village Green Kit: market cross, hawthorn tree, well, benches, hand cart
  TLS-ENV-107 Nature & Weather Kit (NEW): bare oak, ash, snag, hazl shrub, reeds,
        rocks x3, peat bank with standing water, bracken cards
Run: blender -b --python b4_green.py -- --root <repo>
"""
import bpy, os, sys, math, time, random
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import tls_lib as L
import tls_mats as M

OPTS = L.parse_args()
ROOT = OPTS.get("root", "/home/z/my-project/work/lastsin-repo")
SRC = os.path.join(ROOT, "02_Art", "blender", "source", "env")
FBX = os.path.join(ROOT, "02_Art", "exports", "fbx")
STATS = os.path.join(ROOT, "02_Art", "exports", "stats")
TAU = L.TAU
t0 = time.time()
BATCH = []

def finish_asset(asset_id, objs, ucx_objs, blend_name, dims_expected=None, note=""):
    stem = blend_name.replace(".blend", "")
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
    print(f"[B4] {asset_id}: {stats['totals']['verts']}v {stats['totals']['tris']}t "
          f"dims={stats['bbox_m']['dims']} pieces={len(objs)}")

# ---------------------------------------------------------------- tree engine
def branch(p0, direction, length, radius, depth, rng, mats, objs,
           max_depth=4, spread=0.55, up_bias=0.25, twig_r=0.006):
    """Recursive branch: tapered tube + children. Returns tip point."""
    if depth > max_depth or radius < twig_r:
        return p0
    d = Vector(direction)
    d.normalize()
    # slight curvature
    bend = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * 0.18
    p1 = Vector(p0) + (d + bend).normalized() * length
    objs.append(L.tube_between(tuple(p0), tuple(p1), radius, radius * 0.72,
                               n=8 if depth < 2 else 6, name=f"br_{depth}_{len(objs)}",
                               mat=mats, coll="TLS"))
    if depth >= max_depth - 1:
        return p1
    n_child = 2 if depth < 2 else rng.choice([2, 3])
    for i in range(n_child):
        a = TAU * i / n_child + rng.uniform(0, 0.8)
        side = Vector((math.cos(a), math.sin(a), 0))
        newd = (d * (1 - spread) + side * spread + Vector((0, 0, up_bias))).normalized()
        branch(tuple(p1), newd, length * rng.uniform(0.58, 0.75),
               radius * 0.62, depth + 1, rng, mats, objs,
               max_depth, spread, up_bias, twig_r)
    return p1

def berry_cluster(p, rng, mat, objs, n=6):
    """Small dark muted-red berry octahedra around point p (hawthorn, October)."""
    for i in range(n):
        off = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * 0.035
        cx, cy, cz = p[0] + off.x, p[1] + off.y, p[2] + off.z
        verts = [(cx, cy, cz + 0.007), (cx + 0.005, cy, cz + 0.002),
                 (cx, cy + 0.005, cz + 0.002), (cx - 0.005, cy, cz + 0.002),
                 (cx, cy - 0.005, cz + 0.002), (cx + 0.0035, cy, cz - 0.002),
                 (cx, cy + 0.0035, cz - 0.002), (cx - 0.0035, cy, cz - 0.002),
                 (cx, cy - 0.0035, cz - 0.002), (cx, cy, cz - 0.006)]
        faces = [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1),
                 (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (3, 7, 8), (3, 8, 4),
                 (4, 8, 5), (4, 5, 1), (9, 6, 5), (9, 7, 6), (9, 8, 7), (9, 5, 8)]
        objs.append(L.new_mesh_obj(f"berry_{len(objs)}", verts, faces,
                                   uvs=[(0.5, 1)] + [(0.5, 0.5)] * 8 + [(0.5, 0)],
                                   mat=mat, coll="TLS", smooth_angle=50))

def card_quad(name, p, size, mat, rot_x=0.0, rot_z=0.0, coll="TLS"):
    """Single alpha-card quad centered at p."""
    ca, sa = math.cos(rot_z), math.sin(rot_z)
    cx, sx = math.cos(rot_x), math.sin(rot_x)
    raw = [(-size / 2, -size / 2, 0), (size / 2, -size / 2, 0),
           (size / 2, size / 2, 0), (-size / 2, size / 2, 0)]
    pts = []
    for (x, y, z) in raw:
        x2 = x * ca - y * sa
        y2 = x * sa + y * ca
        y3 = y2 * cx - z * sx
        z3 = y2 * sx + z * cx
        pts.append((p[0] + x2, p[1] + y3, p[2] + z3))
    return L.new_mesh_obj(name, pts, [(0, 1, 2, 3)],
                          uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], mat=mat, coll=coll,
                          smooth_angle=None)

def card_cross(name, p, size, mat, coll="TLS"):
    a = card_quad(f"{name}_a", p, size, mat, rot_x=0, coll=coll)
    b = card_quad(f"{name}_b", p, size, mat, rot_x=math.radians(90), coll=coll)
    c = card_quad(f"{name}_c", p, size, mat, rot_x=math.radians(45), coll=coll)
    return [a, b, c]

def noisy_rock(name, rx, ry, rz, seed, mat, coll="TLS", detail=2):
    rng = random.Random(seed)
    rows = 10 + detail * 3
    seg = 12 + detail * 3
    verts, faces, uvs = [], [], []
    top = len(verts); verts.append((0, 0, rz)); uvs.append((0.5, 1))
    for j in range(1, rows):
        t = j / rows
        theta = math.pi * t
        s = math.sin(theta)
        for i in range(seg):
            u = i / seg
            phi = TAU * u
            n = 1 + (rng.uniform(-1, 1) * 0.16 * (1 - abs(math.cos(theta)) * 0.4))
            rr = n
            verts.append((rx * s * math.cos(phi) * rr, ry * s * math.sin(phi) * rr,
                          rz * math.cos(theta)))
            uvs.append((u, t))
    bot = len(verts); verts.append((0, 0, -rz * 0.55)); uvs.append((0.5, 0))
    def vid(j, i): return 1 + (j - 1) * seg + (i % seg)
    for i in range(seg):
        faces.append((top, vid(1, i), vid(1, i + 1)))
    for j in range(1, rows - 1):
        for i in range(seg):
            faces.append((vid(j, i), vid(j, i + 1), vid(j + 1, i + 1), vid(j + 1, i)))
    for i in range(seg):
        faces.append((bot, vid(rows - 1, i + 1), vid(rows - 1, i)))
    return L.new_mesh_obj(name, verts, faces, uvs=uvs, mat=mat, coll=coll)

# ================================================================ ENV-040 green
print("[B4] TLS-ENV-040 village green kit ...")
L.reset_scene(); L.setup_units("TLS_ENV_040")
M._cache.clear()
m_stone = M.pbr("TLS_Mat_Green_Stone", "stone_wall", ao=0.9)
m_oak = M.pbr("TLS_Mat_Green_Oak", "oak", ao=0.82)
m_slate = M.pbr("TLS_Mat_Green_Slate", "slate_roof", ao=0.85)
m_iron = M.pbr("TLS_Mat_Green_Iron", "iron", ao=0.8)
m_bark = M.pbr("TLS_Mat_Green_Bark", "bark", ao=0.9)
m_wood = M.pbr("TLS_Mat_Green_WoodOld", "oak", base=(0.7, 0.68, 0.62), ao=0.7)
m_berry = L.new_mat("TLS_Mat_HawthornBerry", base=(0.34, 0.14, 0.10), rough=0.35)
m_leaf = M.card("TLS_Mat_LeafCard", "leaf")
m_water = L.new_mat("TLS_Mat_WellWater", base=(0.18, 0.24, 0.26), rough=0.06)

gr = []
# 1. market cross (stepped octagonal base + shaft + cross head) 3.2m
mc = []
for i, (r, h) in enumerate([(0.85, 0.16), (0.62, 0.16), (0.42, 0.18)]):
    z = sum(x[1] for x in [(0.85, 0.16), (0.62, 0.16), (0.42, 0.18)][:i])
    mc.append(L.cyl(f"Green_MCrossBase{i}", r, z, z + h, n=8, mat=m_stone))
mc.append(L.cyl("Green_MCrossShaft", 0.13, 0.50, 2.55, n=8, r_top=0.11, mat=m_stone))
mc.append(L.box("Green_MCrossArm", 0.85, 0.13, 0.15, cz=2.38, mat=m_stone))
mc.append(L.box("Green_MCrossHead", 0.14, 0.13, 0.42, cz=2.72, mat=m_stone))
mc.append(L.new_mesh_obj("Green_MCrossTop",
                         [(0, 0, 2.93), (0.05, 0, 2.98), (0, 0.05, 2.98), (-0.05, 0, 2.98),
                          (0, -0.05, 2.98), (0, 0, 3.06)],
                         [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1),
                          (5, 2, 1), (5, 3, 2), (5, 4, 3), (5, 1, 4)],
                         uvs=[(0.5, 0.5)] * 6, mat=m_stone))
mcx = L.join_objects(mc, "Green_MarketCross", coll="TLS")
gr.append(mcx)
# 2. hawthorn tree (the village tree, 4.5m, half-stripped October)
rng = random.Random(1847)
tw = []
branch((0, 0, 0.35), (0.05, 0.1, 1.0), 1.35, 0.14, 0, rng, m_bark, tw,
       max_depth=4, spread=0.62, up_bias=0.22)
# root flare
for i in range(5):
    a = TAU * i / 5 + 0.3
    tw.append(L.tube_between((0, 0, 0.38), (math.cos(a) * 0.22, math.sin(a) * 0.22, 0.02),
                             0.05, 0.07, n=6, name=f"Green_HawRoot{i}", mat=m_bark))
# sparse leaf cards near tips + berries
for k in range(10):
    a = TAU * k / 10 + rng.uniform(0, 0.5)
    r = 1.3 + rng.uniform(-0.25, 0.35)
    p = (math.cos(a) * r, math.sin(a) * r, 2.3 + rng.uniform(-0.5, 0.9))
    gr.extend(card_cross(f"Green_HawLeaf{k}", p, rng.uniform(0.7, 1.0), m_leaf))
for k in range(14):
    a = TAU * k / 14 + rng.uniform(0, 0.4)
    r = 0.9 + rng.uniform(0, 0.7)
    p = (math.cos(a) * r, math.sin(a) * r, 1.7 + rng.uniform(0, 1.2))
    berry_cluster(p, rng, m_berry, tw, n=4)
haw = L.join_objects(tw, "Green_Hawthorn", coll="TLS")
haw.location = (4.0, 0, 0)
L.apply_transforms([haw], location=True)
gr.append(haw)
# 3. well (stone drum + posts + gable + windlass + bucket)
wl = []
wl.append(L.cyl("Green_WellDrum", 0.62, 0.0, 0.75, n=12, r_top=0.58, mat=m_stone))
wl.append(L.cyl("Green_WellRim", 0.66, 0.75, 0.82, n=12, r_top=0.63, mat=m_stone))
wl.append(L.cyl("Green_WellWater", 0.52, 0.55, 0.62, n=12, mat=m_water))
for sx in (-1, 1):
    wl.append(L.box(f"Green_WellPost{sx}", 0.09, 0.09, 1.55, cx=sx * 0.66, cz=0.82,
                    mat=m_oak))
# gable roof
a = math.radians(26)
for sx in (-1, 1):
    pts = []
    for (lx, ly, lz) in [(-0.78, -0.05, -0.04), (0.78, -0.05, -0.04),
                          (0.78, 0.05, -0.04), (-0.78, 0.05, -0.04),
                          (-0.78, -0.05, 0.04), (0.78, -0.05, 0.04),
                          (0.78, 0.05, 0.04), (-0.78, 0.05, 0.04)]:
        x = lx + 0.78
        pts.append((sx * x * math.cos(a), 2.18 + x * math.sin(a) + lz - 0.02 + 0.72 - 0.72 + 1.46 - 1.46 + 0.0 + ly * 0, lz * 0 + 2.18 + x * math.sin(a) * 0 + 0))
    # simpler explicit slab
    del pts
for sx in (-1, 1):
    x0, x1 = 0.0, 0.86
    z_base = 2.16
    ca, sa = math.cos(a), math.sin(a)
    pts = [(sx * x0 * ca - 0.0, -0.72, z_base + x0 * sa),
           (sx * x1 * ca, -0.72, z_base + x1 * sa),
           (sx * x1 * ca, 0.72, z_base + x1 * sa),
           (sx * x0 * ca, 0.72, z_base + x0 * sa),
           (sx * x0 * ca - 0.0, -0.72, z_base + x0 * sa + 0.05),
           (sx * x1 * ca, -0.72, z_base + x1 * sa + 0.05),
           (sx * x1 * ca, 0.72, z_base + x1 * sa + 0.05),
           (sx * x0 * ca, 0.72, z_base + x0 * sa + 0.05)]
    wl.append(L.new_mesh_obj(f"Green_WellRoof{sx}", pts,
                             [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                              (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)],
                             uvs=[(0, 0), (1, 0), (1, 1), (0, 1)] * 2, mat=m_slate))
wl.append(L.box("Green_WellRidge", 0.14, 1.5, 0.07, cz=2.16 + 0.86 * math.sin(a) + 0.03,
                mat=m_slate))
# windlass axle + crank + rope + bucket
wl.append(L.cyl("Green_WellAxle", 0.05, -0.72, 0.72, cz=1.62, n=8, rot_axis=None,
                mat=m_oak) if False else L.new_mesh_obj(
    "Green_WellAxle",
    [(-0.72, 0, 1.62), (0.72, 0, 1.62)],
    [], uvs=None, mat=m_oak, coll="TLS", smooth_angle=None) if False else
    L.new_mesh_obj("Green_WellAxle_dummy", [(0, 0, 0)], [], uvs=None, mat=None,
                   coll="TLS", smooth_angle=None))
# real axle via horizontal tube:
wl.pop()
wl.append(L.tube_between((-0.75, 0, 1.62), (0.75, 0, 1.62), 0.05, 0.05, n=8,
                         name="Green_WellAxle", mat=m_oak))
wl.append(L.tube_between((0.78, 0, 1.62), (0.78, 0.32, 1.50), 0.03, 0.03, n=6,
                         name="Green_WellCrank", mat=m_iron))
wl.append(L.tube_between((0.75, 0, 1.60), (0.75, 0, 1.10), 0.008, 0.008, n=4,
                         name="Green_WellRope", mat=L.new_mat(
                             "TLS_Mat_Rope", base=(0.35, 0.30, 0.22), rough=0.9)))
wl.append(L.cyl("Green_WellBucket", 0.115, 0.72, 0.90, n=10, r_top=0.13, mat=m_wood))
wl.append(torus := L.torus("Green_WellBucketBand", 0.125, 0.006, cz=0.78, n_path=14,
                           n_sec=6, mat=m_iron))
well = L.join_objects(wl, "Green_Well", coll="TLS")
well.location = (-3.2, -2.0, 0)
L.apply_transforms([well], location=True)
gr.append(well)
# 4. benches x2 (oak plank)
for i, bx in enumerate((-1.8, -0.4)):
    bn = []
    bn.append(L.box("bn_seat", 1.8, 0.32, 0.05, cz=0.45, mat=m_oak))
    bn.append(L.box("bn_back", 1.8, 0.05, 0.30, cy=-0.14, cz=0.70, mat=m_oak))
    bn.append(L.box("bn_leg1", 0.06, 0.30, 0.44, cx=-0.75, cz=0.22, mat=m_oak))
    bn.append(L.box("bn_leg2", 0.06, 0.30, 0.44, cx=0.75, cz=0.22, mat=m_oak))
    b = L.join_objects(bn, f"Green_Bench{i}", coll="TLS")
    b.location = (bx, 2.6 + i * 0.9, 0)
    b.rotation_euler = (0, 0, math.radians(4 + i * 3))
    L.apply_transforms([b], location=True)
    gr.append(b)
# 5. hand cart (bed + 2 spoked wheels + shafts)
ct = []
ct.append(L.box("ct_bed", 1.25, 0.72, 0.05, cz=0.42, mat=m_wood))
ct.append(L.box("ct_sideL", 1.25, 0.05, 0.18, cy=-0.36, cz=0.53, mat=m_wood))
ct.append(L.box("ct_sideR", 1.25, 0.05, 0.18, cy=0.36, cz=0.53, mat=m_wood))
for sx in (-1, 1):
    ct.append(L.torus(f"ct_wheel{sx}", 0.36, 0.035, cx=sx * 0.30, cy=-0.42, cz=0.36,
                      n_path=22, n_sec=8, mat=m_wood))
    for k in range(4):
        a = math.pi * k / 4
        dx, dy = math.cos(a) * 0.30, math.sin(a) * 0.30
        ct.append(L.tube_between((sx * 0.30, -0.42 - dx * 0.9, 0.36 - dy * 0.9),
                                 (sx * 0.30, -0.42 + dx * 0.9, 0.36 + dy * 0.9),
                                 0.02, 0.02, n=5, name=f"ct_spoke{sx}{k}", mat=m_wood))
for sx in (-1, 1):
    ct.append(L.box(f"ct_shaft{sx}", 1.0, 0.06, 0.06, cx=0.95, cy=sx * 0.22, cz=0.38,
                    rot_z=math.radians(sx * 3), mat=m_wood))
ct.append(L.box("ct_leg", 0.06, 0.06, 0.34, cx=-0.5, cy=0.3, cz=0.17, mat=m_wood))
cart = L.join_objects(ct, "Green_HandCart", coll="TLS")
cart.location = (1.5, 3.6, 0)
cart.rotation_euler = (0, 0, math.radians(-18))
L.apply_transforms([cart], location=True)
gr.append(cart)
ucx = [L.add_ucx_box(bpy.data.objects["Green_MarketCross"], shrink=0.85),
       L.add_ucx_box(bpy.data.objects["Green_Well"], shrink=0.9)]
finish_asset("TLS-ENV-040", gr, ucx, "tls_env_040_green.blend",
             dims_expected=[7.0, 6.5, 4.4],
             note="market cross + hawthorn (village tree, sparse leaves + berries) + well w/ windlass + 2 benches + hand cart")

# ================================================================ ENV-107 nature
print("[B4] TLS-ENV-107 nature kit ...")
L.reset_scene(); L.setup_units("TLS_ENV_107")
M._cache.clear()
m_bark2 = M.pbr("TLS_Mat_Nat_Bark", "bark", ao=0.92)
m_rock = M.pbr("TLS_Mat_Nat_Rock", "stone_wall", ao=0.95, base=(0.85, 0.85, 0.82))
m_peat = M.pbr("TLS_Mat_Nat_Peat", "moor_peat", ao=0.9)
m_wood2 = M.pbr("TLS_Mat_Nat_DeadWood", "oak", base=(0.6, 0.58, 0.52), ao=0.85)
m_grass = M.card("TLS_Mat_Nat_Grass", "grass")
m_fern = M.card("TLS_Mat_Nat_Fern", "fern")
m_water2 = L.new_mat("TLS_Mat_Nat_PoolWater", base=(0.13, 0.18, 0.19), rough=0.05)

nk = []
# 1. bare oak 6.5m (recursive)
rng = random.Random(47)
ob = []
branch((0, 0, 0.5), (0.02, -0.06, 1.0), 1.9, 0.24, 0, rng, m_bark2, ob,
       max_depth=5, spread=0.58, up_bias=0.18)
for i in range(6):
    a = TAU * i / 6
    ob.append(L.tube_between((0, 0, 0.55), (math.cos(a) * 0.34, math.sin(a) * 0.34, 0.04),
                             0.09, 0.12, n=6, name=f"Nat_OakRoot{i}", mat=m_bark2))
oak = L.join_objects(ob, "Nat_OakBare", coll="TLS")
nk.append(oak)
# 2. ash 5.5m straighter
rng2 = random.Random(1847 + 7)
as_ = []
branch((0, 0, 0.4), (0.0, 0.03, 1.0), 2.1, 0.18, 0, rng2, m_bark2, as_,
       max_depth=4, spread=0.42, up_bias=0.38)
ash = L.join_objects(as_, "Nat_Ash", coll="TLS")
ash.location = (7.0, 0, 0)
L.apply_transforms([ash], location=True)
nk.append(ash)
# 3. dead snag 3.8m
rng3 = random.Random(99)
sn = []
branch((0, 0, 0.2), (0.10, -0.05, 1.0), 1.5, 0.16, 0, rng3, m_wood2, sn,
       max_depth=3, spread=0.5, up_bias=0.05)
snag = L.join_objects(sn, "Nat_Snag", coll="TLS")
snag.location = (10.5, 0.5, 0)
L.apply_transforms([snag], location=True)
nk.append(snag)
# 4. hazel shrub (multi-stem 1.6m)
rng4 = random.Random(31)
hz = []
for i in range(7):
    a = TAU * i / 7 + 0.2
    branch((math.cos(a) * 0.05, math.sin(a) * 0.05, 0.05),
           (math.cos(a) * 0.45, math.sin(a) * 0.45, 1.0), 0.75, 0.035, 0, rng4,
           m_bark2, hz, max_depth=2, spread=0.5, up_bias=0.15)
hazl = L.join_objects(hz, "Nat_Hazel", coll="TLS")
hazl.location = (13.4, -0.6, 0)
L.apply_transforms([hazl], location=True)
nk.append(hazl)
# 5. grass tufts x4 + bracken x2 + reeds x2 (cards)
positions = [(4.2, 2.2), (8.6, -1.8), (12.0, 2.0), (15.4, -0.4)]
for i, (px, py) in enumerate(positions):
    cs = card_cross(f"Nat_Grass{i}", (px, py, 0.22), 0.55, m_grass)
    for c in cs:
        c.location[2] = 0.22
        L.apply_transforms([c], location=True)
    nk.extend(cs)
for i, (px, py) in enumerate([(5.8, -2.4), (11.2, 2.8)]):
    cs = card_cross(f"Nat_Bracken{i}", (px, py, 0.3), 0.7, m_fern)
    nk.extend(cs)
for i, (px, py) in enumerate([(16.8, 1.2), (17.8, -1.0)]):
    cs = card_cross(f"Nat_Reeds{i}", (px, py, 0.5), 1.0, m_grass)
    for c in cs:
        c.scale = (0.6, 0.6, 1.4)
        L.apply_transforms([c])
    nk.extend(cs)
# 6. rocks x3
nk.append(noisy_rock("Nat_RockS", 0.28, 0.24, 0.16, 5, m_rock))
r2 = noisy_rock("Nat_RockM", 0.55, 0.45, 0.30, 12, m_rock, detail=3)
r2.location = (19.4, 0.8, 0)
L.apply_transforms([r2], location=True)
nk.append(r2)
r3 = noisy_rock("Nat_RockL", 1.0, 0.8, 0.55, 23, m_rock, detail=4)
r3.location = (21.6, -1.4, 0)
L.apply_transforms([r3], location=True)
nk.append(r3)
# 7. peat bank with cut steps + standing water
pb = []
pb.append(L.box("Nat_PeatBankBody", 3.0, 1.2, 0.9, cz=0.45, mat=m_peat))
for i in range(4):
    pb.append(L.box(f"Nat_PeatCut{i}", 0.55, 1.24, 0.9 - i * 0.22,
                    cx=-1.0 + i * 0.68, cz=(0.9 - i * 0.22) / 2 + 0.001, mat=m_peat))
pb.append(L.box("Nat_PeatWater", 0.5, 1.1, 0.02, cx=-1.0, cz=0.88, mat=m_water2))
pb.append(L.box("Nat_PeatStack1", 0.45, 0.35, 0.25, cx=1.1, cy=-0.3, cz=0.125, mat=m_peat))
pb.append(L.box("Nat_PeatStack2", 0.45, 0.35, 0.25, cx=1.1, cy=0.05, cz=0.125, mat=m_peat))
pb.append(L.box("Nat_PeatStack3", 0.45, 0.35, 0.25, cx=1.1, cy=-0.12, cz=0.375, mat=m_peat))
peat = L.join_objects(pb, "Nat_PeatBank", coll="TLS")
peat.location = (24.8, 0, 0)
L.apply_transforms([peat], location=True)
nk.append(peat)
ucx = [L.add_ucx_box(oak, shrink=0.5), L.add_ucx_box(peat, shrink=0.95)]
finish_asset("TLS-ENV-107", nk, ucx, "tls_env_107_kit_nature.blend",
             dims_expected=[27.0, 3.6, 6.5],
             note="bare oak + ash + snag + hazel + grass/bracken/reed cards + rocks x3 + peat bank w/ standing water")

# ---------------------------------------------------------------- summary
L.write_json(os.path.join(STATS, "b4_green_batch.json"),
             {"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
              "seconds": round(time.time() - t0, 1), "assets": BATCH})
print(f"[B4] done in {time.time()-t0:.0f}s: {len(BATCH)} assets")
for b in BATCH:
    print(f"  - {b['asset']}: {b['tris']} tris")
