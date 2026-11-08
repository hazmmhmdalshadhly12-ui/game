#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE LAST SIN - parametric body builder v2.
Builds the mannequin DIRECTLY from the existing 65-bone rig positions so the
body is guaranteed compatible with TLS-SKL-001 (bind -> deform tests clean).
Muscle forms via gaussian fields; hands/fingers built from finger bone chains.
"""
import math
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sculpt_lib import gauss_fields, fbm3, mesh_obj, quad_faces, sphere_grid

TAU = math.pi * 2.0

def _bone_map(arm):
    """name -> (head Vector, tail Vector) in armature space."""
    out = {}
    for b in arm.data.bones:
        out[b.name] = (arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local)
    return out

def _ring(c, d, r_fn, n=14):
    """Ring of verts centered c, axis d (unit), radii from r_fn(t in [0,1] angle)."""
    d = np.asarray(d, float); d /= (np.linalg.norm(d) + 1e-9)
    ref = np.array([1.0, 0, 0]) if abs(d[0]) < 0.9 else np.array([0, 0, 1.0])
    u = np.cross(d, ref); u /= np.linalg.norm(u) + 1e-9
    v = np.cross(d, u)
    a = np.linspace(0, TAU, n, endpoint=False)
    r = np.asarray(r_fn(a), dtype=np.float64)
    if r.ndim == 0:
        r = np.full(n, float(r))
    pts = np.asarray(c)[None, :] + r[:, None] * (np.cos(a)[:, None] * u[None, :] + np.sin(a)[:, None] * v[None, :])
    return pts

def tube(p0, p1, r0, r1, n=18, bulge=None, squash=None, seed=1, super_ell=1.0):
    """Lofted tube between two points. bulge: dict {t, amp} radius bumps along t.
    squash: (a_axis, k) superellipse exponent for cross-section.
    Returns (verts, faces) grid: (nseg+1, n)."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0; L = np.linalg.norm(d) + 1e-9; d /= L
    segs = 10
    verts, tvals = [], np.linspace(0, 1, segs + 1)
    for i, t in enumerate(tvals):
        c = p0 + d * L * t
        r = r0 + (r1 - r0) * t
        if bulge:
            for bt, ba, bs in bulge:
                r += ba * math.exp(-((t - bt) / bs) ** 2)
        verts.append(_ring(c, d, lambda a, r=r: r, n))
    verts = np.stack(verts)          # (segs+1, n, 3)
    if squash:
        ax, fac = squash  # multiplicative scale along world axis (0=x,1=y,2=z)
        cc = verts.mean(axis=1, keepdims=True)
        rel = verts - cc
        rel[..., ax] *= fac
        verts = cc + rel
    faces = []
    for i in range(segs):
        for j in range(n):
            j2 = (j + 1) % n
            a = i * n + j; b = i * n + j2; c2 = (i + 1) * n + j2; dd = (i + 1) * n + j
            faces.append((a, b, c2, dd))
    uu, vv = np.meshgrid(np.linspace(0, 1, n, endpoint=False), np.linspace(0, 1, segs + 1))
    uvs = np.stack([uu, vv], axis=-1).reshape(-1, 2)
    return verts.reshape(-1, 3), faces, uvs

def _caps(objs, name, p0, p1, r0, r1, mat=None, coll=None, **kw):
    v, f, uv = tube(p0, p1, r0, r1, **kw)
    ob = mesh_obj(name, v, f, uvs=uv, mat=mat, coll=coll)
    return ob

