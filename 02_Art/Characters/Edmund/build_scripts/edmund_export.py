#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M3.4 - FBX export per docs/TECHNICAL_PIPELINE.md contract
(axis_forward='-Y', axis_up='Z', FBX_SCALE_UNITS, 1m=100uu) + validation.
Mode A (export):  blender -b <blend> --python edmund_export.py -- --mode export --dir <fbx dir>
Mode B (verify):  blender -b --python edmund_export.py -- --mode verify --files a.fbx,b.fbx --stats <json>
"""
import bpy, sys, os, json

HERE = os.path.dirname(os.path.abspath(__file__))

def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts, i = {}, 0
    while i < len(argv):
        if argv[i].startswith("--"):
            opts[argv[i][2:]] = argv[i + 1]; i += 2
        else: i += 1
    return opts

def export(outdir):
    os.makedirs(outdir, exist_ok=True)
    arm = bpy.data.objects.get("TLS_Rig_Human_Edmund")
    def do_export(obj_names, path):
        bpy.ops.object.select_all(action='DESELECT')
        n = 0
        for nm in obj_names:
            o = bpy.data.objects.get(nm)
            if o:
                o.select_set(True); n += 1
        if arm:
            arm.select_set(True)
        bpy.context.view_layer.objects.active = arm
        bpy.ops.export_scene.fbx(
            filepath=path, use_selection=True,
            axis_forward='-Y', axis_up='Z',
            apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
            global_scale=1.0,
            object_types={'ARMATURE', 'MESH'},
            use_mesh_modifiers=False,
            add_leaf_bones=False,
            bake_anim=False,
            path_mode='AUTO',
            # M3.5: TECHNICAL_PIPELINE.md pins mesh_smooth_type='OFF'
            # (normals baked as stored); M3.4 silently used 'FACE'.
            mesh_smooth_type='OFF')
        sz = os.path.getsize(path) / 1e6
        print(f"[FBX] exported {path} ({sz:.1f} MB) objects={n}")
        return sz

    body_names = ["Edmund_Body", "Edmund_HandL", "Edmund_HandR",
                  "Edmund_EyeL", "Edmund_EyeR"]
    outfit_names = ["Edmund_Shirt", "Edmund_Waistcoat", "Edmund_Coat",
                    "Edmund_Neckcloth", "Edmund_Trousers", "Edmund_Boots",
                    "Edmund_Satchel"]
    p1 = os.path.join(outdir, "tls_chr_001_edmund_vale_v001.fbx")
    p2 = os.path.join(outdir, "tls_chr_030_edmund_outfit_v001.fbx")
    s1 = do_export(body_names, p1)
    s2 = do_export(outfit_names, p2)
    print("[FBX] export done")
    return {"body": {"path": p1, "mb": round(s1, 2)},
            "outfit": {"path": p2, "mb": round(s2, 2)}}

def outfit_blend(out_path):
    """M3.5: regenerate TLS-CHR-030 (.blend) from the current session:
    outfit meshes + armature only (character body/eyes/hands/hair removed)."""
    keep = {"Edmund_Shirt", "Edmund_Waistcoat", "Edmund_Coat",
            "Edmund_Neckcloth", "Edmund_Trousers", "Edmund_Boots",
            "Edmund_Satchel"}
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and o.name not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.images):
        for item in list(coll):
            if item.users == 0:
                coll.remove(item)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out_path, compress=True)
    print("[FBX] outfit blend saved", out_path,
          os.path.getsize(out_path) / 1e6, "MB")

def verify(files):
    out = []
    for f in files:
        bpy.ops.wm.read_homefile(use_empty=True)
        before = set(bpy.data.objects.keys())
        try:
            bpy.ops.import_scene.fbx(filepath=f)
        except Exception as e:
            out.append({"file": f, "import_ok": False, "error": str(e)})
            continue
        meshes = [o for o in bpy.data.objects if o.type == 'MESH']
        arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
        tot_v = sum(len(o.data.vertices) for o in meshes)
        tot_t = 0
        for o in meshes:
            for p in o.data.polygons:
                tot_t += max(0, len(p.vertices) - 2)
        # bounds
        mins = [1e9] * 3; maxs = [-1e9] * 3
        for o in meshes:
            for v in o.data.vertices:
                w = o.matrix_world @ v.co
                for k in range(3):
                    mins[k] = min(mins[k], w[k]); maxs[k] = max(maxs[k], w[k])
        height = maxs[2] - mins[2] if meshes else 0
        mats = set()
        for o in meshes:
            for sl in o.material_slots:
                if sl.material: mats.add(sl.material.name)
        rec = {"file": os.path.basename(f), "import_ok": True,
               "meshes": len(meshes), "armatures": len(arms),
               "bones": sum(len(a.data.bones) for a in arms),
               "verts": tot_v, "tris": tot_t,
               "materials": sorted(mats),
               "height_m": round(height, 3),
               "bounds_z": [round(mins[2], 3), round(maxs[2], 3)]}
        out.append(rec)
        print("[FBX verify]", rec)
    return out

def main():
    opts = parse_args()
    if opts.get("mode") == "export":
        r = export(opts.get("dir", "/home/z/my-project/m34_out/fbx"))
        with open(os.path.join(opts.get("dir", "/home/z/my-project/m34_out/fbx"),
                               "_export_log.json"), "w") as fj:
            json.dump(r, fj, indent=2)
    elif opts.get("mode") == "outfit_blend":
        outfit_blend(opts.get("out",
                     "/home/z/my-project/m34_out/tls_chr_030_edmund_outfit.blend"))
    else:
        files = opts.get("files", "").split(",")
        res = verify([f for f in files if f])
        sp = opts.get("stats")
        if sp:
            os.makedirs(os.path.dirname(sp), exist_ok=True)
            with open(sp, "w", encoding="utf-8") as fj:
                json.dump(res, fj, ensure_ascii=False, indent=2)

main()
