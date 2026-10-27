#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M4-B3 buildings batch:
  TLS-ENV-101 KIT-A Cottage (modular: plinth/wall/gable/door/window/roof/ridge/chimney/quoins)
  TLS-ENV-081 Boundary Stone Tŷ Uchel (W-10, opening scene)
  TLS-ENV-106 Graveyard Kit (NEW: headstones x5, chest tomb, mound, iron fence, lychgate, celtic cross)
  TLS-ENV-104 Church Kit (pew, pulpit, font, gothic column, altar, lectern)
  + assembly test scene (evidence render, not a registry asset)
Run: blender -b --python b3_buildings.py -- --root <repo>
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
SRC = os.path.join(ROOT, "02_Art", "blender", "source", "env")
FBX = os.path.join(ROOT, "02_Art", "exports", "fbx")
STATS = os.path.join(ROOT, "02_Art", "exports", "stats")
EV = os.path.join(ROOT, "reports", "M4_BATCH1_EVIDENCE")
os.makedirs(SRC, exist_ok=True)
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
    print(f"[B3] {asset_id}: {stats['totals']['verts']}v {stats['totals']['tris']}t "
          f"dims={stats['bbox_m']['dims']} pieces={len(objs)}")

def hinged(name, w, d, t, side, angle_deg, lift, mat, y0=0.0, zoff=0.0):
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    pts = []
    for (lx, ly, lz) in [(-w/2, -d/2, -t/2), (w/2, -d/2, -t/2), (w/2, d/2, -t/2),
                          (-w/2, d/2, -t/2), (-w/2, -d/2, t/2), (w/2, -d/2, t/2),
                          (w/2, d/2, t/2), (-w/2, d/2, t/2)]:
        x = lx + w / 2
        pts.append((side * x * ca, y0 + ly, lift + x * sa + lz + zoff))
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    u = [(0, 0), (1, 0), (1, 1), (0, 1)] * 2
    return L.new_mesh_obj(name, pts, faces, uvs=u, mat=mat)

def tapered_box(name, sx0, sy0, sz0, sx1, sy1, sz1, zbase, mat, taper=0.06,
                cx=0.0, cy=0.0, nseg=3):
    """Stone-wall box that tapers with height (batter), segmented for texture var."""
    objs = []
    for i in range(nseg):
        f0 = i / nseg; f1 = (i + 1) / nseg
        tx = sx0 + (sx1 - sx0) * f0; tx2 = sx0 + (sx1 - sx0) * f1
        ty = sy0 + (sy1 - sy0) * f0; ty2 = sy0 + (sy1 - sy0) * f1
        z0 = zbase + sz0 * f0; z1 = zbase + sz0 * f1
        objs.append(L.box(f"{name}_s{i}", tx, ty, z1 - z0 + 0.001,
                          cx=cx, cy=cy, cz=(z0 + z1) / 2, mat=mat))
    return objs

# ================================================================ ENV-101 KIT-A
print("[B3] TLS-ENV-101 cottage kit ...")
L.reset_scene(); L.setup_units("TLS_ENV_101")
M._cache.clear()
m_rubble = M.pbr("TLS_Mat_KitA_Rubble", "stone_wall", ao=0.9)
m_lime = M.pbr("TLS_Mat_KitA_Lime", "stone_wall", base=(1.25, 1.22, 1.12), ao=0.55)
m_slate = M.pbr("TLS_Mat_KitA_SlateRoof", "slate_roof", ao=0.85)
m_oak = M.pbr("TLS_Mat_KitA_Oak", "oak", ao=0.8)
m_iron = M.pbr("TLS_Mat_KitA_Iron", "iron", ao=0.8)

