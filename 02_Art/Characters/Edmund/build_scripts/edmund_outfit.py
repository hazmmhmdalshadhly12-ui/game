#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Edmund Vale - 1847 outfit (per docs/CHARACTER_REGISTRY.md TLS-CHR-030):
gray London coat (visually foreign to the village), linen shirt, dark
waistcoat layer, neckcloth, wool trousers, leather boots, leather engraving
satchel + brass fittings. All layers are separate meshes fit over the body.
"""
import math
from mathutils import Vector
from edmund_lib import loft_rings, new_mesh_obj, join_objects, TAU
from edmund_body import tube_along, HEAD_C

# ------------------------------------------------- body radius sampling
TORSO = [  # z, cx, cy, wx, wy   (same as edmund_body.build_torso)
    (0.865, 0.0, 0.006, 0.142, 0.098), (0.900, 0.0, 0.012, 0.150, 0.104),
    (0.955, 0.0, 0.014, 0.146, 0.103), (1.020, 0.0, 0.008, 0.136, 0.098),
    (1.100, 0.0, 0.002, 0.128, 0.094), (1.180, 0.0, -0.004, 0.132, 0.097),
    (1.260, 0.0, -0.010, 0.144, 0.101), (1.330, 0.0, -0.012, 0.152, 0.102),
    (1.400, 0.0, -0.008, 0.148, 0.094), (1.440, 0.0, -0.002, 0.116, 0.082),
    (1.470, 0.0, 0.002, 0.084, 0.072), (1.500, 0.0, 0.004, 0.062, 0.058),
    (1.535, 0.0, 0.004, 0.055, 0.052), (1.556, 0.0, 0.002, 0.053, 0.050),
]
ARM_PATH = [(0.176, -0.006, 1.428), (0.222, -0.008, 1.320), (0.255, -0.010, 1.142),
            (0.300, -0.040, 1.010), (0.320, -0.062, 0.898)]
ARM_RAD = [(0.062, 0.070), (0.054, 0.058), (0.044, 0.048), (0.042, 0.046), (0.030, 0.034)]
LEG_PATH = [(0.094, 0.006, 0.905), (0.100, 0.006, 0.700), (0.104, 0.002, 0.515),
            (0.108, -0.026, 0.395), (0.108, -0.014, 0.090)]
LEG_RAD = [(0.086, 0.096), (0.070, 0.078), (0.060, 0.066), (0.058, 0.068), (0.036, 0.044)]

def _interp(table, z):
    zs = [t[0] for t in table]
    if z <= zs[0]:
        return table[0]
    if z >= zs[-1]:
        return table[-1]
    for i in range(len(zs) - 1):
        if zs[i] <= z <= zs[i + 1]:
            t = (z - zs[i]) / (zs[i + 1] - zs[i])
            a, b = table[i], table[i + 1]
            return tuple(a[k] + (b[k] - a[k]) * t for k in range(len(a)))
    return table[-1]

def torso_ring(z, off=0.0, off_back=0.0, n=36, flare=0.0):
    _, cx, cy, wx, wy = _interp(TORSO, z)
    return {"verts": [(cx + (wx + off + flare) * math.cos(TAU * i / n),
                       cy + (wy + off + off_back) * math.sin(TAU * i / n), z)
                      for i in range(n)]}

def arm_tube(off, z_from=1.44, z_to=0.90, n=14, taper_extra=0.0, side=1):
    """Sleeve tube along the arm path. side=-1 mirrors to the character's left."""
    path, radii = [], []
    # sample along polyline ARM_PATH by arc length between z_from..z_to
    pts = [Vector((side * p[0], p[1], p[2])) for p in ARM_PATH]
    # build dense samples
    dense = []
    for i in range(len(pts) - 1):
        steps = 8
        for k in range(steps):
            t = k / steps
            dense.append(pts[i] + (pts[i + 1] - pts[i]) * t)
    dense.append(pts[-1])
    for i, p in enumerate(dense):
        if not (z_to - 0.02 <= p.z <= z_from + 0.02):
            continue
        # interpolate base radius
        tt = i / (len(dense) - 1)
        base = tt * (len(ARM_RAD) - 1)
        i0 = min(int(base), len(ARM_RAD) - 2)
        f = base - i0
        wx = ARM_RAD[i0][0] + (ARM_RAD[i0 + 1][0] - ARM_RAD[i0][0]) * f
        wy = ARM_RAD[i0][1] + (ARM_RAD[i0 + 1][1] - ARM_RAD[i0][1]) * f
        path.append((p.x, p.y, p.z))
        radii.append((wx + off, wy + off + taper_extra * f))
    return tube_along(path, radii, n_side=n)

