#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE LAST SIN - M4 Batch build library (Blender 5.0.1 headless).
Adapted from the proven M3.4 Edmund library (02_Art/Characters/Edmund/build_scripts/edmund_lib.py)
with additions for batch asset production:
  - generic static/skeletal FBX export per TECHNICAL_PIPELINE.md §4 contract
  - pivot/units/bbox audit helpers, UCX collision proxies
  - manifest writing + md5
All geometry is generated procedurally - no external asset downloads.
"""
import bpy, bmesh, math, json, os, random
from mathutils import Vector, Matrix, Euler

TAU = math.pi * 2.0

# ---------------------------------------------------------------- scene utils
def reset_scene():
    """Remove all objects/data from the file (we start from an empty session)."""
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials,
                 bpy.data.armatures, bpy.data.curves, bpy.data.images,
                 bpy.data.lights, bpy.data.cameras, bpy.data.particles,
                 bpy.data.node_groups, bpy.data.worlds, bpy.data.actions):
        for item in list(coll):
            try:
                coll.remove(item)
            except Exception:
                pass

def setup_units(scene_name="TLS_Batch"):
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 1.0
    sc.unit_settings.length_unit = 'METERS'
    sc.name = scene_name

def get_coll(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c

def link_obj(obj, coll_name="TLS"):
    get_coll(coll_name).objects.link(obj)

# ---------------------------------------------------------------- mesh utils
def new_mesh_obj(name, verts, faces, uvs=None, mat=None, coll="TLS",
                 smooth_angle=40.0):
    """Build a mesh object from python data. uvs = per-vertex (u,v) or None."""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.validate(verbose=False)
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
        # iterate the VALIDATED polygons (validate may drop degenerate faces)
        li = 0
        for poly in mesh.polygons:
            for vi in poly.vertices:
                if li < len(uv.data) and vi < len(uvs):
                    uv.data[li].uv = uvs[vi]
                li += 1
    if mat is not None:
        obj.data.materials.append(mat)
    if smooth_angle is not None:
        smooth_all(obj, smooth_angle)
    return obj

def smooth_all(obj, angle_deg=40.0):
    for p in obj.data.polygons:
        p.use_smooth = True
    m = obj.modifiers.new("EdgeSplit", 'EDGE_SPLIT')
    m.split_angle = math.radians(angle_deg)
    m.use_edge_angle = True
    m.use_edge_sharp = True

def join_objects(objs, name, coll="TLS"):
    """Join meshes into one object (headless-safe, no ops)."""
    bm = bmesh.new()
    mat_map = {}
    for o in objs:
        tmp = bmesh.new()
        tmp.from_mesh(o.data)
        tmp.transform(o.matrix_world)
        for slot in o.material_slots:
            if slot.material and slot.material.name not in mat_map:
                mat_map[slot.material.name] = slot.material
        idx_map = {}
        for i, slot in enumerate(o.material_slots):
            nm = slot.material.name if slot.material else ""
            idx_map[i] = list(mat_map.keys()).index(nm) if nm in mat_map else 0
        for f in tmp.faces:
            f.material_index = idx_map.get(f.material_index, 0)
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
    link_obj(ob, coll)
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

def bbox_world(objs):
    """Exact world-space bounding box over a list of objects (evaluated)."""
    dg = bpy.context.evaluated_depsgraph_get()
    mins = [1e9, 1e9, 1e9]; maxs = [-1e9, -1e9, -1e9]
    for o in objs:
        eo = o.evaluated_get(dg)
        me = eo.to_mesh()
        for v in me.vertices:
            w = eo.matrix_world @ v.co
            for k in range(3):
                mins[k] = min(mins[k], w[k]); maxs[k] = max(maxs[k], w[k])
        eo.to_mesh_clear()
    return {"min": [round(x, 4) for x in mins], "max": [round(x, 4) for x in maxs],
            "dims": [round(maxs[k] - mins[k], 4) for k in range(3)]}

def audit_asset(objs, name, pivot_at_base=True):
    """Standard M4 audit: stats + checks + pivot + bbox (meters)."""
    stats = {"asset": name, "objects": [], "totals": {"verts": 0, "tris": 0}}
    for o in objs:
        s = obj_stats(o)
        s.update(mesh_checks(o))
        s["materials"] = [sl.material.name if sl.material else None
                          for sl in o.material_slots]
        s["uvs"] = [uv.name for uv in o.data.uv_layers]
        s["loc"] = [round(v, 4) for v in o.location]
        stats["objects"].append(s)
        stats["totals"]["verts"] += s["verts"]
        stats["totals"]["tris"] += s["tris"]
    stats["bbox_m"] = bbox_world(objs)
    zs = [o.location.z for o in objs]
    stats["pivot_ok"] = bool(abs(min(zs)) < 0.02) if pivot_at_base else None
    return stats

def add_ucx_box(obj, name=None, shrink=1.0):
    """Add a simple UCX_ collision box matching obj's world bbox (UE convention)."""
    dg = bpy.context.evaluated_depsgraph_get()
    eo = obj.evaluated_get(dg)
    me = eo.to_mesh()
    mins = [1e9] * 3; maxs = [-1e9] * 3
    for v in me.vertices:
        w = eo.matrix_world @ v.co
        for k in range(3):
            mins[k] = min(mins[k], w[k]); maxs[k] = max(maxs[k], w[k])
    eo.to_mesh_clear()
    cx, cy = (mins[0] + maxs[0]) / 2, (mins[1] + maxs[1]) / 2
    cz = (mins[2] + maxs[2]) / 2
    hx = (maxs[0] - mins[0]) / 2 * shrink
    hy = (maxs[1] - mins[1]) / 2 * shrink
    hz = (maxs[2] - mins[2]) / 2
    x0, x1 = cx - hx, cx + hx
    y0, y1 = cy - hy, cy + hy
    z0, z1 = cz - hz, cz + hz
    verts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    ucx = new_mesh_obj(name or f"UCX_{obj.name}", verts, faces, uvs=None,
                       mat=None, coll="UCX", smooth_angle=None)
    ucx.display_type = 'WIRE'
    ucx.hide_render = True
    return ucx

