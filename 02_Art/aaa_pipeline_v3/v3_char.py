#!/usr/bin/env python3
"""v3 character assembly (runs inside Blender):
head STL + real eyeballs (sclera/cornea/iris/pupil) + hair cards with alpha
flow + eyebrows + SSS skin material with zone-tinted albedo -> renders + GLB.
Usage: blender -b -P v3_char.py -- <stl> <landmarks_json> <outdir> <tag> <json_morph_overrides>
"""
import bpy, bmesh, sys, os, json, math, random
import numpy as np
from mathutils import Vector, Euler

argv = sys.argv[sys.argv.index("--")+1:]
STL, LMJ, OUT, TAG = argv[0], argv[1], argv[2], argv[3]
OVR = json.loads(argv[4]) if len(argv) > 4 else {}
os.makedirs(OUT, exist_ok=True)
random.seed(11); np.random.seed(11)

L = json.load(open(LMJ))["landmarks"]
def lm(k): return Vector(L[k])

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------------- head ----------------
bpy.ops.wm.stl_import(filepath=STL)
head = scene.objects[-1]; head.name = f"TLS_{TAG}_Head"
bpy.ops.object.select_all(action='DESELECT'); head.select_set(True); bpy.context.view_layer.objects.active = head
bpy.ops.object.shade_smooth()
m = head.modifiers.new("sm", 'SMOOTH'); m.iterations = 6; m.factor = 0.5

# ---------------- skin material with zone-tinted albedo ----------------
def zone_mask(px_coord, c, r, feather):  # px space helper
    d = np.sqrt(((px_coord - c)**2).sum(-1))
    return np.clip((r-d)/feather, 0, 1)

SZ = 1024
yy, xx = np.mgrid[0:SZ, 0:SZ]
# map head bounds to image: x: [-0.09,0.09] -> [0,SZ], z: [-0.02,0.26] -> [SZ,0]
def to_px(x, z): return ((x+0.09)/0.18*SZ, (0.26-z)/0.28*SZ)
# planar-project albedo from FRONT (good enough for bust QC; real UV in game pass)
base = np.zeros((SZ, SZ, 3), dtype=np.float32)
skin = np.array([0.72, 0.55, 0.46]); base[:] = skin
px = np.stack([xx, yy], axis=-1).astype(np.float32)
for c, r, f, tint in [
    (to_px(0, 0.0955), 90, 60, [0.16, 0.02, -0.02]),   # nose warm
    (to_px(0.070, 0.113), 55, 50, [0.12, 0.0, -0.02]),  # ears warm
    (to_px(0.040, 0.090), 80, 60, [0.10, 0.01, -0.01]), # cheeks flush
    (to_px(0.0315, 0.1085), 45, 40, [-0.16, -0.04, 0.02]),  # peri-orbital
    (to_px(0, 0.0645), 55, 30, [0.10, -0.06, -0.04]),   # lip zone
    (to_px(0, -0.010), 150, 80, [-0.05, 0.0, 0.02]),    # neck paler
]:
    cx, cy = c; w = zone_mask(px, (cx, cy), r, f)[..., None]
    base += w * np.array(tint)[None, None, :]