def leg_tube(off, z_from=1.14, z_to=0.095, n=16, side=1, flare=0.0):
    pts = [Vector((side * p[0], p[1], p[2])) for p in LEG_PATH]
    dense = []
    for i in range(len(pts) - 1):
        steps = 10
        for k in range(steps):
            t = k / steps
            dense.append(pts[i] + (pts[i + 1] - pts[i]) * t)
    dense.append(pts[-1])
    path, radii = [], []
    for i, p in enumerate(dense):
        if not (z_to - 0.02 <= p.z <= z_from + 0.02):
            continue
        tt = i / (len(dense) - 1)
        base = tt * (len(LEG_RAD) - 1)
        i0 = min(int(base), len(LEG_RAD) - 2)
        f = base - i0
        wx = LEG_RAD[i0][0] + (LEG_RAD[i0 + 1][0] - LEG_RAD[i0][0]) * f
        wy = LEG_RAD[i0][1] + (LEG_RAD[i0 + 1][1] - LEG_RAD[i0][1]) * f
        path.append((p.x, p.y, p.z))
        radii.append((wx + off + flare * max(0.0, (p.z - 0.9) / 0.24),
                      wy + off + flare * max(0.0, (p.z - 0.9) / 0.24)))
    return tube_along(path, radii, n_side=n)

def front_angle_delete(verts, faces, rings_n, verts_per_ring, a_lo, a_hi,
                       z_lo=None, z_hi=None):
    """Delete quad faces whose ring-center angle falls inside [a_lo,a_hi] (front=-Y at 270deg).
    Loft-generated side faces only; lofted cap fans (appended at the end) are kept."""
    keep = []
    n_side_faces = max(0, rings_n - 1) * verts_per_ring
    for fi, f in enumerate(faces):
        if fi >= n_side_faces:      # cap fan face -> keep
            keep.append(f)
            continue
        ri = fi // verts_per_ring
        vi = fi % verts_per_ring
        a = TAU * (vi + 0.5) / verts_per_ring
        deg = math.degrees(a) % 360
        ring_z = verts[ri * verts_per_ring][2] if ri * verts_per_ring < len(verts) else 0
        okz = True
        if z_lo is not None and ring_z < z_lo:
            okz = False
        if z_hi is not None and ring_z > z_hi:
            okz = False
        inzone = (a_lo <= deg <= a_hi)
        if inzone and okz:
            continue
        keep.append(f)
    return keep

# ------------------------------------------------- garments
def build_shirt(mats):
    objs = []
    # torso shirt: z 0.88..1.505, slight offset
    zs = [0.88, 0.94, 1.02, 1.10, 1.18, 1.26, 1.33, 1.40, 1.44, 1.47, 1.495, 1.505]
    rings = [torso_ring(z, off=0.008) for z in zs]
    # collar flare at top
    rings[-1] = torso_ring(1.505, off=0.016)
    verts, faces, uvs = loft_rings(rings, closed_loop=True, cap_bottom=True)
    sh = new_mesh_obj("Edm_Shirt", verts, faces, uvs=uvs, mat=mats["shirt"])
    objs.append(sh)
    for s, nm in ((1, "R"), (-1, "L")):
        sv, sf, su = arm_tube(0.008, z_from=1.44, z_to=0.902, side=s)
        c = new_mesh_obj(f"Edm_ShirtSleeve{nm}", sv, sf, uvs=su, mat=mats["shirt"])
        objs.append(c)
        # cuff
        cuff = [torso_ring(0.905 + 0.001, off=0.02)]  # dummy not used
        pts = [(s * 0.320, -0.062, 0.905), (s * 0.323, -0.064, 0.878)]
        cv, cf, cu = tube_along(pts, [(0.038, 0.042), (0.039, 0.043)], n_side=14,
                                cap_end=True)
        cuff_o = new_mesh_obj(f"Edm_Cuff{nm}", cv, cf, uvs=cu, mat=mats["shirt"])
        objs.append(cuff_o)
    return join_objects(objs, "Edmund_Shirt")

