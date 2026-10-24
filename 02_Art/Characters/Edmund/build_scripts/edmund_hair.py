#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Edmund hair as procedural hair-card MESH (game-friendly, UE-exportable).
- Scalp cap (hair-colored dome under strands, hides gaps)
- ~2400 combable strands as thin quad ribbons flowing: part on his left,
  swept right+back, falling beside the ears (1847 unkempt medium hair)
- 2-week stubble (~4000 tiny cards on jaw/chin/upper-lip region)
- eyebrows (~600 cards along the brow ridges)
All geometry is generated from the ACTUAL head mesh surface (root positions
sampled from head vertices + normals).
"""
import math, random
from mathutils import Vector
from edmund_lib import new_mesh_obj, TAU
from edmund_body import HEAD_C, HEAD_R, EYE_C

def _head_frame():
    return Vector(HEAD_C)

def scalp_mask_d(d):
    """d = offset from head center (normalized-space helpers use meters)."""
    if d.length > 0.135:
        return False
    if d.z < 0.005:
        return False
    if d.y < -0.030 and abs(d.x) < 0.052 and d.z < 0.055:
        return False
    return True

def beard_mask_d(d):
    if d.length > 0.135:
        return False
    if d.y > -0.020:
        return False
    if d.z > -0.018 or d.z < -0.112:
        return False
    # exclude the nose volume
    if abs(d.x) < 0.017 and d.y < -0.075 and d.z > -0.040:
        return False
    return True

def brow_mask_d(d):
    if not (-0.095 < d.y < -0.040):
        return False
    if not (0.018 < abs(d.x) < 0.058):
        return False
    if not (0.028 < d.z < 0.060):
        return False
    return True

def _sample_roots(body, mask_fn, count, seed, jitter=0.004, inset=0.0015):
    """Sample roots from body verts whose position satisfies mask (head region)."""
    rng = random.Random(seed)
    hc = Vector(HEAD_C)
    cand = []
    for v in body.data.vertices:
        d = Vector(v.co) - hc
        if mask_fn(d):
            cand.append((Vector(v.co), Vector(v.normal).normalized()))
    if not cand:
        return []
    roots = []
    for _ in range(count):
        p, n = cand[rng.randrange(len(cand))]
        # tangential jitter
        t1 = n.cross(Vector((0, 0, 1)))
        if t1.length < 1e-4:
            t1 = Vector((1, 0, 0))
        t1.normalize()
        t2 = n.cross(t1).normalized()
        a = rng.uniform(0, TAU)
        r = rng.uniform(0, jitter)
        root = p + t1 * (r * math.cos(a)) + t2 * (r * math.sin(a)) - n * inset
        roots.append((root, n, rng))
    return roots

def _strand_points(root, n, rng, length, flow_fn, npts=6, noise=0.006,
                   flat=0.78, hug=True):
    """Integrate a strand from root. With hug=True the comb vector is projected
    onto the scalp tangent plane so the strand lies ON the head, releasing
    gradually toward the raw comb/gravity direction as it grows out."""
    pts = [root]
    raw0 = flow_fn(root, 0.0)
    if hug:
        nrm = _head_normal(root)
        tang = raw0 - raw0.dot(nrm) * nrm
        if tang.length < 1e-5:
            tang = Vector((0, 0, -1))
        tang.normalize()
        d = (n * (1.0 - flat) + tang * flat).normalized()
    else:
        d = (n * (1.0 - flat) + raw0 * flat).normalized()
    L = length * rng.uniform(0.75, 1.1)
    dt = L / (npts - 1)
    p = root
    for i in range(1, npts):
        t = i / (npts - 1)
        raw = flow_fn(root, t)
        if hug:
            # blend tangent-hugging into free fall as the strand leaves the scalp
            nrm = _head_normal(p)
            tang = raw - raw.dot(nrm) * nrm
            if tang.length < 1e-5:
                tang = Vector((0, 0, -1))
            tang.normalize()
            release = min(1.0, max(0.0, (t - 0.25) / 0.6))
            tgt = (tang * (1.0 - release) + raw * release).normalized()
        else:
            tgt = raw
        d = (d * (1.0 - 0.45 * t) + tgt * (0.45 * t + 0.25)).normalized()
        step = d * dt
        step = step + Vector((rng.gauss(0, noise), rng.gauss(0, noise),
                              rng.gauss(0, noise * 0.5)))
        p = p + step
        pts.append(p)
    return pts

def _hair_flow(root, t):
    """1847 style: forehead swept BACK, side part (his left), falling down.
    The RAW comb vector is projected onto the scalp tangent plane by the caller
    so strands hug the skull; near t=1 gravity takes over."""
    p = root - _head_frame()
    # forehead + top-front: sweep back
    if p.y < -0.030 and p.z > -0.01:
        base = Vector((math.copysign(0.45, p.x + 0.012), 0.95, -0.45))
    elif p.x < -0.012:
        base = Vector((-1.0, -0.30, -0.9))
    else:
        base = Vector((1.0, -0.30, -0.9))
    return base

def _head_normal(root):
    hc = _head_frame()
    d = root - hc
    # ellipsoid-ish normal approx: scale y back to sphere
    n = Vector((d.x / 0.094, d.y / 0.109, d.z / 0.126))
    n.normalize()
    return n

def _gravity_flow(root, t):
    return Vector((math.copysign(0.35, root.x - _head_frame().x + 0.012),
                   -0.25, -1.0))

def _ribbons(strands, width, coll="Edmund", mat=None, name="Hair",
             side_mode="root_normal"):
    """strands: list of list-of-Vector. Build one mesh of hair-card ribbons.
    side_mode root_normal: card lies flat against the root surface normal
    (hair hugs the scalp - correct for combed hair)."""
    verts, faces, uvs = [], [], []
    vi = 0
    hc = _head_frame()
    for pts in strands:
        nseg = len(pts) - 1
        root_n = (pts[0] - hc)
        # approximate root normal: from head center to root
        root_n.z = root_n.z * 0.6 + 0.02
        root_n.normalize()
        sides = []
        for i, p in enumerate(pts):
            if i == 0:
                tan = pts[1] - pts[0]
            elif i == nseg:
                tan = pts[-1] - pts[-2]
            else:
                tan = pts[i + 1] - pts[i - 1]
            tan.normalize()
            side = tan.cross(root_n)
            if side.length < 1e-5:
                side = tan.cross(Vector((0, 1, 0)))
            side.normalize()
            sides.append(side)
        w0 = width * 1.35
        w1 = width * 0.55
        for i, p in enumerate(pts):
            w = w0 + (w1 - w0) * (i / nseg)
            s = sides[i] * w
            pa = p + s
            pb = p - s
            verts.append((pa.x, pa.y, pa.z))
            verts.append((pb.x, pb.y, pb.z))
            uvs.append((0.0, i / nseg))
            uvs.append((1.0, i / nseg))
        for i in range(nseg):
            a = vi + i * 2
            faces.append((a, a + 1, a + 3, a + 2))
        vi += len(pts) * 2
    return new_mesh_obj(name, verts, faces, uvs=uvs, mat=mat, coll=coll)

def build_hair(body, mats, seed=42, strand_count=3800, fast=False):
    hc = _head_frame()
    objs = []
    # --- scalp cap: dome of hair-colored skin under the strands
    cap_v, cap_f = [], []
    idx_map = {}
    for v in body.data.vertices:
        d = Vector(v.co) - hc
        if scalp_mask_d(d):
            n = Vector(v.normal).normalized()
            idx_map[v.index] = len(cap_v)
            cap_v.append(tuple(Vector(v.co) - n * 0.004))
    for f in body.data.polygons:
        vs = f.vertices
        if all(i in idx_map for i in vs):
            cap_f.append(tuple(idx_map[i] for i in vs))
    if cap_f:
        objs.append(new_mesh_obj("Edm_ScalpCap", cap_v, cap_f, mat=mats["hair"]))
    # --- strands
    n = 1400 if fast else 4600
    roots = _sample_roots(body, scalp_mask_d, n, seed=seed, jitter=0.005)
    strands = []
    hc2 = _head_frame()
    for root, nrm, rng in roots:
        d = root - hc2
        horiz = math.sqrt(d.x * d.x + d.y * d.y)
        L = 0.095 + 0.045 * max(0.0, d.z / 0.12) + rng.uniform(-0.012, 0.018)
        if d.z < 0.03 and horiz > 0.075:
            L *= 0.50   # above ears short
        if abs(d.x) < 0.03 and d.y < -0.06 and d.z > 0.02:
            L *= 0.62   # forehead fringe shorter
        pts = _strand_points(root, nrm, rng, L, _hair_flow, npts=6,
                             noise=0.0015, flat=0.85)
        strands.append(pts)
    objs.append(_ribbons(strands, width=0.0009, mat=mats["hair"],
                         name="Edm_HairStrands"))
    return join_list(objs, "Edmund_Hair")

def build_stubble(body, mats, seed=77, count=5200, fast=False):
    n = 1800 if fast else count
    roots = _sample_roots(body, beard_mask_d, n, seed=seed, jitter=0.003,
                          inset=0.0006)
    strands = []
    for root, nrm, rng in roots:
        L = rng.uniform(0.003, 0.0055)
        flow = lambda r, t, nn=nrm: nn * 0.6 + Vector((0, -1, -0.25)) * 0.5
        pts = _strand_points(root, nrm, rng, L, flow, npts=3, noise=0.0003,
                             flat=0.35)
        strands.append(pts)
    return _ribbons(strands, width=0.0004, mat=mats["stubble"],
                    name="Edmund_Stubble")

def build_brows(body, mats, seed=99):
    strands = []
    hc = _head_frame()
    rng = random.Random(seed)
    # place along brow ridge arcs (radius outside the ridge bump)
    for sgn in (1, -1):
        for _ in range(300):
            u = rng.uniform(-1.0, 1.0)            # along brow
            v = rng.uniform(-0.35, 0.35)          # across brow
            bx = sgn * (0.033 + 0.016 * u)
            bz = 0.040 - 0.010 * (u * u) + 0.006 * v
            by = -(0.070 + 0.008 * (u * u)) - 0.004 * v
            p = hc + Vector((bx, by, bz))
            d = p - hc
            d.normalize()
            surf = hc + d * (0.1085)
            n = d
            L = rng.uniform(0.012, 0.017)
            flow_dir = Vector((sgn * 0.8, -0.25, -0.35)).normalized()
            pts = [surf - n * 0.001]
            dd = (n + flow_dir * 0.6).normalized()
            q = pts[0]
            for i in range(2):
                q = q + dd * (L / 2)
                dd = (dd * 0.7 + flow_dir * 0.5).normalized()
                pts.append(q)
            strands.append(pts)
    return _ribbons(strands, width=0.0012, mat=mats["brow"],
                    name="Edmund_Brows")

def join_list(objs, name):
    from edmund_lib import join_objects
    if len(objs) == 1:
        objs[0].name = name
        return objs[0]
    return join_objects(objs, name)
