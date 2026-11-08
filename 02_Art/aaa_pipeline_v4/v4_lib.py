# v4 sculpt library — REAL Blender Sculpt Mode brush automation (Xvfb headless)
# Every deformation is applied by genuine sculpt brushes (Clay Strips / Crease /
# Draw Sharp / Smooth / Grab / Flatten / Inflate) through sculpt.brush_stroke.
import bpy, bmesh, math, os, sys
import mathutils
from mathutils import Vector, Euler

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

H = 0.24  # head height in meters (chin 0 -> crown H)

# ---------------------------------------------------------------- session ctx
class Ctx:
    def __init__(self):
        wm = bpy.context.window_manager
        self.win = wm.windows[0]
        self.area = next(a for a in self.win.screen.areas if a.type == 'VIEW_3D')
        self.region = next(r for r in self.area.regions if r.type == 'WINDOW')
        self.rv3d = self.area.spaces.active.region_3d
        self.scene = bpy.context.scene
        self.ts = self.scene.tool_settings
        self.ov = dict(window=self.win, screen=self.win.screen, area=self.area,
                       region=self.region, region_data=self.rv3d, scene=self.scene)

    def redraw(self):
        try:
            with bpy.context.temp_override(**self.ov):
                bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        except Exception:
            pass

    def ortho(self, center=(0.0, 0.0, 0.13), target_ppw=2400.0):
        rv = self.rv3d
        rv.view_perspective = 'ORTHO'
        rv.view_location = Vector(center)
        rv.view_rotation = Euler((math.radians(90), 0, 0), 'XYZ').to_quaternion()
        rv.view_distance = 0.6
        self.redraw()
        self.calibrate(target_ppw)

    def _measure_ppw(self):
        p0 = Vector((0.0, 0.0, 0.13))
        p1 = p0 + Vector((0.1, 0, 0))
        a, b = self.project(p0), self.project(p1)
        if a is None or b is None:
            return 0.0
        return (Vector(a) - Vector(b)).length / 0.1

    def calibrate(self, target=2400.0, iters=8):
        for _ in range(iters):
            self.redraw()
            ppw = self._measure_ppw()
            if ppw <= 1.0:
                self.rv3d.view_distance *= 0.7
                continue
            err = ppw / target
            if abs(err - 1.0) < 0.03:
                break
            self.rv3d.view_distance *= err
        self.redraw()
        self._ppw = self._measure_ppw()

    def px_per_world(self):
        return getattr(self, '_ppw', 0.0) or self._measure_ppw()

    def project(self, p):
        import bpy_extras.view3d_utils as v3du
        return v3du.location_3d_to_region_2d(self.region, self.rv3d, p)

# ---------------------------------------------------------------- brushes
_TOOLS = {'CLAY': 'CLAY_STRIPS', 'CREASE': 'CREASE', 'SHARP': 'DRAW_SHARP',
          'SMOOTH': 'SMOOTH', 'GRAB': 'GRAB', 'FLAT': 'FLATTEN',
          'INFLATE': 'INFLATE', 'DRAW': 'DRAW'}
_META = {}  # brush name -> {'r': world radius, 'sym': bool}

def brush(ctx, name, tool, r=0.02, strength=0.5, symmetry=True, inward=False, passes=1):
    b = bpy.data.brushes.get(name)
    if b is None or not b.use_paint_sculpt:
        b = bpy.data.brushes.new(name, mode='SCULPT')
    b.sculpt_tool = _TOOLS[tool]
    b.strength = strength
    b.auto_smooth_factor = 0.25 if tool in ('CLAY', 'GRAB') else 0.1
    _META[name] = {'r': r, 'sym': symmetry, 'passes': passes}
    if tool == 'CREASE':
        b.crease_pinch_factor = 0.65
        b.direction = 'SUBTRACT' if inward else 'ADD'
    if tool in ('CLAY', 'INFLATE', 'DRAW', 'SHARP'):
        b.direction = 'SUBTRACT' if inward else 'ADD'
    ctx.ts.sculpt.brush = b
    return b

_BC = {}  # one persistent datablock per tool class

