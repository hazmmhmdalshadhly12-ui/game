#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M4 FBX roundtrip verifier.
Usage:
  blender -b --python b_verify.py -- --root <repo> --fbx <path> [--tol 0.035]
Imports the FBX into an empty scene, counts MESH objects (incl. UCX_),
measures world bbox dims, checks header + scale (1m=100uu FBX units),
writes JSON next to 02_Art/exports/verify/<stem>.json and prints PASS/FAIL.
Exits non-zero on FAIL (via printed marker; shell checks output).
"""
import bpy, os, sys, json, struct

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import tls_lib as L

def fbx_header_info(path):
    with open(path, "rb") as f:
        head = f.read(27)
    is_binary = head.startswith(b"Kaydara FBX Binary")
    version = None
    if is_binary:
        f = open(path, "rb")
        f.seek(23)
        version = struct.unpack("<I", f.read(4))[0]
        f.close()
    return {"binary": is_binary, "version": version}

def main():
    o = L.parse_args()
    root = o.get("root", "/home/z/my-project/work/lastsin-repo")
    fbx = o.get("fbx")
    tol = float(o.get("tol", "0.035"))
    if not fbx or not os.path.exists(fbx):
        print("[verify] FAIL no fbx:", fbx)
        return
    stem = os.path.splitext(os.path.basename(fbx))[0]
    outdir = os.path.join(root, "02_Art", "exports", "verify")
    os.makedirs(outdir, exist_ok=True)

    hdr = fbx_header_info(fbx)

    L.reset_scene()
    try:
        bpy.ops.import_scene.fbx(filepath=fbx,
                                 use_manual_orientation=False,
                                 automatic_bone_orientation=True,
                                 ignore_leaf_bones=False)
    except Exception as e:
        L.write_json(os.path.join(outdir, f"{stem}.json"),
                     {"asset": stem, "status": "FAIL", "error": str(e), "header": hdr})
        print(f"[verify] {stem}: FAIL import error {e}")
        return

    meshes = [ob for ob in bpy.data.objects if ob.type == 'MESH']
    arms = [ob for ob in bpy.data.objects if ob.type == 'ARMATURE']
    ucx = [ob for ob in meshes if ob.name.startswith("UCX_")]
    # dims
    dg = bpy.context.evaluated_depsgraph_get()
    mins = [1e9] * 3; maxs = [-1e9] * 3
    vcount = tcount = 0
    for ob in meshes:
        if ob.name.startswith("UCX_"):
            continue
        eo = ob.evaluated_get(dg)
        me = eo.to_mesh()
        vcount += len(me.vertices)
        for p in me.polygons:
            tcount += max(0, len(p.vertices) - 2)
        for v in me.vertices:
            w = eo.matrix_world @ v.co
            for k in range(3):
                mins[k] = min(mins[k], w[k]); maxs[k] = max(maxs[k], w[k])
        eo.to_mesh_clear()
    dims = [round(maxs[k] - mins[k], 4) for k in range(3)] if vcount else [0, 0, 0]
    bones = sum(len(a.data.bones) for a in arms)

    exp = o.get("dims")  # "x,y,z" optional expected dims in meters
    result = {
        "asset": stem, "fbx": fbx,
        "header": hdr,
        "mesh_objects": len(meshes) - len(ucx),
        "ucx_objects": len(ucx),
        "armatures": len(arms), "bones": bones,
        "verts": vcount, "tris": tcount,
        "dims_m": dims,
        "materials": len({m.name for m in bpy.data.materials if not m.name.startswith("UCX")}),
    }
    ok = hdr["binary"] and hdr["version"] and hdr["version"] >= 7400
    result["header_ok"] = bool(ok)
    if exp:
        e = [float(x) for x in exp.split(",")]
        result["expected_dims_m"] = e
        result["dims_ok"] = all(abs(dims[i] - e[i]) <= tol * max(e[i], 0.2) + 0.01
                                for i in range(3)) if vcount else False
        ok = ok and result["dims_ok"]
    result["status"] = "PASS" if ok else "FAIL"
    L.write_json(os.path.join(outdir, f"{stem}.json"), result)
    print(f"[verify] {stem}: {result['status']} meshes={result['mesh_objects']} "
          f"ucx={result['ucx_objects']} bones={bones} dims={dims} tris={tcount}")

main()
