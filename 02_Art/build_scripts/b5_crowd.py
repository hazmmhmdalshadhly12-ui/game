#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M4-B5 crowd system batch:
  TLS-CHR-020 Crowd Body Kit: 3 builds (slim 1.68 / medium 1.75 / heavy 1.80)
  TLS-CHR-021 Crowd Heads Male: 5 truly-varied parametric heads
  TLS-CHR-022 Crowd Heads Female: 5 heads incl. Welsh capot hood
  TLS-CHR-023 Crowd Heads Elder: 3 aged heads
  TLS-CHR-024 Crowd Heads Youth: 4 younger/smaller heads
  TLS-CHR-025 Crowd Garments (NEW): reusable 1847 garment library on medium body
Heads are parametric sculpts (skull+jaw+nose+brow+cheek kernels) - real
geometric variation, not recolors. Bodies/garments unrigged in B1 (rig = M2 gate).
Run: blender -b --python b5_crowd.py -- --root <repo>
"""
import bpy, os, sys, math, time, random

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import tls_lib as L
import tls_mats as M

OPTS = L.parse_args()
ROOT = OPTS.get("root", "/home/z/my-project/work/lastsin-repo")
SRC = os.path.join(ROOT, "02_Art", "blender", "source", "chr")
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
    print(f"[B5] {asset_id}: {stats['totals']['verts']}v {stats['totals']['tris']}t "
          f"dims={stats['bbox_m']['dims']} pieces={len(objs)}")

# ================================================================ head engine
def sculpt_head(name, P, mats, seg=28, rows=22):
    """Parametric head. P = dict of variation params. Returns list of objects
    (head, nose, ears, eyes, brows, hair, neck) joined into ONE head mesh."""
    sw = P.get("skull_w", 0.072)      # half width
    sl = P.get("skull_l", 0.088)      # half length (y)
    sh = P.get("skull_h", 0.094)      # half height
    jw = P.get("jaw_w", 0.92)         # jaw width factor (lower face)
    jl = P.get("jaw_l", 0.86)         # jaw depth factor
    chn = P.get("chin", 0.6)          # chin projection 0..1
    brow = P.get("brow", 0.6)
    nose_l = P.get("nose_l", 0.024)
    nose_w = P.get("nose_w", 0.010)
    cheek = P.get("cheek", 0.5)
    gaunt = P.get("gaunt", 0.0)       # elder hollowing
    wrinkle = P.get("wrinkle", 0.0)
    age = P.get("age", "adult")

    # --- skull lathe: per-row (rx, ry) profile
    prof = [(0.52, 0.62), (0.72, 0.78), (0.88, 0.92), (0.97, 0.99),
            (1.00, 1.00), (0.99, 1.00), (0.96, 0.99), (0.92, 0.98),
            (0.90, 0.96), (0.89, 0.94), (0.88, 0.92), (0.87, 0.90),
            (0.85 * jw + 0.05, 0.88 * jl), (0.80 * jw + 0.05, 0.84 * jl),
            (0.74 * jw + 0.04, 0.80 * jl), (0.66 * jw + 0.02, 0.76 * jl),
            (0.55 * jw, 0.70 * jl), (0.40, 0.62), (0.20, 0.50), (0.02, 0.30)]
    verts, uvs = [], []
    top = len(verts); verts.append((0, 0, sh)); uvs.append((0.5, 1.0))
    z_sh = -1.0  # rows go from top to bottom
    for ri, (fx, fy) in enumerate(prof):
        t = ri / len(prof)             # 0=top .. 1=bottom
        z = sh * (1 - 2 * t)
        for i in range(seg):
            a = TAU * i / seg
            x = math.cos(a) * sw * fx
            y = math.sin(a) * sl * fy
            # face direction -Y
            verts.append((x, y, z)); uvs.append((i / seg, 1 - t))
    bot = len(verts); verts.append((0, 0, -sh * 0.92)); uvs.append((0.5, 0.0))
    faces = []
    def vid(r, i): return 1 + r * seg + (i % seg)
    for i in range(seg):
        faces.append((top, vid(0, i), vid(0, i + 1)))
    for r in range(len(prof) - 1):
        for i in range(seg):
            faces.append((vid(r, i), vid(r, i + 1), vid(r + 1, i + 1), vid(r + 1, i)))
    for i in range(seg):
        faces.append((bot, vid(len(prof) - 1, i + 1), vid(len(prof) - 1, i)))

    # --- sculpt kernels in normalized space (unit sphere coords)
    import numpy as np
    V = np.array(verts, dtype=np.float32)
    N = V / np.array([sw, sl, sh], dtype=np.float32)

    def kern(nx, ny, nz, sx, sy, sz, amp):
        d2 = ((N[:, 0] - nx) / sx) ** 2 + ((N[:, 1] - ny) / sy) ** 2 + \
             ((N[:, 2] - nz) / sz) ** 2
        return amp * np.exp(-d2)

    disp = np.zeros_like(V)
    # brow ridge (front -Y)
    disp[:, 2] += kern(0, -0.88, 0.28, 0.75, 0.35, 0.22, 0.010 * brow)
    # eye sockets
    for s in (-1, 1):
        disp[:, 2] += kern(s * 0.38, -0.82, 0.10, 0.28, 0.22, 0.16, -0.006)
    # cheeks
    for s in (-1, 1):
        disp[:, 0] += kern(s * 0.72, -0.30, -0.08, 0.30, 0.35, 0.35, 0.006 * cheek)
    # gaunt hollows (elder)
    if gaunt > 0:
        for s in (-1, 1):
            disp[:, 0] += kern(s * 0.62, -0.35, -0.25, 0.26, 0.28, 0.30,
                               -0.007 * gaunt)
    # nasolabial creases (elder)
    if wrinkle > 0:
        for s in (-1, 1):
            disp[:, 0] += kern(s * 0.22, -0.78, -0.30, 0.12, 0.14, 0.22,
                               -0.004 * wrinkle)
        disp[:, 2] += kern(0, -0.62, 0.35, 0.5, 0.25, 0.12, -0.003 * wrinkle)
    # forehead
    disp[:, 2] += kern(0, -0.55, 0.62, 0.55, 0.40, 0.25, 0.006)
    # back of skull
    disp[:, 1] += kern(0, 0.75, 0.15, 0.55, 0.40, 0.45, 0.008)
    # temple dents
    for s in (-1, 1):
        disp[:, 0] += kern(s * 0.78, -0.18, 0.30, 0.22, 0.25, 0.28, -0.004)
    # mouth mound + lips
    disp[:, 1] += kern(0, -0.90, -0.34, 0.30, 0.18, 0.14, 0.004)
    disp[:, 1] += kern(0, -0.94, -0.42, 0.24, 0.08, 0.05, 0.003)
    # chin
    disp[:, 1] += kern(0, -0.55, -0.80, 0.28, 0.30, 0.18, 0.009 * chn)
    disp[:, 2] += kern(0, -0.60, -0.78, 0.30, 0.30, 0.20, -0.003 * chn)
    # jaw corner
    for s in (-1, 1):
        disp[:, 0] += kern(s * 0.80, -0.12, -0.42, 0.25, 0.28, 0.30, 0.004)

    V2 = V + disp
    verts = [tuple(v) for v in V2]

    head = L.new_mesh_obj(f"{name}_Skull", verts, faces, uvs=uvs,
                          mat=mats["skin"], coll="TLS")

    parts = [head]
    # nose (wedge)
    nz = []
    tip_y = -sl * 1.02
    nz.append(L.new_mesh_obj(
        f"{name}_Nose",
        [(0, -sl * 0.86, 0.06), (-nose_w, -sl * 0.98, 0.045), (nose_w, -sl * 0.98, 0.045),
         (-nose_w * 0.7, tip_y, 0.028), (nose_w * 0.7, tip_y, 0.028),
         (0, tip_y - 0.004, 0.020),
         (-nose_w * 0.5, -sl * 0.99, -0.012), (nose_w * 0.5, -sl * 0.99, -0.012),
         (0, -sl * 0.96, -0.014), (0, -sl * 0.87, 0.055)],
        [(0, 2, 1), (0, 1, 6), (0, 6, 9), (0, 9, 8), (0, 8, 7), (0, 7, 2),
         (3, 1, 2), (3, 4, 1), (4, 3, 5), (3, 2, 5), (5, 2, 7), (5, 7, 8),
         (5, 8, 6), (5, 6, 9), (9, 6, 1), (9, 1, 4), (4, 7, 8), (4, 8, 9)],
        uvs=[(0.5, 1)] + [(0.3, 0.5)] * 9, mat=mats["skin"], coll="TLS"))
    parts.extend(nz)
    # ears
    for s in (-1, 1):
        ear = L.new_mesh_obj(
            f"{name}_Ear{'L' if s < 0 else 'R'}",
            [(s * sw * 0.96, -0.012, 0.010), (s * sw * 1.12, -0.006, 0.012),
             (s * sw * 1.12, 0.006, 0.010), (s * sw * 0.96, 0.012, 0.008),
             (s * sw * 1.10, 0.0, -0.004), (s * sw * 0.99, 0.0, -0.008)],
            [(0, 1, 2), (0, 2, 3), (1, 4, 2), (2, 4, 3), (0, 3, 5), (0, 5, 4),
             (0, 4, 1), (3, 2, 4), (3, 4, 5)],
            uvs=[(0, 0.5)] * 6, mat=mats["skin"], coll="TLS")
        parts.append(ear)
    # eyes (dark inserts at sockets)
    for s in (-1, 1):
        parts.append(L.new_mesh_obj(
            f"{name}_Eye{'L' if s < 0 else 'R'}",
            [(0, 0, 0.010), (0.006, 0, 0.003), (0, 0.006, 0.003), (-0.006, 0, 0.003),
             (0, -0.006, 0.003), (0.004, 0, -0.003), (0, 0.004, -0.003),
             (-0.004, 0, -0.003), (0, -0.004, -0.003), (0, 0, -0.008)],
            [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1), (1, 5, 6), (1, 6, 2),
             (2, 6, 7), (2, 7, 3), (3, 7, 8), (3, 8, 4), (4, 8, 5), (4, 5, 1),
             (9, 6, 5), (9, 7, 6), (9, 8, 7), (9, 5, 8)],
            uvs=[(0.5, 0.5)] * 10, mat=mats["eye"], coll="TLS"))
        parts[-1].location = (s * sw * 0.40, -sl * 0.82, 0.008)
        L.apply_transforms([parts[-1]], location=True)
    # brows (hair strips)
    for s in (-1, 1):
        br = L.box(f"{name}_Brow{'L' if s < 0 else 'R'}", 0.032, 0.007, 0.005,
                   cx=s * sw * 0.42, cy=-sl * 0.86, cz=0.020,
                   rot_z=s * 0.25, mat=mats["hair"])
        parts.append(br)
    # neck
    parts.append(L.cyl(f"{name}_Neck", 0.031, -sh * 0.86, -sh * 1.35, n=14,
                       r_top=0.035, mat=mats["skin"]))
    # hair
    hs = P.get("hair", "crop")
    hair_mat = mats["hair"]
    if hs == "bald":
        ring = L.torus(f"{name}_HairFringe", sw * 0.98, 0.012, cz=0.030,
                       n_path=24, n_sec=8, mat=hair_mat, arc=math.pi * 1.15)
        parts.append(ring)
    else:
        cov = {"crop": 0.62, "full": 0.72, "long": 0.80, "bun": 0.66, "hood": 1.0}.get(hs, 0.62)
        hz_top = sh * 0.98
        rows_h = 10
        rings = []
        for r in range(rows_h + 1):
            t = r / rows_h
            theta = math.pi * 0.5 * min(1.0, cov * t / max(t, 1e-6) if t else 0)
            # coverage: from top down to fraction of head
            phi = math.pi * 0.5 * (1 - cov) + math.pi * cov * t
            zz = math.cos(phi)
            rad = math.sin(phi)
            sc = 1.06 if hs != "hood" else 1.14
            pts = []
            for i in range(seg):
                a = TAU * i / seg
                pts.append((math.cos(a) * sw * rad * sc,
                            math.sin(a) * sl * rad * sc,
                            zz * sh * sc))
            rings.append({"verts": pts})
        v2, f2, u2 = L.loft_rings(rings, closed_loop=True)
        cap = L.new_mesh_obj(f"{name}_HairCap", v2, f2, uvs=u2, mat=hair_mat,
                             coll="TLS")
        # trim bottom: remove verts below cutoff -> instead scale cap position
        cap.location = (0, 0, sh * 0.05)
        L.apply_transforms([cap], location=True)
        parts.append(cap)
        if hs == "bun":
            bun = L.new_mesh_obj(f"{name}_HairBun",
                                 [(0, 0, 0.024), (0.016, 0, 0.008), (0, 0.016, 0.008),
                                  (-0.016, 0, 0.008), (0, -0.016, 0.008), (0, 0, -0.014)],
                                 [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1),
                                  (5, 2, 1), (5, 3, 2), (5, 4, 3), (5, 1, 4)],
                                 uvs=[(0.5, 1)] + [(0.5, 0.5)] * 4 + [(0.5, 0)],
                                 mat=hair_mat, coll="TLS")
            bun.location = (0, sl * 0.72, sh * 0.25)
            L.apply_transforms([bun], location=True)
            parts.append(bun)
        if hs == "long":
            back = L.new_mesh_obj(f"{name}_HairBack",
                                  [(-sw * 0.8, sl * 0.3, sh * 0.2),
                                   (sw * 0.8, sl * 0.3, sh * 0.2),
                                   (sw * 0.85, sl * 0.62, -sh * 0.55),
                                   (-sw * 0.85, sl * 0.62, -sh * 0.55),
                                   (-sw * 0.8, sl * 0.06, sh * 0.2),
                                   (sw * 0.8, sl * 0.06, sh * 0.2),
                                   (sw * 0.85, sl * 0.70, -sh * 0.55),
                                   (-sw * 0.85, sl * 0.70, -sh * 0.55)],
                                  [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                                   (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)],
                                  uvs=[(0, 0), (1, 0), (1, 1), (0, 1)] * 2,
                                  mat=hair_mat, coll="TLS")
            parts.append(back)
        if hs == "hood":
            # Welsh capot hood: shell + brim frame around face
            shell = [p for p in parts if p.name.endswith("HairCap")][0]
            shell.scale = (1.05, 1.02, 1.0)
            L.apply_transforms([shell])
            brim = L.torus(f"{name}_HoodBrim", (sw + sl) * 0.62, 0.018,
                           cz=0.004, n_path=26, n_sec=8, mat=mats["cloth"],
                           arc=math.pi * 1.5)
            brim.rotation_euler = (0, 0, math.radians(-135))
            L.apply_transforms([brim])
            parts.append(brim)
            cape = L.new_mesh_obj(f"{name}_HoodCape",
                                  [(-sw * 1.1, sl * 0.5, -sh * 0.7),
                                   (sw * 1.1, sl * 0.5, -sh * 0.7),
                                   (sw * 1.25, sl * 0.2, -sh * 1.9),
                                   (-sw * 1.25, sl * 0.2, -sh * 1.9),
                                   (-sw * 1.1, sl * 0.12, -sh * 0.7),
                                   (sw * 1.1, sl * 0.12, -sh * 0.7),
                                   (sw * 1.25, sl * 0.05, -sh * 1.9),
                                   (-sw * 1.25, sl * 0.05, -sh * 1.9)],
                                  [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                                   (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)],
                                  uvs=[(0, 0), (1, 0), (1, 1), (0, 1)] * 2,
                                  mat=mats["cloth"], coll="TLS")
            parts.append(cape)
    # facial hair for some males
    if P.get("beard"):
        parts.append(L.new_mesh_obj(
            f"{name}_Beard",
            [(-sw * 0.62, -sl * 0.60, -sh * 0.25), (sw * 0.62, -sl * 0.60, -sh * 0.25),
             (sw * 0.60, -sl * 0.92, -sh * 0.30), (-sw * 0.60, -sl * 0.92, -sh * 0.30),
             (-sw * 0.34, -sl * 1.02, -sh * 0.62), (sw * 0.34, -sl * 1.02, -sh * 0.62),
             (0, -sl * 0.70, -sh * 0.75),
             (-sw * 0.64, -sl * 0.42, -sh * 0.05), (sw * 0.64, -sl * 0.42, -sh * 0.05)],
            [(0, 3, 2, 1), (0, 1, 5, 4), (1, 2, 5), (2, 3, 4), (3, 0, 4),
             (0, 6, 4), (1, 5, 6), (0, 7, 6), (1, 6, 7)],
            uvs=[(0, 0), (1, 0), (1, 1), (0, 1), (0.2, 1), (0.8, 1), (0.5, 0.9),
                 (0, 0.5), (1, 0.5)],
            mat=mats["hair"], coll="TLS"))
    if P.get("moustache"):
        parts.append(L.box(f"{name}_Mous", 0.024, 0.006, 0.005, cy=-sl * 0.93,
                           cz=-sh * 0.30, mat=mats["hair"]))
    joined = L.join_objects(parts, name, coll="TLS")
    return joined

# ================================================================ body engine
def build_body(name, B, mats):
    """Parametric crowd body in A-pose 15deg. B = build params."""
    h = B["height"]
    s = h / 1.75
    w = B["width"]   # girth factor
    parts = []
    # torso lathe profile (rx, ry, z) - half extents
    torso_prof = [
        (0.145 * w, 0.095 * w, 0.86 * s),   # pelvis
        (0.135 * w, 0.090 * w, 0.98 * s),
        (0.130 * w, 0.088 * w, 1.08 * s),   # waist
        (0.145 * w, 0.096 * w, 1.20 * s),
        (0.165 * w, 0.102 * w, 1.32 * s),   # chest
        (0.175 * w, 0.100 * w, 1.40 * s),   # shoulders mass
        (0.120 * w, 0.075 * w, 1.46 * s),
        (0.048, 0.048, 1.50 * s),           # neck base
    ]
    rings = []
    for rx, ry, z in torso_prof:
        pts = []
        for i in range(20):
            a = TAU * i / 20
            pts.append((math.cos(a) * rx, math.sin(a) * ry, z))
        rings.append({"verts": pts})
    v, f, u = L.loft_rings(rings, closed_loop=True, cap_bottom=True, cap_top=True)
    parts.append(L.new_mesh_obj(f"{name}_Torso", v, f, uvs=u, mat=mats["body"]))
    # shoulders caps
    for sd in (-1, 1):
        parts.append(L.new_mesh_obj(
            f"{name}_Shoulder{sd}",
            [(sd * 0.175 * w, 0, 1.42 * s), (sd * 0.21 * w, 0, 1.40 * s),
             (sd * 0.21 * w, 0.02, 1.39 * s), (sd * 0.21 * w, 0, 1.37 * s),
             (sd * 0.21 * w, -0.02, 1.39 * s), (sd * 0.19 * w, 0.015, 1.41 * s),
             (sd * 0.19 * w, -0.015, 1.41 * s), (sd * 0.16 * w, 0, 1.44 * s)],
            [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1), (1, 5, 6), (1, 6, 2),
             (2, 6, 7), (2, 7, 3), (3, 7, 5), (3, 5, 4), (4, 5, 1)],
            uvs=[(0.5, 0.5)] * 8, mat=mats["body"]))
    # arms (A-pose 15 deg)
    ang = math.radians(15)
    for sd in (-1, 1):
        sh = (sd * 0.19 * w, 0, 1.40 * s)
        el = (sd * (0.19 * w + math.sin(ang) * 0.30 * s), 0.01,
              1.40 * s - math.cos(ang) * 0.30 * s)
        wr = (sd * (0.19 * w + math.sin(ang) * 0.57 * s), 0.02,
              1.40 * s - math.cos(ang) * 0.57 * s)
        hd = (sd * (0.19 * w + math.sin(ang) * 0.70 * s), 0.03,
              1.40 * s - math.cos(ang) * 0.70 * s)
        parts.append(L.tube_between(sh, el, 0.048 * w, 0.036 * w, n=10,
                                    name=f"{name}_UpArm{sd}", mat=mats["body"]))
        parts.append(L.tube_between(el, wr, 0.034 * w, 0.026 * w, n=8,
                                    name=f"{name}_LoArm{sd}", mat=mats["body"]))
        # mitten hand
        parts.append(L.new_mesh_obj(
            f"{name}_Hand{sd}",
            [(hd[0] - 0.018, hd[1] - 0.012, hd[2]), (hd[0] + 0.018, hd[1] - 0.012, hd[2]),
             (hd[0] + 0.018, hd[1] + 0.012, hd[2]), (hd[0] - 0.018, hd[1] + 0.012, hd[2]),
             (hd[0] - 0.016, hd[1] - 0.010, hd[2] + 0.075 * s),
             (hd[0] + 0.016, hd[1] - 0.010, hd[2] + 0.075 * s),
             (hd[0] + 0.016, hd[1] + 0.010, hd[2] + 0.075 * s),
             (hd[0] - 0.016, hd[1] + 0.010, hd[2] + 0.075 * s)],
            [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5),
             (2, 3, 7, 6), (3, 0, 4, 7)],
            uvs=[(0, 0), (1, 0), (1, 1), (0, 1)] * 2, mat=mats["body"]))
    # legs
    for sd in (-1, 1):
        hp = (sd * 0.09 * w, 0, 0.90 * s)
        kn = (sd * 0.095 * w, 0.012, 0.50 * s)
        ak = (sd * 0.09 * w, -0.005, 0.09 * s)
        parts.append(L.tube_between(hp, kn, 0.068 * w, 0.052 * w, n=10,
                                    name=f"{name}_Thigh{sd}", mat=mats["body"]))
        parts.append(L.tube_between(kn, ak, 0.050 * w, 0.034 * w, n=8,
                                    name=f"{name}_Calf{sd}", mat=mats["body"]))
        parts.append(L.box(f"{name}_Shoe{sd}", 0.085, 0.235, 0.062,
                           cx=sd * 0.09 * w, cy=-0.055, cz=0.031, mat=mats["shoe"]))
    joined = L.join_objects(parts, name, coll="TLS")
    return joined

# ================================================================ CHR-020 bodies
print("[B5] TLS-CHR-020 crowd body kit ...")
L.reset_scene(); L.setup_units("TLS_CHR_020")
M._cache.clear()
m_body = L.new_mat("TLS_Mat_Crowd_Skin", base=(0.72, 0.58, 0.47), rough=0.62)
m_bodym = L.new_mat("TLS_Mat_Crowd_SkinM", base=(0.68, 0.53, 0.42), rough=0.62)
m_shoe = M.pbr("TLS_Mat_Crowd_Boot", "leather", ao=0.8)
matsB = {"body": m_body, "shoe": m_shoe}
bodies = []
bodies.append(build_body("Crowd_Body_Slim", {"height": 1.68, "width": 0.88}, matsB))
med = build_body("Crowd_Body_Medium", {"height": 1.75, "width": 1.0}, matsB)
med.location = (1.0, 0, 0)
L.apply_transforms([med], location=True)
bodies.append(med)
hvy = build_body("Crowd_Body_Heavy", {"height": 1.80, "width": 1.24}, matsB)
hvy.location = (2.0, 0, 0)
L.apply_transforms([hvy], location=True)
bodies.append(hvy)
finish_asset("TLS-CHR-020", bodies, [], "tls_chr_020_body_kit.blend",
             dims_expected=[2.5, 0.6, 1.9],
             note="3 builds (slim 1.68/medium 1.75/heavy 1.80) A-pose 15; mitten hands; rig at M2")

# ================================================================ heads
def head_mats(seed):
    tones = [(0.74, 0.60, 0.48), (0.69, 0.55, 0.44), (0.78, 0.63, 0.50),
             (0.65, 0.51, 0.40), (0.72, 0.57, 0.45)]
    hairs = [(0.16, 0.13, 0.10), (0.28, 0.20, 0.12), (0.42, 0.34, 0.22),
             (0.10, 0.09, 0.08), (0.55, 0.50, 0.42)]
    return {"skin": L.new_mat(f"TLS_Mat_Head_Skin{seed}", base=tones[seed % 5], rough=0.6),
            "eye": L.new_mat(f"TLS_Mat_Head_Eye{seed}", base=(0.08, 0.07, 0.06), rough=0.2),
            "hair": L.new_mat(f"TLS_Mat_Head_Hair{seed}", base=hairs[seed % 5], rough=0.55),
            "cloth": M.pbr(f"TLS_Mat_Head_Cloth{seed}", "wool", ao=0.8,
                           base=(0.9, 0.85, 0.8))}

print("[B5] TLS-CHR-021 male heads ...")
L.reset_scene(); L.setup_units("TLS_CHR_021")
M._cache.clear()
male = [
    {"name": "Head_M1", "skull_w": 0.074, "skull_l": 0.090, "jaw_w": 0.95,
     "chin": 0.8, "brow": 0.85, "nose_l": 0.026, "nose_w": 0.011, "cheek": 0.6,
     "hair": "bald", "beard": True},
    {"name": "Head_M2", "skull_w": 0.070, "skull_l": 0.094, "jaw_w": 0.85,
     "chin": 0.5, "brow": 0.5, "nose_l": 0.022, "nose_w": 0.009, "cheek": 0.4,
     "hair": "crop", "moustache": True},
    {"name": "Head_M3", "skull_w": 0.078, "skull_l": 0.086, "jaw_w": 1.02,
     "chin": 0.95, "brow": 1.0, "nose_l": 0.028, "nose_w": 0.013, "cheek": 0.9,
     "hair": "full", "beard": True},
    {"name": "Head_M4", "skull_w": 0.068, "skull_l": 0.092, "jaw_w": 0.90,
     "chin": 0.65, "brow": 0.7, "nose_l": 0.024, "nose_w": 0.010, "cheek": 0.5,
     "hair": "crop"},
    {"name": "Head_M5", "skull_w": 0.076, "skull_l": 0.088, "jaw_w": 0.98,
     "chin": 0.75, "brow": 0.75, "nose_l": 0.025, "nose_w": 0.012, "cheek": 0.7,
     "hair": "bald", "moustache": True},
]
hm = []
for i, P in enumerate(male):
    h = sculpt_head(P["name"], P, head_mats(i))
    h.location = (i * 0.30, 0, 0)
    L.apply_transforms([h], location=True)
    hm.append(h)
finish_asset("TLS-CHR-021", hm, [], "tls_chr_021_heads_male.blend",
             dims_expected=[1.5, 0.25, 0.28],
             note="5 parametric male heads - real geometric variation (skull/jaw/nose/brow/cheek)")

print("[B5] TLS-CHR-022 female heads ...")
L.reset_scene(); L.setup_units("TLS_CHR_022")
M._cache.clear()
female = [
    {"name": "Head_F1", "skull_w": 0.068, "skull_l": 0.086, "jaw_w": 0.82,
     "chin": 0.45, "brow": 0.35, "nose_l": 0.020, "nose_w": 0.008, "cheek": 0.65,
     "hair": "bun"},
    {"name": "Head_F2", "skull_w": 0.070, "skull_l": 0.088, "jaw_w": 0.86,
     "chin": 0.55, "brow": 0.4, "nose_l": 0.021, "nose_w": 0.0085, "cheek": 0.6,
     "hair": "hood"},
    {"name": "Head_F3", "skull_w": 0.066, "skull_l": 0.084, "jaw_w": 0.80,
     "chin": 0.5, "brow": 0.35, "nose_l": 0.019, "nose_w": 0.008, "cheek": 0.7,
     "hair": "long"},
    {"name": "Head_F4", "skull_w": 0.072, "skull_l": 0.087, "jaw_w": 0.88,
     "chin": 0.6, "brow": 0.45, "nose_l": 0.022, "nose_w": 0.009, "cheek": 0.55,
     "hair": "hood"},
    {"name": "Head_F5", "skull_w": 0.067, "skull_l": 0.085, "jaw_w": 0.84,
     "chin": 0.5, "brow": 0.4, "nose_l": 0.020, "nose_w": 0.008, "cheek": 0.62,
     "hair": "bun"},
]
hf = []
for i, P in enumerate(female):
    h = sculpt_head(P["name"], P, head_mats(i + 10))
    h.location = (i * 0.30, 0, 0)
    L.apply_transforms([h], location=True)
    hf.append(h)
finish_asset("TLS-CHR-022", hf, [], "tls_chr_022_heads_female.blend",
             dims_expected=[1.5, 0.3, 0.30],
             note="5 female heads incl. 2 Welsh capot hoods; bun/long variations")

print("[B5] TLS-CHR-023 elder heads ...")
L.reset_scene(); L.setup_units("TLS_CHR_023")
M._cache.clear()
elder = [
    {"name": "Head_E1", "skull_w": 0.072, "skull_l": 0.088, "jaw_w": 0.88,
     "chin": 0.7, "brow": 0.9, "nose_l": 0.027, "nose_w": 0.011, "cheek": 0.3,
     "gaunt": 1.0, "wrinkle": 1.0, "hair": "bald"},
    {"name": "Head_E2", "skull_w": 0.068, "skull_l": 0.086, "jaw_w": 0.82,
     "chin": 0.5, "brow": 0.5, "nose_l": 0.024, "nose_w": 0.009, "cheek": 0.35,
     "gaunt": 0.8, "wrinkle": 0.9, "hair": "bun"},
    {"name": "Head_E3", "skull_w": 0.075, "skull_l": 0.090, "jaw_w": 0.92,
     "chin": 0.8, "brow": 0.85, "nose_l": 0.028, "nose_w": 0.012, "cheek": 0.4,
     "gaunt": 1.1, "wrinkle": 1.0, "hair": "bald", "beard": True},
]
he = []
for i, P in enumerate(elder):
    h = sculpt_head(P["name"], P, head_mats(i + 20))
    h.location = (i * 0.30, 0, 0)
    L.apply_transforms([h], location=True)
    he.append(h)
finish_asset("TLS-CHR-023", he, [], "tls_chr_023_heads_elder.blend",
             dims_expected=[0.9, 0.25, 0.28],
             note="3 aged heads - gaunt hollows + nasolabial creases in geometry")

print("[B5] TLS-CHR-024 youth heads ...")
L.reset_scene(); L.setup_units("TLS_CHR_024")
M._cache.clear()
youth = [
    {"name": "Head_Y1", "skull_w": 0.066, "skull_l": 0.080, "jaw_w": 0.85,
     "chin": 0.45, "brow": 0.3, "nose_l": 0.019, "nose_w": 0.008, "cheek": 0.8,
     "hair": "crop"},
    {"name": "Head_Y2", "skull_w": 0.062, "skull_l": 0.076, "jaw_w": 0.82,
     "chin": 0.4, "brow": 0.28, "nose_l": 0.017, "nose_w": 0.0075, "cheek": 0.85,
     "hair": "long"},
    {"name": "Head_Y3", "skull_w": 0.058, "skull_l": 0.070, "jaw_w": 0.80,
     "chin": 0.35, "brow": 0.25, "nose_l": 0.016, "nose_w": 0.007, "cheek": 0.9,
     "hair": "crop"},
    {"name": "Head_Y4", "skull_w": 0.064, "skull_l": 0.078, "jaw_w": 0.84,
     "chin": 0.42, "brow": 0.3, "nose_l": 0.018, "nose_w": 0.008, "cheek": 0.75,
     "hair": "bun"},
]
hy = []
for i, P in enumerate(youth):
    h = sculpt_head(P["name"], P, head_mats(i + 30))
    h.location = (i * 0.26, 0, 0)
    L.apply_transforms([h], location=True)
    hy.append(h)
finish_asset("TLS-CHR-024", hy, [], "tls_chr_024_heads_youth.blend",
             dims_expected=[1.05, 0.24, 0.26],
             note="4 youth heads incl. 2 child-scale (58-62mm skulls)")

# ================================================================ CHR-025 garments
print("[B5] TLS-CHR-025 garment library ...")
L.reset_scene(); L.setup_units("TLS_CHR_025")
M._cache.clear()
m_woolA = M.pbr("TLS_Mat_Gar_WoolA", "wool", ao=0.85, base=(1.05, 1.0, 0.95))
m_woolB = M.pbr("TLS_Mat_Gar_WoolB", "wool", ao=0.85, base=(0.45, 0.42, 0.38))
m_woolC = M.pbr("TLS_Mat_Gar_WoolC", "wool", ao=0.85, base=(0.30, 0.28, 0.26))
m_linen = M.pbr("TLS_Mat_Gar_Linen", "wool", ao=0.6, base=(1.3, 1.25, 1.15))
m_leath = M.pbr("TLS_Mat_Gar_Leather", "leather", ao=0.8)

gm = []
def garment_tube(name, prof, mat, flare=0.0):
    rings = []
    for (rx, ry, z) in prof:
        pts = []
        for i in range(20):
            a = TAU * i / 20
            pts.append((math.cos(a) * rx, math.sin(a) * ry, z))
        rings.append({"verts": pts})
    v, f, u = L.loft_rings(rings, closed_loop=True)
    return L.new_mesh_obj(name, v, f, uvs=u, mat=mat)

# 1. workman smock (loose, mid-thigh)
gm.append(garment_tube("Gar_Smock", [
    (0.17, 0.12, 1.44), (0.185, 0.13, 1.36), (0.19, 0.135, 1.24),
    (0.185, 0.13, 1.10), (0.175, 0.125, 0.95), (0.19, 0.15, 0.80),
    (0.21, 0.17, 0.68)], m_woolA))
# smock sleeves (loose)
for sd in (-1, 1):
    ang = math.radians(15)
    sh = (sd * 0.20, 0, 1.40)
    el = (sd * (0.20 + math.sin(ang) * 0.32), 0.01, 1.40 - math.cos(ang) * 0.32)
    wr = (sd * (0.20 + math.sin(ang) * 0.58), 0.02, 1.40 - math.cos(ang) * 0.58)
    gm.append(L.tube_between(sh, el, 0.062, 0.052, n=10,
                             name=f"Gar_SmockSlv{sd}", mat=m_woolA))
    gm.append(L.tube_between(el, wr, 0.052, 0.045, n=8,
                             name=f"Gar_SmockSlv2{sd}", mat=m_woolA))
# 2. waistcoat (torso shell, sleeveless)
gm.append(garment_tube("Gar_Waistcoat", [
    (0.165, 0.105, 1.43), (0.172, 0.108, 1.34), (0.178, 0.112, 1.22),
    (0.168, 0.105, 1.06), (0.10, 0.09, 0.96)], m_woolB))
# 3. jacket with skirt
gm.append(garment_tube("Gar_Jacket", [
    (0.185, 0.115, 1.45), (0.195, 0.125, 1.35), (0.20, 0.13, 1.22),
    (0.19, 0.13, 1.05), (0.20, 0.14, 0.92), (0.21, 0.15, 0.82)], m_woolC))
for sd in (-1, 1):
    ang = math.radians(15)
    sh = (sd * 0.215, 0, 1.41)
    el = (sd * (0.215 + math.sin(ang) * 0.31), 0.01, 1.41 - math.cos(ang) * 0.31)
    wr = (sd * (0.215 + math.sin(ang) * 0.57), 0.02, 1.41 - math.cos(ang) * 0.57)
    gm.append(L.tube_between(sh, el, 0.058, 0.046, n=10,
                             name=f"Gar_JacketSlv{sd}", mat=m_woolC))
    gm.append(L.tube_between(el, wr, 0.046, 0.038, n=8,
                             name=f"Gar_JacketSlv2{sd}", mat=m_woolC))
# 4. trousers
for sd in (-1, 1):
    hp = (sd * 0.10, 0, 0.92)
    kn = (sd * 0.105, 0.012, 0.50)
    ak = (sd * 0.10, -0.005, 0.10)
    gm.append(L.tube_between(hp, kn, 0.080, 0.066, n=10,
                             name=f"Gar_Trousers{sd}", mat=m_woolB))
    gm.append(L.tube_between(kn, ak, 0.064, 0.050, n=8,
                             name=f"Gar_Trousers2{sd}", mat=m_woolB))
gm.append(garment_tube("Gar_TrousersHip", [
    (0.15, 0.10, 0.94), (0.152, 0.10, 0.86), (0.148, 0.098, 0.78)], m_woolB))
# 5. skirt (women, ankle length)
gm.append(garment_tube("Gar_Skirt", [
    (0.15, 0.11, 0.96), (0.17, 0.13, 0.80), (0.20, 0.16, 0.60),
    (0.235, 0.19, 0.35), (0.26, 0.22, 0.10)], m_woolA))
# 6. petticoat under-layer hint
gm.append(garment_tube("Gar_Petticoat", [
    (0.235, 0.20, 0.34), (0.25, 0.21, 0.20), (0.262, 0.22, 0.09)], m_linen))
# 7. shawl (shoulder drape - partial torus shell)
shawl_rings = []
for r in range(14):
    a = math.pi * r / 13
    rr = 0.20 + 0.03 * math.sin(a)
    z = 1.46 - 0.10 * a / math.pi * 3
    pts = []
    for i in range(20):
        b = TAU * i / 20
        # partial wrap: front opening
        if -1.2 < b < 1.2 or b > 4.0:
            continue
        pts.append((math.cos(b) * rr, math.sin(b) * rr * 0.9, z))
    if len(pts) > 3:
        shawl_rings.append({"verts": pts})
try:
    v, f, u = L.loft_rings(shawl_rings, closed_loop=False)
    gm.append(L.new_mesh_obj("Gar_Shawl", v, f, uvs=u, mat=m_woolB))
except Exception as e:
    print("shawl loft skipped:", e)
# 8. apron (front panel)
gm.append(L.box("Gar_Apron", 0.34, 0.012, 0.62, cy=-0.155, cz=0.63, mat=m_linen))
gm.append(L.box("Gar_ApronBib", 0.24, 0.012, 0.28, cy=-0.165, cz=1.10, mat=m_linen))
# 9. flat cap
cap_rings = []
for (r, z) in [(0.001, 1.50), (0.065, 1.505), (0.085, 1.49), (0.088, 1.475)]:
    pts = []
    for i in range(16):
        a = TAU * i / 16
        pts.append((math.cos(a) * r, math.sin(a) * r, z))
    cap_rings.append({"verts": pts})
v, f, u = L.loft_rings(cap_rings, closed_loop=True, cap_bottom=True, cap_top=True)
gm.append(L.new_mesh_obj("Gar_FlatCap", v, f, uvs=u, mat=m_woolC))
gm.append(L.torus("Gar_CapBrim", 0.089, 0.006, cz=1.473, n_path=20, n_sec=8, mat=m_woolC))
# 10. leather belt
gm.append(L.torus("Gar_Belt", 0.155, 0.012, cz=1.02, n_path=24, n_sec=8, mat=m_leath))
gm.append(L.box("Gar_BeltBuckle", 0.035, 0.012, 0.030, cy=-0.155, cz=1.02, mat=m_leath))
finish_asset("TLS-CHR-025", gm, [], "tls_chr_025_garments.blend",
             dims_expected=[0.62, 0.55, 1.52],
             note="10 reusable 1847 garments: smock/waistcoat/jacket/trousers/skirt+petticoat/shawl/apron/flat cap/belt - fitted to medium body (Crowd_Body_Medium)")

# ---------------------------------------------------------------- summary
L.write_json(os.path.join(STATS, "b5_crowd_batch.json"),
             {"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
              "seconds": round(time.time() - t0, 1), "assets": BATCH})
print(f"[B5] done in {time.time()-t0:.0f}s: {len(BATCH)} assets")
for b in BATCH:
    print(f"  - {b['asset']}: {b['tris']} tris")