# ---------------------------------------------------------------- geometry
def gauss(p, c, s, amp):
    dx = (p[0] - c[0]) / s[0]
    dy = (p[1] - c[1]) / s[1]
    dz = (p[2] - c[2]) / s[2]
    return amp * math.exp(-(dx * dx + dy * dy + dz * dz))

def smooth_verts(verts, faces, iterations=1, factor=0.5):
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
    """rings: list of dicts {verts:[(x,y,z)...] equal length}. Build lofted tube."""
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

def ellipse_ring(z, cx, cy, wx, wy, n=32, rot=0.0):
    pts = []
    for i in range(n):
        a = TAU * i / n + rot
        pts.append((cx + wx * math.cos(a), cy + wy * math.sin(a), z))
    return {"verts": pts}

def box(name, sx, sy, sz, cx=0.0, cy=0.0, cz=0.0, mat=None, coll="TLS",
        rot_z=0.0):
    """Axis box helper: sizes in meters, center position, optional Z rotation."""
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    ca, sa = math.cos(rot_z), math.sin(rot_z)
    raw = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
           (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
    verts = [(cx + x * ca - y * sa, cy + x * sa + y * ca, cz + z) for x, y, z in raw]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    u = [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0), (1, 0), (1, 1), (0, 1)]
    return new_mesh_obj(name, verts, faces, uvs=u, mat=mat, coll=coll,
                        smooth_angle=None)

