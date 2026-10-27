#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE LAST SIN - Batch 1: Edmund Vale AAA sculpt upgrade (v002).
Pipeline: existing 65-bone rig -> parametric sculpted body -> dense sculpted
head (wrinkles+micro) -> ears/eyes/brows -> hair cards -> stubble -> 1847 outfit
-> materials -> hi-poly .blend + GLB -> game-res (decimate+bind+deform tests)
-> FBX + game .blend -> stats JSON.
Run: blender -b --factory-startup --python build_edmund_v2.py
"""
import bpy, bmesh, os, sys, math, json, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sculpt_lib import build_head, build_ear, mesh_obj, quad_faces, sphere_grid, TAU
from body_lib import build_body_from_rig, join_parts
from outfit_lib import build_outfit, build_hair, build_hair_cap, build_brows, build_stubble
import textures_v2 as tx

REPO = "/home/z/my-project/repo"
TEXDIR = f"{REPO}/02_Art/Characters/Edmund/textures_v2"
SRC = f"{REPO}/02_Art/blender/source/chr"
EXP = f"{REPO}/02_Art/exports"
STATS = {}
T0 = time.time()

def log(*a):
    print(f"[EDMUND-V2 {time.time()-T0:6.1f}s]", *a, flush=True)

# ---------------------------------------------------------------- scene reset
for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.armatures,
             bpy.data.curves, bpy.data.images, bpy.data.lights, bpy.data.cameras):
    for item in list(coll):
        try: coll.remove(item)
        except Exception: pass

def C(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c

CHR = C("EdmundVale_v2")

# ---------------------------------------------------------------- 1. rig
log("loading rig...")
bpy.ops.wm.append(filepath=f"{REPO}/02_Art/blender/source/rig/tls_skl_001_rig_human.blend/Object/",
                  directory=f"{REPO}/02_Art/blender/source/rig/tls_skl_001_rig_human.blend/Object/",
                  filename="TLS_Rig_Human_Edmund")
arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
for c in list(arm.users_collection):
    c.objects.unlink(arm)
CHR.objects.link(arm)
log("rig loaded:", arm.name, len(arm.data.bones), "bones")

# ---------------------------------------------------------------- 2. textures
log("generating textures...")
TEX = {}
def txset(key, fn):
    paths = fn(TEXDIR)
    TEX[key] = paths
    log("  tex", key, len(paths), "maps")

txset("skin_face", lambda d: tx.skin_maps(d, {"tone": (196, 166, 146)}))
txset("skin_body", lambda d: tx.skin_maps(d, {"tone": (178, 150, 128)}))
txset("coat", lambda d: tx.cloth_maps(d, "tls_tex_102_coat_wool", (56, 58, 62), weave=5.5, rough=0.74))
txset("waistcoat", lambda d: tx.cloth_maps(d, "tls_tex_103_wc_wool", (72, 52, 36), weave=4.2, rough=0.70))
txset("shirt", lambda d: tx.linen_maps(d))
txset("cravat", lambda d: tx.linen_maps(d, color=(210, 202, 186)))
TEX["cravat"] = TEX["shirt"]  # same maps fine
txset("trousers", lambda d: tx.cloth_maps(d, "tls_tex_104_trouser", (44, 42, 40), weave=3.4, rough=0.72))
txset("boot", lambda d: tx.leather_maps(d, name="tls_tex_105_boot", color=(58, 40, 28), worn=0.7))
TEX["strap"] = TEX["boot"]
txset("sole", lambda d: tx.leather_maps(d, name="tls_tex_106_sole", color=(38, 30, 24), worn=0.9))
txset("brass", lambda d: tx.brass_maps(d))
txset("hair", lambda d: tx.hair_alpha(d, color=(48, 36, 28), strands=150, seed=5))
txset("stubble", lambda d: tx.stubble_alpha(d))
txset("brow", lambda d: tx.hair_alpha(d, name="tls_tex_107_brow", color=(42, 32, 26), strands=90, seed=9))

def mat_from(key, name, rough=0.7, metallic=0.0, alpha=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = rough
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    if alpha:
        m.blend_method = 'CLIP'
    paths = TEX[key]
    def find(suf):
        for p in paths:
            if f"_{suf}.png" in p:
                return p
        return None
    for suf, sock, colorspace in (("BC", "Base Color", 'sRGB'), ("R", "Roughness", 'Non-Color'),
                                  ("N", "Normal", 'Non-Color')):
        p = find(suf)
        if not p:
            continue
        img = bpy.data.images.load(p)
        img.colorspace_settings.name = colorspace
        tn = m.node_tree.nodes.new("ShaderNodeTexImage")
        tn.image = img
        if sock == "Normal":
            nm = m.node_tree.nodes.new("ShaderNodeNormalMap")
            m.node_tree.links.new(tn.outputs["Color"], nm.inputs["Color"])
            m.node_tree.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
        else:
            m.node_tree.links.new(tn.outputs["Color"], bsdf.inputs[sock])
    if alpha:
        pa = find("RGBA")
        if pa:
            img = bpy.data.images.load(pa)
            img.colorspace_settings.name = 'sRGB'
            tn = m.node_tree.nodes.new("ShaderNodeTexImage")
            tn.image = img
            m.node_tree.links.new(tn.outputs["Alpha"], bsdf.inputs["Alpha"])
            m.blend_method = 'CLIP'
    return m

log("building materials...")
M = {}
M["skin_face"] = mat_from("skin_face", "M_TLS_Skin_Face_v2", rough=0.52)
M["skin_body"] = mat_from("skin_body", "M_TLS_Skin_Body_v2", rough=0.55)
M["coat"] = mat_from("coat", "M_TLS_CoatWool_v2", rough=0.74)
M["waistcoat"] = mat_from("waistcoat", "M_TLS_WaistcoatWool_v2", rough=0.70)
M["shirt"] = mat_from("shirt", "M_TLS_Linen_v2", rough=0.62)
M["cravat"] = mat_from("cravat", "M_TLS_Cravat_v2", rough=0.62)
M["trousers"] = mat_from("trousers", "M_TLS_TrouserWool_v2", rough=0.72)
M["boot"] = mat_from("boot", "M_TLS_BootLeather_v2", rough=0.55)
M["strap"] = mat_from("strap", "M_TLS_StrapLeather_v2", rough=0.55)
M["sole"] = mat_from("sole", "M_TLS_SoleLeather_v2", rough=0.65)
M["brass"] = mat_from("brass", "M_TLS_Brass_v2", rough=0.4, metallic=1.0)
M["hair"] = mat_from("hair", "M_TLS_Hair_v2", rough=0.6, alpha=True)
M["stubble"] = mat_from("stubble", "M_TLS_Stubble_v2", rough=0.6, alpha=True)
M["brow"] = mat_from("brow", "M_TLS_Brow_v2", rough=0.6, alpha=True)
M["eye_white"] = bpy.data.materials.new("M_TLS_EyeWhite")
M["eye_white"].use_nodes = True
eb = M["eye_white"].node_tree.nodes["Principled BSDF"]
eb.inputs["Base Color"].default_value = (0.86, 0.84, 0.80, 1)
eb.inputs["Roughness"].default_value = 0.08
M["iris"] = bpy.data.materials.new("M_TLS_Iris")
M["iris"].use_nodes = True
ib = M["iris"].node_tree.nodes["Principled BSDF"]
ib.inputs["Base Color"].default_value = (0.13, 0.16, 0.19, 1)
ib.inputs["Roughness"].default_value = 0.10
M["pupil"] = bpy.data.materials.new("M_TLS_Pupil")
M["pupil"].use_nodes = True
pb = M["pupil"].node_tree.nodes["Principled BSDF"]
pb.inputs["Base Color"].default_value = (0.01, 0.01, 0.01, 1)
pb.inputs["Roughness"].default_value = 0.05
M["ink"] = bpy.data.materials.new("M_TLS_InkSpot")
M["ink"].use_nodes = True
ib2 = M["ink"].node_tree.nodes["Principled BSDF"]
ib2.inputs["Base Color"].default_value = (0.04, 0.045, 0.06, 1)
ib2.inputs["Roughness"].default_value = 0.5

# ---------------------------------------------------------------- 3. body
log("building body from rig...")
parts, info = build_body_from_rig(arm, CHR, M["skin_body"], {"height": 1.78})
log("  parts:", len(info["parts"]))
body = join_parts(parts, "TLS_Edmund_BodyBase_v2", coll=CHR)
log("  body joined:", len(body.data.vertices), "verts")

# ---------------------------------------------------------------- 4. head
log("sculpting head (dense)...")
HEAD_ORIGIN = (0.0, 0.005, 1.668)
prm = dict(age=38.0, lean=0.60, fem=0.0, brow=1.05, eye_spacing=0.030,
           extents=(0.079, 0.103, 0.118), micro=0.40, seed=7, wrinkle=0.85)
head_obj, hmeta = build_head("TLS_Edmund_HeadSculpt_v2", prm, mat=M["skin_face"],
                             coll=CHR, S=96, P=72, dense_factor=3, micro=True)
head_obj.location = HEAD_ORIGIN
STATS["head_sculpt"] = hmeta
log("  head:", hmeta)

# ears
for sx, tag in ((-1, "L"), (1, "R")):
    ear = build_ear(f"TLS_Edmund_Ear_{tag}", prm, mat=M["skin_face"], coll=CHR, side=sx)
    ear.location = (sx * 0.0745, 0.008, 1.672)
    ear.rotation_euler = (0, sx * 0.10, 0)
    ear.scale = (1.0, 1.0, 1.05)

def _sphere(r, seg, ring):
    dirs, T, PH = sphere_grid(seg, ring)
    p = dirs * r
    return p.reshape(-1, 3), quad_faces(seg, ring)

def _disc(r, n):
    verts = [(0, 0, 0)] + [(r * math.cos(TAU * k / n), r * math.sin(TAU * k / n), 0) for k in range(n)]
    faces = [tuple(range(1, n + 1))]
    for k in range(n):
        k2 = (k + 1) % n
        faces.append((0, k + 1, k2 + 1))
    return np.asarray(verts), faces

# eyes: ball + iris + pupil + limbal
for sx, tag in ((-1, "L"), (1, "R")):
    ball = mesh_obj(f"TLS_Edmund_Eyeball_{tag}", *(_sphere(0.0115, 24, 16)), mat=M["eye_white"], coll=CHR)
    ball.location = (sx * 0.030, -0.089, 1.682)
    iris = mesh_obj(f"TLS_Edmund_Iris_{tag}", *(_disc(0.0058, 20)), mat=M["iris"], coll=CHR)
    iris.location = (sx * 0.030, -0.1016, 1.682)
    iris.rotation_euler = (math.pi / 2, 0, 0)
    pupil = mesh_obj(f"TLS_Edmund_Pupil_{tag}", *(_disc(0.0022, 16)), mat=M["pupil"], coll=CHR)
    pupil.location = (sx * 0.030, -0.1019, 1.682)
    pupil.rotation_euler = (math.pi / 2, 0, 0)

# brows + hair + stubble
import sculpt_lib as _SL
_dirs, _T, _PH = _SL.head_base_dirs(96, 72)
_head_base_for_hair = _SL.sculpt_head_dirs(_dirs, prm)
build_brows(coll=CHR, mat=M["brow"], head_origin=HEAD_ORIGIN)
M["hair_solid"] = bpy.data.materials.new("M_TLS_HairSolid_v2")
M["hair_solid"].use_nodes = True
_hb = M["hair_solid"].node_tree.nodes["Principled BSDF"]
_hb.inputs["Base Color"].default_value = (0.115, 0.082, 0.058, 1)
_hb.inputs["Roughness"].default_value = 0.62
_cap = build_hair_cap(_head_base_for_hair, head_origin=HEAD_ORIGIN, coll=CHR, mat=M["hair_solid"])
if _cap:
    m = _cap.modifiers.get("sol")
    bpy.context.view_layer.objects.active = _cap
    bpy.ops.object.modifier_apply(modifier="sol")
hair_objs = build_hair(head_origin=HEAD_ORIGIN, coll=CHR, mat=M["hair"], n_strands=70,
                       head_base=_head_base_for_hair)
stub = build_stubble(head_obj, HEAD_ORIGIN, coll=CHR, mat=M["stubble"])
log("  hair cards:", len(hair_objs), "| stubble:", bool(stub))

# ink spot on left hand dorsum
ink = mesh_obj("TLS_Edmund_InkSpot", *(_disc(0.012, 14)), mat=M["ink"], coll=CHR)
ink.location = (-0.345, -0.095, 0.845)
ink.rotation_euler = (math.pi / 2 - 0.4, 0.2, 0)

# ---------------------------------------------------------------- 5. outfit
log("building outfit...")
outfit = build_outfit(body, CHR, M)
log("  outfit parts:", {k: (len(v) if isinstance(v, list) else 1) for k, v in outfit.items()})

# ---------------------------------------------------------------- 6. save hi-poly
def ensure_apply_mods(ob):
    bpy.context.view_layer.objects.active = ob
    for m in list(ob.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=m.name)
        except Exception as e:
            log("  mod apply fail", ob.name, m.name, e)

meshes = [o for o in CHR.objects if o.type == 'MESH']
log("applying modifiers on", len(meshes), "meshes...")
for o in meshes:
    ensure_apply_mods(o)

SCENE_META = {
    "generated_by": "aaa_pipeline/build_edmund_v2.py (Blender 5.0.1 headless)",
    "rig": "TLS-SKL-001 (65 bones, A-pose 15deg)",
    "head_params": prm,
    "head_sculpt": hmeta,
}
bpy.context.scene["TLS_META"] = json.dumps(SCENE_META)

hi_blend = f"{SRC}/tls_chr_001_edmund_vale_v002.blend"
bpy.ops.wm.save_as_mainfile(filepath=hi_blend)
log("SAVED hi-poly blend:", hi_blend)

# ---------------------------------------------------------------- 7. exports
os.makedirs(f"{EXP}/glb", exist_ok=True)
tot_tris = 0
for o in CHR.objects:
    if o.type == 'MESH':
        tot_tris += sum(len(p.vertices) - 2 for p in o.data.polygons)
log("total hi-poly tris:", tot_tris)

# GLB hi-poly (body+head+outfit, showcase)
bpy.ops.object.select_all(action='DESELECT')
for o in CHR.objects:
    if o.type == 'MESH':
        o.select_set(True)
bpy.context.view_layer.objects.active = [o for o in CHR.objects if o.type == 'MESH'][0]
glb_hi = f"{EXP}/glb/tls_chr_001_edmund_vale_v002.glb"
bpy.ops.export_scene.gltf(filepath=glb_hi, export_format='GLB', export_apply=True,
                          export_animations=False, export_cameras=False, export_lights=False)
log("EXPORT GLB hi:", glb_hi)

# head-only sculpt GLB
bpy.ops.object.select_all(action='DESELECT')
hd = bpy.data.objects.get("TLS_Edmund_HeadSculpt_v2")
if hd:
    hd.select_set(True)
    bpy.context.view_layer.objects.active = hd
    bpy.ops.export_scene.gltf(filepath=f"{EXP}/glb/tls_chr_001_head_sculpt_v002.glb",
                              export_format='GLB', export_apply=True, use_selection=True)
    log("EXPORT GLB head sculpt")

# ---------------------------------------------------------------- 8. game-res
log("building game-res version...")
bpy.ops.wm.save_as_mainfile(filepath="/home/z/my-project/scripts/_session_hi.blend")

DEC = {"TLS_Edmund_HeadSculpt_v2": 0.11, "TLS_Hair_Stubble": 0.08}
for o in CHR.objects:
    if o.type != 'MESH':
        continue
    tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
    if tris > 3000:
        ratio = DEC.get(o.name, 0.45 if tris > 15000 else 0.7)
        m = o.modifiers.new("dec", 'DECIMATE')
        m.ratio = ratio
        log(f"  decimate {o.name}: {tris} -> ~{int(tris*ratio)}")
for o in CHR.objects:
    if o.type == 'MESH':
        ensure_apply_mods(o)

# join into one skinned mesh (material slots preserved)
bpy.ops.object.select_all(action='DESELECT')
meshes = [o for o in CHR.objects if o.type == 'MESH']
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.join()
game = bpy.context.active_object
game.name = "TLS_EdmundVale_Game_v2"
game_tris = sum(len(p.vertices) - 2 for p in game.data.polygons)
log("  game mesh tris:", game_tris)

# bind to rig: deterministic proximity skinning (auto-weight op failed headless)
def proximity_skin(game, arm):
    import numpy as _np
    excl = {"root", "satchel_anchor", "eye.L", "eye.R"}
    bones = [(b.name, _np.array(b.head_local), _np.array(b.tail_local))
             for b in arm.data.bones
             if b.name not in excl and "twist" not in b.name]
    me = game.data
    n = len(me.vertices)
    vs = _np.empty(n * 3)
    me.vertices.foreach_get("co", vs)
    vs = vs.reshape(-1, 3)
    M = _np.array(game.matrix_world)
    vsw = vs @ M[:3, :3].T + M[:3, 3]
    D = _np.zeros((n, len(bones)), dtype=_np.float32)
    for j, (nm, h, t) in enumerate(bones):
        ab = t - h
        L2 = float(ab @ ab) + 1e-9
        tt = _np.clip(((vsw - h) @ ab) / L2, 0.0, 1.0)
        proj = h[None, :] + tt[:, None] * ab[None, :]
        D[:, j] = _np.linalg.norm(vsw - proj, axis=1)
    idx = _np.argpartition(D, 3, axis=1)[:, :4]
    dd = _np.take_along_axis(D, idx, axis=1)
    w = 1.0 / (dd ** 4 + 1e-7)
    w /= w.sum(axis=1, keepdims=True)
    game.parent = arm
    mod = game.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm
    vgs = {}
    for j, (nm, _, _) in enumerate(bones):
        vgs[j] = game.vertex_groups.get(nm) or game.vertex_groups.new(name=nm)
    idxl = idx.tolist()
    wl = w.tolist()
    for i in range(n):
        for jj, ww in zip(idxl[i], wl[i]):
            vgs[jj].add([i], float(ww), 'REPLACE')
    return len(bones)

nb = proximity_skin(game, arm)
log("  proximity skinning over", nb, "bones")

# ---------------------------------------------------------------- 9. deform tests
def run_deform_tests():
    results = []
    tests = [("arm_raise_R", "upper_arm.R", 'X', 30), ("leg_swing_L", "thigh.L", 'X', -25),
             ("spine_bend", "spine02", 'Y', 12)]
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')
    import mathutils
    def eval_coords():
        deps = bpy.context.evaluated_depsgraph_get()
        ev = game.evaluated_get(deps)
        me = ev.to_mesh()
        vs = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", vs)
        ev.to_mesh_clear()
        return vs.reshape(-1, 3)
    ngroups = len(game.vertex_groups)
    for name, bone, axis, deg in tests:
        pb = arm.pose.bones.get(bone)
        if not pb:
            continue
        pb.rotation_mode = 'XYZ'
        rot = [0.0, 0.0, 0.0]
        rot[0 if axis == 'X' else 1] = math.radians(deg)
        pb.rotation_euler = rot
        bpy.context.view_layer.update()
        vs = eval_coords()
        pb.rotation_euler = (0, 0, 0)
        bpy.context.view_layer.update()
        vs0 = eval_coords()
        disp = np.linalg.norm(vs - vs0, axis=1)
        results.append({"test": name, "bone": bone, "deg": deg,
                        "vertex_groups": ngroups,
                        "moved_verts": int((disp > 0.001).sum()),
                        "max_disp_mm": round(float(disp.max()) * 1000, 2)})
        log("  deform test", name, results[-1])
    bpy.ops.object.mode_set(mode='OBJECT')
    return results

STATS["deform_tests"] = run_deform_tests()

# game blend
game_blend = f"{SRC}/tls_chr_001_edmund_vale_game_v002.blend"
bpy.ops.wm.save_as_mainfile(filepath=game_blend)
log("SAVED game blend:", game_blend)

# FBX export (game-res + rig)
fbx = f"{EXP}/fbx/tls_chr_001_edmund_vale_v002.fbx"
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=False, add_leaf_bones=False,
                         bake_anim=False, apply_unit_scale=True, global_scale=1.0,
                         object_types={'ARMATURE', 'MESH'}, mesh_smooth_type='OFF',
                         path_mode='COPY', embed_textures=False)
log("EXPORT FBX:", fbx)

# ---------------------------------------------------------------- 10. stats
os.makedirs(f"{EXP}/stats", exist_ok=True)
STATS.update({
    "asset": "TLS-CHR-001 Edmund Vale v002 (AAA sculpt upgrade)",
    "hi_blend": hi_blend,
    "glb_hi": glb_hi,
    "fbx_game": fbx,
    "game_blend": game_blend,
    "hi_total_tris": tot_tris,
    "game_tris": game_tris,
    "objects": len(bpy.data.objects),
    "elapsed_s": round(time.time() - T0, 1),
})
with open(f"{EXP}/stats/tls_chr_001_v002.json", "w") as f:
    json.dump(STATS, f, indent=1)
log("DONE.", json.dumps({k: STATS[k] for k in ("hi_total_tris", "game_tris")}))