kit = []
# 1. plinth ring 7 x 5 m, h 0.45, battered rubble
for (px, py, pw, pd) in [(0, -2.5 + 0.15, 7.0, 0.3), (0, 2.5 - 0.15, 7.0, 0.3),
                          (-3.5 + 0.15, 0, 0.3, 5.0 - 0.6), (3.5 - 0.15, 0, 0.3, 5.0 - 0.6)]:
    ring = L.box(f"KitA_Plinth_{len(kit):02d}", pw, pd, 0.45, cx=px, cy=py, cz=0.225,
                 mat=m_rubble)
    kit.append(ring)
# 2. lime-washed wall panels (front 4.2m solid segment example; door/window are cut-ins)
kit.append(L.box("KitA_WallPanel_L", 4.2, 0.45, 1.75, cx=-1.4, cy=-2.28, cz=0.45 + 0.875,
                 mat=m_lime))
kit.append(L.box("KitA_WallPanel_R", 4.2, 0.45, 1.75, cx=1.4, cy=-2.28, cz=0.45 + 0.875,
                 mat=m_lime))
kit.append(L.box("KitA_WallBack", 7.0, 0.45, 1.75, cy=2.28, cz=1.325, mat=m_lime))
kit.append(L.box("KitA_WallSideL", 0.45, 5.0, 1.75, cx=-3.28, cz=1.325, mat=m_lime))
kit.append(L.box("KitA_WallSideR", 0.45, 5.0, 1.75, cx=3.28, cz=1.325, mat=m_lime))
# 3. gable ends (triangular prisms) above walls
for sx in (-1, 1):
    g = []
    gw = 0.45
    apex = 3.55
    # triangle: base at z=2.2 width 5.0 (y axis), apex z=3.55 at y=0
    pts = []
    for (yy, zz) in [(-2.5, 2.2), (2.5, 2.2), (0, apex)]:
        for dx in (-gw / 2, gw / 2):
            pts.append((sx * 3.28 + dx, yy, zz))
    faces = [(0, 1, 3, 2), (0, 2, 5, 4), (1, 0, 4, 5), (3, 1, 5, 3)]
    # simpler: build via 2 slabs
    ang = math.degrees(math.atan(1.35 / 2.5))
    kit.append(hinged(f"KitA_Gable_{sx}_a", 2.62, 0.45, 0.10, -sx, ang if sx == 1 else ang,
                      2.2, m_lime, y0=0.0))
    kit[-1].location = (0, 0, 0)
    # reposition: gable sits at side x=±3.28 spanning y -2.5..0 then mirrored piece
# NOTE: hinged() plates rotate about Y axis at x=0 -> for gable we need rotation
# about X axis spanning z. Rebuild gables properly with explicit verts:
for gx in (-3.28, 3.28):
    for sy in (-1, 1):
        # slab from wall top (z=2.2, y=sy*2.5) up to ridge (z=3.55, y=0)
        y0, y1 = sy * 2.5, 0.0
        z0, z1 = 2.2, 3.55
        pts = [(gx - 0.225, y0, z0), (gx + 0.225, y0, z0),
               (gx + 0.225, y1, z1), (gx - 0.225, y1, z1),
               (gx - 0.225, y0, z0 + 0.10), (gx + 0.225, y0, z0 + 0.10),
               (gx + 0.225, y1, z1 + 0.10), (gx - 0.225, y1, z1 + 0.10)]
        # thin slab thickness along slope normal approximated vertical here
        faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5),
                 (2, 3, 7, 6), (3, 0, 4, 7)]
        u = [(0, 0), (1, 0), (1, 1), (0, 1)] * 2
        kit.append(L.new_mesh_obj(f"KitA_Gable_{'L' if gx < 0 else 'R'}{'N' if sy < 0 else 'P'}",
                                  pts, faces, uvs=u, mat=m_lime))
# remove the two bogus hinged gables appended before (indices known: last 2 before loop)
# (they were appended with names KitA_Gable_-1_a / KitA_Gable_1_a)
for nm in ("KitA_Gable_-1_a", "KitA_Gable_1_a"):
    o = bpy.data.objects.get(nm)
    if o:
        kit.remove(o)
        L.get_coll("TLS").objects.unlink(o)
        bpy.data.objects.remove(o, do_unlink=True)
