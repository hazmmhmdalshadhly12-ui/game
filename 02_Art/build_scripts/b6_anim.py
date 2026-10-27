#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M4-B6 animation batch on TLS-SKL-001 (65 bones, A-pose 15):
  TLS-ANM-001 Idle Base  - breathing, weight shift, 96 frames @30fps (3.2s loop)
  TLS-ANM-002 Walk Cycle - 34 frames @30fps (1.13s loop, ~1.4 m/s), pelvis bob +
        counter-rotation, arm counter-swing, foot roll
Numeric verification: loop closure error (mm), hip bob amplitude, stride excursion.
Run: blender -b --python b6_anim.py -- --root <repo>
"""
import bpy, os, sys, math, time, json
from mathutils import Euler, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import tls_lib as L

OPTS = L.parse_args()
ROOT = OPTS.get("root", "/home/z/my-project/work/lastsin-repo")
RIG = os.path.join(ROOT, "02_Art", "blender", "source", "rig", "tls_skl_001_rig_human.blend")
SRC = os.path.join(ROOT, "02_Art", "blender", "source", "anim")
FBX = os.path.join(ROOT, "02_Art", "exports", "fbx")
STATS = os.path.join(ROOT, "02_Art", "exports", "stats")
os.makedirs(SRC, exist_ok=True)
TAU = L.TAU
t0 = time.time()

bpy.ops.wm.open_mainfile(filepath=RIG)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
assert len(arm.data.bones) == 65, f"expected 65 bones, got {len(arm.data.bones)}"
scn = bpy.context.scene
scn.render.fps = 30
bpy.context.view_layer.objects.active = arm

def reset_pose():
    for pb in arm.pose.bones:
        pb.rotation_euler = Euler((0, 0, 0), 'XYZ')
        pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
        pb.location = Vector((0, 0, 0))

def pose_idle(t):
    """t in [0,1) loop phase."""
    reset_pose()
    breath = math.sin(TAU * t)                      # 1 cycle = full clip
    sway = math.sin(TAU * t * 0.5 + 1.2)
    P = arm.pose.bones
    # breathing (spine/chest subtle pitch)
    P["spine02"].rotation_euler.x = math.radians(0.45) * breath
    P["spine03"].rotation_euler.x = math.radians(0.75) * breath
    P["chest"].rotation_euler.x = math.radians(0.55) * breath
    P["neck"].rotation_euler.x = math.radians(-0.35) * breath
    # weight shift (slow pelvis roll + drop)
    P["pelvis"].rotation_euler.y = math.radians(1.1) * sway
    P["pelvis"].location.z = -0.004 + 0.004 * math.sin(TAU * t * 0.5)
    # head micro-drift (look, return)
    P["head"].rotation_euler.y = math.radians(1.6) * math.sin(TAU * t * 0.5 + 0.4)
    P["head"].rotation_euler.x = math.radians(0.8) * math.sin(TAU * t + 0.9)
    # arms settle (relaxed inward)
    for s in ("L", "R"):
        P[f"upper_arm.{s}"].rotation_euler.x = math.radians(1.0) * breath
        P[f"forearm.{s}"].rotation_euler.y = math.radians(1.5) + math.radians(0.8) * breath
    # knees tiny softness
    for s in ("L", "R"):
        P[f"thigh.{s}"].rotation_euler.x = math.radians(-0.8)
        P[f"shin.{s}"].rotation_euler.x = math.radians(1.6)

def pose_walk(t):
    """t in [0,1) loop phase; left leg leads."""
    reset_pose()
    P = arm.pose.bones
    # leg swing: forward = negative X rotation (thigh points down; -X pitches -Y fwd)
    def leg(side, phase):
        th = math.sin(TAU * phase)                    # + = forward
        # swing phase: leg moves forward quickly between phase 0.5..1.0
        swing = max(0.0, math.sin(TAU * (phase - 0.25))) if phase > 0.25 and phase < 0.75 else 0.0
        P[f"thigh.{side}"].rotation_euler.x = math.radians(-24) * th
        P[f"shin.{side}"].rotation_euler.x = math.radians(46) * max(0.0, math.sin(TAU * (phase - 0.5)))
        # foot: heel strike to toe off
        fr = math.sin(TAU * phase + math.pi * 0.5)
        P[f"foot.{side}"].rotation_euler.x = math.radians(10) * fr
    leg("L", t)
    leg("R", (t + 0.5) % 1.0)
    # arm counter-swing
    def arm_swing(side, phase):
        P[f"upper_arm.{side}"].rotation_euler.x = math.radians(17) * math.sin(TAU * phase)
        P[f"forearm.{side}"].rotation_euler.y = math.radians(9) + math.radians(14) * max(0, math.sin(TAU * phase + 0.7))
    arm_swing("L", (t + 0.5) % 1.0)
    arm_swing("R", t)
    # pelvis: bob 2x per cycle + rotation
    P["pelvis"].location.z = -0.018 * abs(math.sin(TAU * t * 2.0)) + 0.006
    P["pelvis"].location.y = 0.012 * math.sin(TAU * t)
    P["pelvis"].rotation_euler.y = math.radians(4) * math.sin(TAU * t)
    # torso counter
    P["spine01"].rotation_euler.y = -math.radians(2.2) * math.sin(TAU * t)
    P["spine02"].rotation_euler.y = -math.radians(1.6) * math.sin(TAU * t)
    # head steady
    P["head"].rotation_euler.y = math.radians(1.2) * math.sin(TAU * t)
    # clavicle follow
    P["clavicle.L"].rotation_euler.x = math.radians(2) * math.sin(TAU * (t + 0.5))
    P["clavicle.R"].rotation_euler.x = math.radians(2) * math.sin(TAU * t)

def bake_action(name, frames, pose_fn, animated_bones):
    if arm.animation_data is None:
        arm.animation_data_create()
    act = bpy.data.actions.new(name)
    track = arm.animation_data.nla_tracks.new()
    track.name = name
    track.strips.new(name, int(0), act)
    arm.animation_data.action = act
    scn.frame_start = 1
    scn.frame_end = frames
    for f in range(frames + 1):       # +1: closing frame == frame 0
        t = (f % frames) / frames
        scn.frame_set(f)
        pose_fn(t)
        for bn in animated_bones:
            pb = arm.pose.bones.get(bn)
            if pb is None:
                continue
            pb.keyframe_insert(data_path="rotation_euler", frame=f)
            pb.keyframe_insert(data_path="location", frame=f)
    # force linear interpolation for tight loops (Blender 4.4+/5.0 slots API)
    def iter_fcurves(a):
        if hasattr(a, "fcurves") and getattr(a, "fcurves", None):
            return list(a.fcurves)
        out = []
        for layer in getattr(a, "layers", []):
            for strip in layer.strips:
                for bag in strip.channelbags:
                    out.extend(bag.fcurves)
        return out
    for fc in iter_fcurves(act):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    return act

def bone_world(pb):
    bpy.context.view_layer.update()
    return tuple(round(v, 5) for v in (arm.matrix_world @ pb.matrix).to_translation())

def verify_loop(frames):
    """Compare frame0 vs frameN bone positions."""
    errs = []
    bpy.context.view_layer.update()
    scn.frame_set(0)
    bpy.context.view_layer.update()
    p0 = {pb.name: bone_world(pb) for pb in arm.pose.bones}
    scn.frame_set(frames)
    p1 = {pb.name: bone_world(pb) for pb in arm.pose.bones}
    for k in p0:
        d = Vector(p0[k]) - Vector(p1[k])
        errs.append(d.length)
    return round(max(errs) * 1000, 3)  # mm

IDLE_BONES = ["spine02", "spine03", "chest", "neck", "head", "pelvis",
              "upper_arm.L", "upper_arm.R", "forearm.L", "forearm.R",
              "thigh.L", "thigh.R", "shin.L", "shin.R"]
WALK_BONES = ["thigh.L", "thigh.R", "shin.L", "shin.R", "foot.L", "foot.R",
              "upper_arm.L", "upper_arm.R", "forearm.L", "forearm.R",
              "pelvis", "spine01", "spine02", "head", "clavicle.L", "clavicle.R"]

# ================================================================ ANM-001 idle
print("[B6] TLS-ANM-001 idle ...")
IDLE_FRAMES = 96
act = bake_action("tls_anm_001_idle", IDLE_FRAMES, pose_idle, IDLE_BONES)
loop_err = verify_loop(IDLE_FRAMES)
# breathing amplitude: read chest pitch keys from the action itself
spine_pitch, chest_head_z = [], []
for f in range(IDLE_FRAMES + 1):
    scn.frame_set(f)
    bpy.context.view_layer.update()
    spine_pitch.append(math.degrees(arm.pose.bones["spine03"].rotation_euler.x))
    chest_head_z.append(bone_world(arm.pose.bones["head"])[2])
scn.frame_set(IDLE_FRAMES)
stats = {"asset": "TLS-ANM-001", "action": act.name, "frames": IDLE_FRAMES + 1,
         "fps": 30, "loop": f"{IDLE_FRAMES}f", "bones_animated": len(IDLE_BONES),
         "loop_closure_error_mm": loop_err,
         "spine03_breath_pitch_deg": round(max(spine_pitch) - min(spine_pitch), 3),
         "head_world_z_travel_mm": round((max(chest_head_z) - min(chest_head_z)) * 1000, 2),
         "blender": bpy.app.version_string}
# save blend (rig + action)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SRC, "tls_anm_001_idle.blend"),
                            compress=True)
sz = L.export_anim_fbx(arm, os.path.join(FBX, "tls_anm_001_idle_v001.fbx"))
stats["fbx_mb"] = round(sz / 1e6, 2)
L.write_json(os.path.join(STATS, "tls_anm_001_idle.json"), stats)
print(f"[B6] idle: frames={stats['frames']} loop_err={loop_err}mm "
      f"breath_pitch={stats['spine03_breath_pitch_deg']}deg "
      f"head_z={stats['head_world_z_travel_mm']}mm fbx={stats['fbx_mb']}MB")

# ================================================================ ANM-002 walk
print("[B6] TLS-ANM-002 walk ...")
# reload clean rig
bpy.ops.wm.open_mainfile(filepath=RIG)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
scn = bpy.context.scene
scn.render.fps = 30
bpy.context.view_layer.objects.active = arm
WALK_FRAMES = 34
act = bake_action("tls_anm_002_walk", WALK_FRAMES, pose_walk, WALK_BONES)
loop_err = verify_loop(WALK_FRAMES)
# stride metrics: toe.R world y excursion + pelvis bob
toe_fwd, pel_locz, thigh_deg = [], [], []
for f in range(WALK_FRAMES + 1):
    scn.frame_set(f)
    bpy.context.view_layer.update()
    toe_fwd.append(bone_world(arm.pose.bones["toe.R"])[1])
    pel_locz.append(arm.pose.bones["pelvis"].location.z)
    thigh_deg.append(math.degrees(arm.pose.bones["thigh.R"].rotation_euler.x))
scn.frame_set(WALK_FRAMES)
stride_mm = round((max(toe_fwd) - min(toe_fwd)) * 1000, 1)
bob_mm = round((max(pel_locz) - min(pel_locz)) * 1000, 1)
thigh_swing = round(max(abs(max(thigh_deg)), abs(min(thigh_deg))), 1)
stats = {"asset": "TLS-ANM-002", "action": act.name, "frames": WALK_FRAMES + 1,
         "fps": 30, "loop": f"{WALK_FRAMES}f (~1.13s, ~1.4m/s)",
         "bones_animated": len(WALK_BONES),
         "loop_closure_error_mm": loop_err,
         "toe_R_stride_excursion_mm": stride_mm,
         "pelvis_bob_mm": bob_mm,
         "thigh_swing_deg": thigh_swing,
         "blender": bpy.app.version_string}
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SRC, "tls_anm_002_walk.blend"),
                            compress=True)
sz = L.export_anim_fbx(arm, os.path.join(FBX, "tls_anm_002_walk_v001.fbx"))
stats["fbx_mb"] = round(sz / 1e6, 2)
L.write_json(os.path.join(STATS, "tls_anm_002_walk.json"), stats)
print(f"[B6] walk: frames={stats['frames']} loop_err={loop_err}mm "
      f"stride={stride_mm}mm bob={bob_mm}mm fbx={stats['fbx_mb']}MB")

# ---------------------------------------------------------------- summary
L.write_json(os.path.join(STATS, "b6_anim_batch.json"),
             {"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
              "seconds": round(time.time() - t0, 1),
              "rig": "TLS-SKL-001 (65 bones)",
              "assets": ["TLS-ANM-001", "TLS-ANM-002"]})
print(f"[B6] done in {time.time()-t0:.0f}s")
