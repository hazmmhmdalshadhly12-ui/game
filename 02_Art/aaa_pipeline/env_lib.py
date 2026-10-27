#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE LAST SIN - Environment module builders v2.
Displacement-sculpted stone/wood/slate modules (numpy heightfields on grids),
assemblable pieces with matched module size 2.4m, real UVs + PBR textures.
"""
import math
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sculpt_lib import mesh_obj, fbm3, value_noise3
import textures_v2 as tx

TAU = math.pi * 2.0

# ---------------------------------------------------------------- heightfields
def rubble_stone_hf(w=2.4, h=2.2, courses=8, seed=13, nx=96, nz=88, edge_relief=0.5):
    """Coursed rubble wall height displacement (meters). Returns (hf (nz,nx), mask)."""
    u = np.linspace(0, w, nx)
    v = np.linspace(0, h, nz)
    UU, VV = np.meshgrid(u, v)
    rng = np.random.default_rng(seed)
    course_h = h / courses
    row = np.floor(VV / course_h).astype(int)
    hf = np.zeros((nz, nx))
    stone_lines = {}
    edges = {}
    for r in range(courses + 1):
        n = rng.integers(4, 7)
        e = np.sort(rng.uniform(0, w, n))
        e = np.concatenate([[0.0], e, [w]])
        edges[r] = e
    # vertical joints per row
    joint = np.zeros_like(hf)
    for r in range(courses):
        m = (row == r)
        e = edges[r]
        for k in range(1, len(e) - 1):
            d = np.abs(UU - e[k])
            joint[m] = np.maximum(joint[m], np.exp(-(d[m] / 0.018) ** 2))
    # horizontal mortar
    dv = np.abs((VV / course_h) - np.round(VV / course_h))
    horiz = np.exp(-(dv / 0.10) ** 2)
    # stone bulge per cell (hash by row+nearest edge index)
    cid = np.zeros((nz, nx), int)
    for r in range(courses):
        m = (row == r)
        e = edges[r]
        cid[m] = np.digitize(UU[m], e) + r * 97
    hcell = (cid * 2654435761 % 1000) / 1000.0
    bulge = (0.5 + 0.9 * hcell)
    # per-stone rounding: distance to stone center approx via joint+horiz
    inset = np.clip(1 - 1.4 * np.maximum(joint, horiz), 0, 1)
    hf = 0.028 * bulge * (inset ** 0.7)
    # mortar recess
    hf -= 0.010 * np.maximum(joint, horiz)
    # weathering noise + edge relief
    hf += 0.006 * (fbm3(UU * 14, VV * 14, 0.5, 3, seed) - 0.5)
    hf += edge_relief * 0.004 * (fbm3(UU * 60, VV * 60, 0.5, 2, seed + 1) - 0.5)
    return hf, None

def slate_roof_hf(w=2.4, d=1.2, rows=12, seed=4, nx=72, ny=40):
    u = np.linspace(0, w, nx)
    v = np.linspace(0, d, ny)
    UU, VV = np.meshgrid(u, v)
    rng = np.random.default_rng(seed)
    row_h = d / rows
    rowi = np.floor(VV / row_h).astype(int)
    off = (rowi % 2) * (w / 6)
    tile_w = w / 5
    cu = ((UU + off) % tile_w) / tile_w
    edge_u = np.exp(-(cu / 0.06) ** 2) + np.exp(-((1 - cu) / 0.06) ** 2)
    edge_v = np.exp(-((VV % row_h) / (row_h * 0.14)) ** 2)
    hf = 0.006 * np.sin(rowi * 2.3 + UU * 3) + 0.004 * (fbm3(UU * 8, VV * 8, 0.3, 2, seed) - 0.5)
    hf -= 0.010 * np.maximum(edge_u, edge_v)
    hf += 0.002 * np.clip(1 - (VV / d), 0, 1)  # thicker at bottom lap
    return hf

def wood_plank_hf(w=1.0, h=2.1, planks=5, seed=6, nx=40, nz=84):
    u = np.linspace(0, w, nx)
    v = np.linspace(0, h, nz)
    UU, VV = np.meshgrid(u, v)
    ph = h / planks
    pi_ = np.floor(VV / ph)
    gap = np.exp(-((np.abs((VV / ph) % 1 - 0.5)) / 0.06) ** 2)
    grain = fbm3(UU * 40, VV * 4, 0.3, 3, seed)
    hf = 0.0035 * grain - 0.006 * gap
    hf += 0.0015 * np.sin(UU * 90 + pi_ * 7)
    return hf

def grid_mesh(name, w, h, hf, mat=None, coll=None, plane="xz", base_off=0.0,
              thickness=0.12, solid=True, uv_scale=(1, 1)):
    """Build a displaced grid slab in XZ (wall) or XY (floor) plane."""
    nz, nx = hf.shape
    verts, uvs = [], []
    for j in range(nz):
        for i in range(nx):
            uvs.append((i / (nx - 1), j / (nz - 1)))
    uvs = np.asarray(uvs)
    F = np.linspace(0, 1, nx), np.linspace(0, 1, nz)
    FX, FZ = np.meshgrid(np.linspace(0, 1, nx), np.linspace(0, 1, nz))
    if plane == "xz":
        px = FX * w
        py = np.full_like(px, base_off)
        pz = FZ * h
        verts = np.stack([px.ravel(), py.ravel(), pz.ravel()], -1)
        verts[:, 1] -= hf.ravel()
    else:
        px = FX * w
        py = FZ * h
        pz = np.full_like(px, base_off) + hf
        verts = np.stack([px.ravel(), py.ravel(), pz.ravel()], -1)
    faces = []
    for j in range(nz - 1):
        for i in range(nx - 1):
            a = j * nx + i; b = a + 1; c = a + nx + 1; d = a + nx
            faces.append((a, b, c, d))
    ob = mesh_obj(name, verts, faces, uvs=uvs, mat=mat, coll=coll)
    if solid and thickness > 0:
        m = ob.modifiers.new("sol", 'SOLIDIFY')
        m.thickness = thickness
        m.offset = -1.0 if plane == "xz" else -1.0
    return ob

# ---------------------------------------------------------------- modules
def build_stone_wall_module(kind, coll, mats, seed=13):
    """kind: straight | end | corner | door | window. Module 2.4 long x 2.2 high."""
    W, H = 2.4, 2.2
    mat = mats["stone"]
    if kind == "straight":
        hf, _ = rubble_stone_hf(seed=seed)
        return grid_mesh(f"TLS_Env_Wall_{kind}", W, H, hf, mat, coll, thickness=0.24)
    if kind == "end":
        hf, _ = rubble_stone_hf(seed=seed)
        ob = grid_mesh(f"TLS_Env_Wall_{kind}", W, H, hf, mat, coll, thickness=0.24)
        # end pier: box column
        pier = _box_bevel("TLS_Env_Wall_EndPier", (0.34, 0.34, H), (0, 0.17, H / 2), mats["stone"], coll, seed)
        return [ob, pier]
    if kind == "corner":
        hf, _ = rubble_stone_hf(w=2.4, h=H, seed=seed)
        a = grid_mesh(f"TLS_Env_Wall_CornerA", W, H, hf, mat, coll, thickness=0.24)
        hf2, _ = rubble_stone_hf(w=2.4, h=H, seed=seed + 5)
        b = grid_mesh(f"TLS_Env_Wall_CornerB", W, H, hf2, mat, coll, thickness=0.24)
        b.rotation_euler = (0, 0, math.pi / 2)
        b.location = (0.12, 0.12, 0)
        quoins = [_box_bevel(f"TLS_Env_Quoin{i}", (0.30, 0.30, 0.36), (0.06, 0.06, 0.18 + i * 0.38), mats["stone"], coll, seed + i) for i in range(5)]
        return [a, b] + quoins
    if kind == "door":
        # wall with 0.95 x 2.0 opening: two side strips + lintel
        side_w = (W - 0.95) / 2
        hfs = []
        parts = []
        for si, sx in ((0, 0), (1, 1)):
            hf, _ = rubble_stone_hf(w=side_w, h=H, seed=seed + si, nx=36, nz=88)
            ob = grid_mesh(f"TLS_Env_Wall_DoorSide{si}", side_w, H, hf, mat, coll, thickness=0.24)
            ob.location = (sx * (side_w + 0.95), 0, 0)
            parts.append(ob)
        lintel_hf, _ = rubble_stone_hf(w=0.95 + 0.2, h=0.24, courses=1, seed=seed + 9, nx=40, nz=10)
        lin = grid_mesh("TLS_Env_Wall_DoorLintel", 1.15, 0.24, lintel_hf, mats["stone"], coll, thickness=0.24)
        lin.location = (side_w - 0.10, 0, H - 0.24)
        parts.append(linel := lin)
        # timber lintel
        tl = _box_bevel("TLS_Env_Wall_DoorTimber", (1.15, 0.16, 0.10), (side_w + 0.475, 0, H - 0.30), mats["oak"], coll, seed)
        parts.append(tl)
        return parts
    if kind == "window":
        side_w = (W - 0.80) / 2
        parts = []
        for si in (0, 1):
            hf, _ = rubble_stone_hf(w=side_w, h=H, seed=seed + si, nx=30, nz=88)
            ob = grid_mesh(f"TLS_Env_Wall_WinSide{si}", side_w, H, hf, mat, coll, thickness=0.24)
            ob.location = (si * (side_w + 0.80), 0, 0)
            parts.append(ob)
        # under sill + over lintel strips
        for nm, z0, hh, sd in (("Sill", 0.90, 0.26, seed + 3), ("Head", 1.62, H - 1.62, seed + 4)):
            hf, _ = rubble_stone_hf(w=0.80, h=hh, courses=max(1, int(hh / 0.28)), seed=sd, nx=30, nz=max(8, int(hh * 40)))
            ob = grid_mesh(f"TLS_Env_Wall_Win{nm}", 0.80, hh, hf, mat, coll, thickness=0.24)
            ob.location = (side_w, 0, z0)
            parts.append(ob)
        sill = _box_bevel("TLS_Env_Wall_WinSillSlab", (1.04, 0.30, 0.07), (W / 2, 0.02, 0.94), mats["stone"], coll, seed)
        parts.append(sill)
        return parts
    raise ValueError(kind)

def _box_bevel(name, size, loc, mat, coll, seed=1, segments=2):
    import bpy
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    be = ob.modifiers.new("bev", 'BEVEL')
    be.width = 0.012
    be.segments = segments
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier="bev")
    # weathering noise displacement
    import bmesh
    me = ob.data
    vs = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", vs)
    vs = vs.reshape(-1, 3)
    n = fbm3(vs[:, 0] * 9 + seed, vs[:, 1] * 9, vs[:, 2] * 9, 3, seed)
    l = np.linalg.norm(vs - np.array(loc), axis=1, keepdims=True) + 1e-9
    vs = vs + (vs - np.array(loc)) / l * ((n - 0.5) * 0.006)[:, None]
    me.vertices.foreach_set("co", vs.ravel())
    me.update()
    ob.data.materials.append(mat)
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    coll.objects.link(ob)
    return ob

def build_roof_module(coll, mats, seed=4):
    hf = slate_roof_hf(seed=seed)
    ob = grid_mesh("TLS_Env_Roof_Slope", 2.4, 1.5, hf, mats["slate"], coll, plane="xz",
                   thickness=0.06, uv_scale=(1, 1))
    ob.rotation_euler = (-math.radians(38), 0, 0)
    return ob

def build_door(coll, mats, seed=6):
    parts = []
    hf = wood_plank_hf(w=0.92, h=1.98, planks=5, seed=seed)
    door = grid_mesh("TLS_Env_Door", 0.92, 1.98, hf, mats["oak"], coll, plane="xz",
                     thickness=0.05)
    parts.append(door)
    # ledges + braces
    for i, z in enumerate((0.28, 1.70)):
        parts.append(_box_bevel(f"TLS_Env_DoorLedge{i}", (0.92, 0.03, 0.14), (0, 0.035, z), mats["oak"], coll, seed + i))
    # iron hinges + ring handle
    for i, z in enumerate((0.35, 1.62)):
        parts.append(_box_bevel(f"TLS_Env_DoorHinge{i}", (0.34, 0.02, 0.07), (-0.25, 0.05, z), mats["iron"], coll, seed + 10 + i))
    import bpy
    bpy.ops.mesh.primitive_torus_add(major_radius=0.055, minor_radius=0.008,
                                     location=(0.30, 0.05, 1.05), rotation=(math.pi / 2, 0, 0))
    ring = bpy.context.active_object
    ring.name = "TLS_Env_DoorRing"
    ring.data.materials.append(mats["iron"])
    for c in list(ring.users_collection):
        c.objects.unlink(ring)
    coll.objects.link(ring)
    parts.append(ring)
    return parts

def build_window(coll, mats, seed=8):
    parts = []
    # frame
    for nm, sz, loc in (("L", (0.07, 0.14, 1.10), (-0.365, 0, 1.30)),
                        ("R", (0.07, 0.14, 1.10), (0.365, 0, 1.30)),
                        ("T", (0.80, 0.14, 0.07), (0, 0, 1.885)),
                        ("B", (0.80, 0.14, 0.07), (0, 0, 0.715))):
        parts.append(_box_bevel(f"TLS_Env_WinFrame{nm}", sz, loc, mats["oak"], coll, seed))
    # mullion + transom
    parts.append(_box_bevel("TLS_Env_WinMullion", (0.05, 0.12, 1.10), (0, 0, 1.30), mats["oak"], coll, seed + 1))
    parts.append(_box_bevel("TLS_Env_WinTransom", (0.73, 0.12, 0.05), (0, 0, 1.42), mats["oak"], coll, seed + 2))
    # glass panes (slightly inset, glass material)
    import bpy
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, -0.02, 1.30), rotation=(math.pi / 2, 0, 0))
    gl = bpy.context.active_object
    gl.name = "TLS_Env_WinGlass"
    gl.scale = (0.68, 0.55, 1)
    gm = bpy.data.materials.get("M_TLS_Glass") or _mk_glass()
    gl.data.materials.append(gm)
    for c in list(gl.users_collection):
        c.objects.unlink(gl)
    coll.objects.link(gl)
    parts.append(gl)
    # shutter (left, louvered slats)
    for i in range(7):
        parts.append(_box_bevel(f"TLS_Env_ShutterSlat{i}", (0.30, 0.015, 0.10),
                                (-0.62, -0.05, 0.85 + i * 0.13), mats["oak"], coll, seed + 20 + i, segments=1))
    parts.append(_box_bevel("TLS_Env_ShutterFrameL", (0.03, 0.03, 1.0), (-0.76, -0.05, 1.25), mats["oak"], coll, seed + 40))
    parts.append(_box_bevel("TLS_Env_ShutterFrameR", (0.03, 0.03, 1.0), (-0.48, -0.05, 1.25), mats["oak"], coll, seed + 41))
    return parts

def _mk_glass():
    import bpy
    m = bpy.data.materials.new("M_TLS_Glass")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.75, 0.78, 0.76, 1)
    b.inputs["Roughness"].default_value = 0.25
    if "Transmission Weight" in b.inputs:
        b.inputs["Transmission Weight"].default_value = 0.85
    return m

def build_chimney(coll, mats, seed=11):
    parts = []
    parts.append(_box_bevel("TLS_Env_ChimneyStack", (0.62, 0.62, 1.6), (0, 0, 0.8), mats["stone"], coll, seed))
    parts.append(_box_bevel("TLS_Env_ChimneyCap", (0.74, 0.74, 0.12), (0, 0, 1.66), mats["stone"], coll, seed + 1))
    import bpy
    bpy.ops.mesh.primitive_cylinder_add(radius=0.10, depth=0.34, location=(0, 0, 1.88))
    pot = bpy.context.active_object
    pot.name = "TLS_Env_ChimneyPot"
    pot.data.materials.append(mats.get("terracotta") or mats["stone"])
    for c in list(pot.users_collection):
        c.objects.unlink(pot)
    coll.objects.link(pot)
    parts.append(pot)
    return parts

def build_rock(name, scale, seed, coll, mats):
    S, P = 36, 26
    import sculpt_lib as SL
    dirs, T, PH = SL.sphere_grid(S, P)
    rng = np.random.default_rng(seed)
    E = np.array([0.55, 0.42, 0.34]) * scale
    p = dirs * E[None, None, :]
    # flatten bottom
    p[:, :, 2] = np.clip(p[:, :, 2], -E[2] * 0.35, None)
    d = p.reshape(-1, 3)
    n = fbm3(d[:, 0] * 3.2 + seed, d[:, 1] * 3.2, d[:, 2] * 3.2, 4, seed) - 0.5
    n2 = fbm3(d[:, 0] * 11, d[:, 1] * 11, d[:, 2] * 11, 3, seed + 1) - 0.5
    r = np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    d = d + (d / r) * ((n * 0.10 + n2 * 0.035) * scale)[:, None]
    faces = SL.quad_faces(S, P)
    ob = mesh_obj(name, d, faces, mat=mats["rock"], coll=coll)
    ob.scale = (1, 0.8 + rng.uniform(0, 0.4), 1)
    return ob

def build_tree(name, coll, mats, seed=3, h=6.5):
    import bpy
    parts = []
    rng = np.random.default_rng(seed)
    # trunk: lofted tapered tube with bends
    segs = 10
    pts = [(0, 0, 0)]
    ang = rng.uniform(0, TAU)
    for i in range(segs):
        ang += rng.uniform(-0.25, 0.25)
        dz = h / segs
        r = 0.30 * (1 - i / segs * 0.75)
        pts.append((pts[-1][0] + math.cos(ang) * dz * 0.22,
                    pts[-1][1] + math.sin(ang) * dz * 0.22,
                    pts[-1][2] + dz))
    verts, faces = [], []
    NR = 10
    from body_lib import tube
    for i in range(segs):
        r0 = 0.30 * (1 - i / segs * 0.72)
        r1 = 0.30 * (1 - (i + 1) / segs * 0.72)
        v, f, uv = tube(pts[i], pts[i + 1], r0, r1, n=NR)
        base = len(verts)
        verts.extend(v.tolist())
        faces.extend([(a + base, b + base, c + base, d + base) for a, b, c, d in f])
    trunk = mesh_obj(f"{name}_Trunk", np.asarray(verts), faces, mat=mats["bark"], coll=coll)
    parts.append(trunk)
    # branches + leaf cards
    leaf_mat = mats["leaves"]
    for b in range(7):
        t = rng.uniform(0.45, 0.95)
        idx = int(t * segs)
        base = np.array(pts[min(idx, segs)])
        ang = rng.uniform(0, TAU)
        tilt = rng.uniform(0.5, 1.1)
        L = rng.uniform(1.2, 2.2)
        tip = base + np.array([math.cos(ang) * math.sin(tilt), math.sin(ang) * math.sin(tilt), math.cos(tilt)]) * L
        v, f, uv = tube(tuple(base), tuple(tip), 0.09 * (1 - t * 0.5), 0.02, n=6)
        bo = mesh_obj(f"{name}_Branch{b}", v, f, mat=mats["bark"], coll=coll)
        parts.append(bo)
        # leaf blobs (icosa displaced)
        for k in range(3):
            lc = tip + rng.normal(0, 0.35, 3) * np.array([1, 1, 0.6])
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=rng.uniform(0.55, 0.9), location=tuple(lc))
            lo = bpy.context.active_object
            lo.name = f"{name}_Leaves{b}_{k}"
            me = lo.data
            vs = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get("co", vs)
            vs = vs.reshape(-1, 3) + np.array(lc)
            dd = vs - np.array(lc)
            nn = fbm3(dd[:, 0] * 4 + seed, dd[:, 1] * 4, dd[:, 2] * 4, 3, seed + b * 3 + k) - 0.5
            vs = vs + dd / (np.linalg.norm(dd, axis=1, keepdims=True) + 1e-9) * (nn * 0.22)[:, None]
            me.vertices.foreach_set("co", (vs).ravel())
            me.update()
            lo.data.materials.append(leaf_mat)
            for c in list(lo.users_collection):
                c.objects.unlink(lo)
            coll.objects.link(lo)
            parts.append(lo)
    return parts

def build_gravestone(name, style, coll, mats, seed=1):
    parts = []
    if style == "round":
        parts.append(_box_bevel(f"{name}_Slab", (0.52, 0.09, 0.78), (0, 0, 0.39), mats["stone"], coll, seed))
        import bpy
        bpy.ops.mesh.primitive_cylinder_add(radius=0.26, depth=0.09, location=(0, 0, 0.78),
                                            rotation=(math.pi / 2, 0, 0), vertices=24)
        top = bpy.context.active_object
        top.name = f"{name}_Top"
        top.data.materials.append(mats["stone"])
        for c in list(top.users_collection):
            c.objects.unlink(top)
        coll.objects.link(top)
        parts.append(top)
    elif style == "cross":
        parts.append(_box_bevel(f"{name}_Slab", (0.30, 0.10, 1.35), (0, 0, 0.675), mats["stone"], coll, seed))
        parts.append(_box_bevel(f"{name}_ArmH", (0.62, 0.09, 0.20), (0, 0, 1.02), mats["stone"], coll, seed + 1))
        parts.append(_box_bevel(f"{name}_ArmV", (0.20, 0.09, 0.46), (0, 0, 1.12), mats["stone"], coll, seed + 2))
    elif style == "chest":
        parts.append(_box_bevel(f"{name}_Body", (1.05, 0.55, 0.55), (0, 0, 0.30), mats["stone"], coll, seed))
        parts.append(_box_bevel(f"{name}_Lid", (1.15, 0.62, 0.10), (0, 0, 0.62), mats["stone"], coll, seed + 1))
    elif style == "obelisk":
        import bpy
        bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.26, radius2=0.05, depth=1.7,
                                        location=(0, 0, 0.85), rotation=(0, 0, math.pi / 4))
        ob = bpy.context.active_object
        ob.name = f"{name}_Spire"
        ob.data.materials.append(mats["stone"])
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        coll.objects.link(ob)
        parts.append(ob)
    elif style == "broken":
        b = _box_bevel(f"{name}_Stump", (0.5, 0.10, 0.5), (0.03, 0, 0.25), mats["stone"], coll, seed)
        b.rotation_euler = (0, 0.12, 0.06)
        parts.append(b)
        f = _box_bevel(f"{name}_Fallen", (0.4, 0.08, 0.34), (0.45, 0.12, 0.05), mats["stone"], coll, seed + 1)
        f.rotation_euler = (math.pi / 2, 0, 0.5)
        parts.append(f)
    elif style == "slate":
        parts.append(_box_bevel(f"{name}_Slab", (0.40, 0.05, 0.66), (0, 0, 0.33), mats["slate"], coll, seed))
    # base plinth
    parts.append(_box_bevel(f"{name}_Plinth", (0.62, 0.24, 0.10), (0, 0, 0.05), mats["stone"], coll, seed + 7))
    return parts