def build_waistcoat(mats):
    zs = [0.905, 0.96, 1.02, 1.10, 1.18, 1.26, 1.33, 1.40, 1.435]
    rings = [torso_ring(z, off=0.016) for z in zs]
    verts, faces, uvs = loft_rings(rings, closed_loop=True, cap_bottom=True)
    # V-neck: delete front faces (front=-Y ~270deg) above z=1.18, widening up
    keep = []
    nv = 36
    for fi, f in enumerate(faces):
        ri = fi // nv
        vi = fi % nv
        a = math.degrees(TAU * (vi + 0.5) / nv) % 360
        z = zs[min(ri, len(zs) - 1)]
        if 235 <= a <= 305:
            # open from z 1.18 up, opening widens with height
            if z > 1.18:
                halfw = 12 + 26 * (z - 1.18) / 0.255  # degrees
                if abs(((a - 270 + 180) % 360) - 180) < halfw:
                    continue
        keep.append(f)
    wc = new_mesh_obj("Edm_Waistcoat", verts, keep, uvs=uvs, mat=mats["waistcoat"])
    # buttons along front edge (right side)
    metal = []
    for z in (1.12, 1.05, 0.98, 0.94):
        _, cx, cy, wx, wy = _interp(TORSO, z)
        x = cx + (wx + 0.017) * 0.26
        y = cy - (wy + 0.016) * 0.965
        metal.append(brass_button(f"Edm_WCBtn{int(z*100)}", (x, y, z), 0.009, 0.004,
                                  mats["brass"]))
    return join_objects([wc] + metal, "Edmund_Waistcoat")

