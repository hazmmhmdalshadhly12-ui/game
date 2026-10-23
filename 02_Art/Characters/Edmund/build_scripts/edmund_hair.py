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
from edmund_body import HEAD_C, HEAD_R, EYE_C, EYE_R

_BVH_CACHE = {}

def _head_bvh(body):
    """BVH tree over the actual head-region mesh for surface-hug fixes.
    Cached per build (the body mesh is static at hair-build time)."""
    key = body.name
    if key not in _BVH_CACHE:
        from mathutils.bvhtree import BVHTree
        me = body.data
        _BVH_CACHE[key] = (BVHTree.FromPolygons([v.co[:] for v in me.vertices],
                                                [tuple(p.vertices) for p in me.polygons]),
                           len(me.vertices))
    return _BVH_CACHE[key][0]

def _push_outside(bvh, p, t):
    """If p is inside (or grazing) the actual head surface, lift it just
    above the surface along the local normal. Returns p unchanged when it
    is already clear of the mesh."""
    hit = bvh.find_nearest(p)
    if hit is None or hit[0] is None:
        return p
    co, nrm, _, _ = hit
    off = p - co
    if off.dot(nrm) < 0.0006:
        return co + nrm * (0.0008 + 0.006 * t)
    return p

def _head_frame():
    return Vector(HEAD_C)

def scalp_mask_d(d):
    """d = offset from head center (normalized-space helpers use meters).
    M3.6: hairline lowered (face cone cut z<0.040, |x|<0.048, y<-0.034)
    - the v1 hairline left a bare pink forehead a centimeter too tall."""
    if d.length > 0.135:
        return False
    if d.z < 0.005:
        return False
    if d.y < -0.034 and abs(d.x) < 0.048 and d.z < 0.040:
        return False
    return True

def beard_mask_d(d):
    if d.length > 0.135:
        return False
    if d.y > -0.020:
        return False
    # M3.6: cut at z>-0.030 (was -0.018 - the old stubble climbed to the
    # lower orbits and read as disease, not beard shadow)
    if d.z > -0.030 or d.z < -0.112:
        return False
    # M3.6: upper-cheek carve - keep the jaw/chin/lip zone, clear the cheeks
    if d.z > -0.052 and abs(d.x) > 0.030 and d.y > -0.062:
        return False
    # exclude the nose volume
    if abs(d.x) < 0.017 and d.y < -0.075 and d.z > -0.040:
        return False
    # M3.5: exclude the LIPS so the mouth reads clearly (old build grew
    # stubble across both lips and the mouth vanished at mid distance)
    if abs(d.x) < 0.028 and d.y < -0.070 and -0.064 < d.z < -0.024:
        return False
    # M3.6 DESIGNED SIDEBURNS: two narrow strips in front of the tragus
    # connecting the scalp hair to the beard (1847 look)
    if 0.052 < abs(d.x) < 0.078 and -0.030 < d.y < 0.030 and d.z < 0.020:
        return True
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
                   flat=0.78, hug=True, bvh=None):
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
    # M3.6 v2: ELLIPSOID clamp - limits how far a strand can leave the local
    # surface without crushing it back inside the skull. (v1 clamp measured
    # from head center with a SPHERE radius: strands flowing toward a fatter
    # part of the ellipsoid (or over a +8mm kernel bump) got pushed INSIDE
    # the head, leaving only their 2% solid root bands visible as the
    # "blocky chips" on the scalp.)
    do_clamp = length > 0.02
    for i in range(1, npts):
        t = i / (npts - 1)
        raw = flow_fn(root, t)
        if hug:
            # blend tangent-hugging into free fall as the strand leaves the scalp
            # M3.6: release even later (t-0.60)/0.3 - kills the spiky halo
            nrm = _head_normal(p)
            tang = raw - raw.dot(nrm) * nrm
            if tang.length < 1e-5:
                tang = Vector((0, 0, -1))
            tang.normalize()
            release = min(1.0, max(0.0, (t - 0.60) / 0.30))
            tgt = (tang * (1.0 - release) + raw * release).normalized()
        else:
            tgt = raw
        d = (d * (1.0 - 0.45 * t) + tgt * (0.45 * t + 0.25)).normalized()
        step = d * dt
        step = step + Vector((rng.gauss(0, noise), rng.gauss(0, noise),
                              rng.gauss(0, noise * 0.5)))
        p = p + step
        if do_clamp:
            # M3.6 v2 ellipsoid clamp (see note above)
            hc = _head_frame()
            dv = p - hc
            re = math.sqrt((dv.x / 0.094) ** 2 + (dv.y / 0.109) ** 2
                           + (dv.z / 0.132) ** 2)
            lim = 1.03 + 0.42 * t
            if re > lim:
                p = hc + dv * (lim / re)
        # M3.6 v3: surface-hug fix - the ellipsoid tangent is only an
        # approximation of the real head surface (kernels deviate +-8mm);
        # strands dove inside the mesh and only their solid root bands
        # showed as the "chips" on the scalp. BVH closest-point lifts any
        # submerged point back just above the true surface.
        if bvh is not None:
            p = _push_outside(bvh, p, t)
        pts.append(p)
    return pts

