#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE LAST SIN - 1847 outfit + hair builders.
Clothing = offset shells over the unified body mesh (region masks in world
space), with gravity-fold displacement + solidify thickness. Hair = flow-field
ribbon cards. All geometry real, UV-carrying, inspectable.
"""
import math
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sculpt_lib import mesh_obj, fbm3, value_noise3
from body_lib import tube

TAU = math.pi * 2.0

# ---------------------------------------------------------------- helpers
def mesh_arrays(obj):
    import bpy
    me = obj.data
    vs = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", vs)
    vs = vs.reshape(-1, 3)
    fs = [tuple(p.vertices) for p in me.polygons]
    return vs, fs

def vertex_normals(vs, fs):
    fsa = np.asarray(fs)
    a, b, c = vs[fsa[:, 0]], vs[fsa[:, 1]], vs[fsa[:, 2]]
    fn = np.cross(b - a, c - a)
    fn /= (np.linalg.norm(fn, axis=1, keepdims=True) + 1e-9)
    n = np.zeros_like(vs)
    for k in range(fsa.shape[1]):
        np.add.at(n, fsa[:, k], fn)
    n /= (np.linalg.norm(n, axis=1, keepdims=True) + 1e-9)
    return n

def copy_uv(obj, fs, nverts):
    uvl = obj.data.uv_layers[0] if obj.data.uv_layers else None
    if uvl is None:
        return np.zeros((nverts, 2))
    uv = np.zeros((nverts, 2))
    for poly in obj.data.polygons:
        for li, vi in zip(poly.loop_indices, poly.vertices):
            uv[vi] = uvl.data[li].uv
    return uv

def face_mask_centers(vs, fs):
    return vs[np.asarray(fs)].mean(axis=1)

def solidify(obj, thickness=0.0025):
    import bpy
    m = obj.modifiers.new("sol", 'SOLIDIFY')
    m.thickness = thickness
    m.offset = -1.0   # cloth: shell surface is the OUTER surface; push thickness inward
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier="sol")
    return obj

def shell(name, src_obj, mask, offset=0.008, fold_fn=None, thickness=0.0025,
          mat=None, coll=None, delete_faces=None):
    """Build cloth shell from masked region of a mesh object."""
    vs, fs = mesh_arrays(src_obj)
    uvs = copy_uv(src_obj, fs, len(vs))
    vmask = np.zeros(len(vs), bool)
    vmask[mask(vs)] = True
    keep_f = [i for i, f in enumerate(fs) if all(vmask[v] for v in f)]
    if not keep_f:
        return None
    fs2 = [fs[i] for i in keep_f]
    uv2 = uvs
    # remap indices
    used = sorted({v for f in fs2 for v in f})
    remap = {v: i for i, v in enumerate(used)}
    vs2 = vs[used]
    uv2 = uvs[used]
    fs2 = [tuple(remap[v] for v in f) for f in fs2]
    n2 = vertex_normals(vs2, fs2)
    disp = np.full((len(vs2), 3), 0.0)
    disp += n2 * offset
    if fold_fn is not None:
        disp += fold_fn(vs2, n2)
    vs3 = vs2 + disp
    ob = mesh_obj(name, vs3, fs2, uvs=uv2, mat=mat, coll=coll)
    if delete_faces is not None:
        # remove faces by centroid predicate
        cs = np.asarray(fs2)
        cents = vs3[cs].mean(axis=1)
        kill = [i for i, f in enumerate(fs2) if delete_faces(cents[i])]
        if kill:
            me = ob.data
            bm = None
            import bmesh
            bm = bmesh.new(); bm.from_mesh(me)
            faces = list(bm.faces)
            for i in sorted(kill, reverse=True):
                if i < len(faces):
                    bm.faces.remove(faces[i])
            bm.to_mesh(me); bm.free(); me.update()
    solidify(ob, thickness)
    return ob

def fold_field(amp, waves=9, vertical=True, noise_amp=0.35, seed=5, hang=None):
    """Gravity folds: radial ripple + noise. hang: fn(z)->0..1 strength."""
    def f(vs, n):
        c = vs.mean(axis=0)
        ang = np.arctan2(vs[:, 0] - c[0], vs[:, 1] - c[1])
        base = np.sin(ang * waves + fbm3(vs[:, 0] * 8, vs[:, 1] * 8, vs[:, 2] * 8, 2, seed) * 3.0)
        nz = (fbm3(vs[:, 0] * 30, vs[:, 1] * 30, vs[:, 2] * 30, 2, seed + 1) - 0.5) * noise_amp
        d = base + nz
        if hang is not None:
            d = d * hang(vs[:, 2])
        return n * (amp * d)[:, None]
    return f

# ---------------------------------------------------------------- garments
def build_outfit(body, coll, mats, prm=None):
    """body: unified body mesh object. mats: dict name->material."""
    import bpy
    coll = coll or bpy.context.scene.collection
    out = {}
    # ----- coat (frock, knee length, front open below chest)
    def coat_mask(v):
        z = v[:, 2]
        torso = (z > 0.55) & (z < 1.462) & (np.abs(v[:, 0]) < 0.24) & (np.abs(v[:, 1]) < 0.20)
        arms = ((np.abs(v[:, 0]) > 0.20) & (z > 0.83) & (z < 1.445) & (np.abs(v[:, 1]) < 0.22))
        return torso | arms
    def coat_open(c):
        return (np.abs(c[0]) < 0.026) & (c[1] < 0.0) & (c[2] < 1.275)
    def hang(z):
        return np.clip((1.30 - z) / 0.75, 0, 1) * 0.7 + 0.3
    coat = shell("TLS_Outfit_Coat", body, coat_mask, offset=0.012,
                 fold_fn=fold_field(0.0045, waves=11, hang=hang, seed=7),
                 thickness=0.003, mat=mats["coat"], coll=coll, delete_faces=coat_open)
    out["coat"] = coat
    # shirt underlayer: full torso shell (kills any skin show-through)
    def shirt_mask(v):
        return (v[:, 2] > 0.92) & (v[:, 2] < 1.425) & (np.abs(v[:, 0]) < 0.26) & (np.abs(v[:, 1]) < 0.22)
    sh_u = shell("TLS_Outfit_ShirtUnder", body, shirt_mask, offset=0.005,
                 fold_fn=fold_field(0.0008, waves=9, seed=23),
                 thickness=0.0015, mat=mats["shirt"], coll=coll)
    out["shirt_under"] = sh_u
    # coat collar: ring band around neck
    rings = []
    NR = 24
    for z, r in ((1.435, 0.062), (1.462, 0.058), (1.470, 0.055)):
        pts = [(r * math.cos(TAU * k / NR), r * math.sin(TAU * k / NR) * 0.9 - 0.004, z) for k in range(NR)]
        rings.append({"verts": pts})
    # simple loft collar
    verts, faces = [], []
    vi = 0
    for ri, ring in enumerate(rings):
        for p in ring["verts"]:
            verts.append(p)
    for i in range(len(rings) - 1):
        for k in range(NR):
            k2 = (k + 1) % NR
            faces.append((i * NR + k, i * NR + k2, (i + 1) * NR + k2, (i + 1) * NR + k))
    out["collar"] = mesh_obj("TLS_Outfit_CoatCollar", np.asarray(verts), faces,
                             mat=mats["coat"], coll=coll)

    # ----- waistcoat (front panel, V-neck, brass buttons)
    def wc_mask(v):
        return (v[:, 1] < -0.03) & (np.abs(v[:, 0]) < 0.15) & (v[:, 2] > 0.94) & (v[:, 2] < 1.315)
    def wc_vneck(c):
        return (c[2] > 1.20) & (np.abs(c[0]) < max(0.015, (1.285 - c[2]) * 0.16))
    wc = shell("TLS_Outfit_Waistcoat", body, wc_mask, offset=0.007,
               fold_fn=fold_field(0.0012, waves=13, seed=11),
               thickness=0.002, mat=mats["waistcoat"], coll=coll, delete_faces=wc_vneck)
    out["waistcoat"] = wc

    # ----- shirt: collar + cuffs + placket in V
    def collar_mask(v):
        return (v[:, 2] > 1.415) & (v[:, 2] < 1.452) & (np.linalg.norm(v[:, :2], axis=1) < 0.085)
    shirt_collar = shell("TLS_Outfit_ShirtCollar", body, collar_mask, offset=0.006,
                         thickness=0.0015, mat=mats["shirt"], coll=coll)
    out["shirt_collar"] = shirt_collar
    # placket visible in V opening
    verts, faces = [], []
    W, H0, H1, D = 0.040, 1.195, 1.272, -0.098
    grid = [(x, D, z) for z in (H0, H0 + 0.028, H1 - 0.02, H1) for x in (-W, W)]
    for quad in ((0, 1, 3, 2), (2, 3, 5, 4), (4, 5, 7, 6)):
        faces.append(quad)
    plk = mesh_obj("TLS_Outfit_ShirtPlacket", np.asarray(grid), faces,
                   mat=mats["shirt"], coll=coll)
    sol = plk.modifiers.new("sol", 'SOLIDIFY'); sol.thickness = 0.0015; sol.offset = -1
    out["shirt_placket"] = plk
    # cuffs at wrists
    for S, sx in (("L", -1), ("R", 1)):
        verts, faces = [], []
        n = 12
        for z, r in ((0.845, 0.040), (0.862, 0.044)):
            cx, cy = sx * 0.315, -0.058
            for k in range(n):
                a = TAU * k / n
                verts.append((cx + r * math.cos(a), cy + r * math.sin(a), z))
        for k in range(n):
            k2 = (k + 1) % n
            faces.append((k, k2, n + k2, n + k))
        cuff = mesh_obj(f"TLS_Outfit_Cuff_{S}", np.asarray(verts), faces,
                        mat=mats["shirt"], coll=coll)
        out[f"cuff_{S}"] = cuff

    # ----- cravat (neckcloth) : torus + knot
    verts, faces = [], []
    n, m = 20, 6
    for i in range(n):
        a = TAU * i / n
        cx, cy = 0.0, 0.002
        for j in range(m):
            b = TAU * j / m
            r = 0.048
            verts.append((cx + (r + 0.008 * math.cos(b)) * math.cos(a),
                          cy + (r + 0.008 * math.cos(b)) * math.sin(a) * 1.05,
                          1.438 + 0.009 * math.sin(b)))
    for i in range(n):
        i2 = (i + 1) % n
        for j in range(m):
            j2 = (j + 1) % m
            faces.append((i * m + j, i2 * m + j, i2 * m + j2, i * m + j2))
    out["cravat"] = mesh_obj("TLS_Outfit_Cravat", np.asarray(verts), faces,
                             mat=mats["cravat"], coll=coll)

    # ----- trousers
    def tr_mask(v):
        return (v[:, 2] > 0.095) & (v[:, 2] < 1.055) & (np.abs(v[:, 0]) < 0.195) & (v[:, 1] > -0.16) & (v[:, 1] < 0.16)
    tr = shell("TLS_Outfit_Trousers", body, tr_mask, offset=0.013,
               fold_fn=fold_field(0.0028, waves=7, seed=13),
               thickness=0.002, mat=mats["trousers"], coll=coll)
    out["trousers"] = tr
    # waistband
    verts, faces = [], []
    NR = 28
    for z, r in ((1.015, 0.148), (1.042, 0.150)):
        for k in range(NR):
            a = TAU * k / NR
            verts.append((r * math.cos(a) * 1.02, r * math.sin(a) * 0.72 - 0.004, z))
    for i in range(1):
        for k in range(NR):
            k2 = (k + 1) % NR
            faces.append((k, k2, NR + k2, NR + k))
    out["waistband"] = mesh_obj("TLS_Outfit_Waistband", np.asarray(verts), faces,
                                mat=mats["trousers"], coll=coll)

    # ----- boots (leather) + soles
    def boot_mask(v):
        return ((v[:, 2] < 0.335) & (v[:, 2] > 0.02) & (np.abs(v[:, 0]) < 0.155) & (np.abs(v[:, 0]) > 0.03)) | \
               ((v[:, 2] < 0.062) & (np.abs(v[:, 0]) < 0.155))
    boots = shell("TLS_Outfit_Boots", body, boot_mask, offset=0.009,
                  fold_fn=fold_field(0.0009, waves=5, seed=17),
                  thickness=0.003, mat=mats["boot"], coll=coll)
    out["boots"] = boots
    # soles + heels
    for S, sx in (("L", -1), ("R", 1)):
        verts, faces = [], []
        cx = sx * 0.106
        x0, x1 = cx - 0.048, cx + 0.048
        y0, y1 = 0.045, -0.185
        z0, z1 = 0.006, 0.026
        box = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
               (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        idx = [(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]
        sole = mesh_obj(f"TLS_Outfit_Sole_{S}", np.asarray(box), idx, mat=mats["sole"], coll=coll)
        out[f"sole_{S}"] = sole
        heel = mesh_obj(f"TLS_Outfit_Heel_{S}", np.asarray([(x0,y1-0.0,z0),(x1,y1,z0),(x1,y1,z1-0.024),(x0,y1,z1-0.024),
                                                            (x0,y0-0.03,z0),(x1,y0-0.03,z0),(x1,y0-0.03,z1-0.024),(x0,y0-0.03,z1-0.024)][:8]),
                        idx, mat=mats["sole"], coll=coll)
        heel.scale = (0.55, 1.0, 1.0)
        out[f"heel_{S}"] = heel

    # ----- brass buttons (coat + waistcoat)
    import bpy
    btns = []
    bz = [1.245, 1.155, 1.065, 0.975, 0.885]
    for i, z in enumerate(bz):
        x = 0.048 if i % 2 == 0 else 0.046
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.0105, depth=0.004,
                                            location=(x, -0.118 - (0.30 - z) * 0.10, z),
                                            rotation=(math.pi / 2, 0, 0))
        b = bpy.context.active_object
        b.name = f"TLS_Outfit_CoatBtn_{i}"
        b.data.materials.append(mats["brass"])
        for c in list(b.users_collection):
            c.objects.unlink(b)
        coll.objects.link(b)
        btns.append(b)
    for i, z in enumerate((1.235, 1.155, 1.075, 0.995)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.0085, depth=0.0035,
                                            location=(0.0, -0.104 - (1.24 - z) * 0.06, z),
                                            rotation=(math.pi / 2, 0, 0))
        b = bpy.context.active_object
        b.name = f"TLS_Outfit_WCBtn_{i}"
        b.data.materials.append(mats["brass"])
        for c in list(b.users_collection):
            c.objects.unlink(b)
        coll.objects.link(b)
        btns.append(b)
    out["buttons"] = btns

    # ----- satchel strap + bag (leather)
    # strap curve: right shoulder -> chest -> left hip
    pts = [(0.115, -0.115, 1.425), (0.075, -0.150, 1.30), (0.0, -0.148, 1.12),
           (-0.085, -0.135, 0.98), (-0.150, -0.108, 0.905)]
    seg = 14
    curve = []
    for i in range(seg + 1):
        t = i / seg
        k = int(min(t * (len(pts) - 1), len(pts) - 2))
        lt = t * (len(pts) - 1) - k
        p = (np.array(pts[k]) * (1 - lt) + np.array(pts[k + 1]) * lt)
        curve.append(p)
    v, f, uv = tube(curve[0], curve[1], 0.013, 0.013, n=8)
    segsv = [v]
    for i in range(1, seg):
        vv, ff, _ = tube(curve[i], curve[i + 1], 0.013, 0.013, n=8)
        segsv.append(vv)
    # simpler: one tube per segment joined visually (overlapping ends ok)
    strap_objs = []
    for i in range(seg):
        vv, ff, _ = tube(curve[i], curve[i + 1], 0.0135, 0.0135, n=8)
        o = mesh_obj(f"TLS_Outfit_StrapSeg{i:02d}", vv, ff, mat=mats["strap"], coll=coll)
        strap_objs.append(o)
    out["strap"] = strap_objs
    # bag body: rounded box at left hip
    verts, faces = [], []
    bx, by, bz0 = -0.168, -0.098, 0.845
    sx_, sy_, sz_ = 0.055, 0.032, 0.060
    corners = []
    NR = 12
    ringzs = [bz0, bz0 + sz_ * 0.12, bz0 + sz_ * 0.88, bz0 + sz_]
    ringrs = [0.75, 1.0, 1.0, 0.75]
    for z, rr in zip(ringzs, ringrs):
        for k in range(NR):
            a = TAU * k / NR
            corners.append((bx + sx_ * rr * math.cos(a) * (1 + 0.25 * math.cos(a) ** 4),
                            by + sy_ * rr * math.sin(a) * 0.8 - 0.02 * math.sin(a) ** 2,
                            z))
    for i in range(len(ringzs) - 1):
        for k in range(NR):
            k2 = (k + 1) % NR
            faces.append((i * NR + k, i * NR + k2, (i + 1) * NR + k2, (i + 1) * NR + k))
    faces.append(tuple(range(NR)))          # bottom cap (approx)
    faces.append(tuple(range((len(ringzs) - 1) * NR, len(ringzs) * NR))[::-1])
    bag = mesh_obj("TLS_Outfit_Satchel", np.asarray(corners), faces, mat=mats["strap"], coll=coll)
    out["satchel"] = bag
    # flap
    verts, faces = [], []
    for z, dyy in ((bz0 + sz_ - 0.004, 0.0), (bz0 + sz_ * 0.55, -0.052)):
        for x in (bx - sx_ * 0.95, bx + sx_ * 0.95):
            verts.append((x, by - 0.028 + dyy * 0.2, z))
            verts.append((x, by + 0.030 + dyy, z))
    faces += [(0, 1, 3, 2), (4, 5, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)]
    flap = mesh_obj("TLS_Outfit_SatchelFlap", np.asarray(verts), faces, mat=mats["strap"], coll=coll)
    out["satchel_flap"] = flap

    # ----- gloves (leather) over hands
    def glove_mask(v):
        return (v[:, 2] < 0.90) & (v[:, 2] > 0.68) & (np.abs(v[:, 0]) > 0.24)
    gl = shell("TLS_Outfit_Gloves", body, glove_mask, offset=0.008,
               fold_fn=fold_field(0.0006, waves=6, seed=29),
               thickness=0.0018, mat=mats["boot"], coll=coll)
    out["gloves"] = gl

    return out

# ---------------------------------------------------------------- hair
def build_hair_cap(head_base, head_origin=(0, 0.005, 1.668), coll=None, mat=None, offset=0.002):
    """Solid scalp cap: grid faces of the head whose direction lies in the scalp
    region, offset outward. Gives real hair mass under the strand cards."""
    import bpy
    coll = coll or bpy.context.scene.collection
    S, Pp1, _ = head_base.shape
    P = Pp1 - 1
    sel = np.zeros((S, Pp1), bool)
    for i in range(S):
        for j in range(Pp1):
            d = head_base[i, j] / (np.linalg.norm(head_base[i, j]) + 1e-9)
            scalp = (d[2] > 0.08 and not (d[1] < -0.35 and d[2] < 0.55)) or (d[2] > 0.50)
            sel[i, j] = scalp
    verts = head_base.reshape(-1, 3).copy()
    n = np.linalg.norm(verts, axis=1, keepdims=True) + 1e-9
    verts = verts + verts / n * offset
    faces = []
    for i in range(S):
        i2 = (i + 1) % S
        for j in range(P):
            a = i * Pp1 + j; b = i2 * Pp1 + j; c = i2 * Pp1 + j + 1; d = i * Pp1 + j + 1
            if sel[i, j] and sel[i2, j] and sel[i2, j + 1] and sel[i, j + 1]:
                faces.append((a, b, c, d))
    if not faces:
        return None
    # spherical UVs for the cap
    dn = head_base.reshape(-1, 3) / (np.linalg.norm(head_base.reshape(-1, 3), axis=1, keepdims=True) + 1e-9)
    uvs = np.stack([(np.arctan2(dn[:, 1], dn[:, 0]) / (2 * np.pi)) % 1.0,
                    (dn[:, 2] + 1) / 2], axis=-1)
    ob = mesh_obj("TLS_Hair_Cap", verts, faces, uvs=uvs, mat=mat, coll=coll)
    ob.location = head_origin
    # add solidify thickness so cap reads as mass
    m = ob.modifiers.new("sol", 'SOLIDIFY'); m.thickness = 0.0060; m.offset = -1.0
    ss = ob.modifiers.new("sub", 'SUBSURF'); ss.subdivision_type = 'SIMPLE'; ss.levels = 2; ss.render_levels = 2
    return ob


def build_hair(head_origin=(0, 0.005, 1.668), coll=None, mat=None, seed=5, n_strands=110,
               head_base=None):
    """1847 side-part short hair: ribbon cards flowing from part line down/sides/back.
    Built in HEAD LOCAL space then offset by head_origin.
    head_base: (S,P+1,3) base head positions for surface-radius sampling."""
    import bpy
    coll = coll or bpy.context.scene.collection
    rng = np.random.default_rng(seed)
    # surface radius sampler from base head grid
    if head_base is not None:
        hb = head_base.reshape(-1, 3)
        hbn = hb / (np.linalg.norm(hb, axis=1, keepdims=True) + 1e-9)
        hbr = np.linalg.norm(hb, axis=1)
        def surf_r(d):
            d = d / (np.linalg.norm(d) + 1e-9)
            dots = hbn @ d
            k = int(np.argmax(dots))
            return float(hbr[k])
    else:
        def surf_r(d):
            return 0.098
    part_x = 0.024
    strands = []
    tries = 0
    while len(strands) < n_strands and tries < n_strands * 6:
        tries += 1
        d = rng.normal(size=3); d /= np.linalg.norm(d)
        if d[2] < 0.10:            # scalp only (upper)
            continue
        if d[1] < -0.55:           # never on the face
            continue
        if d[1] < -0.30 and d[2] < 0.55:   # forehead zone: only crown-level starts
            continue
        strands.append(d)
    objs = []
    for si, d0 in enumerate(strands):
        side = 1 if d0[0] >= part_x else -1
        # flow: sweep away from part, then down
        segs = 6
        path = []
        p = d0 * surf_r(d0)
        path.append(p.copy())
        for i in range(segs):
            t = i / segs
            tang = np.array([-side * 0.55 * (1 - t * 0.4), 0.15 * d0[1], -0.85 * (0.35 + t)])
            tang /= np.linalg.norm(tang)
            p = p + tang * 0.018
            r = surf_r(p / (np.linalg.norm(p) + 1e-9)) + 0.0100 + 0.005 * t
            p = p / (np.linalg.norm(p) + 1e-9) * r
            path.append(p.copy())
        # ribbon with width taper; u spans ACROSS the ribbon (alpha texture is x-varying)
        verts, faces = [], []
        w0 = rng.uniform(0.009, 0.014)
        uu0 = rng.uniform(0.05, 0.6)
        for i, p in enumerate(path):
            w = w0 * (1.0 - 0.75 * i / segs)
            outward = np.array([p[0], p[1], 0.0]); outward /= (np.linalg.norm(outward) + 1e-9)
            a = p - outward * w
            b = p + outward * w
            verts += [tuple(a), tuple(b)]
            if i > 0:
                k = i * 2
                faces.append((k - 2, k - 1, k + 1, k))
        uvs = []
        for i in range(segs + 1):
            uvs.append((uu0, i / segs))
            uvs.append((uu0 + 0.35, i / segs))
        uvs = np.asarray(uvs)
        ob = mesh_obj(f"TLS_Hair_Card_{si:03d}", np.asarray(verts), faces, uvs=uvs, mat=mat, coll=coll)
        ob.location = head_origin
        objs.append(ob)
    return objs

def build_brows(coll=None, mat=None, head_origin=(0, 0.005, 1.668)):
    objs = []
    for sx in (-1, 1):
        n = 6
        verts, faces = [], []
        for i in range(n):
            t = i / (n - 1)
            x = sx * (0.012 + 0.032 * t)
            z = 0.030 + 0.006 * math.sin(t * math.pi) - 0.002 * t
            y = -0.086 - 0.004 * math.cos(t * math.pi)
            w = 0.0035
            verts.append((x, y - w, z)); verts.append((x, y + w, z))
            if i > 0:
                k = i * 2
                faces.append((k - 2, k - 1, k + 1, k))
        uvs = []
        for i in range(n):
            uvs.append((0.1, i / (n - 1))); uvs.append((0.8, i / (n - 1)))
        ob = mesh_obj(f"TLS_Hair_Brow_{sx}", np.asarray(verts), faces, uvs=np.asarray(uvs), mat=mat, coll=coll)
        ob.location = head_origin
        objs.append(ob)
    return objs

def build_stubble(head_obj, head_origin, coll=None, mat=None, offset=0.0011):
    """Duplicate jaw-region verts of the dense head, offset outward: stubble shell."""
    vs, fs = mesh_arrays(head_obj)
    fwd = -vs[:, 1] / 0.103          # normalized 0..1 toward face front
    lips = (np.abs(vs[:, 0]) < 0.019) & (vs[:, 2] > -0.046) & (vs[:, 2] < -0.024)
    sel = (vs[:, 2] < -0.006) & (vs[:, 2] > -0.092) & (fwd > 0.52) & (np.abs(vs[:, 0]) < 0.075) & (~lips)
    # upper lip mustache zone
    must = (np.abs(vs[:, 0]) < 0.016) & (vs[:, 2] > -0.030) & (vs[:, 2] < -0.017) & (fwd > 0.75)
    vmask = sel | must
    used = np.where(vmask)[0]
    if len(used) == 0:
        return None
    remap = {v: i for i, v in enumerate(used)}
    fs2 = []
    for f in fs:
        if all(v in remap for v in f):
            fs2.append(tuple(remap[v] for v in f))
    if not fs2:
        return None
    vs2 = vs[used]
    uv = copy_uv(head_obj, fs, len(vs))[used]
    n2 = vertex_normals(vs2, fs2)
    vs3 = vs2 + n2 * offset
    ob = mesh_obj("TLS_Hair_Stubble", vs3, fs2, uvs=uv, mat=mat, coll=coll)
    ob.location = head_origin
    return ob