def cyl(name, r, z0, z1, cx=0.0, cy=0.0, n=24, rx=None, ry=None, mat=None,
        coll="TLS", cap=True, r_top=None):
    """Vertical (or tapered) cylinder from z0 to z1 centered (cx,cy)."""
    rt = r if r_top is None else r_top
    lo = ellipse_ring(z0, cx, cy, r if rx is None else rx, r if ry is None else ry, n)
    hi = ellipse_ring(z1, cx, cy, rt if rx is None else rx, rt if ry is None else ry, n)
    v, f, u = loft_rings([lo, hi], closed_loop=True, cap_bottom=cap, cap_top=cap)
    return new_mesh_obj(name, v, f, uvs=u, mat=mat, coll=coll)

def tube_between(p0, p1, r0, r1, n=10, name="tube", mat=None, coll="TLS"):
    """Tapered tube between two 3D points (for branches/handles)."""
    d = Vector(p1) - Vector(p0)
    L = d.length
    if L < 1e-6:
        d = Vector((0, 0, 1))
        L = 1e-6
    up = d.normalized()
    if abs(up.z) > 0.95:
        side = Vector((1, 0, 0))
    else:
        side = up.cross(Vector((0, 0, 1))).normalized()
    fwd = up.cross(side).normalized()
    rings = []
    for (p, r) in ((p0, r0), (p1, r1)):
        ring = []
        for i in range(n):
            a = TAU * i / n
            off = side * (math.cos(a) * r) + fwd * (math.sin(a) * r)
            ring.append((p[0] + off.x, p[1] + off.y, p[2] + off.z))
        rings.append({"verts": ring})
    v, f, u = loft_rings(rings, closed_loop=True, cap_bottom=True, cap_top=True)
    return new_mesh_obj(name, v, f, uvs=u, mat=mat, coll=coll)


def torus(name, R, r, cx=0.0, cy=0.0, cz=0.0, n_path=36, n_sec=12,
          mat=None, coll="TLS", arc=TAU, scale_sec=None):
    """Torus (optionally partial arc) in the XZ-oriented ring plane (ring axis = Z)."""
    rings = []
    for i in range(n_path):
        a = arc * i / n_path
        px, py = cx + R * math.cos(a), cy + R * math.sin(a)
        pts = []
        for j in range(n_sec):
            b = TAU * j / n_sec
            rx, rz = math.cos(b) * r, math.sin(b) * r
            if scale_sec:
                rx *= scale_sec
            pts.append((px + math.cos(a) * rx, py + math.sin(a) * rx, cz + rz))
        rings.append({"verts": pts})
    v, f, u = loft_rings(rings, closed_loop=arc >= TAU - 1e-6,
                         cap_bottom=arc < TAU - 1e-6,
                         cap_top=arc < TAU - 1e-6)
    return new_mesh_obj(name, v, f, uvs=u, mat=mat, coll=coll)

# ---------------------------------------------------------------- materials
def _find_socket(node, names):
    for n in names:
        if n in node.inputs:
            return node.inputs[n]
    return None

def set_principled(node, **kw):
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
                  noncolor=True):
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
    if hasattr(img_or_node, 'outputs'):
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

def add_orm(mat, img, ao_strength=0.8):
    """Wire a packed ORM texture: R=AO->multiplies BaseColor, G=Roughness, B=Metallic."""
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf:
        return
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    try:
        tex.image.colorspace_settings.name = 'Non-Color'
    except Exception:
        pass
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    nt.links.new(tc.outputs['UV'], mp.inputs['Vector'])
    nt.links.new(mp.outputs['Vector'], tex.inputs['Vector'])
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(tex.outputs['Color'], sep.inputs['Color'])
    r_sock = _find_socket(bsdf, ["Roughness"])
    if r_sock is not None:
        nt.links.new(sep.outputs['Green'], r_sock)
    m_sock = _find_socket(bsdf, ["Metallic"])
    if m_sock is not None:
        nt.links.new(sep.outputs['Blue'], m_sock)
    bc_sock = _find_socket(bsdf, ["Base Color"])
    if bc_sock is not None:
        mul = nt.nodes.new('ShaderNodeMixRGB')
        mul.blend_type = 'MULTIPLY'
        mul.inputs['Fac'].default_value = ao_strength
        mul.inputs['Color2'].default_value = (1, 1, 1, 1)
        base_link = None
        for l in nt.links:
            if l.to_socket == bc_sock:
                base_link = l
                break
        if base_link:
            nt.links.new(base_link.from_socket, mul.inputs['Color1'])
            nt.links.remove(base_link)
        else:
            mul.inputs['Color1'].default_value = (0.5, 0.5, 0.5, 1)
        nt.links.new(sep.outputs['Red'], mul.inputs['Color2'])
        nt.links.new(mul.outputs['Color'], bc_sock)

