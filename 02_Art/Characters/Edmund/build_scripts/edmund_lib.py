#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE LAST SIN - M3.4 Edmund character build library.
Parametric mesh / material / texture helpers for Blender 5.0.1 (headless).
All geometry is generated procedurally here - no external asset downloads.
"""
import bpy, bmesh, math, json, os, random
import numpy as np
from mathutils import Vector, Matrix, Euler

TAU = math.pi * 2.0

# ---------------------------------------------------------------- scene utils
def reset_scene():
    """Remove all objects/data from the file (we start from an empty session)."""
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials,
                 bpy.data.armatures, bpy.data.curves, bpy.data.images,
                 bpy.data.lights, bpy.data.cameras, bpy.data.particles,
                 bpy.data.node_groups, bpy.data.worlds):
        for item in list(coll):
            try:
                coll.remove(item)
            except Exception:
                pass

def setup_units():
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 1.0
    sc.unit_settings.length_unit = 'METERS'

def get_coll(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c

def link_obj(obj, coll_name="Edmund"):
    get_coll(coll_name).objects.link(obj)

# ---------------------------------------------------------------- mesh utils
def new_mesh_obj(name, verts, faces, uvs=None, mat=None, coll="Edmund"):
    """Build a mesh object from python data. uvs = list of (u,v) per loop or None."""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.validate(verbose=False)
    # make normals consistent & outward (critical for shading + hair flow)
    if faces:
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    link_obj(obj, coll)
    if uvs is not None:
        uv = mesh.uv_layers.new(name="UVMap")
        flat = []
        for f in faces:
            for vi in f:
                flat.append(uvs[vi])
        for i, co in enumerate(flat):
            uv.data[i].uv = co
    if mat is not None:
        obj.data.materials.append(mat)
    smooth_all(obj)
    return obj

def smooth_all(obj, angle_deg=40.0):
    for p in obj.data.polygons:
        p.use_smooth = True
    m = obj.modifiers.new("EdgeSplit", 'EDGE_SPLIT')
    m.split_angle = math.radians(angle_deg)
    m.use_edge_angle = True
    m.use_edge_sharp = True

def join_objects(objs, name):
    """Join meshes into the first object (headless-safe, no ops)."""
    bm = bmesh.new()
    mat_map = {}
    for o in objs:
        me = o.data
        tmp = bmesh.new()
        tmp.from_mesh(me)
        tmp.transform(o.matrix_world)
        # remap materials
        for slot in o.material_slots:
            if slot.material and slot.material.name not in mat_map:
                mat_map[slot.material.name] = slot.material
        mat_idx_offset = {}
        for i, slot in enumerate(o.material_slots):
            nm = slot.material.name if slot.material else ""
            mat_idx_offset[i] = list(mat_map.keys()).index(nm) if nm in mat_map else 0
        for f in tmp.faces:
            f.material_index = mat_idx_offset.get(f.material_index, 0)
        # append into bm with material remap
        me2 = bpy.data.meshes.new("_tmp_join")
        tmp.to_mesh(me2)
        tmp.free()
        bm.from_mesh(me2)
        bpy.data.meshes.remove(me2)
    out = bpy.data.meshes.new(name)
    bm.to_mesh(out)
    bm.free()
    out.update()
    ob = bpy.data.objects.new(name, out)
    link_obj(ob)
    for mname in mat_map:
        ob.data.materials.append(mat_map[mname])
    smooth_all(ob)
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)
    return ob

def obj_stats(obj):
    mesh = obj.data
    tris = 0
    for p in mesh.polygons:
        tris += max(0, len(p.vertices) - 2)
    return {"name": obj.name, "verts": len(mesh.vertices),
            "polys": len(mesh.polygons), "tris": tris}

def mesh_checks(obj):
    """Boundary edges, loose verts, non-manifold edge count, NaN check."""
    mesh = obj.data
    edge_users = {}
    for p in mesh.polygons:
        n = len(p.vertices)
        for i in range(n):
            a, b = p.vertices[i], p.vertices[(i + 1) % n]
            key = (a, b) if a < b else (b, a)
            edge_users[key] = edge_users.get(key, 0) + 1
    boundary = sum(1 for v in edge_users.values() if v == 1)
    nonmanifold = sum(1 for v in edge_users.values() if v > 2)
    used = set()
    for p in mesh.polygons:
        used.update(p.vertices)
    loose = len(mesh.vertices) - len(used)
    nan = 0
    for v in mesh.vertices:
        co = v.co
        if co.x != co.x or co.y != co.y or co.z != co.z:
            nan += 1
    return {"boundary_edges": boundary, "nonmanifold_edges": nonmanifold,
            "loose_verts": loose, "nan_verts": nan}

# ---------------------------------------------------------------- geometry
def uv_sphere_grid(cx, cy, cz, rx, ry, rz, seg_u=96, seg_v=64, u_off=0.0):
    """Custom UV sphere with welded poles (no duplicated verts at top/bottom).
    Seam at +Y back (u=0.5 front for -Y facing char).
    Returns verts, faces, uvs."""
    verts, uvs = [], []
    pole_top = len(verts); verts.append((cx, cy, cz + rz)); uvs.append((0.5, 1.0))
    for j in range(1, seg_v):
        v = j / seg_v
        theta = math.pi * v
        for i in range(seg_u):
            u = i / seg_u
            phi = u_off + TAU * u
            sx = math.sin(theta) * math.cos(phi)
            sy = math.sin(theta) * math.sin(phi)
            sz = math.cos(theta)
            verts.append((cx + rx * sx, cy + ry * sy, cz + rz * sz))
            uvs.append((u, v))
    pole_bot = len(verts); verts.append((cx, cy, cz - rz)); uvs.append((0.5, 0.0))
    faces = []
    def vid(j, i):
        return 1 + (j - 1) * seg_u + (i % seg_u)
    # top cap
    for i in range(seg_u):
        faces.append((pole_top, vid(1, i), vid(1, i + 1)))
    # body quads
    for j in range(1, seg_v - 1):
        for i in range(seg_u):
            a, b = vid(j, i), vid(j, i + 1)
            c, d = vid(j + 1, i + 1), vid(j + 1, i)
            faces.append((a, b, c, d))
    # bottom cap
    for i in range(seg_u):
        faces.append((pole_bot, vid(seg_v - 1, i + 1), vid(seg_v - 1, i)))
    return verts, faces, uvs

def gauss(p, c, s, amp):
    """Anisotropic gaussian kernel contribution."""
    dx = (p[0] - c[0]) / s[0]
    dy = (p[1] - c[1]) / s[1]
    dz = (p[2] - c[2]) / s[2]
    return amp * math.exp(-(dx * dx + dy * dy + dz * dz))

def smooth_verts(verts, faces, iterations=1, factor=0.5):
    """Simple laplacian relaxation on raw vert list."""
    idx_neighbors = {}
    for f in faces:
        n = len(f)
        for i in range(n):
            a, b = f[i], f[(i + 1) % n]
            idx_neighbors.setdefault(a, set()).add(b)
            idx_neighbors.setdefault(b, set()).add(a)
    for _ in range(iterations):
        new = []
        for i, p in enumerate(verts):
            nb = idx_neighbors.get(i)
            if not nb:
                new.append(p)
                continue
            ax = sum(verts[j][0] for j in nb) / len(nb)
            ay = sum(verts[j][1] for j in nb) / len(nb)
            az = sum(verts[j][2] for j in nb) / len(nb)
            new.append((p[0] + (ax - p[0]) * factor,
                        p[1] + (ay - p[1]) * factor,
                        p[2] + (az - p[2]) * factor))
        verts = new
    return verts

def loft_rings(rings, closed_loop=True, cap_bottom=False, cap_top=False,
               uv_mode="cyl"):
    """rings: list of dicts {verts:[(x,y,z)...] equal length}. Build lofted tube.
    Returns verts, faces, uvs."""
    verts, uvs = [], []
    nv = len(rings[0]["verts"])
    for ri, ring in enumerate(rings):
        vs = ring.get("uvs")
        for vi, p in enumerate(ring["verts"]):
            verts.append(p)
            if vs:
                uvs.append(vs[vi])
            else:
                u = vi / nv if closed_loop else vi / (nv - 1)
                uvs.append((u, ri / max(1, len(rings) - 1)))
    faces = []
    nr = len(rings)
    for ri in range(nr - 1):
        base_a, base_b = ri * nv, (ri + 1) * nv
        for vi in range(nv if closed_loop else nv - 1):
            vi2 = (vi + 1) % nv
            a, b = base_a + vi, base_a + vi2
            c, d = base_b + vi2, base_b + vi
            faces.append((a, b, c, d))
    if cap_bottom:
        cidx = len(verts)
        cx = sum(p[0] for p in rings[0]["verts"]) / nv
        cy = sum(p[1] for p in rings[0]["verts"]) / nv
        cz = sum(p[2] for p in rings[0]["verts"]) / nv
        verts.append((cx, cy, cz))
        uvs.append((0.5, 0.0))
        for vi in range(nv):
            vi2 = (vi + 1) % nv
            faces.append((cidx, vi, vi2))
    if cap_top:
        cidx = len(verts)
        cx = sum(p[0] for p in rings[-1]["verts"]) / nv
        cy = sum(p[1] for p in rings[-1]["verts"]) / nv
        cz = sum(p[2] for p in rings[-1]["verts"]) / nv
        verts.append((cx, cy, cz))
        uvs.append((0.5, 1.0))
        base = (nr - 1) * nv
        for vi in range(nv):
            vi2 = (vi + 1) % nv
            faces.append((cidx, base + vi2, base + vi))
    return verts, faces, uvs

def ellipse_ring(z, cx, cy, wx, wy, n=32, rot=0.0, squash_top=None):
    """One loft cross-section: ellipse at height z centered (cx,cy) half-extents (wx,wy)."""
    pts = []
    for i in range(n):
        a = TAU * i / n + rot
        pts.append((cx + wx * math.cos(a), cy + wy * math.sin(a), z))
    return {"verts": pts}

# ---------------------------------------------------------------- materials
def _find_socket(node, names):
    for n in names:
        if n in node.inputs:
            return node.inputs[n]
    return None

def set_principled(node, **kw):
    """Set principled inputs tolerantly across Blender 4.x/5.x socket names."""
    alias = {
        "base_color": ["Base Color"],
        "metallic": ["Metallic"],
        "roughness": ["Roughness"],
        "ior": ["IOR"],
        "alpha": ["Alpha"],
        "normal": ["Normal"],
        "sss_weight": ["Subsurface Weight", "Subsurface"],
        "sss_radius": ["Subsurface Radius"],
        "sss_scale": ["Subsurface Scale", "Scale"],
        "sss_color": ["Subsurface Color"],
        "spec": ["Specular IOR Level", "Specular"],
        "coat": ["Coat Weight", "Clearcoat"],
        "coat_rough": ["Coat Roughness", "Clearcoat Roughness"],
        "sheen": ["Sheen Weight", "Sheen"],
        "sheen_rough": ["Sheen Roughness"],
        "sheen_tint": ["Sheen Tint", "Sheen TintColor"],
        "emission": ["Emission Color", "Emission"],
        "emission_strength": ["Emission Strength"],
    }
    for key, val in kw.items():
        sock = _find_socket(node, alias.get(key, [key]))
        if sock is None:
            continue
        try:
            if hasattr(sock, "default_value"):
                if isinstance(val, (tuple, list)) and len(val) in (3, 4) and hasattr(sock.default_value, "__len__"):
                    sock.default_value = tuple(val) if len(val) == len(sock.default_value) else (list(val) + [1.0])[:len(sock.default_value)]
                else:
                    sock.default_value = val
        except Exception:
            pass

def new_mat(name, base=(0.5, 0.5, 0.5), rough=0.5, metal=None, **extra):
    if metal is None:
        metal = extra.pop("metallic", 0.0)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf:
        set_principled(bsdf, base_color=base, roughness=rough, metallic=metal, **extra)
    return mat

def add_image_tex(mat, img, coords='UV', scale=(1, 1, 1), loc=(0, 0, 0),
                  vector_sock="Base Color", color2=None, blend_mode='MIX',
                  noncolor=True, mapping_key=None):
    """Insert an image texture node feeding a shader input (optionally mixed with a color)."""
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf:
        return None
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    if noncolor:
        try:
            tex.image.colorspace_settings.name = 'Non-Color'
        except Exception:
            pass
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = scale
    mp.inputs['Location'].default_value = loc
    nt.links.new(tc.outputs[coords], mp.inputs['Vector'])
    nt.links.new(mp.outputs['Vector'], tex.inputs['Vector'])
    sock = _find_socket(bsdf, [vector_sock])
    if sock is None:
        return tex
    if color2 is None:
        nt.links.new(tex.outputs['Color'], sock)
    else:
        mix = nt.nodes.new('ShaderNodeMixRGB')
        mix.blend_type = blend_mode
        mix.inputs['Color2'].default_value = color2 if len(color2) == 4 else (color2 + (1.0,))
        mix.inputs['Fac'].default_value = 1.0
        nt.links.new(tex.outputs['Color'], mix.inputs['Color1'])
        nt.links.new(mix.outputs['Color'], sock)
    return tex

def add_bump(mat, img_or_node, scale=0.3, distance=0.001, through_normal=True):
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf:
        return
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = scale
    bump.inputs['Distance'].default_value = distance
    if hasattr(img_or_node, 'outputs'):  # a node
        src = img_or_node.outputs['Color']
    else:
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = img_or_node
        try:
            tex.image.colorspace_settings.name = 'Non-Color'
        except Exception:
            pass
        src = tex.outputs['Color']
        tc = nt.nodes.new('ShaderNodeTexCoord')
        mp = nt.nodes.new('ShaderNodeMapping')
        nt.links.new(tc.outputs['UV'], mp.inputs['Vector'])
        nt.links.new(mp.outputs['Vector'], tex.inputs['Vector'])
    nt.links.new(src, bump.inputs['Height'])
    if through_normal:
        nrm = _find_socket(bsdf, ["Normal"])
        if nrm is not None:
            nt.links.new(bump.outputs['Normal'], nrm)
    return bump

# ---------------------------------------------------------------- textures
def img_from_array(name, arr, filepath=None, colorspace='sRGB'):
    """arr: HxWx(3|4) float 0..1 numpy -> Blender image (+ optional PNG save)."""
    h, w = arr.shape[:2]
    channels = arr.shape[2] if arr.ndim == 3 else 1
    img = bpy.data.images.new(name, width=w, height=h, alpha=(channels == 4))
    if channels == 1:
        a = np.repeat(arr[:, :, None], 4, axis=2)
    elif channels == 3:
        a = np.dstack([arr, np.ones((h, w, 1), dtype=arr.dtype)])
    else:
        a = arr
    img.pixels.foreach_set(a.reshape(-1))
    if filepath:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        img.filepath_raw = filepath
        img.file_format = 'PNG'
        img.save()
    try:
        img.colorspace_settings.name = colorspace
    except Exception:
        pass
    img.update()
    return img

def save_array_png(name, arr, filepath):
    """Standalone save (no blender image datablock needed afterwards)."""
    img = img_from_array(name, arr, filepath=filepath)
    bpy.data.images.remove(img)

def gen_cloth_weave(res=512, threads=48, fuzz=0.18, seed=7):
    rng = np.random.default_rng(seed)
    x = np.linspace(0, threads * math.pi, res, endpoint=False)
    wx, wy = np.meshgrid(x, x)
    weave = (np.sin(wx) * 0.5 + 0.5) * (np.sin(wy) * 0.5 + 0.5)
    weave = weave * 0.6 + 0.4 * (np.sin(wx) * np.sin(wy) * 0.5 + 0.5)
    n = rng.normal(0, fuzz, (res, res))
    out = np.clip(weave + n, 0, 1)[..., None] * np.ones((1, 1, 3))
    return out.astype(np.float32)

def gen_leather_grain(res=512, cells=90, seed=11):
    """Cheap cellular (voronoi-ish) grain via brute force distance to random points."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:res, 0:res]
    pts = rng.random((cells, 2)) * res
    d1 = np.full((res, res), 1e9, dtype=np.float32)
    d2 = np.full((res, res), 1e9, dtype=np.float32)
    for i in range(cells):
        px, py = pts[i]
        dx = np.minimum(np.abs(xx - px), res - np.abs(xx - px))  # tile wrap
        dy = np.minimum(np.abs(yy - py), res - np.abs(yy - py))
        d = (dx * dx + dy * dy)
        mask2 = d < d2
        d2[mask2] = d[mask2]
        mask1 = d < d1
        d2[mask1] = d1[mask1]
        d1[mask1] = d[mask1]
    edge = np.sqrt(d2) - np.sqrt(d1)
    grain = np.clip(edge / 6.0, 0, 1)
    n = rng.normal(0, 0.05, (res, res))
    out = np.clip(grain * 0.7 + 0.3 + n, 0, 1)
    return np.repeat(out[..., None], 3, axis=2).astype(np.float32)