def build_coat(mats):
    objs = []
    # main body: hem 0.56 -> collar 1.495, front open 213..327deg
    # upper section uses a shoulder-yoke profile that covers the deltoids
    zs = [0.56, 0.64, 0.74, 0.84, 0.92, 1.00, 1.10, 1.20, 1.30, 1.38,
          1.42, 1.45, 1.475, 1.495]
    YOKE = {  # z: (wx, wy) absolute half-extents at the shoulders
        1.42: (0.205, 0.130),
        1.45: (0.185, 0.122),
        1.475: (0.130, 0.100),
        1.495: (0.082, 0.076),
    }
    rings = []
    for z in zs:
        if z < 0.86:
            k = (0.86 - z)
            _, cx, cy, wx, wy = _interp(TORSO, 0.865)
            n = 36
            rings.append({"verts": [(cx + (wx + 0.021 + k * 0.085) * math.cos(TAU * i / n),
                                     cy + (wy + 0.021 + k * 0.06) * math.sin(TAU * i / n), z)
                                    for i in range(n)]})
        elif z in YOKE:
            wx, wy = YOKE[z]
            n = 36
            rings.append({"verts": [(wx * math.cos(TAU * i / n),
                                     -0.004 + wy * math.sin(TAU * i / n), z)
                                    for i in range(n)]})
        else:
            off = 0.020
            if z > 1.38:
                off = 0.030
            rings.append(torso_ring(z, off=off, off_back=0.004))
    verts, faces, uvs = loft_rings(rings, closed_loop=True, cap_bottom=True)
    nv = 36
    faces = front_angle_delete(verts, faces, len(zs), nv, 213, 327, z_lo=0.30, z_hi=1.51)
    coat = new_mesh_obj("Edm_Coat", verts, faces, uvs=uvs, mat=mats["coat"])
    objs.append(coat)
    # sleeves
    for s, nm in ((1, "R"), (-1, "L")):
        sv, sf, su = arm_tube(0.016, z_from=1.425, z_to=0.905, taper_extra=0.001,
                              side=s)
        c = new_mesh_obj(f"Edm_CoatSleeve{nm}", sv, sf, uvs=su, mat=mats["coat"])
        objs.append(c)
    # collar band
    cr = [torso_ring(1.478, off=0.030), torso_ring(1.508, off=0.034, off_back=0.010)]
    cv, cf, cu = loft_rings(cr, closed_loop=True)
    col = new_mesh_obj("Edm_CoatCollar", cv, cf, uvs=cu, mat=mats["coat"])
    objs.append(col)
    # lapels (rolled strips along opening edges)
    for s, nm in ((1, "R"), (-1, "L")):
        path = [(s * 0.062, -0.118, 1.475), (s * 0.078, -0.124, 1.38),
                (s * 0.090, -0.120, 1.26), (s * 0.098, -0.108, 1.14),
                (s * 0.100, -0.090, 1.05)]
        radii = [(0.008, 0.026), (0.010, 0.030), (0.011, 0.032), (0.011, 0.030), (0.010, 0.026)]
        lv, lf, lu = tube_along(path, radii, n_side=10)
        lp = new_mesh_obj(f"Edm_Lapel{nm}", lv, lf, uvs=lu, mat=mats["coat"])
        objs.append(lp)
    # coat buttons (right front edge)
    metal = []
    for z in (1.34, 1.22, 1.10, 0.98):
        _, cx, cy, wx, wy = _interp(TORSO, z)
        x = cx + (wx + 0.024) * 0.80
        y = cy - (wy + 0.024) * 0.55
        metal.append(brass_button(f"Edm_CoatBtn{int(z*100)}", (x, y, z), 0.012, 0.005,
                                  mats["brass"]))
    objs += metal
    return join_objects(objs, "Edmund_Coat")

def build_neckcloth(mats):
    objs = []
    rings = [
        (1.455, 0.0, 0.0, 0.058, 0.056), (1.475, 0.0, -0.002, 0.061, 0.058),
        (1.500, 0.0, -0.004, 0.059, 0.056), (1.515, 0.0, -0.004, 0.055, 0.052),
    ]
    rr = [{"verts": [(cx + wx * math.cos(TAU * i / 28), cy + wy * math.sin(TAU * i / 28), z)
                     for i in range(28)]} for z, cx, cy, wx, wy in rings]
    v, f, u = loft_rings(rr, closed_loop=True)
    objs.append(new_mesh_obj("Edm_NeckBand", v, f, uvs=u, mat=mats["neckcloth"]))
    # knot at front
    kx, ky = 0.0, -0.062
    rings2 = [
        (1.472, kx, ky, 0.013, 0.010), (1.490, kx, ky - 0.002, 0.015, 0.012),
        (1.504, kx, ky - 0.004, 0.013, 0.011),
    ]
    rr2 = [{"verts": [(cx + wx * math.cos(TAU * i / 16), cy + wy * math.sin(TAU * i / 16), z)
                      for i in range(16)]} for z, cx, cy, wx, wy in rings2]
    v, f, u = loft_rings(rr2, closed_loop=True, cap_top=True, cap_bottom=True)
    objs.append(new_mesh_obj("Edm_NeckKnot", v, f, uvs=u, mat=mats["neckcloth"]))
    # hanging tails
    tv, tf, tu = tube_along([(0.0, -0.062, 1.468), (0.005, -0.058, 1.442),
                             (0.004, -0.054, 1.420)],
                            [(0.008, 0.004), (0.009, 0.004), (0.008, 0.003)],
                            n_side=8, cap_end=True)
    objs.append(new_mesh_obj("Edm_NeckTail", tv, tf, uvs=tu, mat=mats["neckcloth"]))
    return join_objects(objs, "Edmund_Neckcloth")

