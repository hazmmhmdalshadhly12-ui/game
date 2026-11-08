# Edmund Vale v4 — REAL brush-sculpt program (Clay/Crease/Draw Sharp/Smooth/Grab)
# Head local frame: origin at under-chin center, +Z up, -Y = face front, H=0.24m
import bpy, sys, math, os, bmesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v4_lib import (Ctx, H, brush, sb, stroke, pass_pts, surface_path, arc_path,
                    sculpt_base_mesh, enter_sculpt, remesh, stats, studio,
                    add_light, add_cam, clay_material, render, export_glb)
from mathutils import Vector

MARK = "V4"
OUT = os.environ.get("V4_OUT", "/home/z/my-project/work/out_v4")
STAGE = int(os.environ.get("V4_STAGE", "1"))

def bbox(ob):
    vs = ob.data.vertices
    if not len(vs):
        return "EMPTY"
    xs = [v.co for v in vs]
    mn = (round(min(v.x for v in xs), 3), round(min(v.y for v in xs), 3), round(min(v.z for v in xs), 3))
    mx = (round(max(v.x for v in xs), 3), round(max(v.y for v in xs), 3), round(max(v.z for v in xs), 3))
    out = sum(1 for v in vs if abs(v.co.x) > 0.2 or v.co.z < -0.2 or v.co.y < -0.3 or v.co.y > 0.2)
    return f"mn={mn} mx={mx} outliers={out}"

def L(x, y, z):
    """landmark in H units -> meters (x lateral, y depth, z height)"""
    return Vector((x * H, y * H, z * H))

