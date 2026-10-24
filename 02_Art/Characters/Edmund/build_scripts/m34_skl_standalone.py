#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create standalone rig-only .blend (TLS-SKL-001) + armature-only FBX."""
import bpy, sys, os

args = sys.argv[sys.argv.index("--") + 1:]
out_blend = args[args.index("--blend") + 1]
out_fbx = args[args.index("--fbx") + 1]

# remove all mesh objects, keep the armature (+ its action-less pose)
for o in list(bpy.data.objects):
    if o.type == 'MESH':
        bpy.data.objects.remove(o, do_unlink=True)
# drop orphan meshes/images
for me in list(bpy.data.meshes):
    if me.users == 0:
        bpy.data.meshes.remove(me)
for im in list(bpy.data.images):
    if im.users == 0:
        bpy.data.images.remove(im)

os.makedirs(os.path.dirname(out_blend), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=out_blend, compress=True)
print("[SKL] saved", out_blend, os.path.getsize(out_blend) / 1e6, "MB")

arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
bpy.ops.object.select_all(action='DESELECT')
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.export_scene.fbx(
    filepath=out_fbx, use_selection=True,
    axis_forward='-Y', axis_up='Z',
    apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
    global_scale=1.0,
    object_types={'ARMATURE'},
    add_leaf_bones=False, bake_anim=False)
print("[SKL] exported", out_fbx, os.path.getsize(out_fbx) / 1e6, "MB")