# 4. door frame + door (opening 0.95 x 1.85 at front center)
kit.append(L.box("KitA_DoorLintel", 1.30, 0.55, 0.22, cy=-2.28, cz=2.02,
                 mat=m_oak))
for s in (-1, 1):
    kit.append(L.box(f"KitA_DoorJamb{s}", 0.18, 0.5, 1.90, cx=s * 0.58, cy=-2.28,
                     cz=0.45 + 0.95, mat=m_oak))
kit.append(L.box("KitA_DoorThreshold", 1.2, 0.62, 0.09, cy=-2.28, cz=0.495, mat=m_rubble))
# door itself (slightly ajar): 5 planks + rails + hinges
door_parts = []
for i in range(5):
    door_parts.append(L.box(f"KitA_DoorPlank{i}", 0.176, 0.055, 1.80,
                            cx=-0.36 + i * 0.18, cy=0, cz=0.90, mat=m_oak))
door_parts.append(L.box("KitA_DoorRail1", 0.90, 0.06, 0.16, cy=0.028, cz=1.45, mat=m_oak))
door_parts.append(L.box("KitA_DoorRail2", 0.90, 0.06, 0.16, cy=0.028, cz=0.40, mat=m_oak))
for i in range(2):
    door_parts.append(L.box(f"KitA_DoorHinge{i}", 0.34, 0.015, 0.05,
                            cx=-0.25, cy=0.055, cz=0.5 + i * 0.8, mat=m_iron))
door_parts.append(L.box("KitA_DoorLatch", 0.10, 0.02, 0.16, cx=0.32, cy=0.055, cz=1.05,
                        mat=m_iron))
door = L.join_objects(door_parts, "KitA_Door", coll="TLS")
# ajar: rotate 12 deg about hinge edge x=-0.45
import bmesh
me = door.data
bm = bmesh.new(); bm.from_mesh(me)
for v in bm.verts:
    a = math.radians(12)
    hx = v.co.x + 0.45
    v.co.x = -0.45 + hx * math.cos(a)
    v.co.y = v.co.y - hx * math.sin(a)
bm.to_mesh(me); bm.free(); me.update()
door.location = (0, -2.28, 0.45)
L.apply_transforms([door], location=True)
kit.append(door)
# 5. window (north wall, 0.9 x 1.1, oak frame + mullion + sill + shutter)
win = []
win.append(L.box("KitA_WinFrame_T", 1.10, 0.16, 0.12, cz=1.98, mat=m_oak))
win.append(L.box("KitA_WinFrame_B", 1.10, 0.16, 0.12, cz=0.98, mat=m_oak))
win.append(L.box("KitA_WinFrame_L", 0.16, 0.16, 1.12, cx=-0.47, cz=1.48, mat=m_oak))
win.append(L.box("KitA_WinFrame_R", 0.16, 0.16, 1.12, cx=0.47, cz=1.48, mat=m_oak))
win.append(L.box("KitA_WinMullion", 0.07, 0.12, 0.98, cz=1.48, mat=m_oak))
win.append(L.box("KitA_WinSill", 1.26, 0.30, 0.07, cz=0.94, mat=m_oak))
# shutter ajar (boarded)
sh_pts = []
for (lx, ly, lz) in [(-0.42, -0.02, -0.50), (0.42, -0.02, -0.50), (0.42, -0.02, 0.50),
                      (-0.42, -0.02, 0.50), (-0.42, 0.04, -0.50), (0.42, 0.04, -0.50),
                      (0.42, 0.04, 0.50), (-0.42, 0.04, 0.50)]:
    a = math.radians(18)
    x = lx + 0.42
    sh_pts.append((-0.62 + x * math.cos(a), ly - x * math.sin(a), lz + 1.48))
faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
win.append(L.new_mesh_obj("KitA_WinShutter", sh_pts, faces,
                          uvs=[(0, 0), (1, 0), (1, 1), (0, 1)] * 2, mat=m_oak))