def run():
    try:
        os.makedirs(OUT, exist_ok=True)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        ctx = Ctx()
        ctx.ortho(center=(0, 0, H * 0.55))

        ob = sculpt_base_mesh("TLS_Edmund_Head_v4")
        enter_sculpt(ctx, ob, voxel=0.001)
        print(MARK, "BASE", stats(ob))
        global REF
        REF = [v.co.copy() for v in ob.data.vertices]
        def disp(tag):
            mx = max((v.co - REF[i]).length for i, v in enumerate(ob.data.vertices))
            print(MARK, "DISP", tag, round(mx, 4))

        # ============ STAGE 1 — PRIMARY FORMS (CLAY, symmetric) ============
        # ---- BLOCKING: merge primitives into one organic mass ----
        b_blksm = sb(ctx, 'SMOOTH', r=0.05, strength=0.9, passes=3)
        for axis, a0, a1 in (((1, 0, 0), -170, 170), ((0, 0, 1), -85, 85),
                             ((1, 0, 0.5), -160, 160), ((1, 0, 0.5), 160, -160)):
            stroke(ctx, ob, arc_path(ob, (0, 0, H * 0.55), H * 0.5, axis, a0, a1, n=26), b_blksm)
        b_blk  = sb(ctx, 'CLAY', r=0.035, strength=1.0, passes=5)
        b_blki = sb(ctx, 'CLAY', r=0.030, strength=0.9, inward=True, passes=4)
        # cranial dome rebuild (kills the sphere/box seam)
        for zrow, r in ((0.98, 0.052), (0.90, 0.056), (0.82, 0.054), (0.74, 0.048), (0.66, 0.040)):
            p = arc_path(ob, (0, H * 0.02, H * 0.68), r * H, (0, 0, 1), -95, 95, n=22, push=0.006)
            stroke(ctx, ob, p, b_blk)
        # occiput mass
        p = arc_path(ob, (0, H * 0.10, H * 0.60), 0.055 * H, (1, 0, 0), -60, 60, n=18, push=0.005)
        stroke(ctx, ob, p, b_blk)
        # face side taper (temple->cheek seams pulled in)
        for sx in (-1, 1):
            p = surface_path(ob, L(0.30 * sx, -0.10, 0.90), L(0.30 * sx, -0.05, 0.30), n=16, bulge=-0.012)
            stroke(ctx, ob, p, b_blki)
            # jaw corner rounding
            p = arc_path(ob, (0.26 * sx * H, -0.02 * H, 0.34 * H), 0.05 * H, (0, 0, 1), sx * 10, sx * 95, n=12)
            stroke(ctx, ob, p, b_blki)
        # frontal taper toward chin
        p = surface_path(ob, L(0, -0.30, 0.16), L(0, -0.34, 0.36), n=10, bulge=-0.006)
        stroke(ctx, ob, p, b_blki)
        # neck-head junction blend
        b_nk = sb(ctx, 'SMOOTH', r=0.035, strength=0.8, passes=3)
        for a0, a1 in ((-140, 140), (140, -140), (-90, 90)):
            stroke(ctx, ob, arc_path(ob, (0, H * 0.06, H * 0.30), H * 0.30, (0, 0, 1), a0, a1, n=20), b_nk)

        b_cr   = sb(ctx, 'CLAY',   r=0.030, strength=1.0, passes=6)
        b_form = sb(ctx, 'CLAY',   r=0.016, strength=1.0, passes=4)
        b_in   = sb(ctx, 'CLAY',   r=0.014, strength=0.9, inward=True, passes=4)

        # cranium mass + occiput + forehead plane
        for zrow, r in ((1.02, 0.045), (0.94, 0.048), (0.86, 0.046), (0.78, 0.042)):
            p = arc_path(ob, (0, H * 0.02, H * 0.70), r * H, (0, 0, 1), -70, 70, n=20, push=0.004)
            stroke(ctx, ob, p, b_cr)
        # frontal eminences
        for sx in (-1, 1):
            p = surface_path(ob, L(0.10 * sx, -0.34, 0.86), L(0.08 * sx, -0.30, 0.90), n=10, bulge=0.006)
            stroke(ctx, ob, p, b_form)
        # brow ridge — heavy arcs through glabella
        for sx in (-1, 1):
            p = surface_path(ob, L(0.20 * sx, -0.24, 0.785), L(0.005 * sx, -0.345, 0.775), n=16, bulge=0.008)
            stroke(ctx, ob, p, b_form)
            p = surface_path(ob, L(0.005 * sx, -0.345, 0.775), L(0.20 * sx, -0.24, 0.785), n=16, bulge=0.008)
            stroke(ctx, ob, p, b_form)
        # glabella
        p = surface_path(ob, L(0, -0.35, 0.80), L(0, -0.35, 0.74), n=8, bulge=0.005)
        stroke(ctx, ob, p, b_form)
        # temporal hollows
        for sx in (-1, 1):
            p = surface_path(ob, L(0.34 * sx, -0.10, 0.70), L(0.30 * sx, 0.02, 0.62), n=12, bulge=-0.010)
            stroke(ctx, ob, p, b_in)
        # cheekbones
        for sx in (-1, 1):
            p = surface_path(ob, L(0.16 * sx, -0.38, 0.62), L(0.32 * sx, -0.16, 0.58), n=16, bulge=0.009)
            stroke(ctx, ob, p, b_form)
        # maxilla pads
        for sx in (-1, 1):
            p = surface_path(ob, L(0.11 * sx, -0.46, 0.56), L(0.12 * sx, -0.47, 0.46), n=10, bulge=0.007)
            stroke(ctx, ob, p, b_form)
        # nasal bridge -> tip wedge
        p = surface_path(ob, L(0, -0.375, 0.76), L(0, -0.545, 0.585), n=18, bulge=0.014)
        stroke(ctx, ob, p, b_form)
        p = surface_path(ob, L(0, -0.545, 0.585), L(0, -0.575, 0.545), n=8, bulge=0.012)
        stroke(ctx, ob, p, b_form)
        # alae
        for sx in (-1, 1):
            p = arc_path(ob, (0.055 * sx * H, -0.52 * H, 0.555 * H), 0.030 * H, (1, 0, 0.2), sx * 130, sx * 40, n=12)
            stroke(ctx, ob, p, b_form)
        # upper / lower lip volumes
        p = surface_path(ob, L(-0.16, -0.505, 0.435), L(0.16, -0.505, 0.435), n=16, bulge=0.006)
        stroke(ctx, ob, p, b_form)
        p = surface_path(ob, L(-0.13, -0.51, 0.395), L(0.13, -0.51, 0.395), n=16, bulge=0.008)
        stroke(ctx, ob, p, b_form)
        # mouth corners
        for sx in (-1, 1):
            p = surface_path(ob, L(0.14 * sx, -0.49, 0.46), L(0.17 * sx, -0.48, 0.38), n=8, bulge=0.005)
            stroke(ctx, ob, p, b_form)
        # chin pad + jaw ridge + mandible angle
        p = surface_path(ob, L(-0.07, -0.465, 0.30), L(0.07, -0.465, 0.30), n=10, bulge=0.009)
        stroke(ctx, ob, p, b_form)
        for sx in (-1, 1):
            p = surface_path(ob, L(0.33 * sx, 0.06, 0.55), L(0.29 * sx, 0.00, 0.34), n=14, bulge=0.007)
            stroke(ctx, ob, p, b_form)
            p = surface_path(ob, L(0.29 * sx, 0.00, 0.34), L(0.08 * sx, -0.46, 0.27), n=14, bulge=0.008)
            stroke(ctx, ob, p, b_form)
        # eye socket depressions
        for sx in (-1, 1):
            p = arc_path(ob, (0.135 * sx * H, -0.44 * H, 0.705 * H), 0.058 * H, (0, 0, 1), sx * 200, sx * -20, n=18)
            stroke(ctx, ob, p, b_in)
        print(MARK, "STAGE1 done", stats(ob), bbox(ob)); disp("stage1")

        if STAGE <= 1:
            print(MARK, "STAGE1_SAVE")
            bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/_stage1.blend")
            bpy.ops.wm.quit_blender()
            return None
        if STAGE == 2:
            bpy.ops.wm.open_mainfile(filepath=f"{OUT}/_stage1.blend")
            ctx = Ctx(); ctx.ortho(center=(0, 0, H * 0.55))
            ob = bpy.data.objects["TLS_Edmund_Head_v4"]
            REF = [v.co.copy() for v in ob.data.vertices]
            def disp(tag):
                mx = max((v.co - REF[i]).length for i, v in enumerate(ob.data.vertices))
                print(MARK, "DISP", tag, round(mx, 4))
            with bpy.context.temp_override(**dict(ctx.ov, object=ob, active_object=ob)):
                bpy.ops.object.mode_set(mode='SCULPT')

        # ============ STAGE 2 — REFINE (smaller clay on same dense mesh) =====
        b_f2  = sb(ctx, 'CLAY',   r=0.009, strength=1.0, passes=3)
        b_cr2 = sb(ctx, 'CREASE', r=0.006, strength=0.9, inward=True, passes=2)
        b_sm  = sb(ctx, 'SMOOTH', r=0.020, strength=0.5, passes=2)

        # nose side planes + wings + nostril notches
        for sx in (-1, 1):
            p = surface_path(ob, L(0.020 * sx, -0.43, 0.72), L(0.055 * sx, -0.545, 0.565), n=12, bulge=0.004)
            stroke(ctx, ob, p, b_f2)
            p = surface_path(ob, L(0.075 * sx, -0.525, 0.565), L(0.050 * sx, -0.575, 0.545), n=10, bulge=0.005)
            stroke(ctx, ob, p, b_f2)
        # philtrum + mentolabial
        stroke(ctx, ob, surface_path(ob, L(0, -0.545, 0.53), L(0, -0.515, 0.46), n=8, bulge=-0.004), b_cr2)
        stroke(ctx, ob, surface_path(ob, L(-0.05, -0.50, 0.345), L(0.05, -0.50, 0.345), n=8, bulge=-0.004), b_cr2)
        # lip line
        stroke(ctx, ob, surface_path(ob, L(-0.15, -0.508, 0.415), L(0.15, -0.508, 0.415), n=18, bulge=-0.005), b_cr2)
        # eyelid bands
        for sx in (-1, 1):
            p = arc_path(ob, (0.135 * sx * H, -0.44 * H, 0.708 * H), 0.040 * H, (0, 0, 1), sx * 210, sx * -30, n=14)
            stroke(ctx, ob, p, b_f2)
            p = arc_path(ob, (0.135 * sx * H, -0.44 * H, 0.700 * H), 0.042 * H, (0, 0, 1), sx * 190, sx * -10, n=14)
            stroke(ctx, ob, p, b_f2)
        # ears — helix C-ridges
        for sx in (-1, 1):
            p = arc_path(ob, (0.365 * sx * H, 0.05 * H, 0.615 * H), 0.075 * H, (1, 0, 0), sx * 150, sx * -150, n=22, push=0.004)
            stroke(ctx, ob, p, b_f2)
        # nasolabial folds (Edmund age 42 — moderate)
        for sx in (-1, 1):
            stroke(ctx, ob, surface_path(ob, L(0.055 * sx, -0.545, 0.545), L(0.14 * sx, -0.50, 0.40), n=12, bulge=-0.005), b_cr2)
        # masseter
        for sx in (-1, 1):
            p = surface_path(ob, L(0.30 * sx, -0.04, 0.48), L(0.26 * sx, -0.10, 0.36), n=10, bulge=0.006)
            stroke(ctx, ob, p, b_f2)
        # global smooth sweeps
        for axis, a0, a1 in (((1, 0, 0), -160, 160), ((0, 0, 1), -80, 80), ((1, 0, 0.4), -150, 150)):
            stroke(ctx, ob, arc_path(ob, (0, 0, H * 0.55), H * 0.52, axis, a0, a1, n=24), b_sm)
        print(MARK, "STAGE2 done", stats(ob), bbox(ob)); disp("stage2")
        if STAGE == 2:
            bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/_stage2.blend")
            print(MARK, "STAGE2_SAVE")
            bpy.ops.wm.quit_blender()
            return None

        if STAGE == 3:
            bpy.ops.wm.open_mainfile(filepath=f"{OUT}/_stage2.blend")
            ctx = Ctx(); ctx.ortho(center=(0, 0, H * 0.55))
            ob = bpy.data.objects["TLS_Edmund_Head_v4"]
            REF = [v.co.copy() for v in ob.data.vertices]
            def disp(tag):
                mx = max((v.co - REF[i]).length for i, v in enumerate(ob.data.vertices))
                print(MARK, "DISP", tag, round(mx, 4))
            with bpy.context.temp_override(**dict(ctx.ov, object=ob, active_object=ob)):
                bpy.ops.object.mode_set(mode='SCULPT')

        # ============ STAGE 3 — DETAIL + AGE + ASYMMETRY ====================
        b_ln  = sb(ctx, 'SHARP',  r=0.0032, strength=0.8, inward=True, passes=2)
        b_ln2 = sb(ctx, 'SHARP',  r=0.0032, strength=0.8, inward=False, passes=1)
        b_smo = sb(ctx, 'SMOOTH', r=0.012, strength=0.45, passes=2)

        # eyelid creases + under-eye
        for sx in (-1, 1):
            p = arc_path(ob, (0.135 * sx * H, -0.44 * H, 0.718 * H), 0.034 * H, (0, 0, 1), sx * 200, sx * -20, n=12)
            stroke(ctx, ob, p, b_ln)
            p = arc_path(ob, (0.135 * sx * H, -0.442 * H, 0.682 * H), 0.036 * H, (0, 0, 1), sx * 170, sx * -10, n=12)
            stroke(ctx, ob, p, b_ln)
        # crow's feet (3 short lines per side)
        for sx in (-1, 1):
            for k, dy in ((0, 0.0), (1, -0.012), (2, -0.024)):
                a = L(0.26 * sx, -0.30 - dy, 0.64 + dy)
                bb = L(0.31 * sx, -0.24 - dy, 0.625 + dy)
                stroke(ctx, ob, surface_path(ob, a, bb, n=7, bulge=-0.0035), b_ln)
        # forehead lines (3) + glabella (2 vertical)
        for zz in (0.855, 0.83, 0.805):
            p = surface_path(ob, L(-0.15, -0.30 - (0.855 - zz) * 0.9, zz), L(0.15, -0.30 - (0.855 - zz) * 0.9, zz), n=14, bulge=-0.003)
            stroke(ctx, ob, p, b_ln)
        for sx in (-1, 1):
            stroke(ctx, ob, surface_path(ob, L(0.028 * sx, -0.352, 0.80), L(0.028 * sx, -0.345, 0.75), n=8, bulge=-0.0035), b_ln)
        # lip micro: upper-lip border, lower lip center cleft
        stroke(ctx, ob, surface_path(ob, L(-0.145, -0.507, 0.442), L(0.145, -0.507, 0.442), n=16, bulge=-0.003), b_ln)
        stroke(ctx, ob, surface_path(ob, L(0, -0.512, 0.412), L(0, -0.512, 0.382), n=6, bulge=-0.0025), b_ln)
        # nostrils
        for sx in (-1, 1):
            p = arc_path(ob, (0.042 * sx * H, -0.555 * H, 0.548 * H), 0.018 * H, (1, 0, 0), sx * 40, sx * 220, n=10)
            stroke(ctx, ob, p, b_ln)
        # ear inner details (antihelix + lobe crease)
        for sx in (-1, 1):
            p = arc_path(ob, (0.362 * sx * H, 0.05 * H, 0.615 * H), 0.045 * H, (1, 0, 0), sx * 120, sx * -120, n=16, push=-0.004)
            stroke(ctx, ob, p, b_ln)
        # symmetry break — Edmund's lived-in face
        b_gb = sb(ctx, 'GRAB', r=0.014, strength=0.6, symmetry=False, passes=1)
        tip = snap_pt(ob, L(0, -0.575, 0.545))
        stroke(ctx, ob, [tip, tip + Vector((-0.006, -0.001, 0.0))], b_gb)          # nose deviates left
        rb = snap_pt(ob, L(0.16, -0.31, 0.775))
        stroke(ctx, ob, [rb, rb + Vector((0.0, 0.002, -0.006))], b_gb)             # right brow lower
        rc = snap_pt(ob, L(0.12, -0.47, 0.415))
        stroke(ctx, ob, [rc, rc + Vector((0.0, -0.003, 0.0))], b_gb)               # deeper R nasolabial pull
        chn = snap_pt(ob, L(0, -0.47, 0.295))
        stroke(ctx, ob, [chn, chn + Vector((-0.004, 0.0, 0.001))], b_gb)           # chin tilt
        # final soft pass
        for axis, a0, a1 in (((1, 0, 0), -150, 150), ((0, 0, 1), -70, 70)):
            stroke(ctx, ob, arc_path(ob, (0, 0, H * 0.55), H * 0.5, axis, a0, a1, n=22), b_smo)
        print(MARK, "STAGE3 done", stats(ob), bbox(ob)); disp("stage3")
        if STAGE == 3:
            bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/_stage3.blend")
            print(MARK, "STAGE3_SAVE")
            bpy.ops.wm.quit_blender()
            return None

        if STAGE >= 4:
            bpy.ops.wm.open_mainfile(filepath=f"{OUT}/_stage3.blend")
            ctx = Ctx(); ctx.ortho(center=(0, 0, H * 0.55))
            ob = bpy.data.objects["TLS_Edmund_Head_v4"]
            with bpy.context.temp_override(**dict(ctx.ov, object=ob, active_object=ob)):
                bpy.ops.object.mode_set(mode='OBJECT')

        # ============ STAGE 4 — EYES + HAIR + SHADING + RENDERS =============
        ov4 = dict(ctx.ov); ov4.update(object=ob, active_object=ob)
        with bpy.context.temp_override(**ov4):
            bpy.ops.object.mode_set(mode='OBJECT')
        eyes = add_eyes(ob)
        hair = add_hair_shell(ob)
        for o in (ob, hair):
            o.data.polygons.foreach_set('use_smooth', [True] * len(o.data.polygons))
            o.data.update()
        clay_material(ob)
        clay_material(hair, (0.13, 0.09, 0.07))
        studio(ctx.scene)
        add_light("KEY", (0.30, -0.65, 0.42), 60)
        add_light("FILL", (-0.45, -0.55, 0.20), 18)
        add_light("RIM", (-0.30, 0.55, 0.45), 45)
        add_light("TOP", (0.0, -0.1, 0.8), 30)
        cams = {"front": add_cam("C_F", (0.0, -0.95, 0.155)),
                "threeQ": add_cam("C_3Q", (0.42, -0.78, 0.20)),
                "profile": add_cam("C_P", (0.92, -0.06, 0.15))}
        for nm, cam in cams.items():
            render(ctx, cam, f"{OUT}/edmund_v4_{nm}.png")
        print(MARK, "RENDERS done")
        bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/edmund_v4_sculpt.blend")
        export_glb(ob, f"{OUT}/edmund_v4_head.glb")
        print(MARK, "DONE", stats(ob))
        bpy.ops.wm.quit_blender()
    except Exception as e:
        import traceback; traceback.print_exc()
        print(MARK, "FAIL", repr(e))
        bpy.ops.wm.quit_blender()
    return None

