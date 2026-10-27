#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE LAST SIN - AAA sculpt engine v2 (numpy-vectorized).
Parametric displacement sculpting on dense quad grids.
Used by build_edmund_v2.py, build_npcs.py, build_env_v2.py, build_props_v2.py.

Method (honest documentation):
- Base surfaces are parametric quad grids (UV-sphere / boxes / lofts).
- Primary anatomical forms are sculpted by anisotropic gaussian displacement
  fields applied along chosen axes (vectorized over all vertices).
- Secondary detail (wrinkles, creases, folds) is carved as distance-to-polyline
  trenches on the subdivided (dense) grid.
- Tertiary micro detail uses 3-octave value-noise displacement.
This is a scripted sculpting pipeline: every pass is real geometry modification
on dense meshes, inspectable in Blender. It is NOT hand sculpting.
"""
import math
import numpy as np

TAU = math.pi * 2.0

# ---------------------------------------------------------------- noise
def _hash3(i, j, k, seed=0):
    h = (i * 374761393 + j * 668265263 + k * 2147483647 + seed * 1274126177) & 0x7FFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0x7FFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0

def value_noise3(x, y, z, seed=0):
    """Trilinear value noise. x,y,z: np arrays. Returns [0,1]."""
    xi, yi, zi = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64), np.floor(z).astype(np.int64)
    xf, yf, zf = x - xi, y - yi, z - zi
    u, v, w = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf), zf * zf * (3 - 2 * zf)
    def c(i, j, k):
        return _hash3(xi + i, yi + j, zi + k, seed)
    n = (c(0,0,0)*(1-u)+c(1,0,0)*u)*(1-v) + (c(0,1,0)*(1-u)+c(1,1,0)*u)*v
    s = (c(0,0,1)*(1-u)+c(1,0,1)*u)*(1-v) + (c(0,1,1)*(1-u)+c(1,1,1)*u)*v
    return n * (1 - w) + s * w

def fbm3(x, y, z, octaves=3, lac=2.0, gain=0.5, seed=0):
    total = np.zeros_like(x)
    amp, freq = 1.0, 1.0
    norm = 0.0
    for o in range(octaves):
        total += amp * value_noise3(x * freq + o * 17.3, y * freq + o * 9.1,
                                    z * freq + o * 31.7, seed + o)
        norm += amp
        amp *= gain; freq *= lac
    return total / max(norm, 1e-9)

# ---------------------------------------------------------------- grids
def sphere_grid(S=96, P=72):
    """Unit direction grid (S, P+1, 3). theta around Z (+X start, -Y at theta=pi/2 -> face), phi pole-to-pole (+Z top)."""
    theta = (np.arange(S) + 0.5) / S * TAU
    phi = np.linspace(0.0, math.pi, P + 1)
    T, PH = np.meshgrid(theta, phi, indexing="ij")
    dx = np.sin(PH) * np.cos(T)
    dy = -np.sin(PH) * np.sin(T)          # face at theta=pi/2 -> dy=-1 (forward = -Y)
    dz = np.cos(PH)
    return np.stack([dx, dy, dz], axis=-1), T, PH

def quad_faces(S, P):
    """Quad face indices for the (S, P+1) grid. Poles (rows 0, P) degenerate to tris."""
    faces = []
    for i in range(S):
        i2 = (i + 1) % S
        for j in range(P):
            a = i * (P + 1) + j
            b = i2 * (P + 1) + j
            c = i2 * (P + 1) + j + 1
            d = i * (P + 1) + j + 1
            if j == 0:            # bottom pole row: tri (collapse a)
                faces.append((b, c, d))
            elif j == P - 1:      # top pole row: tri (collapse c)
                faces.append((a, b, d))
            else:
                faces.append((a, b, c, d))
    return faces

def subdiv_grid(verts, f=2):
    """Bilinear subdivision of a (S, P+1, 3) grid by integer factor f (wrap in S)."""
    S, Pp1, _ = verts.shape
    out = np.empty((S * f, (Pp1 - 1) * f + 1, 3), dtype=np.float64)
    xs = (np.arange(S * f) / f).astype(np.int64) % S
    xt = np.arange(S * f) / f
    fx = xt - np.floor(xt)
    ys = (np.arange((Pp1 - 1) * f + 1) / f).astype(np.int64).clip(0, Pp1 - 1)
    yt = np.arange((Pp1 - 1) * f + 1) / f
    fy = yt - np.floor(yt)
    v00 = verts[np.ix_(xs, ys)]
    v10 = verts[np.ix_((xs + 1) % S, ys)]
    v01 = verts[np.ix_(xs, np.minimum(ys + 1, Pp1 - 1))]
    v11 = verts[np.ix_((xs + 1) % S, np.minimum(ys + 1, Pp1 - 1))]
    out = (v00 * (1 - fx)[:, None, None] * (1 - fy)[None, :, None] +
           v10 * fx[:, None, None] * (1 - fy)[None, :, None] +
           v01 * (1 - fx)[:, None, None] * fy[None, :, None] +
           v11 * fx[:, None, None] * fy[None, :, None])
    return out

def grid_faces(S2, P2):
    """Faces for a subdivided grid (no pole collapse - used after subdiv when top/bottom caps are trimmed)."""
    faces = []
    for i in range(S2):
        i2 = (i + 1) % S2
        for j in range(P2):
            a = i * (P2 + 1) + j
            b = i2 * (P2 + 1) + j
            c = i2 * (P2 + 1) + j + 1
            d = i * (P2 + 1) + j + 1
            faces.append((a, b, c, d))
    return faces

# ---------------------------------------------------------------- sculpt fields
def gauss_fields(p, fields):
    """p: (N,3) positions. fields: list of dicts {c, s(3,), amp, axis(3,)|None(radial)}.
    Returns displacement (N,3)."""
    d = np.zeros_like(p)
    for f in fields:
        c = np.asarray(f["c"], dtype=np.float64)
        s = np.asarray(f["s"], dtype=np.float64)
        w = np.exp(-(((p[:, 0] - c[0]) / s[0]) ** 2 +
                     ((p[:, 1] - c[1]) / s[1]) ** 2 +
                     ((p[:, 2] - c[2]) / s[2]) ** 2))
        a = f["amp"]
        ax = f.get("axis")
        if ax is None:
            d += (a * w)[:, None] * p / (np.linalg.norm(p, axis=1, keepdims=True) + 1e-9)
        else:
            d += (a * w)[:, None] * np.asarray(ax, dtype=np.float64)[None, :]
    return d

def creases(p, strokes, radial=True, center=np.zeros(3)):
    """Carve trenches along 3D polylines.
    strokes: list of {pts: [(x,y,z),...], depth, width, sharp(optional 2..6)}
    Returns (N,3) displacement. Vectorized: distance from every vertex to every segment."""
    d = np.zeros(len(p))
    for st in strokes:
        pts = np.asarray(st["pts"], dtype=np.float64)
        depth, width = st["depth"], st["width"]
        sharp = st.get("sharp", 2.5)
        mind = np.full(len(p), 1e9)
        for k in range(len(pts) - 1):
            a, b = pts[k], pts[k + 1]
            ab = b - a
            L2 = float(ab @ ab) + 1e-12
            t = np.clip(((p - a) @ ab) / L2, 0.0, 1.0)
            proj = a[None, :] + t[:, None] * ab[None, :]
            dist = np.linalg.norm(p - proj, axis=1)
            mind = np.minimum(mind, dist)
        w = np.exp(-(mind / width) ** sharp)
        d -= depth * w
    if radial:
        r = p - center[None, :]
        rn = r / (np.linalg.norm(r, axis=1, keepdims=True) + 1e-9)
        return d[:, None] * rn
    return d[:, None] * np.array([0.0, 0.0, 1.0])[None, :]

def micro_detail(p, scale_mm=1.0, amp_mm=0.35, seed=7, mask=None):
    """3-octave value-noise micro displacement (radial)."""
    q = p / (scale_mm * 0.001)
    n = fbm3(q[:, 0], q[:, 1], q[:, 2], octaves=3, seed=seed) - 0.5
    if mask is not None:
        n = n * mask
    rn = p / (np.linalg.norm(p, axis=1, keepdims=True) + 1e-9)
    return (amp_mm * 0.001) * n[:, None] * rn

# ---------------------------------------------------------------- mesh build
def mesh_obj(name, verts, faces, uvs=None, mat=None, coll=None, smooth=True):
    import bpy, bmesh
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    me.validate(verbose=False)
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    if smooth:
        for poly in me.polygons:
            poly.use_smooth = True
    if uvs is not None:
        uvl = me.uv_layers.new(name="UVMap")
        uvs = np.asarray(uvs, dtype=np.float64)
        if uvs.ndim == 3:
            uvs = uvs.reshape(-1, 2)
        if len(uvs) == len(verts):
            # per-vertex uvs -> map to loops via loop vertex indices (vectorized)
            lvi = np.empty(len(me.loops), dtype=np.int32)
            me.loops.foreach_get("vertex_index", lvi)
            uvloop = np.empty((len(me.loops), 2))
            uvloop[:, 0] = uvs[lvi, 0]
            uvloop[:, 1] = uvs[lvi, 1]
            uvl.data.foreach_set("uv", uvloop.ravel())
        else:
            uvl.data.foreach_set("uv", uvs[:len(me.loops)].ravel())
        me.update()
    ob = bpy.data.objects.new(name, me)
    if mat is not None:
        me.materials.append(mat)
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob

def sphere_uv(T, PH):
    """T, PH are already-meshgridded (S, P+1) angle arrays -> uv per grid vertex."""
    U = (T / TAU) % 1.0
    V = PH / math.pi
    return np.stack([U, V], axis=-1)

# ---------------------------------------------------------------- head engine
# All head params in meters. Local space: +Z up, -Y forward (face), +X left.
def head_base_dirs(S=96, P=72):
    return sphere_grid(S, P)

def sculpt_head_dirs(dirs, prm):
    """dirs: (S,P+1,3) unit dirs. prm: dict of parameters. Returns vertex positions (S,P+1,3)."""
    E = np.asarray(prm.get("extents", (0.079, 0.103, 0.114)))
    p = dirs * E[None, None, :]
    # primary anisotropic fields (position space, meters)
    F = []
    yb = prm.get("brow", 1.0)
    age = prm.get("age", 38.0)
    lean = prm.get("lean", 0.55)
    fem = prm.get("fem", 0.0)  # 0 male, 1 female

    brow_z = 0.030
    F += [
        # cranium / occiput
        dict(c=(0, 0.092, 0.040), s=(0.060, 0.055, 0.050), amp=0.006),
        dict(c=(0, 0.01, 0.080), s=(0.052, 0.052, 0.042), amp=0.002),
        dict(c=(0, 0.0, 0.112), s=(0.050, 0.050, 0.020), amp=-0.0022),
        # forehead fullness
        dict(c=(0, -0.094, 0.052), s=(0.042, 0.034, 0.030), amp=0.0035),
        # brow ridge (male)
        dict(c=(-0.024, -0.095, brow_z), s=(0.020, 0.024, 0.009), amp=0.0044 * yb),
        dict(c=(0.024, -0.095, brow_z), s=(0.020, 0.024, 0.009), amp=0.0044 * yb),
        # glabella
        dict(c=(0, -0.098, 0.024), s=(0.012, 0.020, 0.010), amp=0.0014 * yb),
        # temples slight hollow
        dict(c=(-0.066, -0.015, 0.042), s=(0.020, 0.034, 0.020), amp=-0.0013),
        dict(c=(0.066, -0.015, 0.042), s=(0.020, 0.034, 0.020), amp=-0.0013),
        # cheekbones
        dict(c=(-0.048, -0.070, 0.002), s=(0.020, 0.030, 0.014), amp=0.0030 * (1 - 0.4 * fem)),
        dict(c=(0.048, -0.070, 0.002), s=(0.020, 0.030, 0.014), amp=0.0030 * (1 - 0.4 * fem)),
        # cheek hollow (lean/age)
        dict(c=(-0.042, -0.056, -0.014), s=(0.016, 0.024, 0.014), amp=-0.0017 * (lean + age / 200.0)),
        dict(c=(0.042, -0.056, -0.014), s=(0.016, 0.024, 0.014), amp=-0.0017 * (lean + age / 200.0)),
        # jaw mass + gonial
        dict(c=(-0.058, 0.005, -0.046), s=(0.022, 0.040, 0.020), amp=0.0028 * (1 - 0.55 * fem)),
        dict(c=(0.058, 0.005, -0.046), s=(0.022, 0.040, 0.020), amp=0.0028 * (1 - 0.55 * fem)),
        # chin
        dict(c=(0, -0.096, -0.050), s=(0.021, 0.024, 0.014), amp=0.0030 * (1 - 0.35 * fem), axis=(0, -1, 0.25)),
        # mouth block slight
        dict(c=(0, -0.096, -0.020), s=(0.030, 0.018, 0.016), amp=0.0012),
        # under-chin tighten
        dict(c=(0, 0.02, -0.078), s=(0.030, 0.030, 0.018), amp=-0.0025),
    ]
    # eye sockets (two offset spheres each -> elongated)
    ex, ez = prm.get("eye_spacing", 0.028), 0.014
    for sx in (-1, 1):
        F += [
            dict(c=(sx * ex, -0.088, ez), s=(0.0165, 0.020, 0.013), amp=-0.0046),
            dict(c=(sx * (ex + 0.009), -0.084, ez), s=(0.012, 0.020, 0.012), amp=-0.0020),
            # upper lid ridge
            dict(c=(sx * ex, -0.093, ez + 0.011), s=(0.017, 0.017, 0.0060), amp=0.0020),
            # lower lid bag (age)
            dict(c=(sx * ex, -0.088, ez - 0.009), s=(0.015, 0.015, 0.005), amp=0.0008 * (1 + age / 60.0)),
        ]
    # nose: bridge ridge via axis push on center strip, profile by z
    z0, z1 = 0.030, -0.012  # bridge start -> tip
    zs = np.linspace(z0, z1, 7)
    amps = [0.0016, 0.0028, 0.0038, 0.0050, 0.0066, 0.0088, 0.0102]
    for z, a in zip(zs, amps):
        w = 0.0105 + 0.0030 * (z0 - z) / (z0 - z1)
        F.append(dict(c=(0, -0.096, z), s=(w, 0.020, 0.008), amp=a, axis=(0, -1, -0.08)))
    # nose tip ball + wings + nostril dents
    F += [
        dict(c=(0, -0.099, -0.014), s=(0.0075, 0.012, 0.006), amp=0.0070, axis=(0, -1, -0.15)),
        dict(c=(-0.0115, -0.094, -0.012), s=(0.0062, 0.013, 0.0060), amp=0.0026, axis=(0, -1, 0)),
        dict(c=(0.0115, -0.094, -0.012), s=(0.0062, 0.013, 0.0060), amp=0.0026, axis=(0, -1, 0)),
        dict(c=(-0.008, -0.092, -0.021), s=(0.0035, 0.010, 0.004), amp=-0.0012),
        dict(c=(0.008, -0.092, -0.021), s=(0.0035, 0.010, 0.004), amp=-0.0012),
    ]
    # philtrum + lips
    lipz = prm.get("lip_drop", -0.036)
    F += [
        dict(c=(0, -0.097, lipz + 0.010), s=(0.0016, 0.014, 0.0055), amp=-0.0009),
        dict(c=(0, -0.098, lipz + 0.004), s=(0.0145, 0.014, 0.0045), amp=0.0026 * (1 + 0.5 * fem)),
        dict(c=(0, -0.097, lipz - 0.004), s=(0.0135, 0.014, 0.0050), amp=0.0034 * (1 + 0.5 * fem)),
        dict(c=(-0.0135, -0.094, lipz), s=(0.005, 0.013, 0.006), amp=-0.0010),
        dict(c=(0.0135, -0.094, lipz), s=(0.005, 0.013, 0.006), amp=-0.0010),
        # mentolabial sulcus
        dict(c=(0, -0.094, lipz - 0.011), s=(0.012, 0.014, 0.0035), amp=-0.0010),
    ]
    p = p + gauss_fields(p.reshape(-1, 3), F).reshape(p.shape)
    # neck taper below (collapse to column ~0.058m radius)
    bot = p[:, :, 2] < -0.060
    if bot.any():
        t = np.clip((-0.060 - p[:, :, 2]) / 0.050, 0, 1)
        r_xy = np.linalg.norm(p[:, :, :2], axis=-1, keepdims=True)
        neck_r = 0.026
        shrink = (1 - t[..., None]) + t[..., None] * (neck_r / np.maximum(r_xy, 1e-6))
        p[:, :, :2] = p[:, :, :2] * shrink
        p[:, :, 2] = p[:, :, 2] - t * 0.012  # slight elongation into neck
    return p

def face_crease_strokes(prm):
    """Wrinkle polylines in head local space (meters). Tuned for age/lean."""
    age = prm.get("age", 38.0)
    k = prm.get("wrinkle", min(1.0, age / 45.0))
    ex, ez = prm.get("eye_spacing", 0.028), 0.014
    lipz = prm.get("lip_drop", -0.036)
    yy = -0.096
    S = []
    if k > 0.05:
        # nasolabial folds
        for sx in (-1, 1):
            S.append(dict(
                pts=[(sx * 0.011, yy + 0.002, -0.008), (sx * 0.017, yy - 0.002, -0.018),
                     (sx * 0.021, yy - 0.004, -0.028), (sx * 0.019, yy - 0.006, -0.036)],
                depth=0.0016 * k, width=0.0034, sharp=2.6))
        # forehead lines (3 arcs)
        for i, z in enumerate((0.044, 0.052, 0.060)):
            n = 7
            pts = [(x * 0.032 * (1 - 0.12 * i), yy - 0.002 - 0.0012 * i, z - 0.004 * (x * x) * 14)
                   for x in np.linspace(-1, 1, n)]
            S.append(dict(pts=pts, depth=0.0007 * k * (1 - 0.2 * i), width=0.0028, sharp=2.2))
        # glabella vertical pair
        for sx in (-1, 1):
            S.append(dict(
                pts=[(sx * 0.006, yy, 0.034), (sx * 0.007, yy, 0.026), (sx * 0.006, yy, 0.019)],
                depth=0.0010 * k, width=0.0024, sharp=2.8))
        # crow's feet (3 each side)
        for sx in (-1, 1):
            for j, ang in enumerate((-0.18, 0.0, 0.18)):
                dx0 = sx * (ex + 0.014)
                S.append(dict(
                    pts=[(dx0, yy + 0.002, ez + ang * 0.010),
                         (dx0 + sx * 0.006, yy + 0.001, ez + ang * 0.013),
                         (dx0 + sx * 0.011, yy - 0.001, ez + ang * 0.015)],
                    depth=0.0007 * k, width=0.0019, sharp=2.4))
        # infraorbital trough
        for sx in (-1, 1):
            S.append(dict(
                pts=[(sx * (ex - 0.010), yy - 0.001, ez - 0.010), (sx * ex, yy - 0.002, ez - 0.012),
                     (sx * (ex + 0.011), yy - 0.003, ez - 0.010)],
                depth=0.0006 * k, width=0.0026, sharp=2.2))
        # marionette lines
        for sx in (-1, 1):
            S.append(dict(
                pts=[(sx * 0.015, yy - 0.003, lipz - 0.007), (sx * 0.017, yy - 0.004, lipz - 0.014),
                     (sx * 0.016, yy - 0.005, lipz - 0.021)],
                depth=0.0009 * k, width=0.0025, sharp=2.4))
        # lip seam
        S.append(dict(
            pts=[(x * 0.013, yy - 0.005 - 0.0008 * (1 - x * x), lipz)
                 for x in np.linspace(-1, 1, 7)],
            depth=0.0009, width=0.0016, sharp=3.0))
        # chin crease
        S.append(dict(
            pts=[(x * 0.010, yy - 0.002, lipz - 0.012) for x in np.linspace(-1, 1, 5)],
            depth=0.0006 * k, width=0.0024, sharp=2.2))
    return S

def build_head(name, prm, mat=None, coll=None, S=96, P=72, dense_factor=3,
               micro=True, uv=True):
    """Returns (obj, meta). Dense sculpted head mesh with wrinkles + micro noise."""
    dirs, T, PH = head_base_dirs(S, P)
    base = sculpt_head_dirs(dirs, prm)
    # trim below neck cut (keep z > -0.085 to allow joining body) - keep all, body hides
    for _ in range(dense_factor - 1):
        base = subdiv_grid(base, 2)
    S2, Pp2 = base.shape[0], base.shape[1]
    p = base.reshape(-1, 3)
    # secondary: creases on dense mesh
    cre = creases(p, face_crease_strokes(prm))
    p = p + cre
    # tertiary micro noise (skip near lips/eyes to keep features clean)
    fwd = -p[:, 1]
    mouth_zone = (np.abs(p[:, 2] - (-0.022)) < 0.010) & (fwd > 0.75) & (np.abs(p[:, 0]) < 0.022)
    eye_zone = np.zeros(len(p), bool)
    for sx in (-1, 1):
        eye_zone |= (np.linalg.norm(p[:, :3] - np.array([sx * 0.028, -0.072, 0.014]), axis=1) < 0.014)
    mask = np.where(mouth_zone | eye_zone, 0.25, 1.0)
    if micro:
        p = p + micro_detail(p, scale_mm=1.4, amp_mm=prm.get("micro", 0.38),
                             seed=int(prm.get("seed", 7)), mask=mask)
    p = p.reshape(S2, Pp2, 3)
    faces = grid_faces(S2, Pp2 - 1)
    uvs = sphere_uv(T, PH) if uv else None
    if uv:
        # uvs must be subdivided like verts
        U = np.repeat(sphere_uv(T, PH), 1, axis=0)
        for _ in range(dense_factor - 1):
            U = subdiv_grid(U, 2)
        uvs = U
    obj = mesh_obj(name, p.reshape(-1, 3), faces, uvs=uvs, mat=mat, coll=coll)
    return obj, dict(verts=len(p.reshape(-1, 3)), faces=len(faces),
                     tris=sum(len(f) - 2 for f in faces))

# ---------------------------------------------------------------- ear engine
def build_ear(name, prm, mat=None, coll=None, side=-1):
    """Parametric ear: flattened sphere + helix rim + concha bowl + lobe."""
    S, P = 40, 30
    dirs, T, PH = sphere_grid(S, P)
    E = np.array([0.0045, 0.011, 0.0165])
    p = dirs * E[None, None, :]
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    rim = np.sqrt((np.abs(x) / 0.0045) ** 2 + (y / 0.011) ** 2 + (z / 0.0165) ** 2)
    helix = np.exp(-((rim - 0.78) / 0.16) ** 2)
    concha = np.exp(-(rim / 0.52) ** 2)
    lobe = np.exp(-(((x) / 0.004) ** 2 + ((y + 0.003) / 0.006) ** 2 + ((z + 0.011) / 0.006) ** 2))
    tragus = np.exp(-(((x) / 0.003) ** 2 + ((y - 0.006) / 0.004) ** 2 + ((z - 0.002) / 0.005) ** 2))
    disp = (0.0016 * helix - 0.0034 * concha + 0.0012 * lobe + 0.0008 * tragus)
    n = p / (np.linalg.norm(p, axis=-1, keepdims=True) + 1e-9)
    p = p + disp[..., None] * n
    p[..., 0] *= side
    faces = quad_faces(S, P)
    obj = mesh_obj(name, p.reshape(-1, 3), faces, mat=mat, coll=coll)
    return obj

# ---------------------------------------------------------------- eye engine
def build_eye(name, coll=None, mat=None):
    import bpy
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=20, radius=0.0122)
    ob = bpy.context.active_object
    ob.name = name
    if mat:
        ob.data.materials.append(mat)
    for poly in ob.data.polygons:
        poly.use_smooth = True
    if coll:
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        coll.objects.link(ob)
    return ob
