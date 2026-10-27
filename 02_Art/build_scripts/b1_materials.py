#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M4-B1 materials package:
  TLS-TEX-001 UV checker (PLANNED->TEXTURED)
  TLS-MAT-001 slate / 002 oak / 003 wool / 004 brass / 005 moor terrain set
Support sets (used by M4 assets, packed into their blends):
  stone_wall, slate_roof, bark, iron, leather, paper, thatch, wax
Alpha cards: leaf, grass, fern (512, RGBA)
Run:  blender -b --python b1_materials.py -- --root <repo> [--no-save-stats]
"""
import bpy, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import tls_lib as L
import tls_tex as T

OPTS = L.parse_args()
ROOT = OPTS.get("root", "/home/z/my-project/work/lastsin-repo")
TEXDIR = os.path.join(ROOT, "02_Art", "textures", "materials")
NATDIR = os.path.join(ROOT, "02_Art", "textures", "nature")
DBGDIR = os.path.join(ROOT, "02_Art", "textures", "debug")
STATS = os.path.join(ROOT, "02_Art", "exports", "stats", "materials_stats.json")
RES = 1024

t0 = time.time()
results = []

def save_set(tag, rgb, nrm, orm, res=RES):
    """Save BaseColor/Normal/ORM PNGs; return dict of paths."""
    os.makedirs(os.path.join(TEXDIR, tag), exist_ok=True)
    p1 = os.path.join(TEXDIR, tag, f"tls_tex_{tag}_BaseColor.png")
    p2 = os.path.join(TEXDIR, tag, f"tls_tex_{tag}_Normal.png")
    p3 = os.path.join(TEXDIR, tag, f"tls_tex_{tag}_ORM.png")
    L.save_array_png(f"{tag}_BC", rgb, p1, colorspace='sRGB')
    L.save_array_png(f"{tag}_NM", nrm, p2, colorspace='Non-Color')
    L.save_array_png(f"{tag}_ORM", orm, p3, colorspace='Non-Color')
    return {"basecolor": p1, "normal": p2, "orm": p3}

def build_slab(name, w=1.0, d=0.5, h=0.12):
    """Test slab 1x0.5x0.12 m with box-projected UVs (0..1 per face)."""
    hx, hy, hz = w / 2, d / 2, h / 2
    v = [(-hx, -hy, 0), (hx, -hy, 0), (hx, hy, 0), (-hx, hy, 0),
         (-hx, -hy, h), (hx, -hy, h), (hx, hy, h), (-hx, hy, h)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5),
             (2, 3, 7, 6), (3, 0, 4, 7)]
    uv = [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0), (1, 0), (1, 1), (0, 1)]
    return L.new_mesh_obj(name, v, faces, uvs=uv, coll="TestSlabs")

def make_material_blend(mat_id, mat_name, texs, base_rgb, rough, metal,
                        out_blend, extra_mats=None):
    """Fresh scene with 1 test slab + PBR material wired to saved PNGs, packed."""
    L.reset_scene()
    L.setup_units(f"TLS_{mat_id}")
    m = L.new_mat(mat_name, base=tuple(base_rgb), rough=rough,
                  metallic=metal if metal > 0 else 0.0)
    bc = L.load_png(texs["basecolor"], f"{mat_name}_BC", 'sRGB')
    nm = L.load_png(texs["normal"], f"{mat_name}_NM", 'Non-Color')
    orm = L.load_png(texs["orm"], f"{mat_name}_ORM", 'Non-Color')
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    L.add_orm(m, orm, ao_strength=0.9)
    # rewire base color properly: ORM's AO multiplies the BC image
    # (add_orm chained AO over the default 0.5 grey; insert BC image under it)
    mul = None
    for l in nt.links:
        if l.to_socket == bsdf.inputs['Base Color'] and l.from_node.type == 'MIX_RGB':
            mul = l.from_node
            break
    if mul:
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = bc
        nt.links.new(tex.outputs['Color'], mul.inputs['Color1'])
    # normal map node
    nrm_node = nt.nodes.new('ShaderNodeNormalMap')
    nrm_node.inputs['Strength'].default_value = 1.0
    nm_tex = nt.nodes.new('ShaderNodeTexImage')
    nm_tex.image = nm
    nt.links.new(nm_tex.outputs['Color'], nrm_node.inputs['Color'])
    L.set_principled(bsdf, normal=None)
    nt.links.new(nrm_node.outputs['Normal'], bsdf.inputs['Normal'])
    slab = build_slab(f"Slab_{mat_name}")
    slab.data.materials.append(m)
    for extra in (extra_mats or []):
        slab.data.materials.append(extra)
    try:
        bpy.ops.file.pack_all()
    except Exception as e:
        print("pack warning:", e)
    L.write_json(out_blend.replace(".blend", "_meta.json"),
                 {"asset": mat_id, "material": mat_name,
                  "textures": texs, "slab": slab.name})
    bpy.ops.wm.save_as_mainfile(filepath=out_blend, compress=True)
    return os.path.getsize(out_blend)

# ---------------------------------------------------------------- 1) TEX-001
print("[M4B1] TLS-TEX-001 UV checker ...")
os.makedirs(DBGDIR, exist_ok=True)
p_checker = os.path.join(DBGDIR, "tls_tex_001_uv_checker.png")
L.save_array_png("tls_tex_001_uv_checker", T.uv_checker(1024), p_checker, 'sRGB')
results.append({"asset": "TLS-TEX-001", "file": p_checker,
                "bytes": os.path.getsize(p_checker), "res": 1024})

# ---------------------------------------------------------------- 2) MAT-001 slate
print("[M4B1] TLS-MAT-001 slate ...")
rgb, nrm, orm = T.gen_slate(RES)
texs = save_set("slate", rgb, nrm, orm)
sz = make_material_blend("TLS-MAT-001", "TLS_Mat_Slate_Wall", texs,
                         T.SLT, 0.7, 0.0,
                         os.path.join(ROOT, "02_Art/blender/source/materials/tls_mat_001_slate.blend"))
results.append({"asset": "TLS-MAT-001", "textures": texs, "blend_bytes": sz})

# ---------------------------------------------------------------- 3) MAT-002 oak
print("[M4B1] TLS-MAT-002 oak ...")
rgb, nrm, orm = T.gen_oak(RES)
texs = save_set("oak", rgb, nrm, orm)
sz = make_material_blend("TLS-MAT-002", "TLS_Mat_Oak_Plank", texs,
                         T.BRF, 0.55, 0.0,
                         os.path.join(ROOT, "02_Art/blender/source/materials/tls_mat_002_oak.blend"))
results.append({"asset": "TLS-MAT-002", "textures": texs, "blend_bytes": sz})

# ---------------------------------------------------------------- 4) MAT-003 wool
print("[M4B1] TLS-MAT-003 wool ...")
rgb, nrm, orm = T.gen_wool(RES)
texs = save_set("wool", rgb, nrm, orm)
sz = make_material_blend("TLS-MAT-003", "TLS_Mat_Wool_Work", texs,
                         (0.32, 0.30, 0.27), 0.85, 0.0,
                         os.path.join(ROOT, "02_Art/blender/source/materials/tls_mat_003_wool.blend"))
results.append({"asset": "TLS-MAT-003", "textures": texs, "blend_bytes": sz})

# ---------------------------------------------------------------- 5) MAT-004 brass
print("[M4B1] TLS-MAT-004 brass ...")
rgb, nrm, orm = T.gen_brass(RES)
texs = save_set("brass", rgb, nrm, orm)
sz = make_material_blend("TLS-MAT-004", "TLS_Mat_Brass_Aged", texs,
                         (0.83, 0.66, 0.33), 0.35, 1.0,
                         os.path.join(ROOT, "02_Art/blender/source/materials/tls_mat_004_brass.blend"))
results.append({"asset": "TLS-MAT-004", "textures": texs, "blend_bytes": sz})

# ---------------------------------------------------------------- 6) MAT-005 moor terrain set
print("[M4B1] TLS-MAT-005 moor terrain (peat/heather/bark/leather-earth) ...")
moor = {}
rgb, nrm, orm = T.gen_peat(RES);     moor["peat"] = save_set("moor_peat", rgb, nrm, orm)
rgb, nrm, orm = T.gen_heather(RES);  moor["heather"] = save_set("moor_heather", rgb, nrm, orm)
rgb, nrm, orm = T.gen_bark(RES);     moor["bark"] = save_set("bark", rgb, nrm, orm)
rgb, nrm, orm = T.gen_leather(RES, col_in=(0.24, 0.22, 0.16))
moor["mud"] = save_set("moor_mud", rgb, nrm, orm)
L.reset_scene(); L.setup_units("TLS_MAT_005")
mats = {}
specs = [("TLS_Mat_Moor_Peat", "peat", (0.21, 0.18, 0.14)),
         ("TLS_Mat_Moor_Heather", "heather", (0.30, 0.24, 0.27)),
         ("TLS_Mat_Bark_Oak", "bark", (0.30, 0.27, 0.23)),
         ("TLS_Mat_Mud_Wet", "mud", (0.24, 0.22, 0.16))]
for nm_, key, base in specs:
    m = L.new_mat(nm_, base=base, rough=0.8)
    orm_img = L.load_png(moor[key]["orm"], f"{nm_}_ORM", 'Non-Color')
    bc_img = L.load_png(moor[key]["basecolor"], f"{nm_}_BC", 'sRGB')
    nm_img = L.load_png(moor[key]["normal"], f"{nm_}_NM", 'Non-Color')
    L.add_orm(m, orm_img, ao_strength=0.9)
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    for l in list(nt.links):
        if l.to_socket == bsdf.inputs['Base Color'] and l.from_node.type == 'MIX_RGB':
            tex = nt.nodes.new('ShaderNodeTexImage')
            tex.image = bc_img
            nt.links.new(tex.outputs['Color'], l.from_node.inputs['Color1'])
    nrm_node = nt.nodes.new('ShaderNodeNormalMap')
    nm_node2 = nt.nodes.new('ShaderNodeTexImage')
    nm_node2.image = nm_img
    nt.links.new(nm_node2.outputs['Color'], nrm_node.inputs['Color'])
    nt.links.new(nrm_node.outputs['Normal'], bsdf.inputs['Normal'])
    mats[nm_] = m
# 4 slabs in a row for inspection
objs = []
for i, (nm_, _k, _b) in enumerate(specs):
    s = build_slab(f"Slab_{nm_}")
    s.location = (0, i * 0.7, 0)
    # bake location into verts for consistent audit
    me = s.data
    for v in me.vertices:
        v.co.y += i * 0.7
    s.location = (0, 0, 0)
    me.materials.append(mats[nm_])
    objs.append(s)
try:
    bpy.ops.file.pack_all()
except Exception as e:
    print("pack warning:", e)
out5 = os.path.join(ROOT, "02_Art/blender/source/materials/tls_mat_005_moor_terrain.blend")
bpy.ops.wm.save_as_mainfile(filepath=out5, compress=True)
results.append({"asset": "TLS-MAT-005", "textures": moor,
                "blend_bytes": os.path.getsize(out5), "layers": list(mats.keys())})

# ---------------------------------------------------------------- 7) support sets (no registry row - sub-assets)
print("[M4B1] support sets: stone_wall / slate_roof / iron / paper / thatch / wax ...")
support = {}
for tag, fn in [("stone_wall", T.gen_stone_wall), ("slate_roof", T.gen_slate_roof),
                ("iron", T.gen_iron), ("paper", T.gen_paper),
                ("thatch", T.gen_thatch), ("wax", T.gen_wax)]:
    rgb, nrm, orm = fn(RES if tag not in ("wax",) else 512)
    support[tag] = save_set(tag, rgb, nrm, orm)
results.append({"support": support})

# ---------------------------------------------------------------- 8) alpha cards for nature kit
print("[M4B1] alpha cards: leaf / grass / fern ...")
cards = {}
for tag, fn in [("leaf", T.gen_leaf_card), ("grass", T.gen_grass_card),
                ("fern", T.gen_fern_card)]:
    rgba, alpha = fn(512)
    p = os.path.join(NATDIR, f"tls_tex_card_{tag}.png")
    L.save_array_png(f"card_{tag}", rgba, p, 'sRGB')
    cards[tag] = p
results.append({"cards": cards})

# ---------------------------------------------------------------- summary
L.write_json(STATS, {"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
                     "blender": bpy.app.version_string,
                     "seconds": round(time.time() - t0, 1),
                     "results": results})
print(f"[M4B1] materials done in {time.time()-t0:.0f}s -> {STATS}")