def snap_pt(ob, p):
    hit, loc, n, i = ob.closest_point_on_mesh(p, distance=0.15)
    return Vector(loc) if hit else Vector(p)

def add_eyes(head):
    out = []
    for sx in (-1, 1):
        me = bpy.data.meshes.new("Eye")
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=24, radius=0.0125)
        bm.to_mesh(me); bm.free()
        o = bpy.data.objects.new(f"Eye_{sx}", me)
        o.location = (0.0324 * sx, -0.1056, 0.168)
        bpy.context.scene.collection.objects.link(o)
        m = bpy.data.materials.new("sclera"); m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.88, 0.86, 0.83, 1)
        b.inputs["Roughness"].default_value = 0.15
        me.materials.append(m)
        # iris + pupil discs
        for r, c, nm in ((0.0052, (0.25, 0.30, 0.33), "iris"), (0.0021, (0.01, 0.01, 0.01), "pupil")):
            m2 = bpy.data.meshes.new(nm)
            bm2 = bmesh.new()
            bmesh.ops.create_circle(bm2, cap_ends=True, segments=24, radius=r)
            bm2.to_mesh(m2); bm2.free()
            o2 = bpy.data.objects.new(nm, m2)
            m2.materials.append(mat_flat(c))
            o2.location = (0.0324 * sx, -0.1056 - 0.0121, 0.168)
            o2.rotation_euler = (math.radians(-90), 0, 0)
            bpy.context.scene.collection.objects.link(o2)
    return out

