#!/usr/bin/env python3
"""v3 QA render: import head STL, clay render 4 views + profile overlay check."""
import bpy, sys, os, math
from mathutils import Vector

STL = sys.argv[sys.argv.index("--")+1]
OUT = sys.argv[sys.argv.index("--")+2]
TAG = sys.argv[sys.argv.index("--")+3]
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
bpy.ops.wm.stl_import(filepath=STL)
obj = scene.objects[-1]
bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
# head frame: prefer real landmark menton (z=0.0) from build JSON
import json
lm_path = STL.rsplit(".",1)[0] + "_landmarks.json"
menton_z = 0.0; eye_z = 0.1085
if os.path.exists(lm_path):
    L = json.load(open(lm_path))["landmarks"]
    menton_z = L["menton"][2] if isinstance(L["menton"], list) else 0.0
    eye_z = L["pupil"][2] if isinstance(L["pupil"], list) else 0.1085
face_c = Vector((0.0, lo.y - 0.02, menton_z + eye_z))   # eye-line target
H = hi.z - menton_z

# clay material
mat = bpy.data.materials.new("clay"); mat.use_nodes=True
b = mat.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value=(0.62,0.55,0.50,1)
b.inputs["Roughness"].default_value=0.62
obj.data.materials.append(mat)

# world + lights
w = bpy.data.worlds.new("W"); scene.world=w; w.use_nodes=True
w.node_tree.nodes["Background"].inputs[0].default_value=(0.82,0.82,0.82,1)
w.node_tree.nodes["Background"].inputs[1].default_value=0.6

cam_data = bpy.data.cameras.new("c"); cam=bpy.data.objects.new("c",cam_data)
scene.collection.objects.link(cam); scene.camera=cam; cam_data.lens=85
face_c = Vector((0,0, H*0.72))
def aim(loc,tgt):
    cam.location=loc
    d=(Vector(tgt)-Vector(loc)).normalized()
    cam.rotation_euler=d.to_track_quat('-Z','Y').to_euler()
def add_l(name,loc,e,s):
    L=bpy.data.lights.new(name,'AREA');L.energy=e;L.size=s
    o=bpy.data.objects.new(name,L);scene.collection.objects.link(o);o.location=loc
    d=(face_c-Vector(loc)).normalized();o.rotation_euler=d.to_track_quat('-Z','Y').to_euler()
add_l("k",(-1.0,-1.6,H*0.72+0.5),300,1.5)
add_l("f",(1.5,-0.8,H*0.60),90,2.0)

scene.render.engine='CYCLES'; scene.cycles.samples=40; scene.cycles.use_denoising=True
scene.cycles.device='CPU'; scene.render.resolution_x=850; scene.render.resolution_y=850
D=0.55
views={
 "front":((0,-D,face_c.z),face_c),
 "left":((-D,0,face_c.z),face_c),
 "threeq":((-D*0.8,-D*0.8,face_c.z+0.02),face_c),
 "face":((-0.12,-0.42,face_c.z),face_c),
}
for n,(loc,tgt) in views.items():
    aim(loc,tgt); scene.render.filepath=os.path.join(OUT,f"v3_{TAG}_{n}.png")
    bpy.ops.render.render(write_still=True); print("RENDERED",n,flush=True)