def _hair_flow(root, t):
    """1847 style: forehead swept BACK, side part (his left), falling down.
    The RAW comb vector is projected onto the scalp tangent plane by the caller
    so strands hug the skull; near t=1 gravity takes over.
    M3.5 v2: side/back flow mostly DOWNWARD (was +-1.0 outward which made the
    silhouette explode on render).
    M3.6 v3: the front-top quadrant (part-line forwards, above the fringe)
    MUST sweep back - the old side-down rule let those strands fall FORWARD
    onto the face, laying hair cards across the eyes on render."""
    p = root - _head_frame()
    # forehead + top-front: sweep back (fringe falls forward-down slightly)
    if p.y < -0.030 and p.z > -0.01:
        base = Vector((math.copysign(0.30, p.x + 0.012), 0.70, -0.70))
    # front-top quadrant: sweep back too (never forward)
    elif p.z > 0.055 and p.y < 0.045:
        base = Vector((math.copysign(0.30, p.x + 0.012), 0.95, -0.35))
    elif p.x < -0.012:
        base = Vector((-0.35, 0.30, -1.0))   # M3.6: falls down-BACK, never
    else:                                     # forward across the face
        base = Vector((0.35, 0.30, -1.0))
    return base

def _head_normal(root):
    hc = _head_frame()
    d = root - hc
    # ellipsoid-ish normal approx: scale y back to sphere
    # M3.6: rz synced with HEAD_R[2]=0.132 (was stale 0.126 from M3.4 crown)
    n = Vector((d.x / 0.094, d.y / 0.109, d.z / 0.132))
    n.normalize()
    return n

def _gravity_flow(root, t):
    return Vector((math.copysign(0.35, root.x - _head_frame().x + 0.012),
                   -0.25, -1.0))

def _ribbons(strands, width, coll="Edmund", mat=None, name="Hair",
             side_mode="root_normal"):
    """strands: list of list-of-Vector. Build one mesh of hair-card ribbons.
    M3.6 v4: PARALLEL-TRANSPORTED side vector. The v1 code crossed every
    tangent with the CONSTANT root normal - once a strand curved over the
    dome and started hanging down, the tangent rotated ~180 deg relative to
    the root normal, the side vector flipped, and the ribbon folded over
    itself into the hard-edged dark "chips" seen on every render since
    M3.5. Transporting the side vector along the strand (re-orthogonalized
    against each tangent) keeps the ribbon flat and twist-free."""
    verts, faces, uvs = [], [], []
    vi = 0
    hc = _head_frame()
    for pts in strands:
        nseg = len(pts) - 1
        root_n = (pts[0] - hc)
        root_n.z = root_n.z * 0.6 + 0.02
        root_n.normalize()
        prev_side = None
        sides = []
        for i, p in enumerate(pts):
            if i == 0:
                tan = pts[1] - pts[0]
            elif i == nseg:
                tan = pts[-1] - pts[-2]
            else:
                tan = pts[i + 1] - pts[i - 1]
            tan.normalize()
            if prev_side is None:
                side = tan.cross(root_n)
                if side.length < 1e-5:
                    side = tan.cross(Vector((0, 1, 0)))
            else:
                # parallel transport: keep prev side, re-orthogonalize
                side = prev_side - tan * prev_side.dot(tan)
                if side.length < 1e-5:
                    side = tan.cross(root_n)
            side.normalize()
            sides.append(side)
            prev_side = side
        w0 = width * 1.15
        # M3.6 v5: strong geometric taper (tip = 22% of root) replaces the
        # disabled alpha-texture fade - solid cards must taper to read as hair
        w1 = width * 0.22
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
    bvh = _head_bvh(body)
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
        # M3.6: solid hair-cap material (alpha card texture on the dome UV
        # produced blocky transparency - see edmund_materials.py note)
        objs.append(new_mesh_obj("Edm_ScalpCap", cap_v, cap_f, mat=mats["hair_cap"]))
    # --- strands
    n = 1400 if fast else 3600
    roots = _sample_roots(body, scalp_mask_d, n, seed=seed, jitter=0.005)
    strands = []
    hc2 = _head_frame()
    for root, nrm, rng in roots:
        d = root - hc2
        horiz = math.sqrt(d.x * d.x + d.y * d.y)
        # M3.6: shorter overall (0.095+0.045 -> 0.082+0.032) - the 1847 cut
        L = 0.082 + 0.032 * max(0.0, d.z / 0.12) + rng.uniform(-0.010, 0.014)
        if d.z < 0.03 and horiz > 0.075:
            L *= 0.34   # above ears short (backward flow keeps them clear)
        if abs(d.x) < 0.03 and d.y < -0.06 and d.z > 0.02:
            L *= 0.85   # forehead fringe (tapered hairline, M3.6)
        if d.y > 0.045 and d.z < 0.05:
            L *= 0.60   # nape/back-hair shorter so it hugs the skull
        pts = _strand_points(root, nrm, rng, L, _hair_flow, npts=6,
                             noise=0.0020, flat=0.92, bvh=bvh)
        # M3.6: HARD FACE FILTER - any strand reaching the lower-front face
        # volume (in front of the skin, below mid-forehead, between the
        # temples) is discarded. The box top (+0.030 rel. head center) sits
        # BELOW the fringe root band (+0.036..+0.055) so the hairline itself
        # survives; only strands hanging DOWN onto the eyes/brows are cut.
        bad = False
        for p in pts:
            dp = p - hc2
            if dp.y < -0.055 and abs(dp.x) < 0.055 and dp.z < 0.020:
                bad = True
                break
        if bad:
            continue
        strands.append(pts)
    # M3.6: fewer but WIDER cards (0.0011 -> 0.0014 solid, tapered to 22%):
    # the geometric taper carries the tip fade since the alpha texture is off
    objs.append(_ribbons(strands, width=0.0014, mat=mats["hair"],
                         name="Edm_HairStrands"))
    return join_list(objs, "Edmund_Hair")