# mottling + freckles
rng = np.random.default_rng(7)
low = rng.normal(0, 1, (SZ//8, SZ//8, 1))
low = np.kron(low, np.ones((8, 8, 1)))[:SZ, :SZ]
base += low * np.array([0.020, 0.012, 0.010])[None, None, :]
freck = (rng.random((SZ, SZ)) > 0.9992).astype(np.float32)[..., None]
base -= freck * np.array([0.14, 0.09, 0.06])[None, None, :]
# stubble jaw zone (male): dark speckle  (Edmund: short beard)
if not OVR.get("noBeard", False):
    jc, jz = to_px(0, 0.030)
    jaw_w = zone_mask(px, (jc, jz), 140, 55)
    stub = (rng.random((SZ, SZ)) > 0.62).astype(np.float32)[..., None]
    base -= stub * jaw_w[..., None] * np.array([0.10, 0.08, 0.065])[None, None, :]
base = np.clip(base, 0, 1)
img = bpy.data.images.new("skin_bc", SZ, SZ)
img.pixels.foreach_set(np.dstack([base, np.ones((SZ, SZ, 1), dtype=np.float32)]).ravel())
img.pack()

rough = np.full((SZ, SZ), 0.52, dtype=np.float32)
rough -= 0.10*zone_mask(px, to_px(0, 0.105), 110, 70)   # T-zone gloss
rough += 0.06*zone_mask(px, to_px(0, 0.10), 200, 80)
img_r = bpy.data.images.new("skin_r", SZ, SZ); img_r.pixels.foreach_set(np.dstack([rough]*3+[np.ones_like(rough)]).ravel()); img_r.pack()

smat = bpy.data.materials.new("TLS_skin"); smat.use_nodes = True
nt = smat.node_tree; bsdf = nt.nodes["Principled BSDF"]
bsdf.inputs["Roughness"].default_value = 0.5
for k, v in [("Subsurface Weight", 0.04), ("Subsurface Radius", Vector((0.008, 0.003, 0.002))), ("Subsurface Scale", 0.008)]:
    if k in bsdf.inputs: bsdf.inputs[k].default_value = v
tb = nt.nodes.new("ShaderNodeTexImage"); tb.image = img; tb.location = (-500, 200)
nt.links.new(tb.outputs["Color"], bsdf.inputs["Base Color"])
tr = nt.nodes.new("ShaderNodeTexImage"); tr.image = img_r; tr.location = (-500, -100)
nt.links.new(tr.outputs["Color"], bsdf.inputs["Roughness"])
head.data.materials.append(smat)

# planar UV from front (bust QC)
uv = head.data.uv_layers.new(name="front_uv")
for poly in head.data.polygons:
    for li in poly.loop_indices:
        v = head.data.vertices[head.data.loops[li].vertex_index].co
        uv.data[li].uv = ((v.x+0.09)/0.18, (0.26-v.z)/0.28)

# ---------------- eyeballs ----------------
def add_uv_sphere(name, loc, r, seg=24, ring=16):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=ring, radius=r)
    bm.to_mesh(me); bm.free(); o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o); o.location = loc
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.object.shade_smooth()
    return o

eye_m = bpy.data.materials.new("sclera"); eye_m.use_nodes = True
eb = eye_m.node_tree.nodes["Principled BSDF"]
eb.inputs["Base Color"].default_value = (0.92, 0.90, 0.87, 1); eb.inputs["Roughness"].default_value = 0.15
iris_m = bpy.data.materials.new("iris"); iris_m.use_nodes = True
ib = iris_m.node_tree.nodes["Principled BSDF"]
ib.inputs["Base Color"].default_value = (0.16, 0.10, 0.05, 1); ib.inputs["Roughness"].default_value = 0.12
pupil_m = bpy.data.materials.new("pupil"); pupil_m.use_nodes = True
pb = pupil_m.node_tree.nodes["Principled BSDF"]
pb.inputs["Base Color"].default_value = (0.01, 0.01, 0.01, 1); pb.inputs["Roughness"].default_value = 0.1
cornea_m = bpy.data.materials.new("cornea"); cornea_m.use_nodes = True
cb = cornea_m.node_tree.nodes["Principled BSDF"]
cb.inputs["Base Color"].default_value = (1, 1, 1, 1)
cb.inputs["Transmission Weight"].default_value = 1.0 if "Transmission Weight" in cb.inputs else 0
cb.inputs["Roughness"].default_value = 0.03; cb.inputs["IOR"].default_value = 1.376

EYE_R = 0.0122
for s in (-1, 1):
    pup = lm('pupil'); pup.x = s*pup.x
    center = pup + Vector((0, 0.0095, 0))          # eyeball center behind pupil point
    e = add_uv_sphere(f"eyeball_{s}", center, EYE_R)
    e.data.materials.append(eye_m)
    # cornea bulge
    c = add_uv_sphere(f"cornea_{s}", pup + Vector((0, 0.002, 0)), 0.0062, seg=16, ring=12)
    c.data.materials.append(cornea_m)
    # iris + pupil discs (slightly proud of cornea)
    for nm, r_, mat, dy in [("iris", 0.0058, iris_m, 0.0052), ("pupil", 0.0024, pupil_m, 0.0056)]:
        me = bpy.data.meshes.new(f"{nm}_{s}"); bm = bmesh.new()
        bmesh.ops.create_circle(bm, cap_ends=True, segments=24, radius=r_)
        bm.to_mesh(me); bm.free(); o = bpy.data.objects.new(f"{nm}_{s}", me)
        scene.collection.objects.link(o); o.location = pup + Vector((0, dy, 0))
        o.rotation_euler = Euler((math.radians(90), 0, 0)); o.data.materials.append(mat)

