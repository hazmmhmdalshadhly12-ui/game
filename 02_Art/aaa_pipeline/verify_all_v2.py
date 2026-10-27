#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE LAST SIN - independent verification of all v2 exports.
1) GLB files: loaded with trimesh (independent of Blender) -> mesh stats.
2) Blend/FBX: re-imported in Blender -> object counts, tris, materials, UVs.
Writes 02_Art/exports/verify/v2_verification.json + prints summary.
"""
import bpy, os, sys, json, glob
import numpy as np

REPO = "/home/z/my-project/repo"
OUT = f"{REPO}/02_Art/exports/verify/v2_verification.json"
os.makedirs(os.path.dirname(OUT), exist_ok=True)

results = {"trimesh_glb": [], "blender_reimport": []}

# ---------- 1. trimesh GLB check (external tool)
try:
    import trimesh
    for p in sorted(glob.glob(f"{REPO}/02_Art/exports/glb/*.glb")):
        if "_v2" not in os.path.basename(p) and "npc" not in p.lower() and not any(
                k in os.path.basename(p) for k in ("003", "004", "006", "007", "030")):
            continue
        try:
            sc = trimesh.load(p, force='scene')
            tris = sum(int(len(g.faces)) for g in sc.geometry.values())
            verts = sum(int(len(g.vertices)) for g in sc.geometry.values())
            ext = sc.extents.tolist() if hasattr(sc, "extents") else None
            results["trimesh_glb"].append({
                "file": os.path.basename(p), "geometry_nodes": len(sc.geometry),
                "tris": tris, "verts": verts, "extents_m": [round(x, 3) for x in ext] if ext else None,
                "status": "PASS" if tris > 0 else "FAIL_EMPTY"})
        except Exception as e:
            results["trimesh_glb"].append({"file": os.path.basename(p), "status": "FAIL", "error": str(e)})
except ImportError:
    results["trimesh_glb"].append({"status": "trimesh unavailable"})

# ---------- 2. Blender re-import (blend + fbx)
def audit_current(label, path):
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    arm = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes)
    nv = sum(len(o.data.vertices) for o in meshes)
    uvs = all(len(o.data.uv_layers) > 0 for o in meshes) if meshes else False
    mats = sum(len(set(m.name for m in o.data.materials if m)) for o in meshes)
    r = {"label": label, "file": os.path.basename(path), "meshes": len(meshes),
         "verts": nv, "tris": tris, "armatures": len(arm),
         "bones": sum(len(a.data.bones) for a in arm),
         "all_meshes_have_uv": uvs, "material_slots": mats,
         "status": "PASS" if tris > 0 else "FAIL_EMPTY"}
    return r

for p in sorted(glob.glob(f"{REPO}/02_Art/blender/source/chr/*_v2*.blend")) + \
         sorted(glob.glob(f"{REPO}/02_Art/blender/source/chr/tls_chr_0*.blend")):
    if "_v002.blend" in p or "_game_v002" in p or any(k in p for k in ("_003_", "_004_", "_006_", "_007_")):
        bpy.ops.wm.open_mainfile(filepath=p)
        results["blender_reimport"].append(audit_current("blend", p))

for p in sorted(glob.glob(f"{REPO}/02_Art/exports/fbx/*_v002.fbx")) + \
         sorted(glob.glob(f"{REPO}/02_Art/exports/fbx/tls_chr_00*.fbx")):
    bpy.ops.wm.read_homefile(use_empty=True)
    try:
        bpy.ops.import_scene.fbx(filepath=p)
        results["blender_reimport"].append(audit_current("fbx_reimport", p))
    except Exception as e:
        results["blender_reimport"].append({"file": os.path.basename(p), "status": "FAIL", "error": str(e)})

for p in sorted(glob.glob(f"{REPO}/02_Art/blender/source/env/*_v2*.blend")) + \
         [f"{REPO}/02_Art/blender/source/env/tls_env_020_church.blend",
          f"{REPO}/02_Art/blender/source/prp/tls_prp_030_investigation_set_v2.blend"]:
    if os.path.exists(p):
        bpy.ops.wm.open_mainfile(filepath=p)
        results["blender_reimport"].append(audit_current("blend", p))

with open(OUT, "w") as f:
    json.dump(results, f, indent=1)

npass = sum(1 for r in results["trimesh_glb"] + results["blender_reimport"] if r.get("status") == "PASS")
nfail = sum(1 for r in results["trimesh_glb"] + results["blender_reimport"] if r.get("status", "").startswith("FAIL"))
print(f"VERIFY: PASS={npass} FAIL={nfail}")
for r in results["trimesh_glb"]:
    print("  GLB", r.get("file"), r.get("status"), r.get("tris"))
for r in results["blender_reimport"]:
    print("  ", r.get("label"), r.get("file"), r.get("status"), "tris=", r.get("tris"), "bones=", r.get("bones"))