window = L.join_objects(win, "KitA_Window", coll="TLS")
window.location = (0, 2.28, 0)
L.apply_transforms([window], location=True)
kit.append(window)
# 6. roof panels (2 slopes 3.72 long x 5.3 wide, ~21 deg)
for sx in (-1, 1):
    kit.append(hinged(f"KitA_Roof{sx}", 3.72, 5.30, 0.10, sx, 20.9,
                      3.42, m_slate))
# 7. ridge
kit.append(L.box("KitA_Ridge", 0.28, 5.35, 0.12, cz=3.60, mat=m_slate))
# 8. chimney (stack at back side, top 4.15)
chim = []
for i in range(3):
    s = 1.0 - i * 0.06
    chim.append(L.box(f"KitA_Chim_s{i}", 0.78 * s, 0.78 * s, 0.75,
                      cx=2.2, cy=1.4, cz=2.6 + 0.375 + i * 0.75, mat=m_rubble))
chim.append(L.box("KitA_Chim_Cap", 0.95, 0.95, 0.14, cx=2.2, cy=1.4, cz=4.98, mat=m_rubble))
chim.append(L.box("KitA_Chim_Pot", 0.24, 0.24, 0.30, cx=2.2, cy=1.4, cz=5.20, mat=m_rubble))
kit.extend(chim)
# 9. quoins (corner stone sets)
for (qx, qy) in [(-3.4, -2.4), (3.4, -2.4), (-3.4, 2.4), (3.4, 2.4)]:
    for k in range(4):
        kit.append(L.box(f"KitA_Quoin_{qx}{qy}_{k}", 0.5, 0.5, 0.42,
                         cx=qx, cy=qy, cz=0.25 + k * 0.55, mat=m_rubble))
ucx = [L.add_ucx_box(bpy.data.objects["KitA_Door"], shrink=0.9),
       L.add_ucx_box(bpy.data.objects["KitA_Window"], shrink=0.8)]
finish_asset("TLS-ENV-101", kit, ucx, "tls_env_101_kit_cottage.blend",
             dims_expected=[7.3, 5.35, 5.35],
             note="modular cottage kit: plinth+5 wall panels+2 gables+door+window+2 roof+ridge+chimney+16 quoins")

# ================================================================ ENV-081 boundary stone
print("[B3] TLS-ENV-081 boundary stone ...")
L.reset_scene(); L.setup_units("TLS_ENV_081")
M._cache.clear()
m_stone2 = M.pbr("TLS_Mat_Boundary_Stone", "stone_wall", ao=0.9, base=(0.9, 0.9, 0.88))
bs = []
# weathered square-section pillar tapering, 1.35 tall
prof = [(0.11, 0.0), (0.105, 0.3), (0.10, 0.8), (0.096, 1.15), (0.10, 1.30),
        (0.085, 1.35)]
rings = []
for r, z in prof:
    pts = [(r * math.cos(TAU * i / 4 + math.pi / 4), r * math.sin(TAU * i / 4 + math.pi / 4), z)
           for i in range(4)]
    rings.append({"verts": pts})
v, f, u = L.loft_rings(rings, closed_loop=True, cap_bottom=True, cap_top=True)
bs.append(L.new_mesh_obj("Boundary_Pillar", v, f, uvs=u, mat=m_stone2))
# worn cap
bs.append(L.box("Boundary_Cap", 0.26, 0.26, 0.07, cz=1.385, rot_z=math.radians(8),
                mat=m_stone2))
# two weathered recessed letter panels (carved bands - geometry not fake text)
for i, z in enumerate((0.75, 1.0)):
    bs.append(L.box(f"Boundary_Letter{i}", 0.028, 0.115, 0.16, cy=-0.096, cz=z,
                    mat=m_stone2, rot_z=math.radians(i * 4)))