# ---------------------------------------------------------------- textures
def img_from_array(name, arr, filepath=None, colorspace='sRGB'):
    import numpy as np
    arr = np.ascontiguousarray(np.clip(arr, 0.0, 1.0), dtype=np.float32)
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

def save_array_png(name, arr, filepath, colorspace='sRGB'):
    img = img_from_array(name, arr, filepath=filepath, colorspace=colorspace)
    bpy.data.images.remove(img)

def load_png(path, name=None, colorspace='sRGB'):
    img = bpy.data.images.load(path, check_existing=True)
    if name:
        img.name = name
    try:
        img.colorspace_settings.name = colorspace
    except Exception:
        pass
    return img

# ---------------------------------------------------------------- export
def select_only(objs, extra=None):
    bpy.ops.object.select_all(action='DESELECT')
    sel = list(objs) + (extra or [])
    n = 0
    for o in sel:
        if o and o.name in bpy.data.objects:
            o.select_set(True)
            n += 1
    return n

def apply_transforms(objs, location=False):
    """Ctrl+A rotation+scale equivalent (headless-safe) for static assets."""
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.transform_apply(location=location, rotation=True, scale=True)

def export_static_fbx(objs, path, ucx_objs=None):
    """Static-mesh FBX per TECHNICAL_PIPELINE.md §4 contract."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    select_only(objs, extra=ucx_objs or [])
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True,
        axis_forward='-Y', axis_up='Z',
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
        global_scale=1.0,
        object_types={'MESH'},
        use_mesh_modifiers=True,
        bake_space_transform=False,
        add_leaf_bones=False,
        bake_anim=False,
        path_mode='AUTO',
        mesh_smooth_type='FACE')
    return os.path.getsize(path)

def export_skeletal_fbx(arm_obj, mesh_objs, path, apply_mods=False):
    """Skeletal FBX per contract (armature + mesh, no leaf bones)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    select_only(mesh_objs, extra=[arm_obj])
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True,
        axis_forward='-Y', axis_up='Z',
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
        global_scale=1.0,
        object_types={'ARMATURE', 'MESH'},
        use_mesh_modifiers=apply_mods,
        bake_space_transform=False,
        add_leaf_bones=False,
        bake_anim=False,
        path_mode='AUTO',
        mesh_smooth_type='FACE')
    return os.path.getsize(path)

def export_anim_fbx(arm_obj, path, mesh_objs=None):
    """Animation FBX: armature (+ optional skin) with baked action."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    select_only(mesh_objs or [], extra=[arm_obj])
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True,
        axis_forward='-Y', axis_up='Z',
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
        global_scale=1.0,
        object_types={'ARMATURE', 'MESH'},
        use_mesh_modifiers=False,
        bake_space_transform=False,
        add_leaf_bones=False,
        bake_anim=True,
        bake_anim_use_nla_strips=True,
        bake_anim_use_all_actions=True,
        bake_anim_use_all_bones=True,
        bake_anim_simplify_factor=0.0,
        path_mode='AUTO',
        mesh_smooth_type='FACE')
    return os.path.getsize(path)

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

def parse_args():
    import sys
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts, i = {}, 0
    while i < len(argv):
        if argv[i].startswith("--"):
            opts[argv[i][2:]] = argv[i + 1]
            i += 2
        else:
            i += 1
    return opts