def gen_skin_micro(res=512, pore=260, seed=23):
    rng = np.random.default_rng(seed)
    base = rng.normal(0.5, 0.16, (res, res)).astype(np.float32)
    yy, xx = np.mgrid[0:res, 0:res]
    dots = np.zeros((res, res), dtype=np.float32)
    for _ in range(pore):
        px, py = rng.integers(0, res, 2)
        r = rng.integers(1, 3)
        m = ((xx - px) ** 2 + (yy - py) ** 2) <= r * r
        dots[m] = 0.85
    dots = np.roll(dots, res // 2, axis=1)
    out = np.clip(base * 0.55 + dots, 0, 1)
    return np.repeat(out[..., None], 3, axis=2).astype(np.float32)

def gen_iris(res=512, seed=31, base=(0.30, 0.36, 0.42)):
    """Gray-blue radial fiber iris, dark limbal ring, black pupil center."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:res, 0:res]
    cx = cy = res / 2
    dx, dy = xx - cx, yy - cy
    r = np.sqrt(dx * dx + dy * dy) / (res / 2)
    ang = np.arctan2(dy, dx)
    fibers = np.sin(ang * 90 + rng.uniform(0, 6, 1)[0]) * 0.5 + 0.5
    spokes = np.sin(ang * 26) * 0.5 + 0.5
    iris = 0.55 + 0.25 * fibers * spokes
    col = np.zeros((res, res, 3), dtype=np.float32)
    for i in range(3):
        col[..., i] = base[i] * (0.7 + 0.55 * iris)
    col[..., 0] *= 0.9  # cooler
    limbal = np.clip((r - 0.82) / 0.10, 0, 1)
    for i in range(3):
        col[..., i] *= (1.0 - limbal * 0.85)
    pupil = np.clip((0.30 - r) / 0.06, 0, 1)
    for i in range(3):
        col[..., i] = col[..., i] * (1 - pupil)
    outside = (r > 1.0).astype(np.float32)
    for i in range(3):
        col[..., i] = col[..., i] * (1 - outside) + 0.85 * outside
    return np.clip(col, 0, 1)

def gen_eyeball_base(res=256):
    out = np.ones((res, res, 3), dtype=np.float32) * 0.88
    return out

# ---------------------------------------------------------------- misc
def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

def md5_of(path):
    import hashlib
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
