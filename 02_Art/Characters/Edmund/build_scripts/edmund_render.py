#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M3.4 - renders of the ACTUAL Edmund model (Cycles CPU, headless).
Non-destructive: opens the saved .blend, adds temporary studio/cinema rig +
subdivision for display, renders PNGs, never saves the .blend.
Run:
  blender -b <blend> --python edmund_render.py -- --mode neutral \
      --shots front,side,back --out <dir> [--samples N] [--res 1280x720]
"""
import bpy, sys, os, math, json
from mathutils import Vector, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from edmund_lib import new_mesh_obj, loft_rings, TAU

def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts, i = {}, 0
    while i < len(argv):
        if argv[i].startswith("--"):
            opts[argv[i][2:]] = argv[i + 1]; i += 2
        else: i += 1
    return opts

# ---------------------------------------------------------------- set build
def build_cyclorama(mat):
    rings = []
    R = 4.8
    WALL_H = 4.2
    prof = [(R, 0.0)]
    for k in range(1, 9):
        a = (k / 8) * (math.pi / 2)
        prof.append((R - 1.2 + math.cos(a) * 1.2, math.sin(a) * 1.2))
    for k in range(5):
        prof.append((R - 1.2, 1.2 + (WALL_H - 1.2) * (k + 1) / 5))
    rr = []
    for r, z in prof:
        rr.append({"verts": [(r * math.cos(TAU * i / 48), r * math.sin(TAU * i / 48), z)
                             for i in range(48)]})
    v, f, u = loft_rings(rr, closed_loop=True)
    o = new_mesh_obj("TLS_Studio_Cyc", v, f, uvs=u, mat=mat, coll="Stage")
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.flip_normals()
    bpy.ops.object.mode_set(mode='OBJECT')
    return o

def aim(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

def add_light(name, loc, energy, size, color=(1, 1, 1), spot=None):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energy
    ld.size = size
    ld.color = color
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    bpy.context.scene.collection.objects.link(ob)
    aim(ob, (0, 0, 1.05))
    return ob

def add_camera(name, loc, target, lens=50):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.02
    ob = bpy.data.objects.new(name, cd)
    ob.location = loc
    bpy.context.scene.collection.objects.link(ob)
    aim(ob, target)
    return ob

def clear_stage():
    for o in list(bpy.data.objects):
        if o.name.startswith("TLS_Stage_") or o.name.startswith("TLS_Studio_") \
           or o.name.startswith("TLS_Cine_") or o.type == 'CAMERA' or o.type == 'LIGHT':
            bpy.data.objects.remove(o, do_unlink=True)

def setup_neutral():
    mats = bpy.data.materials
    bm = mats.get("TLS_Studio_Backdrop")
    build_cyclorama(bm)
    w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.055, 0.056, 0.06, 1)
        bg.inputs[1].default_value = 1.0
    add_light("TLS_Stage_Key", (2.4, -2.6, 2.7), 420, 2.4)
    add_light("TLS_Stage_Fill", (-3.0, -1.6, 1.9), 95, 3.0)
    add_light("TLS_Stage_Rim", (-0.6, 2.9, 2.3), 220, 1.8)
    add_light("TLS_Stage_Top", (0.4, -0.4, 3.4), 130, 2.0)

def setup_cinematic():
    w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.0035, 0.0045, 0.008, 1)
        bg.inputs[1].default_value = 1.0
    # ground
    gm = bpy.data.materials.get("TLS_Cine_Ground")
    v = [(-6, -6, 0), (6, -6, 0), (6, 6, 0), (-6, 6, 0)]
    new_mesh_obj("TLS_Cine_GroundPlane", v, [(0, 1, 2, 3)], mat=gm, coll="Stage")
    # volumetric fog cube
    fm = bpy.data.materials.new("TLS_Cine_Fog")
    fm.use_nodes = True
    nt2 = fm.node_tree
    for n in list(nt2.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt2.nodes.remove(n)
    outn = next(n for n in nt2.nodes if n.type == 'OUTPUT_MATERIAL')
    scat = nt2.nodes.new('ShaderNodeVolumeScatter')
    scat.inputs['Density'].default_value = 0.012
    scat.inputs['Anisotropy'].default_value = 0.3
    nt2.links.new(scat.outputs['Volume'], outn.inputs['Volume'])
    fv = [(-4, -4, 0.01), (4, -4, 0.01), (4, 4, 0.01), (-4, 4, 0.01),
          (-4, -4, 3.2), (4, -4, 3.2), (4, 4, 3.2), (-4, 4, 3.2)]
    faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5),
             (2, 3, 7, 6), (3, 0, 4, 7)]
    new_mesh_obj("TLS_Cine_FogCube", fv, faces, mat=fm, coll="Stage")
    # lights: warm low key (lantern feel), cool rim, faint fill
    k = add_light("TLS_Stage_Key", (1.15, -1.75, 1.75), 130, 0.9, color=(1.0, 0.63, 0.36))
    r = add_light("TLS_Stage_Rim", (-1.7, 2.3, 2.1), 260, 1.2, color=(0.45, 0.58, 1.0))
    f = add_light("TLS_Stage_Fill", (0.0, -3.2, 0.7), 14, 2.5, color=(0.55, 0.6, 0.7))
    pt = bpy.data.lights.new("TLS_Stage_LanternPt", 'POINT')
    pt.energy = 9; pt.color = (1.0, 0.55, 0.25); pt.shadow_soft_size = 0.05
    pob = bpy.data.objects.new("TLS_Stage_LanternPt", pt)
    pob.location = (0.42, -0.72, 1.02)
    bpy.context.scene.collection.objects.link(pob)

CAMS = {
    "front":       ((0.0, -4.15, 0.98), (0.0, 0.0, 0.95), 55),
    "side":        ((4.15, -0.05, 0.98), (0.0, 0.0, 0.95), 55),
    "back":        ((0.0, 4.15, 0.98), (0.0, 0.0, 0.95), 55),
    "three_quarter": ((2.55, -3.15, 1.10), (0.02, 0.0, 0.98), 55),
    "face_closeup": ((0.10, -0.58, 1.688), (0.0, -0.02, 1.679), 78),
    "materials":   ((0.52, -0.92, 1.34), (0.02, -0.02, 1.13), 70),
    "rig_apose":   ((1.15, -3.9, 1.35), (0.0, 0.0, 0.97), 55),
    "rig_readiness": ((0.0, -4.15, 0.98), (0.0, 0.0, 0.95), 55),
    "head_side":   ((-0.62, 0.05, 1.672), (0.0, -0.03, 1.663), 60),
    "cinematic":   ((1.55, -2.75, 1.42), (-0.05, 0.05, 1.28), 35),
}

def apply_test_pose():
    pj = "/home/z/my-project/m34_out/rig_test_pose.json"
    if not os.path.exists(pj):
        return False
    arm = bpy.data.objects.get("TLS_Rig_Human_Edmund")
    if not arm:
        return False
    with open(pj) as f:
        pose = json.load(f)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')
    for bname, rot in pose.items():
        pb = arm.pose.bones.get(bname)
        if pb:
            pb.rotation_mode = 'XYZ'
            pb.rotation_euler = rot
    bpy.context.view_layer.update()
    return True

def clear_pose():
    arm = bpy.data.objects.get("TLS_Rig_Human_Edmund")
    if not arm:
        return
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')
    for pb in arm.pose.bones:
        pb.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()

def add_subsurf():
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name.startswith("Edmund_"):
            m = o.modifiers.new("TmpSubsurf", 'SUBSURF')
            m.levels = 0
            m.render_levels = 1

def main():
    opts = parse_args()
    mode = opts.get("mode", "neutral")
    shots = opts.get("shots", "front").split(",")
    outdir = opts.get("out", "/home/z/my-project/m34_out/renders")
    samples = int(opts.get("samples", "96"))
    res = opts.get("res", "1280x720")
    square = {"face_closeup", "materials"}

    os.makedirs(outdir, exist_ok=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
        sc.cycles.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
    except Exception:
        pass
    sc.render.image_settings.file_format = 'PNG'
    sc.render.resolution_percentage = 100
    try:
        sc.view_settings.view_transform = 'AgX'
        if mode == "cine":
            sc.view_settings.look = 'AgX - Punchy'
        else:
            sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception as e:
        print("view transform warn:", e)

    clear_stage()
    if mode == "neutral":
        setup_neutral()
    else:
        setup_cinematic()
    add_subsurf()

    rx, ry = (int(x) for x in res.split("x"))
    posed = False
    for shot in shots:
        if shot not in CAMS:
            print("unknown shot", shot); continue
        loc, tgt, lens = CAMS[shot]
        cam = add_camera(f"Cam_{shot}", loc, tgt, lens)
        sc.camera = cam
        if shot == "rig_readiness" and not posed:
            clear_pose()
            posed = apply_test_pose()
        elif shot == "rig_apose" and posed:
            clear_pose()
            posed = False
        res_x, res_y = (1024, 1024) if shot in square else (rx, ry)
        sc.render.resolution_x = res_x
        sc.render.resolution_y = res_y
        path = os.path.join(outdir, f"edmund_{shot}.png")
        sc.render.filepath = path
        import time
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"[RENDER] {shot} -> {path} ({os.path.getsize(path)/1e6:.2f} MB, {time.time()-t0:.0f}s)")
    clear_pose()
    print("[RENDER] all done")

main()