# ---------------- hair cards ----------------
def hair_material(name, base_col):
    hm = bpy.data.materials.new(name); hm.use_nodes = True
    hb = hm.node_tree.nodes["Principled BSDF"]
    hb.inputs["Base Color"].default_value = (*base_col, 1)
    hb.inputs["Roughness"].default_value = 0.38
    return hm

hair_m = hair_material("TLS_hair", (0.085, 0.055, 0.035))

hg = head.data.vertices
hverts = np.array([v.co[:] for v in hg])

# --- HAIR CAP: scalp-fitted shell (guarantees hair silhouette) -------------
capverts = [v.co[:] for v in hg if v.co.z > 0.128 and np.linalg.norm(np.array(v.co[:]) - np.array([0, 0.01, 0.11])) < 0.15]
capverts = np.array(capverts)
# build cap as duplicated surface pushed slightly out along normals-ish
cap_v = capverts + (capverts - np.array([0, 0.01, 0.11])) * 0.012
cap_me = bpy.data.meshes.new("haircap")
cap_me.from_pydata(cap_v, [], [])
cap_me.update()
# trimesh pointcloud->convex hull would be wrong; instead use remesh via bmesh convex hull
cap_obj = bpy.data.objects.new("haircap", cap_me); scene.collection.objects.link(cap_obj)
bpy.context.view_layer.objects.active = cap_obj; cap_obj.select_set(True)
bpy.ops.object.select_all(action='DESELECT'); cap_obj.select_set(True)
bpy.ops.object.mode_set(mode='OBJECT')
import bmesh as _bm
bm2 = _bm.new(); bm2.from_mesh(cap_me)
_bm.ops.convex_hull(bm2, input=bm2.verts)
bm2.to_mesh(cap_me); bm2.free()
cap_obj.data.materials.append(hair_m)
bpy.ops.object.shade_smooth()
cap_solid = cap_obj.modifiers.new("sol", 'SOLIDIFY'); cap_solid.thickness = 0.004; cap_solid.offset = 1.0
cap_displace = cap_obj.modifiers.new("nse", 'DISPLACE')
tex = bpy.data.textures.new("hairnoise", 'CLOUDS'); tex.noise_scale = 0.02
cap_displace.texture = tex; cap_displace.strength = 0.006
cap_obj.name = f"TLS_{TAG}_HairCap"

def strand_card(p0, dirv, length, width, curl=0.3, seg=7):
    """Ribbon along dirv with sinusoidal curl, billboard-ish facing dir."""
    d = np.array(dirv, dtype=np.float64); d /= np.linalg.norm(d)+1e-9
    side = np.cross(d, [0, 0, 1.0])
    if np.linalg.norm(side) < 0.5: side = np.cross(d, [0, 1.0, 0])
    side /= np.linalg.norm(side)+1e-9
    up = np.cross(d, side)
    pts = []
    for k in range(seg+1):
        t = k/seg
        bend = math.sin(t*math.pi*1.4)*curl*length*0.16
        p = p0 + d*length*t + up*bend*t
        w = width*(0.35+0.65*math.sin(min(1, t*1.15)*math.pi*0.62+0.4))*(1-t*0.35)
        pts.append([p+side*w/2, p-side*w/2])
    verts = [v for pr in pts for v in pr]
    faces = []
    for k in range(seg):
        a = 2*k; faces.append((a, a+1, a+3, a+2))
    me = bpy.data.meshes.new("card"); me.from_pydata(verts, [], faces); me.update()
    o = bpy.data.objects.new("card", me); scene.collection.objects.link(o)
    o.data.materials.append(hair_m)
    return o

crown = Vector((0, 0.008, 0.205))
card_objs = []
sel = np.where((hverts[:, 2] > 0.148) & (hverts[:, 2] < 0.245))[0]
sel = sel[np.random.rand(len(sel)) < 0.16][:520]
for vi in sel:
    p = hverts[vi]
    n = p - np.array([0, 0.01, 0.11]); n = n/(np.linalg.norm(n)+1e-9)
    d = n*0.7 + np.array([0, 0.15, -0.75]); d = d/(np.linalg.norm(d)+1e-9)
    # tangent-project gravity: hair lies ON the scalp, flowing down
    g = np.array([0, 0.12, -1.0]); g = g/(np.linalg.norm(g)+1e-9)
    if n[2] > 0.82:   # crown whorl: flow outward in XY plane from apex
        t = np.array([p[0], p[1]+0.005, 0.0]); t = t/(np.linalg.norm(t)+1e-9)
    else:
        t = g - n*(g*n).sum(axis=-1, keepdims=True)
        t = t/(np.linalg.norm(t, axis=-1, keepdims=True)+1e-9)
    d = t*0.88 + n*0.12; d = d/(np.linalg.norm(d)+1e-9)
    ln = 0.028+np.random.rand()*0.045
    card_objs.append(strand_card(p+np.array([0, -0.002, 0]), d, ln, 0.0035+np.random.rand()*0.003, curl=0.25+np.random.rand()*0.3))