# base rubble plinth
bs.append(L.box("Boundary_Base", 0.5, 0.5, 0.18, cz=0.09, rot_z=math.radians(6),
                mat=m_stone2))
ucx = [L.add_ucx_box(bs[0])]
finish_asset("TLS-ENV-081", bs, ucx, "tls_env_081_boundary_stone.blend",
             dims_expected=[0.52, 0.52, 1.46],
             note="Tŷ Uchel - Josiah's death spot, opening scene; 2 weathered letter panels")

# ================================================================ ENV-106 graveyard kit
print("[B3] TLS-ENV-106 graveyard kit ...")
L.reset_scene(); L.setup_units("TLS_ENV_106")
M._cache.clear()
m_gslate = M.pbr("TLS_Mat_Grave_Slate", "slate", ao=0.92)
m_grubble = M.pbr("TLS_Mat_Grave_Rubble", "stone_wall", ao=0.9)
m_giron = M.pbr("TLS_Mat_Grave_Iron", "iron", ao=0.85)
m_goak = M.pbr("TLS_Mat_Grave_Oak", "oak", ao=0.85)
m_earth = M.pbr("TLS_Mat_Grave_Earth", "moor_peat", ao=0.85)

gk = []
# headstone helper
def headstone(name, w, h, t, style, lean=0.0, base_w=None):
    parts = []
    if style == "round":
        n = 10
        pts = []
        for i in range(n + 1):
            a = math.pi * i / n
            pts.append((-w / 2 + w * (i / n), 0, 0))
        # build via lathe-like: body + half-cylinder top
        parts.append(L.box(f"{name}_body", w, t, h - w / 2, cz=(h - w / 2) / 2,
                           mat=m_gslate))
        lo = L.ellipse_ring(0, 0, 0, 0, 0, 0)
        rings_top = []
        n2 = 8
        for j in range(n2 + 1):
            a = math.pi * j / n2
            r = w / 2
            rings_top.append({"verts": [(r * math.cos(a), -t / 2, h - w / 2 + r * math.sin(a)),
                                        (r * math.cos(a), t / 2, h - w / 2 + r * math.sin(a))]})
        # build half dome via loft of 2-point rings
        v2, f2, u2 = L.loft_rings(rings_top, closed_loop=False, cap_bottom=False,
                                  cap_top=False)
        parts.append(L.new_mesh_obj(f"{name}_top", v2, f2, uvs=u2, mat=m_gslate))
    elif style == "square":
        parts.append(L.box(f"{name}_body", w, t, h, cz=h / 2, mat=m_gslate))
        parts.append(L.box(f"{name}_cap", w + 0.06, t + 0.04, 0.06, cz=h + 0.03,
                           mat=m_gslate))
    elif style == "cross":
        parts.append(L.box(f"{name}_body", w * 0.4, t, h * 0.62, cz=h * 0.31, mat=m_gslate))
        parts.append(L.box(f"{name}_arm", w * 1.7, t, w * 0.4, cz=h * 0.60, mat=m_gslate))
        parts.append(L.box(f"{name}_cap", w * 0.5, t + 0.02, 0.05, cz=h * 0.62 + h * 0.31,
                           mat=m_gslate))
    elif style == "pediment":
        parts.append(L.box(f"{name}_body", w, t, h - 0.12, cz=(h - 0.12) / 2, mat=m_gslate))
        pts = []
        gw, gh = w / 2, 0.12
        for (xx, zz) in [(-gw, 0), (0, gh), (gw, 0)]:
            pts.append((xx, -t / 2, h - 0.12 + zz))
        for (xx, zz) in [(-gw, 0), (0, gh), (gw, 0)]:
            pts.append((xx, t / 2, h - 0.12 + zz))
        faces_t = [(0, 2, 1), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)]
        parts.append(L.new_mesh_obj(f"{name}_top", pts, faces_t,
                                    uvs=[(0, 0)] * 6, mat=m_gslate))
    # plinth
    parts.append(L.box(f"{name}_plinth", (base_w or w + 0.16), t + 0.10, 0.14,
                       cz=0.07, mat=m_grubble))
    ob = L.join_objects(parts, name, coll="TLS")
    if lean:
        import bmesh as _bm
        me = ob.data
        bm2 = _bm.new(); bm2.from_mesh(me)
        a = math.radians(lean)
        for vv in bm2.verts:
            zz = vv.co.z
            vv.co.x += math.sin(a) * zz
            vv.co.z *= math.cos(a)
        bm2.to_mesh(me); bm2.free(); me.update()
    return ob