def build_body_from_rig(arm, coll, mat_skin, prm=None):
    """Build full mannequin conforming to armature. Returns dict part->obj + info."""
    prm = prm or {}
    H = prm.get("height", 1.78)
    B = _bone_map(arm)
    def gp(name):  # get positions if bone exists
        return B.get(name)
    parts = {}

    # ---------------- limbs (from bones, fallback to proportional defaults)
    def chain_caps(names, radii, suffix, bulges=None):
        """Build tubes between consecutive bone heads/tails."""
        made = []
        for nm, (r0, r1) in zip(names, radii):
            bt = gp(nm)
            if not bt:
                continue
            h, t = bt
            v, f = tube((h.x, h.y, h.z), (t.x, t.y, t.z), r0, r1, n=14,
                        bulge=bulges, seed=hash(nm) % 97)
            ob = mesh_obj(f"TLS_Body_{nm}", v, f, mat=mat_skin, coll=coll)
            made.append(ob)
        return made

    # arms (A-pose 15 deg down): upper arm, forearm
    for side, S in ((-1, "L"), (1, "R")):
        ua = gp(f"upper_arm.{S}")
        fa = gp(f"forearm.{S}")
        if ua and fa:
            h, t = ua
            v, f, uv = tube((h.x, h.y, h.z), (t.x, t.y, t.z), 0.048, 0.040, n=20,
                        bulge=[(0.18, 0.006, 0.14), (0.75, 0.003, 0.16)])
            parts[f"upperarm_{S}"] = mesh_obj(f"TLS_Body_UpperArm_{S}", v, f, uvs=uv, mat=mat_skin, coll=coll)
            h2, t2 = fa
            v, f, uv = tube((h2.x, h2.y, h2.z), (t2.x, t2.y, t2.z), 0.040, 0.027, n=14,
                        bulge=[(0.22, 0.005, 0.16)])
            parts[f"forearm_{S}"] = mesh_obj(f"TLS_Body_Forearm_{S}", v, f, uvs=uv, mat=mat_skin, coll=coll)
    # legs
    for side, S in ((-1, "L"), (1, "R")):
        th = gp(f"thigh.{S}")
        sh = gp(f"shin.{S}")
        if th:
            h, t = th
            v, f, uv = tube((h.x, h.y, h.z), (t.x, t.y, t.z), 0.082, 0.055, n=20,
                        bulge=[(0.28, 0.008, 0.16)])
            parts[f"thigh_{S}"] = mesh_obj(f"TLS_Body_Thigh_{S}", v, f, uvs=uv, mat=mat_skin, coll=coll)
        if sh:
            h, t = sh
            v, f, uv = tube((h.x, h.y, h.z), (t.x, t.y, t.z), 0.055, 0.036, n=14,
                        bulge=[(0.30, 0.007, 0.14)])
            parts[f"shin_{S}"] = mesh_obj(f"TLS_Body_Shin_{S}", v, f, uvs=uv, mat=mat_skin, coll=coll)

    # ---------------- hands from finger chains
    for side, S in ((-1, "L"), (1, "R")):
        hand = gp(f"hand.{S}")
        if not hand:
            continue
        h, t = hand
        meshes = []
        # palm: flattened box loft between hand bone start and fingers root zone
        palm_len = 0.075
        d = np.array([t.x - h.x, t.y - h.y, t.z - h.z]); L = np.linalg.norm(d) + 1e-9
        d /= L
        wrist = np.array([h.x, h.y, h.z])
        knuck = wrist + d * palm_len
        # palm built from rings squashed
        v, f, uv = tube(wrist - d * 0.01, knuck, 0.042, 0.038, n=12, squash=(1, 0.55))
        meshes.append(mesh_obj(f"TLS_Body_Palm_{S}", v, f, uvs=uv, mat=mat_skin, coll=coll))
        # fingers: find bones like thumb_1.L etc.
        fbnames = [nm for nm in B if (f".{S}" in nm) and any(k in nm.lower() for k in ("thumb", "index", "middle", "ring", "pinky"))]
        chains = {}
        for nm in fbnames:
            base = nm.split(".")[0].rsplit("_", 1)[0]
            chains.setdefault(base, []).append(nm)
        for base, bones in chains.items():
            bones.sort()
            prev_tip = knuck + d * 0.012
            r = 0.0095 if "thumb" not in base.lower() else 0.0110
            for k, nm in enumerate(bones):
                bh, bt = B[nm]
                p0, p1 = np.array([bh.x, bh.y, bh.z]), np.array([bt.x, bt.y, bt.z])
                r1 = r * 0.82
                v, f, uv = tube(p0, p1, r, r1, n=8, bulge=[(0.06, r * 0.18, 0.30), (0.94, r * 0.15, 0.30)])
                meshes.append(mesh_obj(f"TLS_Body_{nm}", v, f, uvs=uv, mat=mat_skin, coll=coll))
                r = r1
        parts[f"hand_{S}"] = meshes

    # ---------------- torso (lofted superellipse rings, shaped by fields)
    hips = gp("pelvis")
    spine = [gp(nm) for nm in ("spine01", "spine02", "spine03") if gp(nm)]
    neck = gp("neck") or gp("neck_01")
    if hips and neck:
        pel = np.array([hips[0].x, hips[0].y, hips[0].z])
        nbase = np.array([neck[0].x, neck[0].y, neck[0].z])
        z0, z1 = pel[2], nbase[2]
        rings, zs = [], np.linspace(z0 - 0.02, z1 + 0.02, 26)
        for z in zs:
            t = (z - z0) / (z1 - z0)
            # width profile: hips -> waist -> chest -> shoulders
            w = (0.148 + 0.030 * math.exp(-((t - 0.02) / 0.16) ** 2)
                 - 0.026 * math.exp(-((t - 0.42) / 0.13) ** 2)
                 + 0.034 * math.exp(-((t - 0.80) / 0.15) ** 2))
            dep = (0.118 + 0.022 * math.exp(-((t - 0.05) / 0.18) ** 2)
                   - 0.024 * math.exp(-((t - 0.40) / 0.12) ** 2)
                   + 0.013 * math.exp(-((t - 0.82) / 0.14) ** 2))
            rings.append((w, dep))
        verts, faces, vi = [], [], 0
        NR = 28
        for (w, dep), z in zip(rings, zs):
            for k in range(NR):
                a = TAU * k / NR
                x = w * np.sign(math.cos(a)) * abs(math.cos(a)) ** 0.85
                y = -dep * np.sign(math.sin(a)) * abs(math.sin(a)) ** 1.05
                verts.append((x, y, z))
        for i in range(len(rings) - 1):
            for j in range(NR):
                j2 = (j + 1) % NR
                faces.append((i * NR + j, i * NR + j2, (i + 1) * NR + j2, (i + 1) * NR + j))
        verts = np.asarray(verts)
        # muscle fields: pecs, abs, spine groove, clavicle hint, lats
        F = [
            dict(c=(-0.045, -0.075, z1 - 0.045), s=(0.040, 0.030, 0.028), amp=0.011, axis=(0, -1, 0)),
            dict(c=(0.045, -0.075, z1 - 0.045), s=(0.040, 0.030, 0.028), amp=0.011, axis=(0, -1, 0)),
            dict(c=(0, -0.058, z1 - 0.115), s=(0.030, 0.020, 0.045), amp=-0.006, axis=(0, -1, 0)),
            dict(c=(0, 0.055, z1 - 0.11), s=(0.022, 0.030, 0.06), amp=-0.008, axis=(0, 1, 0)),
            dict(c=(0, 0.045, z1 - 0.02), s=(0.045, 0.020, 0.012), amp=0.004, axis=(0, 1, 0)),
            # shoulder caps (deltoid)
            dict(c=(-0.155, 0, z1 - 0.055), s=(0.038, 0.038, 0.038), amp=0.014),
            dict(c=(0.155, 0, z1 - 0.055), s=(0.038, 0.038, 0.038), amp=0.014),
        ]
        verts = verts + gauss_fields(verts, F)
        u_t = np.tile(np.linspace(0, 1, NR), len(rings))
        v_t = np.repeat(np.linspace(0, 1, len(rings)), NR)
        parts["torso"] = mesh_obj("TLS_Body_Torso", verts, faces, uvs=np.stack([u_t, v_t], -1), mat=mat_skin, coll=coll)

        # neck
        v, f, uv = tube((nbase[0], nbase[1], nbase[2] - 0.005), (nbase[0], nbase[1], nbase[2] + 0.085),
                    0.052, 0.048, n=12)
        parts["neck"] = mesh_obj("TLS_Body_Neck", v, f, uvs=uv, mat=mat_skin, coll=coll)

    # ---------------- feet (from foot bones) -> skin feet (boots go over)
    for side, S in ((-1, "L"), (1, "R")):
        ft = gp(f"foot.{S}")
        if ft:
            h, t = ft
            v, f, uv = tube((h.x, h.y, h.z), (t.x, t.y, t.z), 0.040, 0.030, n=10, squash=(2, 0.55))
            parts[f"foot_{S}"] = mesh_obj(f"TLS_Body_Foot_{S}", v, f, uvs=uv, mat=mat_skin, coll=coll)

    info = {"parts": list(parts.keys())}
    return parts, info

def join_parts(parts, name, coll=None):
    """Join part objects (lists allowed) into one mesh object."""
    import bpy
    objs = []
    for v in parts.values():
        if isinstance(v, (list, tuple)):
            objs.extend(v)
        elif v is not None:
            objs.append(v)
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.active_object
    ob.name = name
    if coll:
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        coll.objects.link(ob)
    return ob
