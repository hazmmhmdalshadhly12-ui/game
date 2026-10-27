#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Doc renders for Edmund v2: studio stage + Cycles CPU. Views configurable."""
import bpy, os, sys, math, json
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = {}
i = 0
while i < len(argv):
    if argv[i].startswith("--"):
        opts[argv[i][2:]] = argv[i + 1]; i += 2
    else: i += 1

BLEND = opts.get("blend")
OUT = opts.get("out", "/home/z/my-project/repo/02_Art/renders/edmund_v002")
SHOTS = opts.get("shots", "front,threeq,side,back,face").split(",")
SAMPLES = int(opts.get("samples", "48"))
RES = opts.get("res", "1024x768")
WIREFRAME = opts.get("wire", "1") == "1"
ENGINE = opts.get("engine", "cycles")

bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = map(int, RES.split("x"))
sc.render.image_settings.file_format = 'PNG'

# stage: cyclorama
import numpy as np
def cyc():
    R, H = 5.0, 4.0
    prof = [(R, 0.0)]
    for k in range(1, 9):
        a = (k / 8) * (math.pi / 2)
        prof.append((R - 1.4 + math.cos(a) * 1.4, math.sin(a) * 1.4))
    for k in range(4):
        prof.append((R - 1.4, 1.4 + (H - 1.4) * (k + 1) / 4))
    verts, faces = [], []
    NR = 40
    for r, z in prof:
        for k in range(NR):
            a = 2 * math.pi * k / NR
            verts.append((r * math.cos(a), r * math.sin(a), z))
    for i in range(len(prof) - 1):
        for k in range(NR):
            k2 = (k + 1) % NR
            faces.append((i * NR + k, i * NR + k2, (i + 1) * NR + k2, (i + 1) * NR + k))
    me = bpy.data.meshes.new("Cyc")
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new("Cyc", me)
    sc.collection.objects.link(ob)
    m = bpy.data.materials.new("CycM"); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.42, 0.42, 0.44, 1)
    b.inputs["Roughness"].default_value = 0.9
    me.materials.append(m)
    # flip normals inward
    import bmesh
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    return ob

cyc()

def add_light(name, loc, energy, size, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy, ld.size, ld.color = energy, size, color
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    sc.collection.objects.link(ob)
    d = Vector((0, 0, 1.0)) - Vector(loc)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return ob

add_light("Key", (2.2, -2.6, 2.6), 600, 2.0, (1.0, 0.97, 0.92))
add_light("Fill", (-2.8, -1.6, 1.6), 220, 3.0, (0.85, 0.9, 1.0))
add_light("Rim", (0.5, 2.6, 2.4), 500, 1.6, (1.0, 0.98, 0.9))

def add_cam(name, loc, target, lens=50):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_start = 0.02
    ob = bpy.data.objects.new(name, cd)
    ob.location = loc
    sc.collection.objects.link(ob)
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return ob

# hide stage for wireframe
CHAR = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith("Cyc")]

VIEWS = {
    "front":  ((0, -3.2, 1.05), (0, 0, 0.95), 50),
    "threeq": ((1.9, -2.6, 1.15), (0, 0, 0.95), 50),
    "side":   ((3.1, -0.2, 1.05), (0, 0, 0.95), 50),
    "back":   ((0, 3.2, 1.05), (0, 0, 0.95), 50),
    "face":   ((0.16, -0.62, 1.70), (0.0, -0.09, 1.685), 85),
    "face_side": ((0.62, -0.10, 1.69), (0.0, -0.09, 1.685), 85),
}

if ENGINE == "cycles":
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    sc.cycles.device = 'CPU'
else:
    sc.render.engine = 'BLENDER_WORKBENCH'

os.makedirs(OUT, exist_ok=True)
for shot in SHOTS:
    shot = shot.strip()
    if shot not in VIEWS:
        continue
    loc, tgt, lens = VIEWS[shot]
    cam = add_cam(f"Cam_{shot}", loc, tgt, lens)
    sc.camera = cam
    if WIREFRAME and ENGINE == "workbench":
        pass
    sc.render.filepath = os.path.join(OUT, f"tls_chr_001_v002_{shot}.png")
    bpy.ops.render.render(write_still=True)
    print("[RENDER]", shot, "->", sc.render.filepath, flush=True)

if WIREFRAME and ENGINE == "cycles":
    # workbench wireframe pass (fast, honest geometry view)
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'MATERIAL'
    sc.display.shading.show_cavity = True
    sc.display.shading.show_wireframes = True
    sc.display.shading.wireframe_opacity = 0.5
    for shot in ("threeq", "face"):
        loc, tgt, lens = VIEWS[shot]
        cam = add_cam(f"CamW_{shot}", loc, tgt, lens)
        sc.camera = cam
        sc.render.filepath = os.path.join(OUT, f"tls_chr_001_v002_{shot}_wire.png")
        bpy.ops.render.render(write_still=True)
        print("[RENDER]", shot, "wire ->", sc.render.filepath, flush=True)
print("[RENDER DONE]")