gk.append(headstone("Grave_HS_Round", 0.55, 0.95, 0.08, "round", lean=4))
gk.append(headstone("Grave_HS_Square", 0.60, 1.05, 0.09, "square", lean=-3))
gk.append(headstone("Grave_HS_Cross", 0.16, 1.45, 0.09, "cross", lean=2))
gk.append(headstone("Grave_HS_Pediment", 0.62, 1.10, 0.09, "pediment", lean=-6))
gk.append(headstone("Grave_HS_SmallRound", 0.40, 0.62, 0.07, "round", lean=8))
# chest tomb (0.7 x 1.9 x 0.75)
ct = []
ct.append(L.box("Grave_ChestTombBase", 0.95, 2.10, 0.16, cz=0.08, mat=m_grubble))
ct.append(L.box("Grave_ChestTombBody", 0.72, 1.86, 0.55, cz=0.16 + 0.275, mat=m_gslate))
for (px, py) in [(-0.32, -0.8), (0.32, -0.8), (-0.32, 0.8), (0.32, 0.8)]:
    ct.append(L.box(f"Grave_ChestPanel_{px}{py}", 0.04, 0.5, 0.34, cx=px, cy=py,
                    cz=0.60, mat=m_gslate))
ct.append(L.box("Grave_ChestTombLid", 0.92, 2.04, 0.14, cz=0.87, mat=m_gslate))
gk.extend(ct)
# fresh grave mound
gk.append(L.new_mesh_obj("Grave_Mound",
                         [(-0.45, -1.0, 0), (0.45, -1.0, 0), (0.45, 1.0, 0), (-0.45, 1.0, 0),
                          (-0.28, -0.7, 0.22), (0.28, -0.7, 0.22), (0.28, 0.7, 0.22),
                          (-0.28, 0.7, 0.22), (0, 0, 0.30)],
                         [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5),
                          (2, 3, 7, 6), (3, 0, 4, 7), (8, 5, 4), (8, 6, 5), (8, 7, 6), (8, 4, 7)],
                         uvs=[(0, 0), (1, 0), (1, 1), (0, 1)] * 2 + [(0.5, 0.5)],
                         mat=m_earth))
# iron fence post + rail section (2m)
gk.append(L.cyl("Grave_FencePost", 0.022, 0, 1.05, n=8, mat=m_giron))
gk.append(L.torus("Grave_FenceKnob", 0.030, 0.012, cz=1.08, n_path=14, n_sec=8,
                  mat=m_giron))
for i, z in enumerate((0.25, 0.85)):
    gk.append(L.box(f"Grave_FenceRail{i}", 2.0, 0.035, 0.035, cx=1.0, cz=z, mat=m_giron))
# spear finial on post
gk.append(L.new_mesh_obj("Grave_FenceFinial",
                         [(0, 0, 1.05), (0.02, 0, 1.10), (0, 0.02, 1.10), (-0.02, 0, 1.10),
                          (0, -0.02, 1.10), (0, 0, 1.17)],
                         [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1), (5, 2, 1), (5, 3, 2),
                          (5, 4, 3), (5, 1, 4)],
                         uvs=[(0, 0)] * 6, mat=m_giron))
# lychgate: 2 oak posts + gable roof (opening scene of graveyard)
ly = []
for sx in (-1, 1):
    ly.append(L.box(f"Grave_LychPost{sx}", 0.16, 0.16, 2.2, cx=sx * 0.85, cz=1.1,
                    mat=m_goak))