def sb(ctx, tool, r=None, strength=None, symmetry=None, inward=None, passes=None):
    """Mutate-and-reuse a single brush datablock per tool class."""
    b = _BC.get(tool)
    try:
        if b is not None and b.name not in bpy.data.brushes:
            b = None
    except ReferenceError:
        b = None
    if b is None:
        b = bpy.data.brushes.new("V4_" + tool, mode='SCULPT')
        b.sculpt_tool = _TOOLS[tool]
        _BC[tool] = b
    if strength is not None:
        b.strength = strength
    if tool in ('CLAY', 'GRAB'):
        b.auto_smooth_factor = 0.25
    if inward is not None:
        if tool == 'CREASE':
            b.crease_pinch_factor = 0.65
        b.direction = 'SUBTRACT' if inward else 'ADD'
    ctx.ts.sculpt.brush = b
    meta = _META.setdefault(b.name, {'r': 0.016, 'sym': True, 'passes': 1})
    if r is not None:
        meta['r'] = r
    if symmetry is not None:
        meta['sym'] = symmetry
    if passes is not None:
        meta['passes'] = passes
    return b

# ---------------------------------------------------------------- surface snap
def snap(ob, p, dist=0.15):
    hit, loc, nrm, idx = ob.closest_point_on_mesh(Vector(p), distance=dist)
    return Vector(loc) if hit else Vector(p)

def surface_path(ob, p0, p1, n=24, bulge=0.0, nrm_hint=None):
    a, b = Vector(p0), Vector(p1)
    nrm = Vector(nrm_hint) if nrm_hint else Vector((-0.3, -1.0, 0.0)).normalized()
    pts = []
    for i in range(n):
        t = i / (n - 1)
        p = a.lerp(b, t)
        if bulge:
            p = p + nrm * (bulge * math.sin(math.pi * t))
        pts.append(snap(ob, p))
    return pts

def arc_path(ob, center, r_world, axis, a0, a1, n=28, push=0.0):
    center = Vector(center)
    ax = Vector(axis).normalized()
    ref = Vector((0.0, -1.0, 0.0))
    if abs(ax.dot(ref)) > 0.9:
        ref = Vector((0.0, 1.0, 0.0))
    t1 = ref.cross(ax).normalized()
    t2 = ax.cross(t1).normalized()
    pts = []
    for i in range(n):
        t = i / (n - 1)
        ang = math.radians(a0 + (a1 - a0) * t)
        p = center + t1 * (math.cos(ang) * r_world) + t2 * (math.sin(ang) * r_world)
        if push:
            p = p + (p - center).normalized() * push
        pts.append(snap(ob, p, 0.2))
    return pts

# ---------------------------------------------------------------- stroke core
def stroke(ctx, ob, path, br, pressure_fn=None):
    meta = _META.get(br.name, {'r': 0.02, 'sym': True, 'passes': 1})
    # symmetry lives on the object/paint settings in 4.2, not on the brush
    try:
        ob.use_symmetry_x = bool(meta['sym'])
    except Exception:
        pass
    try:
        ctx.ts.sculpt.symmetry_axes = {'X'} if meta['sym'] else set()
    except Exception:
        pass
    r = meta['r']
    br.size = min(1000, max(2, int(round(2.0 * r * ctx.px_per_world()))))
    for p_i in range(int(meta.get('passes', 1))):
        pts = []
        total = len(path)
        for i, wp in enumerate(path):
            t = i / max(1, total - 1)
            loc = snap(ob, wp)  # re-glue path to CURRENT surface every pass/op
            m2 = ctx.project(loc)
            if m2 is None:
                continue
            pr = pressure_fn(t) if pressure_fn else 1.0
            p = {"name": "", "location": loc, "mouse": m2,
                 "mouse_event": (int(m2[0]), int(m2[1])), "pressure": pr,
                 "size": 1, "pen_flip": False, "x_tilt": 0.0, "y_tilt": 0.0,
                 "time": float(i) * 0.012, "is_start": i == 0}
            pts.append(p)
        if len(pts) < 2:
            return False
        ov = dict(ctx.ov); ov.update(object=ob, active_object=ob,
                                     selected_objects=[ob], selected_editable_objects=[ob])
        with bpy.context.temp_override(**ov):
            bpy.ops.sculpt.brush_stroke(stroke=pts)
    return True

def pass_pts(t):
    if t < 0.15:
        return t / 0.15
    if t > 0.85:
        return (1.0 - t) / 0.15
    return 1.0