def build_trousers(mats):
    objs = []
    # hip yoke
    zs = [0.92, 0.98, 1.06, 1.14]
    rings = [torso_ring(z, off=0.012, off_back=0.006) for z in zs]
    v, f, u = loft_rings(rings, closed_loop=True, cap_top=True)
    # front fly line: no geometry needed
    objs.append(new_mesh_obj("Edm_TrousersHip", v, f, uvs=u, mat=mats["trousers"]))
    for s, nm in ((1, "R"), (-1, "L")):
        lv, lf, lu = leg_tube(0.011, z_from=1.14, z_to=0.10, side=s, flare=0.008)
        objs.append(new_mesh_obj(f"Edm_TrouserLeg{nm}", lv, lf, uvs=lu,
                                 mat=mats["trousers"]))
    return join_objects(objs, "Edmund_Trousers")

LEG_LOWER = [  # z, cx, cy, wx, wy sampled from the leg path radii
    (0.090, 0.108, -0.014, 0.036, 0.044),
    (0.200, 0.107, -0.022, 0.056, 0.065),
    (0.300, 0.107, -0.024, 0.058, 0.067),
    (0.350, 0.107, -0.024, 0.058, 0.067),
]

def build_boots(mats):
    objs = []
    for s, nm in ((1, "R"), (-1, "L")):
        # shaft z 0.10..0.335
        rings = []
        for z, gr in ((0.335, 0.016), (0.28, 0.013), (0.20, 0.012), (0.13, 0.012),
                      (0.095, 0.012)):
            _, cx, cy, wx, wy = _interp(LEG_LOWER, z)
            rings.append({"verts": [(cx * s + (wx + gr) * math.cos(TAU * i / 20),
                                     cy + (wy + gr) * math.sin(TAU * i / 20), z)
                                    for i in range(20)]})
        sv, sf, su = loft_rings(rings, closed_loop=True, cap_top=True)
        objs.append(new_mesh_obj(f"Edm_BootShaft{nm}", sv, sf, uvs=su, mat=mats["boot"]))
        # foot: elongated toward -Y
        fr = [
            (0.092, s * 0.108, -0.016, 0.046, 0.056),
            (0.062, s * 0.110, -0.034, 0.049, 0.061),
            (0.036, s * 0.112, -0.078, 0.049, 0.064),
            (0.026, s * 0.112, -0.128, 0.044, 0.058),
            (0.024, s * 0.112, -0.158, 0.038, 0.048),
        ]
        rr = [{"verts": [(cx + wx * math.cos(TAU * i / 20), cy + wy * math.sin(TAU * i / 20), z)
                         for i in range(20)]} for z, cx, cy, wx, wy in fr]
        fv, ff, fu = loft_rings(rr, closed_loop=True, cap_top=True)
        objs.append(new_mesh_obj(f"Edm_BootFoot{nm}", fv, ff, uvs=fu, mat=mats["boot"]))
        # sole: closed band following the footprint perimeter
        sole_rings = []
        for z, src in ((0.030, fr[1]), (0.030, fr[-1]), (0.014, fr[-1]), (0.014, fr[1])):
            _, cx, cy, wx, wy = src
            sole_rings.append({"verts": [(cx + (wx + 0.007) * math.cos(TAU * i / 20),
                                          cy + (wy + 0.007) * math.sin(TAU * i / 20), z)
                                         for i in range(20)]})
        sov, sof, sou = loft_rings(sole_rings, closed_loop=True)
        objs.append(new_mesh_obj(f"Edm_BootSole{nm}", sov, sof, uvs=sou, mat=mats["sole"]))
        # heel block (rear)
        hz = 0.030
        heel = [
            (hz, s * 0.108, 0.018, 0.034, 0.042),
            (0.014, s * 0.108, 0.014, 0.032, 0.040),
        ]
        hr = [{"verts": [(cx + wx * math.cos(TAU * i / 16), cy + wy * math.sin(TAU * i / 16), z)
                         for i in range(16)]} for z, cx, cy, wx, wy in heel]
        hv, hf, hu = loft_rings(hr, closed_loop=True, cap_top=True, cap_bottom=True)
        objs.append(new_mesh_obj(f"Edm_BootHeel{nm}", hv, hf, uvs=hu, mat=mats["sole"]))
    return join_objects(objs, "Edmund_Boots")