ly.append(hinged("Grave_LychRoofL", 1.25, 2.0, 0.06, -1, 28, 2.25, m_goak))
ly.append(hinged("Grave_LychRoofR", 1.25, 2.0, 0.06, 1, 28, 2.25, m_goak))
ly.append(L.box("Grave_LychRidge", 0.16, 2.05, 0.08, cz=2.84, mat=m_goak))
for sx in (-1, 1):
    ly.append(L.box(f"Grave_LychBrace{sx}", 0.08, 0.08, 0.9, cx=sx * 0.72, cz=1.9,
                    rot_z=sx * 0.5, mat=m_goak))
gk.extend(ly)
# celtic cross (ringed)
cc = []
cc.append(L.box("Grave_CelticBase", 0.6, 0.35, 0.22, cz=0.11, mat=m_grubble))
cc.append(L.box("Grave_CelticStem", 0.16, 0.14, 1.5, cz=0.22 + 0.75, mat=m_gslate))
cc.append(L.box("Grave_CelticArm", 0.72, 0.14, 0.18, cz=1.52, mat=m_gslate))
cc.append(L.torus("Grave_CelticRing", 0.19, 0.035, cz=1.38, n_path=28, n_sec=10,
                  mat=m_gslate))
gk.extend(cc)
ucx = [L.add_ucx_box(gk[2]), L.add_ucx_box(bpy.data.objects["Grave_ChestTombBody"])]
finish_asset("TLS-ENV-106", gk, ucx, "tls_env_106_kit_graveyard.blend",
             dims_expected=[4.7, 2.3, 2.9],
             note="5 headstones + chest tomb + mound + iron fence set + lychgate + celtic cross")

# ================================================================ ENV-104 church kit
print("[B3] TLS-ENV-104 church kit ...")
L.reset_scene(); L.setup_units("TLS_ENV_104")
M._cache.clear()
m_coak = M.pbr("TLS_Mat_Church_Oak", "oak", ao=0.82)
m_cstone = M.pbr("TLS_Mat_Church_Stone", "stone_wall", ao=0.9)
m_cslate = M.pbr("TLS_Mat_Church_Slate", "slate", ao=0.9)

ck = []
# pew 2.4m
pw = []
pw.append(L.box("Church_PewSeat", 2.4, 0.34, 0.045, cz=0.46, mat=m_coak))
pw.append(L.box("Church_PewBack", 2.4, 0.05, 0.55, cy=-0.155, cz=0.75, mat=m_coak))
pw.append(L.box("Church_PewFront", 2.4, 0.05, 0.42, cy=0.155, cz=0.67, mat=m_coak))
for i in range(3):
    pw.append(L.box(f"Church_PewEnd{i}", 0.05, 0.36, 0.92, cx=-1.2 + i * 1.2, cz=0.46,
                    mat=m_coak))
pew = L.join_objects(pw, "Church_Pew", coll="TLS")
ck.append(pew)
# kneeler rail
ck.append(L.box("Church_PewKneeler", 2.3, 0.05, 0.07, cy=-0.19, cz=0.16, mat=m_coak))
# pulpit (hexagonal, 1.1 tall)
pl = []
n = 6
for i in range(n):
    a = TAU * i / n
    pl.append(L.box(f"Church_PulpitPanel{i}", 0.55, 0.05, 0.75,
                    cx=math.cos(a) * 0.48, cy=math.sin(a) * 0.48, cz=1.10,
                    rot_z=a + math.pi / 2, mat=m_coak))
pl.append(L.cyl("Church_PulpitStem", 0.16, 0.15, 0.72, n=8, mat=m_cstone))
pl.append(L.cyl("Church_PulpitBase", 0.42, 0.0, 0.15, n=8, mat=m_cstone))
pl.append(L.cyl("Church_PulpitRail", 0.56, 1.48, 1.48, n=6, r_top=0.56, mat=m_coak,
                cap=False))
