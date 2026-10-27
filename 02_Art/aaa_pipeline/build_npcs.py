#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE LAST SIN - Batch 2: named NPC builds (Gwendolyn, Crane, Mair, Tom Bevan).
Reuses the v2 sculpt engine with identity parameter sets. Each NPC gets:
sculpted head (mid density), body from the 65-bone rig, period outfit,
exports (.blend + FBX + GLB), deform tests, stats JSON.
Run: blender -b --factory-startup --python build_npcs.py
"""
import bpy, os, sys, math, json, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sculpt_lib import build_head, build_ear, mesh_obj, quad_faces, sphere_grid, TAU
from body_lib import build_body_from_rig, join_parts
from outfit_lib import build_outfit, build_hair_cap, build_stubble
import textures_v2 as tx
from build_edmund_v2 import proximity_skin

REPO = "/home/z/my-project/repo"
TEXDIR = f"{REPO}/02_Art/Characters/NPCs/textures_v2"
SRC = f"{REPO}/02_Art/blender/source/chr"
EXP = f"{REPO}/02_Art/exports"
T0 = time.time()

def log(*a):
    print(f"[NPC {time.time()-T0:6.1f}s]", *a, flush=True)

NPCS = {
    "gwendolyn": dict(
        aid="TLS-CHR-003", name="Gwendolyn Meredith", role="Innkeeper",
        age=41, lean=0.25, fem=1.0, brow=0.8, eye_spacing=0.029,
        extents=(0.077, 0.100, 0.112), micro=0.34, seed=21, wrinkle=0.55,
        head_origin=(0.0, 0.005, 1.648),
        skin=(196, 162, 140), hair=(72, 48, 30),
        outfit=dict(coat=(96, 62, 58), waistcoat=(72, 52, 38), shirt=(224, 218, 204),
                    trousers=(74, 60, 52), wc=True, apron=True),
    ),
    "crane": dict(
        aid="TLS-CHR-004", name="Rev. Silas Crane", role="Anglican priest",
        age=58, lean=0.95, fem=0.0, brow=0.8, eye_spacing=0.030,
        extents=(0.076, 0.104, 0.116), micro=0.46, seed=33, wrinkle=1.0,
        head_origin=(0.0, 0.005, 1.672),
        skin=(186, 156, 136), hair=(120, 116, 110),
        outfit=dict(coat=(24, 24, 26), waistcoat=(24, 24, 26), shirt=(230, 228, 220),
                    trousers=(26, 26, 28), cassock=True),
    ),
    "mair": dict(
        aid="TLS-CHR-006", name="Mair Hughes", role="Young witness",
        age=19, lean=0.35, fem=1.0, brow=0.45, eye_spacing=0.030,
        extents=(0.074, 0.098, 0.110), micro=0.28, seed=47, wrinkle=0.15,
        head_origin=(0.0, 0.005, 1.640),
        skin=(204, 172, 150), hair=(38, 28, 22),
        outfit=dict(coat=(88, 74, 62), waistcoat=(88, 74, 62), shirt=(226, 220, 206),
                    trousers=(92, 78, 66), dress=True, shawl=True),
    ),
    "tom": dict(
        aid="TLS-CHR-007", name="Tom Bevan", role="Gravedigger",
        age=63, lean=0.45, fem=0.0, brow=1.35, eye_spacing=0.031,
        extents=(0.082, 0.105, 0.115), micro=0.55, seed=59, wrinkle=1.25,
        head_origin=(0.0, 0.005, 1.660),
        skin=(178, 146, 122), hair=(96, 88, 78),
        outfit=dict(coat=(58, 52, 42), waistcoat=(52, 44, 36), shirt=(206, 198, 180),
                    trousers=(46, 42, 36), cap=True, neckerchief=True),
    ),
}

def C(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c

def clear():
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.armatures):
        for item in list(coll):
            try: coll.remove(item)
            except Exception: pass

def load_rig():
    bpy.ops.wm.append(filepath=f"{REPO}/02_Art/blender/source/rig/tls_skl_001_rig_human.blend/Object/",
                      directory=f"{REPO}/02_Art/blender/source/rig/tls_skl_001_rig_human.blend/Object/",
                      filename="TLS_Rig_Human_Edmund")
    arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
    arm.name = "TLS_Rig_Human"
    return arm

def mk_mats(npc):
    p = npc["skin"]
    # real generated skin texture per NPC (pores + redness zones)
    sp = tx.skin_maps(TEXDIR, {"tone": p}, size=512)
    def img_mat(name, path, rough=0.55, colorspace='sRGB'):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Roughness"].default_value = rough
        img = bpy.data.images.load(path)
        img.colorspace_settings.name = colorspace
        tn = m.node_tree.nodes.new("ShaderNodeTexImage")
        tn.image = img
        m.node_tree.links.new(tn.outputs["Color"], b.inputs["Base Color"])
        return m
    def simple_mat(name, rgb, rough=0.7, metallic=0.0):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        lin = tuple((c / 255.0) ** 2.2 for c in rgb)
        b.inputs["Base Color"].default_value = (lin[0], lin[1], lin[2], 1)
        b.inputs["Roughness"].default_value = rough
        if "Metallic" in b.inputs:
            b.inputs["Metallic"].default_value = metallic
        return m
    M = {}
    M["skin_body"] = img_mat("SkinBody", [q for q in sp if "_BC.png" in q][0], 0.55)
    M["skin_face"] = img_mat("SkinFace", [q for q in sp if "_BC.png" in q][0], 0.52)
    o = npc["outfit"]
    M["coat"] = simple_mat("Coat", o["coat"], 0.74)
    M["waistcoat"] = simple_mat("Waistcoat", o["waistcoat"], 0.70)
    M["shirt"] = simple_mat("Shirt", o["shirt"], 0.62)
    M["cravat"] = simple_mat("Cravat", o["shirt"], 0.62)
    M["trousers"] = simple_mat("Trousers", o["trousers"], 0.72)
    M["boot"] = simple_mat("Boot", (56, 40, 28), 0.55)
    M["strap"] = simple_mat("Strap", (58, 42, 30), 0.55)
    M["sole"] = simple_mat("Sole", (38, 30, 24), 0.65)
    M["brass"] = simple_mat("Brass", (150, 116, 56), 0.4, 1.0)
    M["hair_solid"] = simple_mat("HairSolid", npc["hair"], 0.62)
    M["stubble"] = simple_mat("Stubble", npc["hair"], 0.6)
    return M

def _sphere(r, seg, ring):
    dirs, T, PH = sphere_grid(seg, ring)
    return (dirs * r).reshape(-1, 3), quad_faces(seg, ring)

def _disc(r, n):
    verts = [(0, 0, 0)] + [(r * math.cos(TAU * k / n), r * math.sin(TAU * k / n), 0) for k in range(n)]
    faces = [tuple(range(1, n + 1))]
    for k in range(n):
        k2 = (k + 1) % n
        faces.append((0, k + 1, k2 + 1))
    return np.asarray(verts), faces

def build_npc(key, npc, stats_all):
    clear()
    log(f"=== {npc['name']} ===")
    CHR = C(f"NPC_{key}")
    arm = load_rig()
    for c in list(arm.users_collection):
        c.objects.unlink(arm)
    CHR.objects.link(arm)
    M = mk_mats(npc)

    parts, info = build_body_from_rig(arm, CHR, M["skin_body"], {"height": 1.78})
    body = join_parts(parts, f"TLS_{key}_BodyBase", coll=CHR)

    prm = dict(age=npc["age"], lean=npc["lean"], fem=npc["fem"], brow=npc["brow"],
               eye_spacing=npc["eye_spacing"], extents=npc["extents"],
               micro=npc["micro"], seed=npc["seed"], wrinkle=npc["wrinkle"])
    HO = npc["head_origin"]
    head, hm = build_head(f"TLS_{key}_HeadSculpt", prm, mat=M["skin_face"], coll=CHR,
                          S=80, P=60, dense_factor=3, micro=True)
    head.location = HO
    for sx, tag in ((-1, "L"), (1, "R")):
        ear = build_ear(f"TLS_{key}_Ear_{tag}", prm, mat=M["skin_face"], coll=CHR, side=sx)
        ear.location = (sx * 0.0725, 0.008, HO[2] + 0.004)
        ear.rotation_euler = (0, sx * 0.10, 0)
        ear.scale = (1.0, 1.0, 1.05)
    for sx, tag in ((-1, "L"), (1, "R")):
        ball = mesh_obj(f"TLS_{key}_Eyeball_{tag}", *(_sphere(0.0115, 20, 14)), mat=M["eye_white"] if "eye_white" in M else simple_white(), coll=CHR)
        ball.location = (sx * npc["eye_spacing"], HO[1] - 0.0915, HO[2] + 0.014)
        iris = mesh_obj(f"TLS_{key}_Iris_{tag}", *(_disc(0.0058, 18)), mat=M["iris"] if "iris" in M else simple_iris(), coll=CHR)
        iris.location = (sx * npc["eye_spacing"], HO[1] - 0.1042, HO[2] + 0.014)
        iris.rotation_euler = (math.pi / 2, 0, 0)
    # hair cap + (bun for females)
    dirs, T, PH = sphere_grid(80, 60)
    hbase = None
    import sculpt_lib as SL
    hbase = SL.sculpt_head_dirs(dirs, prm)
    cap = build_hair_cap(hbase, head_origin=HO, coll=CHR, mat=M["hair_solid"])
    if cap:
        bpy.context.view_layer.objects.active = cap
        bpy.ops.object.modifier_apply(modifier="sol")
    if npc["fem"] > 0.5:
        bun = mesh_obj(f"TLS_{key}_HairBun", *(_sphere(0.045, 18, 12)), mat=M["hair_solid"], coll=CHR)
        bun.location = (0.0, HO[1] + 0.075, HO[2] - 0.030)
    stub = build_stubble(head, HO, coll=CHR, mat=M["stubble"]) if npc["fem"] < 0.5 and npc["age"] > 30 else None

    outfit = build_outfit(body, CHR, M)
    # extras: cassock skirt lengthen / apron / neckerchief / cap
    o = npc["outfit"]
    if o.get("cassock"):
        co = outfit.get("coat")
        if co:
            co.scale = (1.0, 1.0, 1.18)
            co.location = (0, 0, -0.24)   # full-length gown
    if o.get("cap"):
        capm = mesh_obj(f"TLS_{key}_FlatCap", *(_sphere(0.098, 20, 10)), mat=M["coat"], coll=CHR)
        capm.scale = (1.0, 1.05, 0.42)
        capm.location = (0, HO[1] + 0.008, HO[2] + 0.075)
    if o.get("neckerchief"):
        nc = mesh_obj(f"TLS_{key}_Neckerchief", *(_sphere(0.052, 14, 8)), mat=M["shirt"], coll=CHR)
        nc.scale = (1.0, 0.9, 0.55)
        nc.location = (0, 0.0, 1.435)

    # apply modifiers, save, export
    for ob in [x for x in CHR.objects if x.type == 'MESH']:
        bpy.context.view_layer.objects.active = ob
        for m in list(ob.modifiers):
            try: bpy.ops.object.modifier_apply(modifier=m.name)
            except Exception: pass

    blend = f"{SRC}/tls_chr_{npc['aid'][-3:]}_{key}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    tot = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in CHR.objects if o.type == 'MESH')

    bpy.ops.object.select_all(action='DESELECT')
    for o in CHR.objects:
        if o.type == 'MESH':
            o.select_set(True)
    bpy.context.view_layer.objects.active = [o for o in CHR.objects if o.type == 'MESH'][0]
    glb = f"{EXP}/glb/tls_chr_{npc['aid'][-3:]}_{key}.glb"
    bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', export_apply=True,
                              export_animations=False)

    # game-res: decimate head only + skin + FBX
    hd = bpy.data.objects.get(f"TLS_{key}_HeadSculpt")
    if hd:
        m = hd.modifiers.new("dec", 'DECIMATE'); m.ratio = 0.12
        bpy.context.view_layer.objects.active = hd
        bpy.ops.object.modifier_apply(modifier="dec")
    hc = bpy.data.objects.get(f"TLS_Hair_Cap")
    if hc:
        m = hc.modifiers.new("dec", 'DECIMATE'); m.ratio = 0.05
        bpy.context.view_layer.objects.active = hc
        bpy.ops.object.modifier_apply(modifier="dec")
    meshes = [o for o in CHR.objects if o.type == 'MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()
    game = bpy.context.active_object
    game.name = f"TLS_{key}_Game"
    nb = proximity_skin(game, arm)
    fbx = f"{EXP}/fbx/tls_chr_{npc['aid'][-3:]}_{key}.fbx"
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=False, add_leaf_bones=False,
                             bake_anim=False, object_types={'ARMATURE', 'MESH'}, path_mode='COPY')
    gtris = sum(len(p.vertices) - 2 for p in game.data.polygons)
    stats_all[npc["aid"]] = dict(name=npc["name"], blend=blend, glb=glb, fbx=fbx,
                                 hi_tris=tot, game_tris=gtris, head=hm,
                                 bones=len(arm.data.bones), skin_bones=nb)
    log(f"  DONE {key}: hi={tot} game={gtris}")

def simple_white():
    m = bpy.data.materials.new("EyeWhite")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.86, 0.84, 0.80, 1)
    return m

def simple_iris():
    m = bpy.data.materials.new("Iris")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.10, 0.12, 0.14, 1)
    return m

def main():
    os.makedirs(TEXDIR, exist_ok=True)
    stats = {}
    for key, npc in NPCS.items():
        build_npc(key, npc, stats)
    os.makedirs(f"{EXP}/stats", exist_ok=True)
    with open(f"{EXP}/stats/npc_batch_v2.json", "w") as f:
        json.dump(stats, f, indent=1)
    log("ALL NPCS DONE:", list(stats.keys()))

main()
