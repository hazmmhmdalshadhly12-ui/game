#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M3.4 - Edmund rig: 65-bone humanoid skeleton (per TLS-SKL-001 contract:
A-pose 15 deg, original rig, no store rigs), automatic skinning, deformation
tests with honest metrics. Run:
  blender -b <edmund.blend> --python edmund_rig.py -- --stats <json> --posejson <json>
"""
import bpy, sys, os, math, json
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from edmund_body import EYE_C, HEAD_C

def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts, i = {}, 0
    while i < len(argv):
        if argv[i].startswith("--"):
            opts[argv[i][2:]] = argv[i + 1]; i += 2
        else: i += 1
    return opts

# ------------------------------------------------- bone table
def bone_table():
    B = []
    def add(n, h, t, parent=None, connect=False):
        B.append({"name": n, "head": h, "tail": t, "parent": parent, "connect": connect})
    # spine chain
    add("root", (0, 0.0, 0.86), (0, 0.0, 0.92))
    add("pelvis", (0, 0.0, 0.90), (0, 0.0, 1.03), "root", True)
    add("spine01", (0, 0.0, 1.03), (0, 0.0, 1.13), "pelvis", True)
    add("spine02", (0, 0.0, 1.13), (0, 0.0, 1.23), "spine01", True)
    add("spine03", (0, 0.0, 1.23), (0, 0.0, 1.33), "spine02", True)
    add("chest", (0, 0.0, 1.33), (0, 0.0, 1.44), "spine03", True)
    add("neck", (0, 0.0, 1.44), (0, 0.0, 1.535), "chest", True)
    add("head", (0, 0.0, 1.535), (0, 0.0, 1.70), "neck", True)
    add("eye.L", (-EYE_C[0], EYE_C[1], EYE_C[2]), (-EYE_C[0], EYE_C[1] - 0.033, EYE_C[2]), "head")
    add("eye.R", (EYE_C[0], EYE_C[1], EYE_C[2]), (EYE_C[0], EYE_C[1] - 0.033, EYE_C[2]), "head")
    s = 1
    for suf in (".R", ".L"):
        sgn = 1 if suf == ".R" else -1
        p = f"clavicle{suf}"
        add(p, (0.014 * sgn, 0.002, 1.452), (0.16 * sgn, -0.006, 1.430), "chest")
        ua = f"upper_arm{suf}"
        add(ua, (0.176 * sgn, -0.006, 1.428), (0.255 * sgn, -0.010, 1.142), p)
        uat = f"upper_arm_twist{suf}"
        add(uat, (0.176 * sgn, -0.006, 1.428),
            (0.222 * sgn, -0.008, 1.320), ua)
        fa = f"forearm{suf}"
        add(fa, (0.255 * sgn, -0.010, 1.142), (0.320 * sgn, -0.062, 0.898), ua, True)
        fat = f"forearm_twist{suf}"
        add(fat, (0.255 * sgn, -0.010, 1.142),
            (0.295 * sgn, -0.040, 1.020), fa)
        hand = f"hand{suf}"
        add(hand, (0.320 * sgn, -0.062, 0.898), (0.352 * sgn, -0.088, 0.816), fa, True)
        # finger chains (approx knuckle positions along hand axis)
        import math as _m
        t = Vector((0.253 * sgn, -0.208, -0.943)).normalized()
        t = Vector((t.x, t.y, t.z))
        upx = Vector((1, 0, 0)) - Vector((1, 0, 0)).dot(t) * t; upx.normalize()
        t0 = Vector((0.320 * sgn, -0.062, 0.898))
        pc = t0 + t * 0.048
        pn = Vector((-sgn, 0, 0)); pn = (pn - pn.dot(t) * t).normalized()
        fingers = [(0.034, (0.030, 0.022, 0.016)), (0.012, (0.034, 0.026, 0.018)),
                   (-0.010, (0.031, 0.023, 0.017)), (-0.031, (0.024, 0.019, 0.015))]
        names = ["index", "middle", "ring", "pinky"]
        curl = 0.0
        for (lat, lens), fnm in zip(fingers, names):
            start = pc + t * 0.082 + upx * lat + pn * -0.002
            d = t.copy(); p0 = start.copy(); prev = None
            for seg in range(3):
                curl += _m.radians(14 if seg == 0 else 18)
                cs, sn = _m.cos(curl), _m.sin(curl)
                nd = d.normalized()
                axis = nd.cross(pn)
                if axis.length < 1e-5:
                    axis = upx
                axis.normalize()
                nd2 = nd * cs + axis.cross(nd) * sn + axis * (axis.dot(nd)) * (1 - cs)
                nd2.normalize()
                nxt = p0 + nd2 * lens[seg]
                add(f"{fnm}_{'123'[seg]}{suf}", tuple(p0), tuple(nxt),
                    hand if seg == 0 else f"{fnm}_{'123'[seg-1]}{suf}",
                    seg > 0)
                p0 = nxt; d = nd2
        # thumb
        tstart = pc + t * 0.030 + upx * (sgn * 0.040) + pn * -0.004
        tdir = (t * 0.55 + upx * (sgn * 0.75) + pn * 0.28).normalized()
        p0 = tstart.copy()
        for seg, L in enumerate((0.036, 0.030, 0.024)):
            nxt = p0 + tdir * L
            add(f"thumb_{'123'[seg]}{suf}", tuple(p0), tuple(nxt),
                hand if seg == 0 else f"thumb_{'123'[seg-1]}{suf}", seg > 0)
            p0 = nxt
            tdir = (tdir + pn * -0.10).normalized()
        # leg
        th = f"thigh{suf}"
        add(th, (0.094 * sgn, 0.006, 0.905), (0.104 * sgn, 0.002, 0.515),
            "pelvis")
        tht = f"thigh_twist{suf}"
        add(tht, (0.094 * sgn, 0.006, 0.905), (0.100 * sgn, 0.006, 0.700), th)
        sh = f"shin{suf}"
        add(sh, (0.104 * sgn, 0.002, 0.515), (0.108 * sgn, -0.014, 0.090), th, True)
        sht = f"shin_twist{suf}"
        add(sht, (0.104 * sgn, 0.002, 0.515), (0.108 * sgn, -0.026, 0.395), sh)
        ft = f"foot{suf}"
        add(ft, (0.108 * sgn, -0.014, 0.090), (0.110 * sgn, -0.10, 0.038), sh, True)
        add(f"toe{suf}", (0.110 * sgn, -0.10, 0.038), (0.112 * sgn, -0.16, 0.032),
            ft, True)
    add("satchel_anchor", (-0.155, -0.075, 0.90), (-0.158, -0.078, 0.985), "spine01")
    return B

def build_armature():
    arm = bpy.data.armatures.new("TLS_Rig_Human_Edmund")
    arm.display_type = 'OCTAHEDRAL'
    obj = bpy.data.objects.new("TLS_Rig_Human_Edmund", arm)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.edit_bones
    for spec in bone_table():
        b = eb.new(spec["name"])
        b.head = spec["head"]; b.tail = spec["tail"]
        if spec["parent"] and spec["parent"] in eb:
            b.parent = eb[spec["parent"]]
            b.use_connect = spec["connect"]
    bpy.ops.object.mode_set(mode='OBJECT')
    return obj

def select_meshes(names):
    bpy.ops.object.select_all(action='DESELECT')
    for n in names:
        o = bpy.data.objects.get(n)
        if o:
            o.select_set(True)

def main():
    opts = parse_args()
    stats_path = opts.get("stats", "/home/z/my-project/m34_out/rig_stats.json")
    posejson = opts.get("posejson", "/home/z/my-project/m34_out/rig_test_pose.json")

    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    mesh_names = [o.name for o in meshes]
    print("[RIG] meshes:", mesh_names)

    arm = build_armature()
    nbones = len(arm.data.bones)
    print(f"[RIG] bones: {nbones}")

    # automatic weights: meshes selected, armature active
    select_meshes(mesh_names)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')

    # eyes: skinned via ARMATURE_AUTO (they sit inside eye.L/eye.R zones);
    # explicit parent_bone caused doubled transforms on FBX round-trip.
    # satchel strap crosses chest -> auto weights already; bag body gets anchor bone too
    sat = bpy.data.objects.get("Edmund_Satchel")
    if sat:
        vg = sat.vertex_groups.get("satchel_anchor")
        if vg is None:
            vg = sat.vertex_groups.new(name="satchel_anchor")
        vg.add(list(range(len(sat.data.vertices))), 0.35, 'ADD')

    # ---------------- deformation tests ----------------
    dg = bpy.context.evaluated_depsgraph_get()
    def snapshot(objname):
        o = bpy.data.objects[objname]
        eo = o.evaluated_get(dg)
        me = eo.to_mesh()
        pts = [Vector((v.co.x, v.co.y, v.co.z)) for v in me.vertices]
        eo.to_mesh_clear()
        return pts

    def edge_stretch(rest, posed):
        o = bpy.data.objects[[n for n in rest.keys()][0]] if False else None
        return None

    tests = []
    body = bpy.data.objects["Edmund_Body"]
    rest = snapshot("Edmund_Body")
    rest_edges = [(e.vertices[0], e.vertices[1]) for e in body.data.edges]
    import random
    random.seed(3)
    sample_edges = random.sample(rest_edges, min(4000, len(rest_edges)))

    def run_test(name, bone, axis, angle, expect_forward=None):
        pb = bpy.context.view_layer.objects.active = arm
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode='POSE')
        pb = arm.pose.bones[bone]
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = Vector((0, 0, 0))
        setattr_vec = [0.0, 0.0, 0.0]
        setattr_vec[{'X': 0, 'Y': 1, 'Z': 2}[axis]] = angle
        pb.rotation_euler = tuple(setattr_vec)
        bpy.context.view_layer.update()
        dg2 = bpy.context.evaluated_depsgraph_get()
        eo = body.evaluated_get(dg2)
        me = eo.to_mesh()
        nverts = len(me.vertices)
        moved = 0; maxd = 0.0; nan = 0; maxstretch = 0.0
        disp_sum = Vector((0, 0, 0)); disp_dir = Vector((0, 0, 0))
        posed_co = []
        for i, v in enumerate(me.vertices):
            posed_co.append(Vector(v.co))
            d = Vector(v.co) - rest[i]
            L = d.length
            if L > 0.001:
                moved += 1
            if L > maxd:
                maxd = L; disp_dir = d.normalized()
            if v.co.x != v.co.x: nan += 1
            disp_sum += d
        for (a, b) in sample_edges:
            la = (rest[a] - rest[b]).length
            lb = (posed_co[a] - posed_co[b]).length
            if la > 1e-6:
                r = lb / la
                if r > maxstretch: maxstretch = r
        eo.to_mesh_clear()
        # restore
        pb.rotation_euler = (0, 0, 0)
        bpy.context.view_layer.update()
        tests.append({"test": name, "bone": bone, "axis": axis, "angle_deg": round(math.degrees(angle), 1),
                      "verts_moved_gt1mm": moved, "max_disp_m": round(maxd, 4),
                      "nan_verts": nan, "max_edge_stretch": round(maxstretch, 3),
                      "avg_disp": [round(disp_sum.x / nverts, 5),
                                    round(disp_sum.y / nverts, 5),
                                    round(disp_sum.z / nverts, 5)]})
        print("[RIG] test:", tests[-1])

    run_test("elbow_bend", "forearm.L", 'X', 0.7)
    run_test("head_turn", "head", 'Z', 0.5)
    run_test("spine_twist", "spine02", 'Y', 0.25)
    run_test("thigh_raise", "thigh.R", 'X', 0.5)
    run_test("shoulder_raise", "upper_arm.R", 'X', 0.6)

    # zero-weight audit on body
    zw = 0
    for v in body.data.vertices:
        if len(v.groups) == 0:
            zw += 1
    rig_stats = {"bones": nbones,
                 "bone_names": [b.name for b in arm.data.bones],
                 "skinned_objects": mesh_names,
                 "body_zero_weight_verts": zw,
                 "body_verts": len(body.data.vertices),
                 "tests": tests}
    bpy.ops.object.mode_set(mode='OBJECT')

    # save rig test pose for render script
    pose = {"forearm.L": [0.7, 0, 0], "head": [0, 0, 0.5],
            "upper_arm.R": [0.6, 0, 0], "spine02": [0, 0.25, 0]}
    os.makedirs(os.path.dirname(posejson), exist_ok=True)
    with open(posejson, "w") as f:
        json.dump(pose, f, indent=2)

    bpy.ops.wm.save_mainfile()
    if stats_path:
        os.makedirs(os.path.dirname(stats_path), exist_ok=True)
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(rig_stats, f, ensure_ascii=False, indent=2)
    print("[RIG] saved. bones:", nbones, "zero-weight verts:", zw)

main()
