#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M3.4 - Edmund Vale full character build (Blender 5.0.1 headless).
Run:  blender -b --python edmund_build.py -- --out <blend path> --texdir <dir> --stats <json>
Produces the real, openable .blend: body + face + eyes + hands + 1847 outfit +
generated PBR textures + hair/stubble/brow particle systems. Original repo
assets are never touched.
"""
import bpy, sys, os, math, json, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from edmund_lib import (reset_scene, setup_units, link_obj, new_mesh_obj,
                        join_objects, obj_stats, mesh_checks, write_json,
                        smooth_all)
import edmund_materials as MATS
import edmund_body as BODY
import edmund_outfit as OUTFIT
import edmund_hair as HAIR
from edmund_body import HEAD_C, HEAD_R, EYE_C
from mathutils import Vector

def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts = {}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--"):
            opts[argv[i][2:]] = argv[i + 1]
            i += 2
        else:
            i += 1
    return opts

def vgroup_from_mask(obj, name, fn):
    vg = obj.vertex_groups.new(name=name)
    n = 0
    for v in obj.data.vertices:
        if fn(v.co):
            vg.add([v.index], 1.0, 'REPLACE')
            n += 1
    return n

def add_hair_system(obj, name, dens_vg, len_vg, length, count, child_r, child_v,
                    mat, step=4, randomness=0.35, clump=0.25, curl=0.0,
                    noise=0.02, root_radius=None):
    mod = obj.modifiers.new(name, 'PARTICLE_SYSTEM')
    psys = obj.particle_systems[-1]
    st = psys.settings
    st.type = 'HAIR'
    st.count = count
    st.hair_length = length
    st.hair_step = step
    st.use_advanced_hair = True
    st.child_type = 'INTERPOLATED'
    st.child_percent = child_v
    st.rendered_child_count = child_r
    st.child_radius = 0.02
    st.child_roundness = 0.6
    st.clump_factor = clump
    st.roughness_endpoint = 0.0
    st.roughness_end_shape = 0.0
    st.length_random = randomness
    # material slot for hair
    idx = None
    for i, slot in enumerate(obj.material_slots):
        if slot.material and slot.material.name == mat.name:
            idx = i
            break
    if idx is None:
        obj.data.materials.append(mat)
        idx = len(obj.material_slots) - 1
    st.material = idx + 1
    try:
        st.kink = 'NOISE'
        st.kink_amplitude = noise
        st.kink_frequency = 2.0
    except Exception:
        pass
    if curl:
        try:
            st.kink = 'CURL'
            st.kink_amplitude = curl
            st.kink_frequency = 1.2
        except Exception:
            pass
    return psys

def main():
    t0 = time.time()
    opts = parse_args()
    out_blend = opts.get("out", "/home/z/my-project/m34_out/edmund_test.blend")
    tex_dir = opts.get("texdir", "/home/z/my-project/m34_out/textures")
    stats_path = opts.get("stats", "/home/z/my-project/m34_out/build_stats.json")
    fast = "--fast" in sys.argv

    reset_scene()
    setup_units()
    sc = bpy.context.scene
    sc.name = "TLS_Edmund"

    print("[M3.4] generating textures ...")
    texs = MATS.build_textures(tex_dir)
    mats = MATS.build_materials(texs)

    print("[M3.4] building body anatomy ...")
    body = BODY.build_body(mats)
    eyes = BODY.build_eyes(mats)
    hands = BODY.build_hands(mats)

    print("[M3.4] building 1847 outfit ...")
    outfit = OUTFIT.build_outfit(mats)

    print("[M3.4] hair / stubble / brow vertex groups ...")
    hc = Vector(HEAD_C)
    def scalp_mask(co):
        d = Vector(co) - hc
        if d.length > 0.135:
            return False
        if d.z < 0.005:
            return False
        # exclude face cone: front & low & central
        if d.y < -0.030 and abs(d.x) < 0.052 and d.z < 0.055:
            return False
        return True
    def hairlen_mask(co):
        d = Vector(co) - hc
        return d.z > 0.045 and d.length < 0.13   # crown longer
    def brow_mask(co):
        d = Vector(co) - hc
        if not (-0.095 < d.y < -0.040):
            return False
        if not (0.018 < abs(d.x) < 0.058):
            return False
        if not (0.028 < d.z < 0.060):
            return False
        return True
    def beard_mask(co):
        d = Vector(co) - hc
        if d.length > 0.135:
            return False
        if d.y > -0.020:
            return False
        if d.z > -0.005 or d.z < -0.105:
            return False
        # skip mouth interior: keep lips (short stubble ok on lips region edges)
        return True

    n_scalp = vgroup_from_mask(body, "scalp", scalp_mask)
    n_hlen = vgroup_from_mask(body, "hair_long", hairlen_mask)
    n_brow = vgroup_from_mask(body, "brow", brow_mask)
    n_beard = vgroup_from_mask(body, "beard", beard_mask)
    print(f"[M3.4] groups: scalp={n_scalp} hair_long={n_hlen} brow={n_brow} beard={n_beard}")

    print("[M3.4] procedural hair (cards) / stubble / brows ...")
    hair = HAIR.build_hair(body, mats, fast=fast)
    stub = HAIR.build_stubble(body, mats, fast=fast)
    brows = HAIR.build_brows(body, mats)
    print(f"[M3.4] hair objects: {hair.name} {obj_stats(hair)['tris']} tris, "
          f"{stub.name} {obj_stats(stub)['tris']} tris, {brows.name} {obj_stats(brows)['tris']} tris")

    # scene stats
    print("[M3.4] collecting stats ...")
    stats = {"blender": bpy.app.version_string, "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
             "objects": [], "render_extras": [], "totals": {}}
    tot_v = tot_t = 0
    for o in [body] + eyes + hands + list(outfit.values()):
        s = obj_stats(o)
        s.update(mesh_checks(o))
        s["materials"] = [sl.material.name if sl.material else None
                          for sl in o.material_slots]
        s["uvs"] = [uv.name for uv in o.data.uv_layers]
        s["modifiers"] = [(m.type, m.name) for m in o.modifiers]
        stats["objects"].append(s)
        tot_v += s["verts"]; tot_t += s["tris"]
    # M3.5: hair/stubble/brows accounted separately (render/game-optional)
    for o in [hair, stub, brows]:
        s = obj_stats(o)
        s.update(mesh_checks(o))
        s["materials"] = [sl.material.name if sl.material else None
                          for sl in o.material_slots]
        stats["render_extras"].append(s)
    stats["totals"] = {"objects": len(stats["objects"]), "verts": tot_v, "tris": tot_t,
                       "materials": len([m for m in bpy.data.materials
                                         if not m.name.startswith("TLS_Studio")
                                         and not m.name.startswith("TLS_Cine")]),
                       "texture_files": texs, "build_seconds": round(time.time() - t0, 1)}

    # dimension check
    dg = bpy.context.evaluated_depsgraph_get()
    mins = [1e9, 1e9, 1e9]; maxs = [-1e9, -1e9, -1e9]
    for o in [body] + hands + list(outfit.values()):
        eo = o.evaluated_get(dg)
        me = eo.to_mesh()
        for v in me.vertices:
            w = eo.matrix_world @ v.co
            for k in range(3):
                mins[k] = min(mins[k], w[k]); maxs[k] = max(maxs[k], w[k])
        eo.to_mesh_clear()
    stats["bounds_min"] = [round(x, 4) for x in mins]
    stats["bounds_max"] = [round(x, 4) for x in maxs]
    stats["height_m"] = round(maxs[2] - mins[2], 4)

    os.makedirs(os.path.dirname(out_blend), exist_ok=True)
    try:
        bpy.ops.file.pack_all()
    except Exception as e:
        print("pack_all warning:", e)
    bpy.ops.wm.save_as_mainfile(filepath=out_blend, compress=True)
    size_mb = os.path.getsize(out_blend) / 1e6
    stats["blend_path"] = out_blend
    stats["blend_size_mb"] = round(size_mb, 2)
    write_json(stats_path, stats)
    print(f"[M3.4] SAVED {out_blend} ({size_mb:.1f} MB) in {time.time()-t0:.0f}s")
    print(f"[M3.4] TOTALS: verts={tot_v} tris={tot_t} height={stats['height_m']}m")

main()