def brass_button(name, loc, r=0.01, h=0.004, mat=None, axis="y"):
    verts, faces, uvs = [], [], []
    rings = [(-h / 2, r), (0.0, r), (h / 2, r * 0.86), (h / 2 + r * 0.35, r * 0.45)]
    rr = []
    for z, rr_ in rings:
        if axis == "y":
            rr.append({"verts": [(loc[0] + rr_ * math.cos(TAU * i / 14),
                                  loc[1] + z, loc[2] + rr_ * math.sin(TAU * i / 14))
                                 for i in range(14)]})
        else:
            rr.append({"verts": [(loc[0] + rr_ * math.cos(TAU * i / 14),
                                  loc[1] + rr_ * math.sin(TAU * i / 14), loc[2] + z)
                                 for i in range(14)]})
    v, f, u = loft_rings(rr, closed_loop=True, cap_top=True, cap_bottom=True)
    return new_mesh_obj(name, v, f, uvs=u, mat=mat)

def build_satchel(mats):
    objs = []
    # bag at left hip (strap over right shoulder)
    bx, by, bz = -0.155, -0.075, 0.86
    rings = []
    for z, wx, wy in ((bz - 0.095, 0.115, 0.042), (bz - 0.055, 0.125, 0.046),
                      (bz - 0.010, 0.128, 0.048), (bz + 0.030, 0.125, 0.045),
                      (bz + 0.058, 0.112, 0.040)):
        rings.append({"verts": [(bx + wx * math.cos(TAU * i / 24),
                                 by + wy * math.sin(TAU * i / 24), z)
                                for i in range(24)]})
    v, f, u = loft_rings(rings, closed_loop=True, cap_top=True, cap_bottom=True)
    objs.append(new_mesh_obj("Edm_SatchelBody", v, f, uvs=u, mat=mats["satchel"]))
    # flap
    fr = []
    for z, wx, wy in ((bz + 0.052, 0.118, 0.044), (bz + 0.020, 0.128, 0.048),
                      (bz - 0.040, 0.126, 0.047)):
        fr.append({"verts": [(bx + wx * math.cos(TAU * i / 24),
                              by + wy * math.sin(TAU * i / 24), z)
                             for i in range(24)]})
    v, f, u = loft_rings(fr, closed_loop=True, cap_bottom=True)
    objs.append(new_mesh_obj("Edm_SatchelFlap", v, f, uvs=u, mat=mats["satchel"]))
    # buckle
    objs.append(brass_button("Edm_SatchelBuckle", (bx, by - 0.052, bz - 0.02),
                             0.014, 0.006, mats["brass"]))
    # strap: right shoulder -> left hip, diagonal across chest
    path = [(0.16, -0.055, 1.42), (0.09, -0.10, 1.30), (0.03, -0.13, 1.14),
            (-0.05, -0.13, 0.99), (-0.12, -0.11, 0.92)]
    radii = [(0.016, 0.006)] * len(path)
    sv, sf, su = tube_along(path, radii, n_side=8)
    objs.append(new_mesh_obj("Edm_SatchelStrap", sv, sf, uvs=su, mat=mats["satchel"]))
    return join_objects(objs, "Edmund_Satchel")

def build_outfit(mats):
    return {
        "shirt": build_shirt(mats),
        "waistcoat": build_waistcoat(mats),
        "coat": build_coat(mats),
        "neckcloth": build_neckcloth(mats),
        "trousers": build_trousers(mats),
        "boots": build_boots(mats),
        "satchel": build_satchel(mats),
    }
