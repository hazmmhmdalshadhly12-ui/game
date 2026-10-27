#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M4 evidence renderer: opens a saved .blend, auto-frames the scene,
adds a temporary sun+sky rig, renders 3/4 + front PNGs. Never saves.
Run: blender -b <file.blend> --python b_render.py -- --out <dir> [--res 960x540]
     [--shots three_quarter,front,side] [--samples 24] [--angle 25]
"""
import bpy, sys, os, math
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import tls_lib as L

def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    o, i = {}, 0
    while i < len(argv):
        if argv[i].startswith("--"):
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                o[argv[i][2:]] = argv[i + 1]; i += 2
            else:
                o[argv[i][2:]] = True; i += 1
        else:
            i += 1
    return o

def scene_bbox():
    objs = [o for o in bpy.context.scene.objects
            if o.type == 'MESH' and "UCX_" not in o.name]
    if not objs:
        return None
    dg = bpy.context.evaluated_depsgraph_get()
    mins = Vector((1e9,) * 3); maxs = Vector((-1e9,) * 3)
    for o in objs:
        if o.hide_render:
            continue
        eo = o.evaluated_get(dg)
        me = eo.to_mesh()
        for v in me.vertices:
            w = eo.matrix_world @ v.co
            mins.x = min(mins.x, w.x); mins.y = min(mins.y, w.y); mins.z = min(mins.z, w.z)
            maxs.x = max(maxs.x, w.x); maxs.y = max(maxs.y, w.y); maxs.z = max(maxs.z, w.z)
        eo.to_mesh_clear()
    return mins, maxs

def main():
    o = parse()
    out = o.get("out", "/tmp/render")
    res = o.get("res", "960x540")
    shots = o.get("shots", "three_quarter,front,side").split(",")
    samples = int(o.get("samples", 24))
    os.makedirs(out, exist_ok=True)
    w, h = (int(x) for x in res.split("x"))

    bb = scene_bbox()
    if bb is None:
        print("[render] no renderable meshes - skip")
        return
    mins, maxs = bb
    center = (mins + maxs) / 2
    size = max((maxs - mins).x, (maxs - mins).y, (maxs - mins).z, 0.05)
    dist = size * 1.9 + 0.35

    # world + sun
    world = bpy.data.worlds.get("TLS_World")
    if world is None:
        world = bpy.data.worlds.new("TLS_World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.62, 0.67, 0.74, 1.0)
        bg.inputs[1].default_value = 0.55
    sun = bpy.data.lights.new("TLS_Sun", 'SUN')
    sun.energy = 3.2
    sun.angle = math.radians(6)
    sun.color = (0.95, 0.94, 0.90)
    sun_ob = bpy.data.objects.new("TLS_Sun", sun)
    sun_ob.rotation_euler = (math.radians(55), 0, math.radians(-40))
    bpy.context.scene.collection.objects.link(sun_ob)
    fill = bpy.data.lights.new("TLS_Fill", 'AREA')
    fill.energy = max(30, size * 60)
    fill.size = size * 1.6
    fill.color = (0.70, 0.75, 0.85)
    fill_ob = bpy.data.objects.new("TLS_Fill", fill)
    fill_ob.location = center + Vector((-dist * 0.7, -dist * 0.4, size * 0.9))
    bpy.context.scene.collection.objects.link(fill_ob)
    d = Vector((0, 0, center.z + size * 0.2)) - fill_ob.location
    fill_ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

    # ground plane to catch shadows (only if asset doesn't sit on one)
    gname = "TLS_RenderGround"
    if gname not in bpy.data.objects:
        g = L.box(gname, size * 4, size * 4, 0.01, cz=-0.005,
                  coll="TLS_Render")
        gm = L.new_mat("TLS_RenderGround", base=(0.30, 0.32, 0.30), rough=0.9)
        g.data.materials.append(gm)
        g.hide_render = False

    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.image_settings.file_format = 'PNG'
    sc.render.film_transparent = False

    cam_data = bpy.data.cameras.new("TLS_Cam")
    cam_data.lens = 50
    cam = bpy.data.objects.new("TLS_Cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    sc.camera = cam

    for shot in shots:
        if shot == "front":
            az = math.radians(180)
            el = math.radians(8)
        elif shot == "side":
            az = math.radians(90)
            el = math.radians(8)
        else:  # three_quarter
            az = math.radians(135)
            el = math.radians(20)
        cd = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el),
                     math.sin(el))) * dist
        cam.location = center + cd + Vector((0, 0, size * 0.12))
        d = center - cam.location
        cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        cam_data.lens = max(28, min(85, 1300 * size / max(dist, 0.5) / 40))
        p = os.path.join(out, f"{shot}.png")
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        print(f"[render] {p}")

main()