def build_stubble(body, mats, seed=77, count=5200, fast=False):
    n = 1800 if fast else 4400
    roots = _sample_roots(body, beard_mask_d, n, seed=seed, jitter=0.003,
                          inset=0.0006)
    strands = []
    for root, nrm, rng in roots:
        # M3.6: shorter crop (2-week beard, not scrub)
        L = rng.uniform(0.0025, 0.0042)
        flow = lambda r, t, nn=nrm: nn * 0.6 + Vector((0, -1, -0.25)) * 0.5
        pts = _strand_points(root, nrm, rng, L, flow, npts=3, noise=0.0003,
                             flat=0.35)
        strands.append(pts)
    return _ribbons(strands, width=0.00045, mat=mats["stubble"],
                    name="Edmund_Stubble")

def build_brows(body, mats, seed=99):
    """M3.6 v2: brow roots sampled from the ACTUAL head surface (the v1
    parametric ring got buried under the strengthened M3.6 brow-ridge
    kernels and the strands poked through the skin like floating wire)."""
    roots = _sample_roots(body, brow_mask_d, 760, seed=seed, jitter=0.0018,
                          inset=0.0008)
    strands = []
    hc = _head_frame()
    for root, nrm, r2 in roots:
        L = r2.uniform(0.0070, 0.0105)
        sgn = math.copysign(1.0, root.x - hc.x)
        flow_dir = Vector((sgn * 0.85, -0.18, -0.22)).normalized()
        pts = [root]
        dd = (nrm * 0.5 + flow_dir * 0.5).normalized()
        q = pts[0]
        for i in range(2):
            q = q + dd * (L / 2)
            dd = (dd * 0.7 + flow_dir * 0.5).normalized()
            pts.append(q)
        strands.append(pts)
    return _ribbons(strands, width=0.0008, mat=mats["brow"],
                    name="Edmund_Brows")

def build_lashes(body, mats, seed=101):
    """M3.6: upper-lid eyelashes (render-extra cards along the lid rim).
    Root ring sits on the lid shell at the upper aperture angle (41 deg);
    lashes sweep up-and-out with center-weighted length."""
    rng = random.Random(seed)
    strands = []
    for s in (1, -1):
        ec = Vector((EYE_C[0] * s, EYE_C[1], EYE_C[2]))
        ex = EYE_C[0] if s > 0 else -EYE_C[0]
        ecx = ex
        el = math.radians(41.0)
        for i in range(140):
            az = rng.uniform(-1.72, 1.72)
            # skip the extreme outer corner (10%)
            if abs(az) > 1.60 and rng.random() < 0.5:
                continue
            d = Vector((math.sin(el) * math.sin(az),
                        -math.cos(el),
                        math.sin(el) * math.cos(az)))
            d.normalize()
            root = ec + d * (EYE_R + 0.0026)
            # slight inward-out curvature across the aperture
            jitter = Vector((rng.gauss(0, 0.0004), rng.gauss(0, 0.0004),
                             rng.gauss(0, 0.0002)))
            root = root + jitter
            # center lashes longer (cos weight on azimuth)
            L = 0.0040 + 0.0035 * (math.cos(az * 0.5) ** 2) + rng.uniform(0, 0.0012)
            flow = (d * 0.30 + Vector((0.0, -0.18, 0.92))).normalized()
            n = d
            pts = [root]
            dd = (n * 0.4 + flow * 0.6).normalized()
            q = pts[0]
            for k in range(2):
                q = q + dd * (L / 2)
                dd = (dd * 0.6 + flow * 0.4).normalized()
                pts.append(q)
            strands.append(pts)
    return _ribbons(strands, width=0.0003, mat=mats["brow"],
                    name="Edmund_Lashes")

def join_list(objs, name):
    from edmund_lib import join_objects
    if len(objs) == 1:
        objs[0].name = name
        return objs[0]
    return join_objects(objs, name)
