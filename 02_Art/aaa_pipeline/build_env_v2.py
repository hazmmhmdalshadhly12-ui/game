#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE LAST SIN - Batch 3: environment builds.
Kit modules (stone/slate/wood), Josiah cottage assembly, St Cynog church,
cemetery set, nature set. Real displacement geometry + PBR textures + UCX.
Run: blender -b --factory-startup --python build_env_v2.py
"""
import bpy, os, sys, math, json, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import env_lib as EV
from env_lib import grid_mesh, _box_bevel, rubble_stone_hf
import textures_v2 as tx
from sculpt_lib import mesh_obj

REPO = "/home/z/my-project/repo"
SRC = f"{REPO}/02_Art/blender/source/env"
EXP = f"{REPO}/02_Art/exports"
TEXDIR = f"{REPO}/02_Art/textures/materials_v2"
T0 = time.time()

def log(*a):
    print(f"[ENV {time.time()-T0:6.1f}s]", *a, flush=True)

def C(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c

def clear():
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for item in list(coll):
            try: coll.remove(item)
            except Exception: pass

def mk_env_mats():
    os.makedirs(TEXDIR, exist_ok=True)
    M = {}
    paths = {}
    paths["stone"] = tx.stone_maps(TEXDIR, "tls_tex_201_stone_rubble", courses=8, seed=13)
    paths["stone2"] = tx.stone_maps(TEXDIR, "tls_tex_202_stone_rubble_b", courses=7, seed=41)
    paths["slate"] = tx.slate_maps(TEXDIR, "tls_tex_203_slate")
    paths["oak"] = tx.wood_maps(TEXDIR, "tls_tex_204_oak_planks", planks=5)
    paths["bark"] = tx.wood_maps(TEXDIR, "tls_tex_205_bark", planks=1, color=(70, 58, 44), seed=9)
    paths["iron"] = tx.iron_maps(TEXDIR, "tls_tex_206_iron")
    paths["dirt"] = tx.dirt_maps(TEXDIR, "tls_tex_207_mud")
    def img_mat(name, plist, rough=0.75, metallic=None):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Roughness"].default_value = rough
        if metallic is not None and "Metallic" in b.inputs:
            b.inputs["Metallic"].default_value = metallic
        for p in plist:
            img = bpy.data.images.load(p)
            img.colorspace_settings.name = 'Non-Color' if "_N." in p else ('sRGB')
            tn = m.node_tree.nodes.new("ShaderNodeTexImage")
            tn.image = img
            if "_BC." in p:
                m.node_tree.links.new(tn.outputs["Color"], b.inputs["Base Color"])
            elif "_R." in p:
                m.node_tree.links.new(tn.outputs["Color"], b.inputs["Roughness"])
            elif "_N." in p:
                nm = m.node_tree.nodes.new("ShaderNodeNormalMap")
                m.node_tree.links.new(tn.outputs["Color"], nm.inputs["Color"])
                m.node_tree.links.new(nm.outputs["Normal"], b.inputs["Normal"])
            elif "_M." in p:
                m.node_tree.links.new(tn.outputs["Color"], b.inputs["Metallic"])
        return m
    M["stone"] = img_mat("M_TLS_StoneRubble", paths["stone"])
    M["stone2"] = img_mat("M_TLS_StoneRubbleB", paths["stone2"])
    M["slate"] = img_mat("M_TLS_Slate", paths["slate"], 0.6)
    M["oak"] = img_mat("M_TLS_Oak", paths["oak"], 0.65)
    M["bark"] = img_mat("M_TLS_Bark", paths["bark"], 0.8)
    M["iron"] = img_mat("M_TLS_Iron", paths["iron"], 0.55, 0.8)
    M["dirt"] = img_mat("M_TLS_Dirt", paths["dirt"], 0.85)
    M["rock"] = img_mat("M_TLS_Rock", paths["stone2"], 0.8)
    M["leaves"] = bpy.data.materials.new("M_TLS_Leaves")
    M["leaves"].use_nodes = True
    lb = M["leaves"].node_tree.nodes["Principled BSDF"]
    lb.inputs["Base Color"].default_value = (0.055, 0.10, 0.030, 1)
    lb.inputs["Roughness"].default_value = 0.6
    M["glass"] = EV._mk_glass()
    M["terracotta"] = bpy.data.materials.new("M_TLS_Terracotta")
    M["terracotta"].use_nodes = True
    tb = M["terracotta"].node_tree.nodes["Principled BSDF"]
    tb.inputs["Base Color"].default_value = (0.28, 0.13, 0.07, 1)
    tb.inputs["Roughness"].default_value = 0.8
    return M

def apply_all(coll):
    for ob in [o for o in coll.objects if o.type == 'MESH']:
        bpy.context.view_layer.objects.active = ob
        for m in list(ob.modifiers):
            try: bpy.ops.object.modifier_apply(modifier=m.name)
            except Exception as e:
                log("  modfail", ob.name, e)

def ucx_from(objs, name, coll, pad=0.01):
    """Simple UCX box collision around given objects (UE naming)."""
    import numpy as _np
    mn = _np.array([1e9] * 3); mx = -_np.array([1e9] * 3)
    for o in objs:
        if o.type != 'MESH':
            continue
        vs = _np.empty(len(o.data.vertices) * 3)
        o.data.vertices.foreach_get("co", vs)
        vs = vs.reshape(-1, 3)
        mw = _np.array(o.matrix_world)
        vsw = vs @ mw[:3, :3].T + mw[:3, 3]
        mn = _np.minimum(mn, vsw.min(axis=0)); mx = _np.maximum(mx, vsw.max(axis=0))
    mn -= pad; mx += pad
    ctr, sz = (mn + mx) / 2, (mx - mn)
    box = _box_bevel(name, tuple(sz), tuple(ctr), None, coll, seed=1, segments=1)
    if box.data.materials:
        box.data.materials.clear()
    return box

def save_export(coll, blend_name, exp_base, stats, note=""):
    apply_all(coll)
    # isolate: remove objects not belonging to this collection (keep materials)
    keep = set(o.name for o in coll.objects)
    for o in list(bpy.data.objects):
        if o.name not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    blend = f"{SRC}/{blend_name}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    tot = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in coll.objects if o.type == 'MESH')
    nv = sum(len(o.data.vertices) for o in coll.objects if o.type == 'MESH')
    bpy.ops.object.select_all(action='DESELECT')
    for o in coll.objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = [o for o in coll.objects if o.type == 'MESH'][0]
    os.makedirs(f"{EXP}/glb", exist_ok=True)
    glb = f"{EXP}/glb/{exp_base}.glb"
    bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', export_apply=True)
    os.makedirs(f"{EXP}/fbx", exist_ok=True)
    fbx = f"{EXP}/fbx/{exp_base}.fbx"
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, add_leaf_bones=False,
                             bake_anim=False, object_types={'MESH'}, path_mode='COPY')
    stats[blend_name] = dict(blend=blend, glb=glb, fbx=fbx, tris=tot, verts=nv,
                             objects=len([o for o in coll.objects if o.type == 'MESH']), note=note)
    log(f"  {blend_name}: tris={tot} objs={stats[blend_name]['objects']}")

def main():
    clear()
    M = mk_env_mats()
    stats = {}

    # ---------------- 1. cottage kit v2 (modular)
    log("cottage kit...")
    KIT = C("Kit_Cottage_v2")
    mods = []
    mods += EV.build_stone_wall_module("straight", KIT, M, seed=13) if isinstance(EV.build_stone_wall_module("straight", KIT, M, seed=13), list) else [EV.build_stone_wall_module("straight", KIT, M, seed=13)]
    mods += EV.build_stone_wall_module("end", KIT, M, seed=17)
    mods += EV.build_stone_wall_module("corner", KIT, M, seed=19)
    mods += EV.build_stone_wall_module("door", KIT, M, seed=23)
    mods += EV.build_stone_wall_module("window", KIT, M, seed=29)
    mods += [EV.build_roof_module(KIT, M, seed=4)]
    mods += EV.build_door(KIT, M, seed=6)
    mods += EV.build_window(KIT, M, seed=8)
    mods += EV.build_chimney(KIT, M, seed=11)
    # place kit pieces in a row for inspection
    x = 0.0
    for grp in mods:
        objs = grp if isinstance(grp, list) else [grp]
        for o in objs:
            o.location.x += x
        x += 2.7
    save_export(KIT, "tls_env_101_kit_cottage_v2", "tls_env_101_kit_cottage_v2", stats,
                "modular stone kit v2: walls/corners/door/window/roof/chimney")

    # ---------------- 2. Josiah cottage assembly
    log("cottage assembly...")
    COT = C("Cottage_Josiah")
    import math as _m
    WW, WH = 2.4, 2.6          # wall module size
    T = 0.26                    # wall thickness
    LX, LY = 7.2, 4.8           # footprint
    def wall_seg(nm, x0, y0, x1, y1, sd, h=WH, mat=None):
        """Place a displaced wall slab between two points (plan view)."""
        hf, _ = rubble_stone_hf(w=2.4, h=h, courses=max(4, int(h / 0.30)), seed=sd, nx=72, nz=max(24, int(h * 30)))
        w = grid_mesh(nm, 2.4, h, hf, mat or M["stone"], COT, thickness=T)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        L = _m.hypot(x1 - x0, y1 - y0)
        w.scale = (L / 2.4, 1, 1)
        w.rotation_euler = (0, 0, _m.atan2(y1 - y0, x1 - x0))
        w.location = (cx, cy, 0)
        return w
    # floor
    floor = grid_mesh("TLS_Cottage_Floor", LX + 0.3, LY + 0.3, np.zeros((6, 8)), M["oak"], COT,
                      plane="xy", base_off=0.05, thickness=0.10)
    # back wall y=+LY/2 : three segments
    wall_seg("TLS_Cottage_BackA", -LX/2, LY/2, -LX/6, LY/2, 31)
    wall_seg("TLS_Cottage_BackB", -LX/6, LY/2, LX/6, LY/2, 33)
    wall_seg("TLS_Cottage_BackC", LX/6, LY/2, LX/2, LY/2, 35)
    # front wall y=-LY/2 : straight + door + window
    wall_seg("TLS_Cottage_FrontA", -LX/2, -LY/2, -LX/2 + 2.4, -LY/2, 37)
    dparts = EV.build_stone_wall_module("door", COT, M, seed=39)
    for o in (dparts if isinstance(dparts, list) else [dparts]):
        o.rotation_euler = (0, 0, 0)
        o.location = (-LX/2 + 2.4 + o.location.x, -LY/2, o.location.z)
    wparts = EV.build_stone_wall_module("window", COT, M, seed=41)
    for o in (wparts if isinstance(wparts, list) else [wparts]):
        o.location = (-LX/2 + 4.8 + o.location.x, -LY/2, o.location.z)
    # side walls
    wall_seg("TLS_Cottage_SideL", -LX/2, -LY/2 + 2.4, -LX/2, LY/2 - 0.0 + 0.0, 43)
    wall_seg("TLS_Cottage_SideR", LX/2, -LY/2 + 2.4, LX/2, LY/2, 45)
    # gable triangles at x=+-LX/2 (over side walls, up to ridge)
    HR = 4.4   # ridge height (Welsh pitch ~33deg)
    for sx in (-1, 1):
        verts = [(sx*LX/2, -LY/2 - 0.05, 0), (sx*LX/2, LY/2 + 0.05, 0),
                 (sx*LX/2, LY/2 + 0.05, WH), (sx*LX/2, 0, HR), (sx*LX/2, -LY/2 - 0.05, WH)]
        faces = [(4, 2, 1, 0), (4, 3, 2)]
        g = mesh_obj(f"TLS_Cottage_Gable{sx}", np.asarray(verts), faces, mat=M["stone"], coll=COT)
        m = g.modifiers.new("sol", 'SOLIDIFY'); m.thickness = T; m.offset = 0
    # roof slopes (pitch from HR: rise = HR - WH over half-span LY/2)
    rise = HR - WH
    half = LY / 2 + 0.35
    SLEN = _m.hypot(half, rise)
    pitch = _m.atan2(rise, half)
    for zi, sgn in enumerate((-1, 1)):
        hfR = EV.slate_roof_hf(w=LX + 1.0, d=SLEN + 0.25, rows=14, seed=4 + zi, nx=120, ny=52)
        roof = grid_mesh(f"TLS_Cottage_Roof{zi}", LX + 1.0, SLEN + 0.25, hfR, M["slate"], COT, thickness=0.07)
        roof.rotation_euler = (sgn * pitch, 0, 0)
        roof.location = (0, sgn * (half / 2 + 0.02) * _m.cos(pitch) * 0 - sgn * 0.0, WH + rise / 2 + 0.05)
        roof.location = (0, sgn * half / 2 * 1.0 - sgn * 0.0, WH + rise / 2 + 0.05)
    # ridge cap
    _box_bevel("TLS_Cottage_Ridge", (LX + 1.0, 0.30, 0.10), (0, 0, HR + 0.10), M["slate"], COT, seed=55)
    # chimney on ridge
    ch = EV.build_chimney(COT, M, seed=11)
    for o in ch:
        o.location = (2.4, 0, HR - 0.4 + o.location.z)
    # door + window fitted into openings
    dr = EV.build_door(COT, M, seed=6)
    for o in dr:
        o.location = (o.location.x - LX/2 + 2.4 + 0.475, -LY/2 + 0.02, o.location.z)
    win = EV.build_window(COT, M, seed=8)
    for o in win:
        o.location = (o.location.x - LX/2 + 4.8 + 0.40, -LY/2 + 0.02, o.location.z)
    # interior furniture
    _box_bevel("TLS_Cottage_Hearth", (1.6, 0.5, 1.5), (0, LY/2 - 0.35, 0.75), M["stone"], COT, seed=61)
    _box_bevel("TLS_Cottage_Table", (1.4, 0.8, 0.08), (0.5, 0.2, 0.74), M["oak"], COT, seed=62)
    for lx, ly in ((-0.6, -0.3), (0.6, -0.3), (-0.6, 0.3), (0.6, 0.3)):
        _box_bevel(f"TLS_Cottage_TableLeg{lx}{ly}", (0.07, 0.07, 0.72), (0.5 + lx, 0.2 + ly, 0.36), M["oak"], COT, seed=63)
    _box_bevel("TLS_Cottage_Bench", (1.3, 0.32, 0.06), (0.5, -0.5, 0.44), M["oak"], COT, seed=64)
    _box_bevel("TLS_Cottage_Bed", (1.9, 1.15, 0.35), (-2.3, 1.4, 0.28), M["oak"], COT, seed=65)
    ucx_from([o for o in COT.objects if o.name.startswith("TLS_Cottage_Back") or o.name.startswith("TLS_Cottage_Front")],
             "UCX_TLS_Cottage_Walls", COT)
    save_export(COT, "tls_env_010_sin_eater_cottage", "tls_env_010_sin_eater_cottage", stats,
                "Josiah cottage: walls/roof/gables/chimney/interior + UCX")

    # ---------------- 3. St Cynog church
    log("church...")
    CH = C("Church")
    # nave floor
    fl = grid_mesh("TLS_Church_Floor", 6.4, 14.4, np.zeros((10, 6)), M["stone"], CH, plane="xy", base_off=0.05, thickness=0.2)
    # nave walls (3 full-length segments per side)
    for i, sx in enumerate((-3.0, 3.0)):
        for k, yc in enumerate((-4.8, 0.0, 4.8)):
            hf, _ = rubble_stone_hf(w=4.8, h=3.4, courses=11, seed=70 + i * 3 + k, nx=68, nz=48)
            w = grid_mesh(f"TLS_Church_NaveWall{i}{k}", 4.8, 3.4, hf, M["stone"], CH, thickness=0.30)
            w.rotation_euler = (0, 0, math.pi / 2)
            w.location = (sx, yc, 0)
    # west wall + tower
    hf, _ = rubble_stone_hf(w=6.0, h=3.4, courses=11, seed=80, nx=80, nz=48)
    ww = grid_mesh("TLS_Church_WestWall", 6.0, 3.4, hf, M["stone"], CH, thickness=0.30)
    ww.location = (0, -7.25, 0)
    tow = _box_bevel("TLS_Church_Tower", (3.2, 3.2, 8.0), (0, -8.9, 4.0), M["stone"], CH, seed=81)
    for k in range(3):
        _box_bevel(f"TLS_Church_TowerLedge{k}", (3.5, 3.5, 0.18), (0, -8.9, 2.6 + k * 1.7), M["stone"], CH, seed=82 + k)
    spire = _box_bevel("TLS_Church_TowerRoof", (3.0, 3.0, 2.2), (0, -8.9, 9.1), M["slate"], CH, seed=85)
    # buttresses
    for sx in (-1, 1):
        for y in (-4.6, 0, 4.6):
            _box_bevel(f"TLS_Church_Buttress{sx}{y}", (0.5, 0.7, 3.2), (sx * 3.35, y, 1.6), M["stone"], CH, seed=90 + int(sx) * 3 + int(y))
    # roof (pitch ~32deg from wall top 3.4)
    rise_c, half_c = 2.1, 3.35
    SLEN_c = math.hypot(half_c, rise_c)
    pitch_c = math.atan2(rise_c, half_c)
    for zi, sgn in enumerate((-1, 1)):
        hfR = EV.slate_roof_hf(w=14.6, d=SLEN_c + 0.25, rows=16, seed=92 + zi, nx=150, ny=52)
        roof = grid_mesh(f"TLS_Church_Roof{zi}", 14.6, SLEN_c + 0.25, hfR, M["slate"], CH, thickness=0.08)
        roof.rotation_euler = (sgn * pitch_c, 0, 0)
        roof.location = (0, sgn * half_c / 2, 3.4 + rise_c / 2 + 0.05)
    _box_bevel("TLS_Church_Ridge", (14.6, 0.32, 0.10), (0, 0, 3.4 + rise_c + 0.10), M["slate"], CH, seed=93)
    # east chancel wall + windows (gothic-ish pointed = two boxes + diamond)
    hf, _ = rubble_stone_hf(w=6.0, h=3.4, courses=11, seed=95, nx=80, nz=48)
    ew = grid_mesh("TLS_Church_EastWall", 6.0, 3.4, hf, M["stone"], CH, thickness=0.30)
    ew.location = (0, 7.25, 0)
    # windows: pointed arch frames on both sides (simplified gothic)
    for sx in (-1, 1):
        for y in (-4.0, 0.5, 4.5):
            fr = _box_bevel(f"TLS_Church_WinF{sx}{y}", (0.12, 1.0, 1.7), (sx * 3.0, y, 1.9), M["oak"], CH, seed=96)
            gl = _box_bevel(f"TLS_Church_WinG{sx}{y}", (0.06, 0.8, 1.5), (sx * 2.93, y, 1.9), M["glass"], CH, seed=97)
            gl.data.materials.clear(); gl.data.materials.append(M["glass"])
    # west door
    dr = EV.build_door(CH, M, seed=6)
    for o in dr:
        o.rotation_euler = (0, 0, math.pi / 2)
        o.location = (-2.95 if o.location.x == 0 else -3.0, -7.25 + o.location.x, o.location.z)
    # interior: pews x6, pulpit, altar, font
    for r in range(4):
        for sx in (-1, 1):
            _box_bevel(f"TLS_Church_Pew{r}{sx}", (0.34, 2.6, 0.06), (sx * 1.5, -2.0 + r * 2.0, 0.42), M["oak"], CH, seed=100 + r * 2 + int(sx > 0))
            _box_bevel(f"TLS_Church_PewBack{r}{sx}", (0.06, 2.6, 0.60), (sx * 1.67, -2.0 + r * 2.0, 0.72), M["oak"], CH, seed=110 + r * 2 + int(sx > 0))
            for ly in (-1.15, 1.15):
                _box_bevel(f"TLS_Church_PewLeg{r}{sx}{ly}", (0.30, 0.08, 0.39), (sx * 1.5, -2.0 + r * 2.0 + ly, 0.195), M["oak"], CH, seed=120 + r * 4 + int(sx > 0) * 2 + int(ly > 0))
    _box_bevel("TLS_Church_Altar", (1.5, 0.8, 1.0), (0, 6.4, 0.55), M["stone"], CH, seed=120)
    _box_bevel("TLS_Church_Pulpit", (0.7, 0.7, 1.2), (1.9, 4.8, 0.65), M["oak"], CH, seed=121)
    import bpy as _bp
    _bp.ops.mesh.primitive_cylinder_add(radius=0.35, depth=0.9, location=(-1.9, 4.8, 0.5), vertices=16)
    font = _bp.context.active_object
    font.name = "TLS_Church_Font"
    font.data.materials.append(M["stone"])
    for c in list(font.users_collection):
        c.objects.unlink(font)
    CH.objects.link(font)
    ucx_from([ww, tow], "UCX_TLS_Church_West", CH)
    save_export(CH, "tls_env_020_church", "tls_env_020_church", stats,
                "St Cynog: nave+tower+buttresses+interior (pews/altar/pulpit/font)")

    # ---------------- 4. cemetery
    log("cemetery...")
    CE = C("Cemetery")
    styles = ["round", "cross", "chest", "obelisk", "broken", "slate"]
    pos = [(-2.2, 1.2, 0.1), (-0.7, 2.0, 0.05), (0.9, 1.4, 0.12), (2.1, 2.2, 0.07),
           (-1.6, 3.4, 0.09), (0.5, 3.6, 0.06)]
    for i, (st, (x, y, z)) in enumerate(zip(styles, pos)):
        parts = EV.build_gravestone(f"TLS_Cem_Grave{i}", st, CE, M, seed=130 + i)
        rot = 0.15 * ((i % 3) - 1)
        for o in parts:
            o.location = (o.location.x + x, o.location.y + y, o.location.z + z)
            o.rotation_euler.z += rot
    # boundary wall (low) 3 segments
    for i in range(3):
        hf, _ = rubble_stone_hf(w=4.8, h=1.1, courses=4, seed=140 + i, nx=70, nz=18)
        w = grid_mesh(f"TLS_Cem_Wall{i}", 4.8, 1.1, hf, M["stone"], CE, thickness=0.30)
        w.location = (-4.8 + i * 4.8, -2.5, 0)
    # iron gate
    for i in range(7):
        _box_bevel(f"TLS_Cem_GateBar{i}", (0.04, 0.04, 1.25), (-1.05 + i * 0.32, -2.5, 0.72), M["iron"], CE, seed=150 + i)
    _box_bevel("TLS_Cem_GateFrameT", (2.3, 0.06, 0.07), (0, -2.5, 1.38), M["iron"], CE, seed=160)
    _box_bevel("TLS_Cem_GateFrameB", (2.3, 0.06, 0.07), (0, -2.5, 0.12), M["iron"], CE, seed=161)
    # ground path + yew tree
    pa = grid_mesh("TLS_Cem_Path", 1.4, 9.0, (EV.fbm3(np.linspace(0, 3, 20), 0.5, 0.5, 2, 7)[None, :].repeat(40, 0) - 0.5) * 0.05, M["dirt"], CE, plane="yz", base_off=0.02, thickness=0.05)
    tree = EV.build_tree("TLS_Cem_Yew", CE, M, seed=155, h=7.0)
    for o in tree:
        o.location = (3.6, 3.0, 0)
    save_export(CE, "tls_env_106_kit_graveyard_v2", "tls_env_106_kit_graveyard_v2", stats,
                "cemetery: 6 grave styles + wall + iron gate + path + yew")

    # ---------------- 5. nature set
    log("nature...")
    NA = C("Nature")
    for i in range(3):
        r = EV.build_rock(f"TLS_Nat_Rock{i}", 0.8 + i * 0.35, 170 + i, NA, M)
        r.location = (i * 1.6, 0, 0)
    for i, sd in enumerate((3, 9)):
        tr = EV.build_tree(f"TLS_Nat_Tree{i}", NA, M, seed=sd, h=5.5 + i * 1.8)
        for o in tr:
            o.location.x += i * 5.0 - 2.0
            o.location.y += 4.0
    # grass tufts: displaced cones clusters
    for g in range(3):
        parts = []
        for k in range(9):
            import bpy as bp
            bp.ops.mesh.primitive_cone_add(vertices=5, radius1=0.035, radius2=0.0,
                                           depth=0.28, location=(g * 2.0 - 1.0 + np.random.uniform(-0.14, 0.14),
                                                                  1.6 + np.random.uniform(-0.14, 0.14),
                                                                  0.14),
                                           rotation=(np.random.uniform(-0.3, 0.3), np.random.uniform(-0.3, 0.3), 0))
            o = bp.context.active_object
            o.name = f"TLS_Nat_Grass{g}_{k}"
            o.data.materials.append(M["leaves"])
            for c in list(o.users_collection):
                c.objects.unlink(o)
            NA.objects.link(o)
    save_export(NA, "tls_env_107_kit_nature_v2", "tls_env_107_kit_nature_v2", stats,
                "nature: 3 rocks + 2 trees + grass tufts")

    os.makedirs(f"{EXP}/stats", exist_ok=True)
    with open(f"{EXP}/stats/env_batch_v2.json", "w") as f:
        json.dump(stats, f, indent=1)
    log("ALL ENV DONE:", {k: v["tris"] for k, v in stats.items()})

main()