def mat_flat(c):
    m = bpy.data.materials.new(f"flat_{c}")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*c, 1)
    b.inputs["Roughness"].default_value = 0.5
    return m

def add_hair_shell(head):
    """Separate hair volume: scalp-fitted shell built from scaled head verts (top region)."""
    me = head.data
    import bmesh as _bm
    bm = _bm.new()
    bm.from_mesh(me)
    keep = []
    for v in bm.verts:
        wz = v.co.z
        wy = v.co.y
        # scalp region: above brow (z>0.78H) minus face-front area, plus back of head above nape
        if wz > 0.80 * H or (wz > 0.62 * H and wy > -0.10 * H):
            keep.append(v)
    _bm.ops.delete(bm, geom=[v for v in bm.verts if v not in keep], context='VERTS')
    for v in bm.verts:
        n = v.normal
        v.co += n * 0.006  # hair thickness
    # side part: crease along parting line via slight inward drag on a stroke path (visual)
    out = bpy.data.meshes.new("TLS_Edmund_Hair_v4")
    bm.to_mesh(out); bm.free()
    o = bpy.data.objects.new("TLS_Edmund_Hair_v4", out)
    bpy.context.scene.collection.objects.link(o)
    return o

bpy.app.timers.register(run, first_interval=2.0)
