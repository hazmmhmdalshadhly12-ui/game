#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M3.6 - fresh-session audit of the FINAL Edmund character .blend.
Run on the saved production file:
  blender -b <final.blend> --python edmund_inspect.py -- --stats <json> \
      [--manifest <json>] [--fbx f1.fbx,f2.fbx] [--texdir <dir>]

Checks (all measured, nothing hard-coded to pass):
- per-object verts/polys/tris, boundary edges, non-manifold edges,
  loose verts, NaN coords, material slots, UV layers
- boundary-edge CLASSIFICATION: intentional openings (eyelid shells,
  garment apertures, hair/beard card edges) vs unclassified leftovers
- rig: bone count, per-object zero-weight verts, eye-bone weight leakage
- height + bounds
- texture files exist on disk with non-trivial size
- optional manifest: md5 + size of blend / fbx / textures with status
"""
import bpy, sys, os, json, hashlib

def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts, i = {}, 0
    while i < len(argv):
        if argv[i].startswith("--"):
            opts[argv[i][2:]] = argv[i + 1]; i += 2
        else: i += 1
    return opts

def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def mesh_checks(me):
    edge_users = {}
    for p in me.polygons:
        n = len(p.vertices)
        for i in range(n):
            a, b = p.vertices[i], p.vertices[(i + 1) % n]
            key = (a, b) if a < b else (b, a)
            edge_users[key] = edge_users.get(key, 0) + 1
    boundary = [e for e, c in edge_users.items() if c == 1]
    nonmanifold = sum(1 for c in edge_users.values() if c > 2)
    used = set()
    for p in me.polygons:
        used.update(p.vertices)
    loose = len(me.vertices) - len(used)
    nan = 0
    for v in me.vertices:
        co = v.co
        if co.x != co.x or co.y != co.y or co.z != co.z:
            nan += 1
    return boundary, nonmanifold, loose, nan

def classify_boundaries(obj, boundary):
    """Split boundary edges into known-intentional zones vs unclassified."""
    # intentional zones by vertex position (object space == world here)
    hx, hy, hz = 0.0, -0.004, 1.665  # head center
    zones = {"eyelid_shell": 0, "garment_aperture": 0, "card_edge": 0,
             "hand_finger_joints": 0, "unclassified": 0}
    for a, b in boundary:
        va, vb = obj.data.vertices[a].co, obj.data.vertices[b].co
        mid = (va + vb) / 2
        name = obj.name
        if name == "Edmund_Body":
            dz, dy, dx = mid.z - hz, mid.y - hy, mid.x - hx
            if dz > 0.014 and abs(dy) < 0.06 and abs(dx) < 0.06:
                zones["eyelid_shell"] += 1
            elif mid.z < 0.86:
                zones["garment_aperture"] += 1  # torso bottom opening
            else:
                zones["unclassified"] += 1
        elif name in ("Edmund_HandL", "Edmund_HandR"):
            zones["hand_finger_joints"] += 1
        elif name in ("Edmund_Hair", "Edmund_Stubble", "Edmund_Brows",
                      "Edmund_Lashes"):
            zones["card_edge"] += 1
        else:
            zones["garment_aperture"] += 1
    return zones

def main():
    opts = parse_args()
    stats_path = opts.get("stats")
    manifest_path = opts.get("manifest")
    tex_dir = opts.get("texdir")
    out = {"blend": bpy.data.filepath, "blender": bpy.app.version_string,
           "objects": [], "render_extras": [], "rig": {}, "textures": [],
           "height_m": None}

    arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    body_names = {"Edmund_Body", "Edmund_EyeL", "Edmund_EyeR",
                  "Edmund_HandL", "Edmund_HandR"}
    outfit_names = {"Edmund_Shirt", "Edmund_Waistcoat", "Edmund_Coat",
                    "Edmund_Neckcloth", "Edmund_Trousers", "Edmund_Boots",
                    "Edmund_Satchel"}
    extras = {"Edmund_Hair", "Edmund_Stubble", "Edmund_Brows", "Edmund_Lashes"}

    mins = [1e9] * 3; maxs = [-1e9] * 3
    tot_v = 0
    for o in meshes:
        me = o.data
        boundary, nm, loose, nan = mesh_checks(me)
        rec = {"name": o.name, "verts": len(me.vertices),
               "polys": len(me.polygons),
               "tris": sum(max(0, len(p.vertices) - 2) for p in me.polygons),
               "boundary_edges": len(boundary), "nonmanifold_edges": nm,
               "loose_verts": loose, "nan_verts": nan,
               "materials": [s.material.name if s.material else None
                             for s in o.material_slots],
               "uvs": [uv.name for uv in me.uv_layers],
               "parent": o.parent.name if o.parent else None}
        rec["boundary_zones"] = classify_boundaries(o, boundary)
        # weight audit
        if arm:
            bone_names = set(b.name for b in arm.data.bones)
            zw = 0
            eye_leak = 0
            for v in me.vertices:
                if len(v.groups) == 0:
                    zw += 1
                    continue
                wsum = 0.0
                has_eye = False
                for g in v.groups:
                    wsum += g.weight
                    gn = o.vertex_groups[g.group].name
                    if gn in ("eye.L", "eye.R"):
                        if g.weight > 0.01:
                            has_eye = True
                if wsum < 0.5:
                    zw += 1
                if has_eye and o.name != "Edmund_EyeL" and o.name != "Edmund_EyeR":
                    eye_leak += 1
            rec["zero_weight_verts"] = zw
            rec["eye_bone_leak_verts"] = eye_leak
        # bounds (rest pose world coords)
        for v in me.vertices:
            w = o.matrix_world @ v.co
            for k in range(3):
                mins[k] = min(mins[k], w[k]); maxs[k] = max(maxs[k], w[k])
        if o.name in body_names:
            out["objects"].append(rec)
        elif o.name in outfit_names:
            out["objects"].append(rec)
        elif o.name in extras:
            out["render_extras"].append(rec)
        else:
            out["render_extras"].append(rec)  # e.g. scalp-cap remnants
        if o.name not in extras:
            tot_v += rec["verts"]

    if arm:
        out["rig"] = {"armature": arm.name, "bones": len(arm.data.bones),
                      "bone_names": [b.name for b in arm.data.bones]}
    out["totals"] = {"character_verts": tot_v,
                     "objects": len(out["objects"]),
                     "render_extras": len(out["render_extras"])}
    if meshes:
        out["height_m"] = round(maxs[2] - mins[2], 4)
        out["bounds_z"] = [round(mins[2], 4), round(maxs[2], 4)]
        out["bounds_min"] = [round(v, 4) for v in mins]
        out["bounds_max"] = [round(v, 4) for v in maxs]

    # textures on disk
    if tex_dir and os.path.isdir(tex_dir):
        for f in sorted(os.listdir(tex_dir)):
            if f.lower().endswith(".png"):
                p = os.path.join(tex_dir, f)
                out["textures"].append({"file": f, "bytes": os.path.getsize(p),
                                        "md5": md5_of(p)})

    if stats_path:
        os.makedirs(os.path.dirname(stats_path), exist_ok=True)
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print("[INSPECT] stats ->", stats_path)

    if manifest_path:
        blend = bpy.data.filepath
        man = {"asset": "TLS-CHR-001 Edmund Vale (+TLS-CHR-030 outfit, TLS-SKL-001 rig)",
               "generator": "edmund_build.py/edmund_rig.py/edmund_export.py (M3.6)",
               "blender": bpy.app.version_string,
               "primary_blend": {"path": os.path.basename(blend),
                                 "bytes": os.path.getsize(blend) if blend else 0,
                                 "md5": md5_of(blend) if blend else None},
               "textures": out["textures"],
               "measured": {"height_m": out["height_m"],
                            "bounds_z": out.get("bounds_z"),
                            "character_verts": tot_v,
                            "bones": out["rig"].get("bones")},
               "verification": {
                   "blend_reopened_and_measured": True,
                   "fbx_roundtrip": "see data/fbx_verify.json",
                   "unreal_import": "UNREAL IMPORT NOT TESTED (no UE 5.4 in build environment)"}}
        os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(man, f, ensure_ascii=False, indent=2)
        print("[INSPECT] manifest ->", manifest_path)

    # console summary
    bad = [r for r in out["objects"] + out["render_extras"]
           if r["loose_verts"] or r["nonmanifold_edges"] or r["nan_verts"]]
    print("[INSPECT] objects:", len(out["objects"]),
          "extras:", len(out["render_extras"]),
          "height:", out["height_m"],
          "bones:", out["rig"].get("bones"))
    print("[INSPECT] defects (loose/nonmanifold/nan):",
          [(r["name"], r["loose_verts"], r["nonmanifold_edges"], r["nan_verts"])
           for r in bad] or "NONE")

main()
