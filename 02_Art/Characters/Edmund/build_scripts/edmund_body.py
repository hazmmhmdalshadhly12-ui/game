#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Edmund Vale - parametric human anatomy builder.
Design contract from docs/CHARACTER_REGISTRY.md (CHR-01):
  1.78m, slender trunk, solid rounded shoulders, dark-brown unkempt hair,
  two-week stubble, tired gray eyes, ink stain on left hand.
Facing: character looks toward -Y (matches repo FBX contract axis_forward='-Y').
"""
import math
from mathutils import Vector
from edmund_lib import (uv_sphere_grid, gauss, loft_rings, ellipse_ring,
                        new_mesh_obj, join_objects, smooth_verts, TAU)

H = 1.78  # total height

# head center (relative world) - tuned so total height with crown lands at 1.78m
# M3.5: crown +6mm (rz 0.126->0.132) so measured height lands at ~1.775m with
# grounded boots (M3.5 fixes the 14mm float of the old build)
HEAD_C = (0.0, -0.004, 1.665)
HEAD_R = (0.094, 0.109, 0.132)

# ---------------------------------------------------------------- helpers
def tube_along(path, radii, n_side=14, up_hint=(1, 0, 0), u_close=True,
               cap_start=False, cap_end=False):
    """Loft an elliptical tube through path points. radii = [(wx,wy) per point]."""
    rings = []
    for i, p in enumerate(path):
        p = Vector(p)
        if i == 0:
            t = (Vector(path[1]) - Vector(path[0]))
        elif i == len(path) - 1:
            t = (Vector(path[-1]) - Vector(path[-2]))
        else:
            t = (Vector(path[i + 1]) - Vector(path[i - 1]))
        t.normalize()
        up = Vector(up_hint)
        x = up - up.dot(t) * t
        if x.length < 1e-4:
            x = Vector((0, 0, 1))
            x = x - x.dot(t) * t
        x.normalize()
        y = t.cross(x)
        wx, wy = radii[i]
        pts, uvs = [], []
        for k in range(n_side):
            a = TAU * k / n_side
            px = p + x * (wx * math.cos(a)) + y * (wy * math.sin(a))
            pts.append((px.x, px.y, px.z))
            uvs.append((k / n_side, i / max(1, len(path) - 1)))
        rings.append({"verts": pts, "uvs": uvs})
    verts, faces, uvs = loft_rings(rings, closed_loop=u_close,
                                   cap_bottom=cap_start, cap_top=cap_end)
    return verts, faces, uvs

def mirror_path(path):
    return [(-p[0], p[1], p[2]) for p in path]

# ---------------------------------------------------------------- torso+neck
def build_torso():
    rings_spec = [
        # z,    cx, cy,     wx,    wy
        (0.865, 0.0,  0.006, 0.142, 0.098),
        (0.900, 0.0,  0.012, 0.150, 0.104),
        (0.955, 0.0,  0.014, 0.146, 0.103),
        (1.020, 0.0,  0.008, 0.136, 0.098),
        (1.100, 0.0,  0.002, 0.128, 0.094),
        (1.180, 0.0, -0.004, 0.132, 0.097),
        (1.260, 0.0, -0.010, 0.144, 0.101),
        (1.330, 0.0, -0.012, 0.152, 0.102),
        (1.400, 0.0, -0.008, 0.148, 0.094),
        (1.440, 0.0, -0.002, 0.116, 0.082),
        (1.470, 0.0,  0.002, 0.084, 0.072),
        (1.500, 0.0,  0.004, 0.062, 0.058),
        (1.535, 0.0,  0.004, 0.055, 0.052),
        (1.556, 0.0,  0.002, 0.053, 0.050),
    ]
    rings = [ellipse_ring(z, cx, cy, wx, wy, n=36) for z, cx, cy, wx, wy in rings_spec]
    verts, faces, uvs = loft_rings(rings, closed_loop=True, cap_bottom=True)
    # chest pecs + back flatten + glute shaping via gentle local displacement
    out = []
    for (x, y, z) in verts:
        if 1.24 < z < 1.40 and y < 0 and abs(x) < 0.09:
            k = math.exp(-((z - 1.32) / 0.055) ** 2) * math.exp(-((x / 0.055) ** 2))
            y -= 0.014 * k
        if 1.10 < z < 1.34 and y > 0.055:
            y -= 0.012 * math.exp(-((z - 1.22) / 0.09) ** 2)
        if 0.88 < z < 1.00 and y > 0.03:
            y += 0.010 * math.exp(-((z - 0.94) / 0.05) ** 2) * math.exp(-((x / 0.06) ** 2))
        if 1.18 < z < 1.34 and y < -0.04:  # sternum groove
            y += 0.004 * math.exp(-((x / 0.012) ** 2)) * math.exp(-((z - 1.26) / 0.06) ** 2)
        out.append((x, y, z))
    return out, faces, uvs

# ---------------------------------------------------------------- limbs
def build_arm(side):  # side=+1 right(+X), -1 left
    s = side
    sh = (s * 0.176, -0.006, 1.428)
    elb = (s * 0.255, -0.010, 1.142)
    wr = (s * 0.320, -0.062, 0.898)
    path = [sh, (s * 0.222, -0.008, 1.320), elb, (s * 0.300, -0.040, 1.010), wr]
    radii = [(0.062, 0.070), (0.054, 0.058), (0.044, 0.048), (0.042, 0.046), (0.030, 0.034)]
    return tube_along(path, radii, n_side=16)

def build_leg(side):
    s = side
    hip = (s * 0.094, 0.006, 0.905)
    knee = (s * 0.104, 0.002, 0.515)
    ank = (s * 0.108, -0.014, 0.090)
    path = [hip, (s * 0.100, 0.006, 0.700), knee, (s * 0.108, -0.026, 0.395), ank]
    radii = [(0.086, 0.096), (0.070, 0.078), (0.060, 0.066), (0.058, 0.068), (0.036, 0.044)]
    return tube_along(path, radii, n_side=16)

def build_foot(side):
    s = side
    # simple foot wedge (hidden inside boot), toe forward -Y
    rings = [
        (0.088, s * 0.108, -0.014, 0.036, 0.046),
        (0.056, s * 0.110, -0.030, 0.040, 0.052),
        (0.030, s * 0.112, -0.070, 0.040, 0.056),
        (0.020, s * 0.112, -0.120, 0.036, 0.050),
        (0.018, s * 0.112, -0.150, 0.030, 0.040),
    ]
    rr = [{"verts": [(cx + wx * math.cos(TAU * i / 14), cy + wy * math.sin(TAU * i / 14), z)
                     for i in range(14)]} for z, cx, cy, wx, wy in rings]
    return loft_rings(rr, closed_loop=True, cap_top=True, cap_bottom=True)

# ---------------------------------------------------------------- head
BROW_Z = HEAD_C[2] + 0.036
# eyeball pushed near the surface so it shows through the socket
# M3.5: eyes 11% larger (0.0126->0.0140) - the old eyes read too small at any range
EYE_C = (HEAD_C[0] + 0.031, HEAD_C[1] - 0.091, HEAD_C[2] + 0.017)
EYE_R = 0.0140

def head_kernels():
    cx, cy, cz = HEAD_C
    K = []
    def k(dx, dy, dz, s, amp):
        K.append(((cx + dx, cy + dy, cz + dz), s, amp))
    # skull
    k(0.0, 0.020, 0.075, (0.070, 0.060, 0.050), +0.012)      # occipital
    k(0.0, -0.030, 0.092, (0.055, 0.030, 0.035), -0.004)     # forehead flatten
    k(0.0, -0.050, 0.060, (0.060, 0.030, 0.040), +0.004)     # forehead ridge
    k(0.062, 0.020, 0.030, (0.030, 0.040, 0.045), -0.006)    # temple hollows
    k(-0.062, 0.020, 0.030, (0.030, 0.040, 0.045), -0.006)
    # brow ridge
    k(0.033, -0.072, 0.040, (0.026, 0.016, 0.011), +0.0075)
    k(-0.033, -0.072, 0.040, (0.026, 0.016, 0.011), +0.0075)
    k(0.0, -0.078, 0.036, (0.014, 0.014, 0.010), -0.0025)    # glabella
    # eye sockets
    k(0.031, -0.066, 0.018, (0.022, 0.019, 0.017), -0.0090)
    k(-0.031, -0.066, 0.018, (0.022, 0.019, 0.017), -0.0090)
    # under-eye fatigue ridge (tired eyes)
    k(0.030, -0.060, 0.000, (0.018, 0.010, 0.007), +0.0020)
    k(-0.030, -0.060, 0.000, (0.018, 0.010, 0.007), +0.0020)
    # cheekbones (M3.5: more defined)
    k(0.051, -0.034, 0.006, (0.019, 0.017, 0.014), +0.0075)
    k(-0.051, -0.034, 0.006, (0.019, 0.017, 0.014), +0.0075)
    # tired cheek hollow
    k(0.042, -0.048, -0.026, (0.015, 0.013, 0.012), -0.0032)
    k(-0.042, -0.048, -0.026, (0.015, 0.013, 0.012), -0.0032)
    # nose: bridge -> tip -> wings (M3.5: stronger tip, wider wings)
    k(0.0, -0.088, 0.020, (0.011, 0.013, 0.016), +0.010)
    k(0.0, -0.098, -0.002, (0.012, 0.013, 0.016), +0.019)
    k(0.0, -0.106, -0.016, (0.013, 0.012, 0.013), +0.020)
    k(0.017, -0.090, -0.014, (0.011, 0.012, 0.011), +0.009)
    k(-0.017, -0.090, -0.014, (0.011, 0.012, 0.011), +0.009)
    # M3.5 v2: the -0.003 under-nose kernel PINCHED the tip into a star
    # artifact on render - softened to -0.0012
    k(0.0, -0.098, -0.030, (0.014, 0.010, 0.009), -0.0012)   # under-nose
    # mouth (M3.5: fuller lips so the mouth reads under the stubble)
    k(0.0, -0.084, -0.036, (0.026, 0.012, 0.009), +0.0125)   # upper lip
    k(0.0, -0.082, -0.053, (0.020, 0.012, 0.010), +0.0145)   # lower lip
    k(0.0, -0.088, -0.044, (0.024, 0.009, 0.005), -0.0085)   # lip line
    k(0.0, -0.079, -0.029, (0.006, 0.008, 0.008), +0.0020)   # philtrum
    k(0.021, -0.072, -0.037, (0.010, 0.011, 0.011), -0.0028) # nasolabial
    k(-0.021, -0.072, -0.037, (0.010, 0.011, 0.011), -0.0028)
    # chin & jaw (M3.5: firmer chin)
    k(0.0, -0.058, -0.072, (0.021, 0.019, 0.015), +0.0130)
    k(0.0, -0.052, -0.086, (0.014, 0.014, 0.010), -0.0025)   # under-chin
    k(0.049, -0.012, -0.048, (0.018, 0.017, 0.015), +0.0060) # jaw corners
    k(-0.049, -0.012, -0.048, (0.018, 0.017, 0.015), +0.0060)
    k(0.070, 0.000, -0.020, (0.020, 0.024, 0.030), +0.005)   # ramus
    k(-0.070, 0.000, -0.020, (0.020, 0.024, 0.030), +0.005)
    return K

def build_head():
    cx, cy, cz = HEAD_C
    rx, ry, rz = HEAD_R
    verts, faces, uvs = uv_sphere_grid(cx, cy, cz, rx, ry, rz, seg_u=96, seg_v=72)
    K = head_kernels()
    # skull shaping + kernels, displacement along radial dir from center
    out = []
    for (x, y, z) in verts:
        p = Vector((x, y, z))
        d = p - Vector(HEAD_C)
        n = d.normalized()
        disp = 0.0
        # vertical skull shaping: narrow top, taper jaw below
        if d.z > 0.03:
            disp -= 0.012 * min(1.0, (d.z - 0.03) / 0.09)   # crown narrow
        if d.z < -0.03:
            disp -= 0.012 * min(1.0, (-d.z - 0.03) / 0.09)  # lower face taper
        for c, s, amp in K:
            disp += gauss((x, y, z), c, s, amp)
        p2 = Vector(HEAD_C) + d + n * disp
        # jaw width narrowing below cheekbone level (adult male lower face)
        # M3.5: slightly stronger taper (0.16->0.20) for a leaner 29-year-old face
        if d.z < -0.02 and abs(p2.x - HEAD_C[0]) > 0.028:
            f = min(1.0, (-d.z - 0.02) / 0.10)
            p2.x = HEAD_C[0] + (p2.x - HEAD_C[0]) * (1.0 - 0.20 * f)
        out.append((p2.x, p2.y, p2.z))
    # gentle relax to blend kernel seams
    out = smooth_verts(out, faces, iterations=1, factor=0.22)
    return out, faces, uvs

def build_ear(side):
    s = side
    ecx = HEAD_C[0] + s * 0.096
    ecy = HEAD_C[1] + 0.004
    ecz = HEAD_C[2] + 0.004
    # M3.5: slightly larger ears (was 0.013/0.020/0.030)
    verts, faces, uvs = uv_sphere_grid(ecx, ecy, ecz, 0.015, 0.023, 0.034,
                                       seg_u=28, seg_v=20, u_off=0.25)
    out = []
    for (x, y, z) in verts:
        lx = (x - ecx) * s
        ly = y - ecy
        lz = z - ecz
        # flatten inner half into skull
        if lx < 0:
            x = ecx + s * lx * 0.35
        # helix rim: raised ring near outer edge
        rr = math.sqrt((ly / 0.017) ** 2 + (lz / 0.026) ** 2)
        rim = math.exp(-((rr - 0.78) / 0.16) ** 2)
        x += s * rim * 0.004
        # concha bowl
        bowl = math.exp(-((rr - 0.30) / 0.22) ** 2)
        x -= s * bowl * 0.005
        # lobe
        if lz < -0.014 and ly > -0.006:
            lz_scale = 1.0 + 0.15 * (-lz / 0.026)
            z = ecz + lz * lz_scale
        out.append((x, y, z))
    return out, faces, uvs

def build_eyeball(side):
    s = side
    ex = EYE_C[0] if s > 0 else -EYE_C[0]
    verts, faces, uvs = uv_sphere_grid(ex, EYE_C[1], EYE_C[2], EYE_R, EYE_R, EYE_R,
                                       seg_u=40, seg_v=28)
    # planar-front UV so iris texture maps circularly on the -Y front
    uvs2 = []
    fwd = Vector((0, -1, 0))
    for (x, y, z) in verts:
        d = Vector((x - ex, y - EYE_C[1], z - EYE_C[2]))
        front = d.dot(fwd) / EYE_R
        px = d.x / EYE_R
        pz = d.z / EYE_R
        if front > 0.05:
            # M3.5: iris covers more of the eye (was /3.4 -> tiny irises)
            u = 0.5 + px / 2.6
            v = 0.5 + pz / 2.6
        else:
            # back hemisphere: clamp to outer ring of texture (sclera white)
            a = math.atan2(d.z, d.x) / TAU
            u = (a * 0.5 + 0.5) * 0.02
            v = 0.5 + (d.y / EYE_R) * 0.02
        uvs2.append((u, v))
    return verts, faces, uvs2

def build_lid(side, upper=True):
    """Eyelid shell: sphere slightly larger than eyeball with a forward window."""
    s = side
    ex = EYE_C[0] if s > 0 else -EYE_C[0]
    r = EYE_R + 0.0018
    yoff = -0.0008
    verts, faces, uvs = uv_sphere_grid(ex, EYE_C[1] + yoff, EYE_C[2], r, r, r,
                                       seg_u=40, seg_v=24)
    keep = []
    fwd = Vector((0, -1, 0))
    up = Vector((0, 0, 1))
    cos_open = math.cos(math.radians(46 if upper else 54))
    for f in faces:
        okf = True
        for vi in f:
            d = Vector((verts[vi][0] - ex, verts[vi][1] - EYE_C[1],
                        verts[vi][2] - EYE_C[2])).normalized()
            if d.dot(fwd) > cos_open:
                okf = False
                break
            if upper and d.dot(up) < -0.30:
                okf = False
                break
            if not upper and d.dot(up) > 0.22:
                okf = False
                break
        if okf:
            keep.append(f)
    return verts, keep, uvs

# ---------------------------------------------------------------- hands
def build_hand(side):
    """Relaxed slightly-curved hand. Returns (verts, faces, uvs). Palm inward."""
    s = side
    wrist = Vector((s * 0.320, -0.062, 0.898))
    t = Vector((s * 0.253, -0.208, -0.943)).normalized()  # forearm dir continuation
    upx = Vector((1, 0, 0)) - Vector((1, 0, 0)).dot(t) * t
    upx.normalize()
    yax = t.cross(upx).normalized()   # points backward-ish
    palm_w = 0.044
    palm_t = 0.017
    # palm center offset from wrist
    pc = wrist + t * 0.048
    back = yax  # back of hand direction (opposite palm normal)
    # palm normal: inward (-x for right hand)
    pn = Vector((-s * 1.0, 0, 0))
    pn = (pn - pn.dot(t) * t).normalized()

    def frame(knuckle_t, lateral, normal_off=0.0):
        """point in hand local frame: along hand axis, across, palm-normal offset"""
        return pc + t * knuckle_t + upx * lateral + pn * normal_off

    verts, faces, uvs = [], [], []
    vbase = 0
    # palm as loft along t: 5 rings from wrist to knuckles
    rings = []
    prof = [
        (0.000, 0.030, 0.020),
        (0.018, 0.036, 0.021),
        (0.040, 0.043, 0.019),
        (0.062, 0.046, 0.015),
        (0.082, 0.043, 0.013),
    ]
    for ktt, hw, ht in prof:
        pts = []
        for k in range(16):
            a = TAU * k / 16
            q = frame(ktt, hw * math.cos(a) * 0.5 + hw * 0.0,
                      0.0)  # placeholder replaced below
        # build ring manually: ellipse across (upx) x normal (pn)
        for k in range(16):
            a = TAU * k / 16
            exx = hw * math.cos(a)
            eyy = ht * math.sin(a)
            p = pc + t * ktt + upx * exx + pn * eyy
            pts.append((p.x, p.y, p.z))
        rings.append({"verts": pts})
    pv, pf, pu = loft_rings(rings, closed_loop=True, cap_bottom=True)
    verts += pv; faces += [tuple(i + vbase for i in f) for f in pf]; uvs += pu
    vbase += len(pv)

    # fingers
    fingers = [
        # lateral offset, knuckle start, lengths (3 segs), radius
        (0.029, 0.082, (0.030, 0.022, 0.016), 0.0085),   # index
        (0.010, 0.086, (0.034, 0.026, 0.018), 0.0090),   # middle
        (-0.009, 0.082, (0.031, 0.023, 0.017), 0.0086),  # ring
        (-0.027, 0.072, (0.024, 0.019, 0.015), 0.0078),  # pinky
    ]
    curl0 = math.radians(22)
    for lat, k0, lens, r0 in fingers:
        start = frame(k0, lat, -0.002)
        d = t.normalized()
        p0 = Vector(start)
        ang = curl0
        prev_dir = d.copy()
        pts = [p0.copy()]
        for li, L in enumerate(lens):
            ang += math.radians(14 if li == 0 else 18)
            # curl rotates the finger direction toward the palm normal
            # (rotation axis = tangent x palm-normal)
            nd = prev_dir.normalized()
            axis = nd.cross(pn)
            if axis.length < 1e-5:
                axis = upx
            axis.normalize()
            cs, sn = math.cos(ang), math.sin(ang)
            nd2 = nd * cs + axis.cross(nd) * sn + axis * (axis.dot(nd)) * (1 - cs)
            nd2.normalize()
            p0 = p0 + nd2 * L
            pts.append(p0.copy())
            prev_dir = nd2
        radii = [(r0, r0 * 0.95), (r0 * 0.88, r0 * 0.85),
                 (r0 * 0.78, r0 * 0.75), (r0 * 0.66, r0 * 0.64)]
        fv, ff, fu = tube_along([tuple(p) for p in pts], radii, n_side=12,
                                up_hint=tuple(upx), cap_end=True)
        verts += fv; faces += [tuple(i + vbase for i in f) for f in ff]; uvs += fu
        vbase += len(fv)

    # thumb
    tstart = frame(0.030, s * 0.034, -0.004)
    tdir = (t.normalized() * 0.55 + upx * (s * 0.75) + pn * 0.28).normalized()
    pts = [Vector(tstart)]
    p0 = Vector(tstart)
    for L, r in [(0.036, 0.0105), (0.030, 0.0092), (0.024, 0.0080)]:
        p0 = p0 + tdir * L
        tdir = (tdir + pn * -0.10).normalized()
        pts.append(p0.copy())
    radii = [(0.0135, 0.0130), (0.0112, 0.0108), (0.0095, 0.0092), (0.0082, 0.0080)]
    tv, tf, tu = tube_along([tuple(p) for p in pts], radii, n_side=12,
                            up_hint=tuple(upx), cap_end=True)
    verts += tv; faces += [tuple(i + vbase for i in f) for f in tf]; uvs += tu
    return verts, faces, uvs

# ---------------------------------------------------------------- assembly
# M3.5 SIDE-NAMING FIX: the character faces -Y, so anatomical LEFT = +X
# (Blender/Rigify convention). The old build named s=+1 "R" which put every
# .R label on the character's left - wrong for UE retargeting and put the
# CHR-01 ink stain on the wrong hand. Now: s=+1 -> ".L", s=-1 -> ".R".
def build_body(mats):
    objs = []
    torso = new_mesh_obj("Edm_Torso", *build_torso(), mat=mats["skin"])
    objs.append(torso)
    for s, nm in ((1, "L"), (-1, "R")):
        a = new_mesh_obj(f"Edm_Arm{nm}", *build_arm(s), mat=mats["skin"])
        l = new_mesh_obj(f"Edm_Leg{nm}", *build_leg(s), mat=mats["skin"])
        f = new_mesh_obj(f"Edm_Foot{nm}", *build_foot(s), mat=mats["skin"])
        objs += [a, l, f]
        # deltoid cap to blend arm into shoulder
        verts, faces, uvs = uv_sphere_grid(s * 0.176, -0.006, 1.428, 0.064, 0.066, 0.070,
                                           seg_u=24, seg_v=16)
        d = new_mesh_obj(f"Edm_Delt{nm}", verts, faces, uvs=uvs, mat=mats["skin"])
        objs.append(d)
    head = new_mesh_obj("Edm_Head", *build_head(), mat=mats["skin"])
    objs.append(head)
    for s, nm in ((1, "R"), (-1, "L")):
        e = new_mesh_obj(f"Edm_Ear{nm}", *build_ear(s), mat=mats["skin"])
        objs.append(e)
        lv, lf, lu = build_lid(s, upper=True)
        uv_, lf2, _ = build_lid(s, upper=False)
        ul = new_mesh_obj(f"Edm_LidU{nm}", lv, lf, uvs=lu, mat=mats["skin"])
        ll = new_mesh_obj(f"Edm_LidL{nm}", uv_, lf2, mat=mats["skin"])
        objs += [ul, ll]
    body = join_objects(objs, "Edmund_Body")
    return body

def build_eyes(mats):
    eyes = []
    for s, nm in ((1, "L"), (-1, "R")):
        e = new_mesh_obj(f"Edmund_Eye{nm}", *build_eyeball(s), mat=mats["eye"])
        eyes.append(e)
    return eyes

def build_hands(mats):
    hands = []
    # M3.5: ink stain follows the anatomical LEFT hand (CHR-01: "يسار يده")
    for s, nm in ((1, "L"), (-1, "R")):
        m = mats["skin_ink"] if s > 0 else mats["skin"]
        h = new_mesh_obj(f"Edmund_Hand{nm}", *build_hand(s), mat=m)
        hands.append(h)
    return hands