print("hair cards:", len(card_objs), flush=True)
# brows: two strips of short cards
brow_m = hair_material("TLS_brow", (0.10, 0.065, 0.04))
def brow_cards(side):
    io_ = lm('canthus_i'); io_.x = side*io_.x
    oo_ = lm('canthus_o'); oo_.x = side*oo_.x
    objs = []
    for k in range(34):
        t = k/33
        p = io_*(1-t)+oo_*t + Vector((0, -0.002, 0.0075 + 0.0022*math.sin(t*math.pi)))
        d = Vector((side*0.75, 0.05, -0.12)).normalized()
        ln = 0.012+np.random.rand()*0.014
        me = bpy.data.meshes.new("b"); 
        pts = []
        dd = np.array(d); dd /= np.linalg.norm(dd)
        sidev = np.cross(dd, [0, 0, 1.0]); sidev /= np.linalg.norm(sidev)+1e-9
        for kk in range(3):
            q = np.array(p) + dd*ln*kk/2
            w2 = 0.0016
            pts.append([q+sidev*w2, q-sidev*w2])
        verts = [v for pr in pts for v in pr]
        faces = [(0, 1, 3, 2), (2, 3, 5, 4)]
        me.from_pydata(verts, [], faces); me.update()
        o = bpy.data.objects.new("b", me); scene.collection.objects.link(o)
        o.data.materials.append(brow_m); objs.append(o)
    return objs
brow_cards(1); brow_cards(-1)

# ---------------- lights + world ----------------
w = bpy.data.worlds.new("W"); scene.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.58, 0.62, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.35
def add_l(name, loc, e, s):
    Lb = bpy.data.lights.new(name, 'AREA'); Lb.energy = e; Lb.size = s
    o = bpy.data.objects.new(name, Lb); scene.collection.objects.link(o); o.location = loc
    d = (Vector((0, -0.04, 0.105)) - Vector(loc)).normalized()
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
add_l("key", (-0.9, -0.9, 0.42), 150, 0.9)
add_l("fill", (1.3, -0.5, 0.16), 55, 1.6)
add_l("rim", (0.4, 0.9, 0.45), 120, 0.8)

# ---------------- cameras + renders ----------------
cam_data = bpy.data.cameras.new("c"); cam = bpy.data.objects.new("c", cam_data)
scene.collection.objects.link(cam); scene.camera = cam; cam_data.lens = 85
face_c = Vector((0, -0.05, 0.095))
scene.render.engine = 'CYCLES'; scene.cycles.samples = 40; scene.cycles.use_denoising = True
scene.cycles.device = 'CPU'; scene.render.resolution_x = 820; scene.render.resolution_y = 820
scene.view_settings.view_transform = 'Standard'; scene.view_settings.exposure = -0.55
D = 0.62
def aim(loc, tgt):
    cam.location = loc
    d = (Vector(tgt)-Vector(loc)).normalized()
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
views = {
    "front": ((0, -D, face_c.z), face_c),
    "left": ((-D*0.98, -0.06, face_c.z), face_c),
    "threeq": ((-D*0.72, -D*0.72, face_c.z+0.05), face_c),
    "back": ((0.15, 0.72, face_c.z+0.02), Vector((0, 0.02, 0.11))),
    "face": ((-0.10, -0.40, face_c.z+0.01), face_c),
}
for n, (loc, tgt) in views.items():
    aim(loc, tgt); scene.render.filepath = os.path.join(OUT, f"v3c_{TAG}_{n}.png")
    bpy.ops.render.render(write_still=True); print("RENDERED", n, flush=True)

# ---------------- export ----------------
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, f"TLS_{TAG}_head_v3.blend"))
exports = [head] + [o for o in scene.objects if o.name.startswith(("eyeball", "cornea", "iris", "pupil", "card", "b"))]
for o in exports: o.select_set(True)
bpy.context.view_layer.objects.active = head
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, f"TLS_{TAG}_head_v3.glb"), use_selection=True, export_apply=True)
print("EXPORTED", flush=True)
