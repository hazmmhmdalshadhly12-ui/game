#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE LAST SIN - Batch 4: investigation props v2.
Lantern, ledgers, letters, candlestick, keys, lock, coins, rope, quill, Bible.
Real geometry + brass/iron/leather/paper PBR textures. Grid layout + exports.
Run: blender -b --factory-startup --python build_props_v2.py
"""
import bpy, os, sys, math, json, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sculpt_lib import mesh_obj, fbm3, value_noise3
import textures_v2 as tx

REPO = "/home/z/my-project/repo"
SRC = f"{REPO}/02_Art/blender/source/prp"
EXP = f"{REPO}/02_Art/exports"
TEXDIR = f"{REPO}/02_Art/textures/materials_v2"
T0 = time.time()

def log(*a):
    print(f"[PRP {time.time()-T0:6.1f}s]", *a, flush=True)

def C(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c

def _box(name, size, loc, mat, coll, seed=1, bevel=0.008, rot=(0, 0, 0), seg=2):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    be = ob.modifiers.new("bev", 'BEVEL')
    be.width = bevel; be.segments = seg
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier="bev")
    ob.data.materials.append(mat)
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    coll.objects.link(ob)
    return ob

def _cyl(name, r, d, loc, mat, coll, rot=(0, 0, 0), verts=16):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d, location=loc, rotation=rot, vertices=verts)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(mat)
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    coll.objects.link(ob)
    return ob

def _torus(name, R, r, loc, mat, coll, rot=(0, 0, 0), mj=24, mn=10):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, location=loc,
                                     rotation=rot, major_segments=mj, minor_segments=mn)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(mat)
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    coll.objects.link(ob)
    return ob

def page_block(name, w, d, t, mat_paper, coll, loc, seed=1, rot=0):
    """Book page block with irregular page edges."""
    nx, ny, nz = 26, 18, 8
    verts, faces = [], []
    rng = np.random.default_rng(seed)
    for k in range(nz):
        z = -t / 2 + t * k / (nz - 1)
        for j in range(ny):
            for i in range(nx):
                x = -w / 2 + w * i / (nx - 1)
                y = -d / 2 + d * j / (ny - 1)
                edge = min(i, nx - 1 - i, j, ny - 1 - j)
                jitter = (fbm3(x * 60 + seed, y * 60, z * 60, 2, seed) - 0.5) * 0.0035 if edge == 0 else 0
                verts.append((x + jitter, y + jitter, z))
    for k in range(nz - 1):
        for j in range(ny - 1):
            for i in range(nx - 1):
                a = k * nx * ny + j * nx + i
                b = a + 1; c2 = a + nx; dd = a + nx + 1
                e = a + nx * ny; f = b + nx * ny; g = c2 + nx * ny; h = dd + nx * ny
                faces.append((a, b, dd, c2)); faces.append((e, g, h, f))
                faces.append((a, e, f, b)); faces.append((c2, dd, h, g))
    # outer side faces
    for k in range(nz - 1):
        for j in range(ny - 1):
            a = k * nx * ny + j * nx
            faces.append((a, a + nx * ny, a + nx * ny + nx, a + nx))
            b = a + nx - 1
            faces.append((b, b + nx, b + nx * ny + nx, b + nx * ny))
    ob = mesh_obj(name, np.asarray(verts), faces, mat=mat_paper, coll=coll)
    ob.location = loc
    ob.rotation_euler = (0, 0, rot)
    return ob

def build_lantern(coll, mats, seed=1):
    parts = []
    # base + 4 posts
    parts.append(_cyl("TLS_Lantern_Base", 0.052, 0.014, (0, 0, 0.007), mats["brass"], coll))
    for i in range(4):
        a = math.pi / 2 * i + math.pi / 4
        x, y = 0.043 * math.cos(a), 0.043 * math.sin(a)
        parts.append(_cyl(f"TLS_Lantern_Post{i}", 0.004, 0.16, (x, y, 0.094), mats["brass"], coll))
    # top pyramid + finial
    bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.062, radius2=0.008, depth=0.05,
                                    location=(0, 0, 0.199), rotation=(0, 0, math.pi / 4))
    top = bpy.context.active_object
    top.name = "TLS_Lantern_Top"
    top.data.materials.append(mats["brass"])
    for c in list(top.users_collection):
        c.objects.unlink(top)
    coll.objects.link(top)
    parts.append(top)
    parts.append(_cyl("TLS_Lantern_Finial", 0.006, 0.02, (0, 0, 0.234), mats["brass"], coll))
    # glass panes
    for i in range(4):
        a = math.pi / 2 * i
        g = _box(f"TLS_Lantern_Glass{i}", (0.083, 0.0015, 0.135), (0.045 * math.sin(a), 0.045 * math.cos(a), 0.096),
                 mats["glass"], coll, rot=(0, 0, a), bevel=0.0005, seg=1)
        parts.append(g)
    # candle + wax
    parts.append(_cyl("TLS_Lantern_Candle", 0.011, 0.075, (0, 0, 0.052), mats["wax"], coll))
    # handle ring
    parts.append(_torus("TLS_Lantern_Ring", 0.032, 0.004, (0, 0, 0.245), mats["brass"], coll,
                        rot=(math.pi / 2, 0, 0)))
    # soot darkening: small dark cone inside top
    return parts

def build_ledger(coll, mats, seed=2, open_=False):
    parts = []
    if not open_:
        blk = page_block("TLS_Ledger_Pages", 0.20, 0.26, 0.035, mats["paper"], coll, (0, 0, 0.028), seed)
        cov = _box("TLS_Ledger_Cover", (0.215, 0.275, 0.008), (0, 0, 0.005), mats["leather"], coll)
        parts += [blk, cov]
        parts.append(_box("TLS_Ledger_Strap", (0.028, 0.28, 0.002), (0.062, 0, 0.049), mats["strap"], coll))
    else:
        for sgn in (-1, 1):
            blk = page_block(f"TLS_LedgerOpen_Pages{sgn}", 0.155, 0.24, 0.018, mats["paper"], coll,
                             (sgn * 0.082, 0, 0.012), seed + int(sgn))
            blk.rotation_euler = (0, sgn * -0.06, 0)
            parts.append(blk)
        parts.append(_box("TLS_LedgerOpen_Spine", (0.03, 0.25, 0.006), (0, 0, 0.004), mats["leather"], coll))
    return parts

def build_letters(coll, mats, seed=3):
    parts = []
    rng = np.random.default_rng(seed)
    for i in range(4):
        w = rng.uniform(0.10, 0.12); d = rng.uniform(0.14, 0.16)
        p = _box(f"TLS_Letters_Sheet{i}", (w, d, 0.0018),
                 (rng.uniform(-0.02, 0.02), rng.uniform(-0.02, 0.02), 0.002 + i * 0.0022),
                 mats["paper"], coll, rot=(0, 0, rng.uniform(-0.35, 0.35)), bevel=0.0006, seg=1)
        parts.append(p)
    parts.append(_cyl("TLS_Letters_Seal", 0.011, 0.004, (0.01, 0.01, 0.013), mats["wax"], coll))
    return parts

def build_candlestick(coll, mats, seed=4):
    parts = []
    parts.append(_cyl("TLS_Candle_Base", 0.055, 0.012, (0, 0, 0.006), mats["brass"], coll))
    parts.append(_cyl("TLS_Candle_Stem", 0.008, 0.13, (0, 0, 0.077), mats["brass"], coll))
    parts.append(_cyl("TLS_Candle_Cup", 0.024, 0.02, (0, 0, 0.148), mats["brass"], coll))
    parts.append(_cyl("TLS_Candle_Candle", 0.010, 0.11, (0, 0, 0.20), mats["wax"], coll))
    # wax drips
    for i in range(4):
        a = i * math.pi / 2
        parts.append(_cyl(f"TLS_Candle_Drip{i}", 0.004, 0.03, (0.010 * math.cos(a), 0.010 * math.sin(a), 0.16 - 0.008 * i),
                          mats["wax"], coll))
    return parts

def build_keys(coll, mats, seed=5):
    parts = []
    for i, (L, bw) in enumerate(((0.055, 0.020), (0.070, 0.026), (0.048, 0.016))):
        a = i * 2.1 - 0.8
        cx, cy = math.cos(a) * 0.012, math.sin(a) * 0.012
        shank = _cyl(f"TLS_Key{i}_Shank", 0.0035, L, (cx + L / 2 * math.cos(a + 1.57), cy + L / 2 * math.sin(a + 1.57), 0.004),
                     mats["iron"], coll, rot=(0, math.pi / 2, a))
        bow = _torus(f"TLS_Key{i}_Bow", bw, 0.004, (cx, cy, 0.004), mats["iron"], coll, rot=(0, math.pi / 2, a), mj=16, mn=6)
        bit = _box(f"TLS_Key{i}_Bit", (0.006, 0.018, 0.004),
                   (cx + L * math.cos(a + 1.57) - 0.006 * math.sin(a), cy + L * math.sin(a + 1.57) + 0.006 * math.cos(a), 0.004),
                   mats["iron"], coll, rot=(0, 0, a), bevel=0.001, seg=1)
        parts += [shank, bow, bit]
    return parts

def build_lock(coll, mats, seed=6):
    parts = []
    parts.append(_box("TLS_Lock_Body", (0.075, 0.020, 0.10), (0, 0, 0.05), mats["iron"], coll))
    parts.append(_torus("TLS_Lock_Shackle", 0.030, 0.006, (0, 0, 0.115), mats["iron"], coll,
                        rot=(math.pi / 2, 0, 0), mj=18, mn=8))
    parts.append(_cyl("TLS_Lock_Keyhole", 0.006, 0.024, (0.012, 0, 0.045), mats["brass"], coll,
                      rot=(math.pi / 2, 0, 0)))
    return parts

def build_coins(coll, mats, seed=7):
    parts = []
    rng = np.random.default_rng(seed)
    for i in range(4):
        a = rng.uniform(0, 6.28)
        r = rng.uniform(0.004, 0.035)
        parts.append(_cyl(f"TLS_Coin{i}", 0.011, 0.0016,
                          (r * math.cos(a), r * math.sin(a), 0.001 + (i % 2) * 0.0018),
                          mats["brass"], coll, rot=(rng.uniform(-0.06, 0.06), rng.uniform(-0.06, 0.06), 0), verts=20))
    return parts

def build_rope(coll, mats, seed=8):
    parts = []
    R = 0.13
    for i in range(3):
        r = 0.012 - i * 0.001
        parts.append(_torus(f"TLS_Rope_Coil{i}", R - i * 0.014, r, (0, 0, 0.013 + i * 0.024),
                            mats["rope"], coll, mj=40, mn=8))
    return parts

def build_quill(coll, mats, seed=9):
    parts = []
    from body_lib import tube
    v, f, uv = tube((0, 0, 0), (0.09, 0.02, 0.004), 0.004, 0.0012, n=8)
    parts.append(mesh_obj("TLS_Quill", np.asarray(v), f, uvs=uv, mat=mats["wax"], coll=coll))
    # nib
    parts.append(_box("TLS_Quill_Nib", (0.012, 0.002, 0.001), (0.096, 0.021, 0.004), mats["iron"], coll, bevel=0.0004, seg=1))
    parts.append(_cyl("TLS_Inkwell", 0.028, 0.035, (0.13, -0.01, 0.0175), mats["glass"], coll))
    return parts

def build_bible(coll, mats, seed=10):
    parts = []
    blk = page_block("TLS_Bible_Pages", 0.11, 0.16, 0.028, mats["paper"], coll, (0, 0, 0.020), seed)
    cov = _box("TLS_Bible_Cover", (0.122, 0.172, 0.007), (0, 0, 0.004), mats["leather"], coll)
    cross_v = _box("TLS_Bible_CrossV", (0.008, 0.030, 0.001), (0, 0, 0.0095), mats["brass"], coll, bevel=0.0008, seg=1)
    cross_h = _box("TLS_Bible_CrossH", (0.020, 0.008, 0.001), (0, 0.006, 0.0095), mats["brass"], coll, bevel=0.0008, seg=1)
    parts += [blk, cov, cross_v, cross_h]
    return parts

def mk_mats():
    os.makedirs(TEXDIR, exist_ok=True)
    paths = {}
    paths["brass"] = tx.brass_maps(TEXDIR, "tls_tex_206_brass")
    paths["iron"] = tx.iron_maps(TEXDIR, "tls_tex_206_iron")
    paths["leather"] = tx.leather_maps(TEXDIR, "tls_tex_105_boot", color=(58, 40, 28), worn=0.7)
    paths["strap"] = tx.leather_maps(TEXDIR, "tls_tex_210_strap", color=(74, 52, 34), worn=0.5)
    paths["rope"] = tx.wood_maps(TEXDIR, "tls_tex_211_hemp", planks=1, color=(150, 128, 92), seed=21)
    def img_mat(name, plist, rough=0.6, metallic=0.0):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Roughness"].default_value = rough
        if "Metallic" in b.inputs:
            b.inputs["Metallic"].default_value = metallic
        for p in plist:
            img = bpy.data.images.load(p)
            img.colorspace_settings.name = 'Non-Color' if "_N." in p else 'sRGB'
            tn = m.node_tree.nodes.new("ShaderNodeTexImage")
            tn.image = img
            if "_BC." in p:
                m.node_tree.links.new(tn.outputs["Color"], b.inputs["Base Color"])
            elif "_N." in p:
                nm = m.node_tree.nodes.new("ShaderNodeNormalMap")
                m.node_tree.links.new(tn.outputs["Color"], nm.inputs["Color"])
                m.node_tree.links.new(nm.outputs["Normal"], b.inputs["Normal"])
        return m
    M = {}
    M["brass"] = img_mat("M_P_Brass", paths["brass"], 0.38, 1.0)
    M["iron"] = img_mat("M_P_Iron", paths["iron"], 0.55, 0.85)
    M["leather"] = img_mat("M_P_Leather", paths["leather"], 0.55)
    M["strap"] = img_mat("M_P_Strap", paths["strap"], 0.55)
    M["rope"] = img_mat("M_P_Rope", paths["rope"], 0.8)
    M["paper"] = bpy.data.materials.new("M_P_Paper")
    M["paper"].use_nodes = True
    pb = M["paper"].node_tree.nodes["Principled BSDF"]
    pb.inputs["Base Color"].default_value = (0.62, 0.57, 0.46, 1)
    pb.inputs["Roughness"].default_value = 0.85
    M["wax"] = bpy.data.materials.new("M_P_Wax")
    M["wax"].use_nodes = True
    wb = M["wax"].node_tree.nodes["Principled BSDF"]
    wb.inputs["Base Color"].default_value = (0.72, 0.66, 0.52, 1)
    wb.inputs["Roughness"].default_value = 0.5
    M["glass"] = bpy.data.materials.new("M_P_Glass")
    M["glass"].use_nodes = True
    gb = M["glass"].node_tree.nodes["Principled BSDF"]
    gb.inputs["Base Color"].default_value = (0.8, 0.82, 0.8, 1)
    gb.inputs["Roughness"].default_value = 0.2
    if "Transmission Weight" in gb.inputs:
        gb.inputs["Transmission Weight"].default_value = 0.9
    return M

def main():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for item in list(c):
            try: c.remove(item)
            except Exception: pass
    M = mk_mats()
    COL = C("Props_v2")
    stats = {}
    builders = {
        "tls_prp_001_lantern_v2": build_lantern,
        "tls_prp_002_ledger_v2": lambda c, m: build_ledger(c, m, open_=False),
        "tls_prp_015_ledger_open_v2": lambda c, m: build_ledger(c, m, open_=True),
        "tls_prp_016_letters": build_letters,
        "tls_prp_017_candlestick": build_candlestick,
        "tls_prp_004_gate_key_v2": build_keys,
        "tls_prp_018_church_lock": build_lock,
        "tls_prp_019_coins": build_coins,
        "tls_prp_020_rope": build_rope,
        "tls_prp_021_quill_inkwell": build_quill,
        "tls_prp_022_bible": build_bible,
    }
    grid = {}
    for idx, (nm, fn) in enumerate(builders.items()):
        col = C(f"P_{idx}")
        parts = fn(col, M)
        gx, gy = (idx % 4) * 0.6, (idx // 4) * 0.6
        for o in parts:
            o.location.x += gx
            o.location.y += gy
        grid[nm] = (gx, gy)
    # save combined
    allc = [o for c in [bpy.data.collections.get(f"P_{i}") for i in range(len(builders))] for o in c.objects]
    bpy.ops.wm.save_as_mainfile(filepath=f"{SRC}/tls_prp_030_investigation_set_v2.blend")
    tot = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in allc)
    os.makedirs(f"{EXP}/glb", exist_ok=True)
    bpy.ops.object.select_all(action='DESELECT')
    for o in allc:
        o.select_set(True)
    bpy.context.view_layer.objects.active = allc[0]
    bpy.ops.export_scene.gltf(filepath=f"{EXP}/glb/tls_prp_030_investigation_set_v2.glb",
                              export_format='GLB', export_apply=True)
    os.makedirs(f"{EXP}/fbx", exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=f"{EXP}/fbx/tls_prp_030_investigation_set_v2.fbx",
                             use_selection=True, add_leaf_bones=False, bake_anim=False,
                             object_types={'MESH'}, path_mode='COPY')
    stats["tls_prp_030_investigation_set_v2"] = dict(
        tris=tot, objects=len(allc),
        blend=f"{SRC}/tls_prp_030_investigation_set_v2.blend",
        glb=f"{EXP}/glb/tls_prp_030_investigation_set_v2.glb",
        fbx=f"{EXP}/fbx/tls_prp_030_investigation_set_v2.fbx",
        items=list(builders.keys()))
    with open(f"{EXP}/stats/props_batch_v2.json", "w") as f:
        json.dump(stats, f, indent=1)
    log(f"PROPS DONE: {tot} tris, {len(allc)} objects")

main()