# reading desk slope
pl.append(hinged("Church_PulpitDesk", 0.42, 0.30, 0.04, 1, 22, 1.52, m_coak))
pulpit = L.join_objects(pl, "Church_Pulpit", coll="TLS")
ck.append(pulpit)
# font: octagonal bowl on stem
fn = []
bowl = L.cyl("Church_FontBowl", 0.36, 0.72, 0.92, n=8, r_top=0.30, mat=m_cstone)
fn.append(bowl)
fn.append(L.cyl("Church_FontStem", 0.14, 0.18, 0.72, n=8, mat=m_cstone))
fn.append(L.cyl("Church_FontBase", 0.34, 0.0, 0.18, n=8, r_top=0.26, mat=m_cstone))
fn.append(L.cyl("Church_FontWater", 0.30, 0.78, 0.80, n=8, r_top=0.30,
                mat=L.new_mat("TLS_Mat_FontWater", base=(0.35, 0.42, 0.45), rough=0.08)))
font = L.join_objects(fn, "Church_Font", coll="TLS")
ck.append(font)
# gothic column (0.30 dia, 3.2 tall with base+capital)
gc = []
gc.append(L.cyl("Church_ColShaft", 0.13, 0.35, 2.75, n=12, mat=m_cstone))
gc.append(L.cyl("Church_ColBase", 0.21, 0.0, 0.35, n=12, r_top=0.16, mat=m_cstone))
gc.append(L.cyl("Church_ColCapital", 0.20, 2.75, 3.10, n=12, r_top=0.15, mat=m_cstone))
col = L.join_objects(gc, "Church_Column", coll="TLS")
ck.append(col)
# altar table
at = []
at.append(L.box("Church_AltarTop", 1.65, 0.75, 0.07, cz=0.93, mat=m_coak))
for (ax, ay) in [(-0.72, -0.28), (0.72, -0.28), (-0.72, 0.28), (0.72, 0.28)]:
    at.append(L.box(f"Church_AltarLeg_{ax}{ay}", 0.09, 0.09, 0.90, cx=ax, cy=ay,
                    cz=0.45, mat=m_coak))
at.append(L.box("Church_AltarApron", 1.5, 0.05, 0.18, cy=-0.30, cz=0.80, mat=m_coak))
altar = L.join_objects(at, "Church_Altar", coll="TLS")
ck.append(altar)
# lectern with book
lc = []
lc.append(L.cyl("Church_LecternStem", 0.07, 0.0, 1.05, n=8, r_top=0.05, mat=m_cstone))
lc.append(L.cyl("Church_LecternBase", 0.25, 0.0, 0.08, n=8, r_top=0.18, mat=m_cstone))
lc.append(hinged("Church_LecternDesk", 0.40, 0.52, 0.035, 1, 35, 1.10, m_coak))
lc.append(L.box("Church_LecternBook", 0.30, 0.42, 0.045, cz=1.20, mat=m_coak))
lect = L.join_objects(lc, "Church_Lectern", coll="TLS")
ck.append(lect)
ucx = [L.add_ucx_box(bpy.data.objects["Church_Pew"], shrink=0.9),
       L.add_ucx_box(bpy.data.objects["Church_Altar"])]
finish_asset("TLS-ENV-104", ck, ucx, "tls_env_104_kit_church.blend",
             dims_expected=[2.5, 2.3, 3.3],
             note="pew+desk rail, hex pulpit, octagonal font, gothic column, altar, lectern")

# ---------------------------------------------------------------- summary
L.write_json(os.path.join(STATS, "b3_buildings_batch.json"),
             {"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
              "seconds": round(time.time() - t0, 1), "assets": BATCH})
print(f"[B3] done in {time.time()-t0:.0f}s: {len(BATCH)} assets")
for b in BATCH:
    print(f"  - {b['asset']}: {b['tris']} tris")