# ---------------------------------------------------------------- mesh setup
def sculpt_base_mesh(name):
    """Blockout volumes -> union -> voxel remesh = sculptor's DynaMesh base."""
    bm = bmesh.new()

    def box(cx, cy, cz, sx, sy, sz, rx=0.0):
        sub = bmesh.ops.create_cube(bm, size=1.0)
        e = Euler((rx, 0, 0), 'XYZ').to_matrix()
        for v in sub['verts']:
            v.co.x *= sx; v.co.y *= sy; v.co.z *= sz
            if rx:
                v.co = e @ v.co
            v.co += Vector((cx, cy, cz))

    # cranium ellipsoid
    s = bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=32, radius=H * 0.42)
    for v in s['verts']:
        v.co.x *= 0.86; v.co.y *= 1.06
        v.co += Vector((0.0, H * 0.02, H * 0.70))
    # face mass (ellipsoid, tilted)
    s = bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=28, radius=1.0)
    e = Euler((math.radians(-12), 0, 0), 'XYZ').to_matrix()
    for v in s['verts']:
        v.co.x *= H * 0.30; v.co.y *= H * 0.34; v.co.z *= H * 0.36
        v.co = e @ v.co
        v.co += Vector((0, -H * 0.16, H * 0.55))
    # jaw mass (ellipsoid)
    s = bmesh.ops.create_uvsphere(bm, u_segments=36, v_segments=24, radius=1.0)
    e = Euler((math.radians(6), 0, 0), 'XYZ').to_matrix()
    for v in s['verts']:
        v.co.x *= H * 0.24; v.co.y *= H * 0.30; v.co.z *= H * 0.28
        v.co = e @ v.co
        v.co += Vector((0, -H * 0.10, H * 0.28))
    cyl = bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=H * 0.20,
                                radius2=H * 0.20, depth=H * 0.75)
    for v in cyl['verts']:
        v.co += Vector((0, H * 0.06, -H * 0.12))
    me = bpy.data.meshes.new(name)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0008)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    return ob

def enter_sculpt(ctx, ob, voxel=None):
    ov = dict(ctx.ov); ov.update(object=ob, active_object=ob,
                                 selected_objects=[ob], selected_editable_objects=[ob])
    with bpy.context.temp_override(**ov):
        bpy.ops.object.mode_set(mode='SCULPT')
        if voxel:
            ob.data.remesh_voxel_size = voxel
            bpy.ops.object.voxel_remesh()
    return ob

def remesh(ctx, ob, voxel):
    ob.data.remesh_voxel_size = voxel
    ov = dict(ctx.ov); ov.update(object=ob, active_object=ob)
    with bpy.context.temp_override(**ov):
        bpy.ops.object.voxel_remesh()

def stats(ob):
    me = ob.data
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    return dict(name=ob.name, verts=len(me.vertices), tris=tris)

# ---------------------------------------------------------------- render
def studio(scene):
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    scene.view_settings.view_transform = 'Filmic'
    scene.view_settings.look = 'Medium Contrast'

def add_light(name, loc, energy, size=0.6, color=(1, 1, 1)):
    d = bpy.data.lights.new(name, 'AREA')
    d.energy = energy; d.size = size; d.color = color
    o = bpy.data.objects.new(name, d)
    o.location = loc
    bpy.context.scene.collection.objects.link(o)
    return o

def add_cam(name, loc, look_at=(0, 0, 0.12)):
    cd = bpy.data.cameras.new(name); cd.lens = 85
    c = bpy.data.objects.new(name, cd)
    c.location = loc
    d = Vector(look_at) - Vector(loc)
    c.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.collection.objects.link(c)
    return c

def clay_material(ob, rgb=(0.72, 0.55, 0.45)):
    m = bpy.data.materials.new(ob.name + "_clay")
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = 0.85
    ob.data.materials.clear(); ob.data.materials.append(m)

def render(ctx, cam, path):
    ctx.scene.camera = cam
    ctx.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)

# ---------------------------------------------------------------- export
def export_glb(ob, path):
    for o in bpy.data.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    if ob.mode != 'OBJECT':
        ov = dict(window=bpy.context.window_manager.windows[0],
                  screen=bpy.context.window_manager.windows[0].screen,
                  scene=bpy.context.scene)
        for a in ov['screen'].areas:
            if a.type == 'VIEW_3D':
                ov['area'] = a
                ov['region'] = next(r for r in a.regions if r.type == 'WINDOW')
                break
        ov.update(object=ob, active_object=ob)
        with bpy.context.temp_override(**ov):
            bpy.ops.object.mode_set(mode='OBJECT')
    ov2 = dict(window=bpy.context.window_manager.windows[0],
               screen=bpy.context.window_manager.windows[0].screen,
               scene=bpy.context.scene, object=ob, active_object=ob,
               selected_objects=[ob], selected_editable_objects=[ob])
    with bpy.context.temp_override(**ov2):
        bpy.ops.export_scene.gltf(filepath=path, use_selection=True, export_format='GLB',
                                  export_apply=True, export_animations=False)
