#!/usr/bin/env python3
"""v3 head mesh builder: SDF -> marching cubes -> anatomical deformation passes.
Produces a high-detail head mesh (STL) + landmark JSON for downstream stages."""
import numpy as np, json, os, sys, time
from skimage.measure import marching_cubes
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v3_anatomy import HeadMorph, head_sdf, wrinkle_paths

RES   = 0.00135          # grid step (m)  -> ~2-4M cells
BND   = dict(x=(-0.115, 0.115), y=(-0.095, 0.135), z=(-0.125, 0.255))

def build_grid(m):
    xs = np.arange(BND['x'][0], BND['x'][1] + RES, RES)
    ys = np.arange(BND['y'][0], BND['y'][1] + RES, RES)
    zs = np.arange(BND['z'][0], BND['z'][1] + RES, RES)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
    return np.stack([X, Y, Z], axis=-1).astype(np.float32), (xs, ys, zs)

def polygonize(m, res=RES):
    P, (xs, ys, zs) = build_grid(m)
    t0 = time.time()
    # chunk over x-slabs to cap memory
    vol = np.empty(P.shape[:-1], dtype=np.float32)
    for i in range(0, P.shape[0], 24):
        vol[i:i+24] = head_sdf(m, P[i:i+24])
    print(f"[sdf] {vol.shape} in {time.time()-t0:.1f}s  min={vol.min():.4f} max={vol.max():.4f}", flush=True)
    verts, faces, normals, _ = marching_cubes(vol, level=0.0, spacing=(RES, RES, RES))
    verts[:, 0] += BND['x'][0]; verts[:, 1] += BND['y'][0]; verts[:, 2] += BND['z'][0]
    print(f"[mc] {len(verts)} verts {len(faces)} tris", flush=True)
    return verts.astype(np.float32), faces.astype(np.int64)

# ---------------------------------------------------------------------------
# Deformation passes
# ---------------------------------------------------------------------------
def _seg_dist(p, a, b):
    ab = b - a
    t = np.clip(((p - a) * ab).sum(-1) / max((ab*ab).sum(), 1e-12), 0, 1)
    proj = a + ab * t[..., None]
    return np.sqrt(((p - proj) ** 2).sum(-1)), t

def _line_dir(pts):
    """Average tangent along a polyline."""
    d = np.diff(pts, axis=0)
    d = d / (np.linalg.norm(d, axis=1, keepdims=True) + 1e-9)
    return d.mean(axis=0)

def apply_crease(verts, path_pts, depth, width, bulge):
    """Cut a V-groove along path (in surface space): displacement = depth at
    centerline, +bulge on both flanks. Vertical displacement uses smoothed
    normal estimate = direction from head center axis (cheap, stable)."""
    n = len(verts)
    disp = np.zeros(len(verts), dtype=np.float32)
    for i in range(len(path_pts) - 1):
        a, b = path_pts[i], path_pts[i+1]
        dist, t = _seg_dist(verts.astype(np.float64), a, b)
        w = np.clip(1.0 - dist / width, 0, 1)
        w = w * w * (3 - 2 * w)                      # smooth falloff
        disp += -depth * w * 2                       # groove
        flank = np.clip(1.0 - np.abs(dist - width*0.9) / (width*0.8), 0, 1)
        disp += bulge * flank * flank * (3-2*flank)  # flanking bulge
    # endpoints taper
    return disp

def apply_wrinkles(verts, m, progress=[0]):
    A = m.anchors()
    center = np.array([0.0, 0.02, 0.10])   # head mass center for normal est.
    total = np.zeros(len(verts), dtype=np.float32)
    for wp in wrinkle_paths(m):
        for path in wp['pts']:
            total += apply_crease(verts, path, wp['depth'], wp['width'], wp['bulge'])
    # displacement direction: radial from center (stable for a head)
    dirv = verts - center
    dirv /= (np.linalg.norm(dirv, axis=1, keepdims=True) + 1e-9)
    verts += dirv * total[..., None]
    print(f"[wrinkles] applied ({len(wrinkle_paths(m))} path groups)", flush=True)
    return verts

def apply_asymmetry(verts, m):
    rng = np.random.default_rng(m.asymSeed)
    # low-frequency asymmetric volume bias: left/right lumps + nose deflection
    t = np.linspace(0, 1, len(verts))
    modes = rng.normal(size=(6, 3)) * m.asym * 0.006
    basis = np.stack([np.sin(2*np.pi*t*(i+2)) for i in range(6)], axis=1)
    disp = basis @ modes
    # nose tip deflection (always)
    A = m.anchors()
    tip_off = np.array([m.asym * 0.004 * (1 if m.asymSeed % 2 else -1), 0, 0])
    near_tip = np.linalg.norm(verts - A['pronasale'], axis=1) < 0.02
    disp[near_tip] += tip_off * (1 - np.linalg.norm(verts[near_tip] - A['pronasale'], axis=1)/0.02)[:, None]
    verts = verts + disp.astype(np.float32)
    print("[asym] applied", flush=True)
    return verts

def apply_skin_undulation(verts, m, midline_mask=None):
    """Low-amp skin micro-relief, masked to face region (pores/creases follow
    zones: stronger on nose wings/cheek forehead, none on lips/ears)."""
    rng = np.random.default_rng(1000 + m.asymSeed)
    A = m.anchors()
    c = np.array([0, -0.01, 0.09])
    r = np.linalg.norm(verts[:, :2] - c[None, :2], axis=1)
    z = verts[:, 2]
    face_zone = (np.linalg.norm(verts - c, axis=1) < 0.13) & (z > 0.03) & (z < 0.20) & (verts[:, 1] < 0.02)
    # avoid lips
    lip_c = np.array([0, A['stomion'][1]+0.002, 0.066])
    face_zone &= (np.linalg.norm(verts - lip_c, axis=1) > 0.022)
    amp = 0.00042 * (1 + 0.3*m.age/40)
    f1 = np.sin(verts[:,0]*2600) * np.sin(verts[:,1]*2500 + 1.3) * np.sin(verts[:,2]*2400 + 0.7)
    f2 = np.sin(verts[:,0]*5300 + 2.1) * np.sin(verts[:,1]*5100) * np.sin(verts[:,2]*4900 + 1.9)
    disp = (f1 * 0.7 + f2 * 0.3) * amp
    verts = verts + disp[..., None] * 0  # placeholder keep z later
    verts[:, 2] += np.where(face_zone, disp * 0.35, 0)          # vertical only
    # sag: jowl/under-chin volume drop with age
    jowl_c = np.array([0, A['stomion'][1]+0.010, 0.034])
    dj = np.linalg.norm(verts - jowl_c, axis=1)
    sag_zone = (dj < 0.055) & (verts[:,1] > -0.01)
    sag = (1 - dj/0.055).clip(0,1)**2 * 0.0022 * max(0.0,(m.age-35))/30.0
    verts[:, 2] -= np.where(sag_zone, sag, 0)
    print("[skin] undulation + sag applied", flush=True)
    return verts

def laplacian_smooth(verts, faces, iters=2, lam=0.35):
    """Sparse neighbor smoothing for the whole mesh (removes MC staircases)."""
    import scipy.sparse as sp
    n = len(verts)
    i = np.concatenate([faces[:,0], faces[:,1], faces[:,2], faces[:,0], faces[:,1], faces[:,2]])
    j = np.concatenate([faces[:,1], faces[:,2], faces[:,0], faces[:,0], faces[:,1], faces[:,2]])
    W = sp.coo_matrix((np.ones(len(i), dtype=np.float32), (i, j)), shape=(n, n)).tocsr()
    W = W + sp.eye(n, dtype=np.float32)
    deg = np.asarray(W.sum(axis=1)).ravel()
    Wn = sp.diags(1.0/deg) @ W
    for it in range(iters):
        verts = verts * (1-lam) + np.asarray(Wn @ verts) * lam
    return verts.astype(np.float32)

def build_head(morph, out_prefix):
    t0 = time.time()
    verts, faces = polygonize(morph)
    verts = laplacian_smooth(verts, faces, iters=2, lam=0.45)
    verts = apply_wrinkles(verts, morph)
    verts = apply_asymmetry(verts, morph)
    verts = apply_skin_undulation(verts, morph)
    verts = laplacian_smooth(verts, faces, iters=1, lam=0.2)
    os.makedirs(os.path.dirname(out_prefix), exist_ok=True)
    # STL via trimesh
    import trimesh
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=True)
    stl_path = out_prefix + ".stl"
    mesh.export(stl_path)
    A = morph.anchors()
    lm = {k: (float(v) if np.isscalar(v) else [float(vv) for vv in v]) for k, v in A.items()}
    with open(out_prefix + "_landmarks.json", "w") as f:
        json.dump(dict(landmarks=lm, morph={k: getattr(morph, k) for k in vars(morph)},
                       stats=dict(verts=int(len(mesh.vertices)), tris=int(len(mesh.faces)),
                                  bounds=mesh.bounds.tolist())), f, indent=1)
    print(f"[done] {stl_path}: {len(mesh.vertices)} verts {len(mesh.faces)} tris in {time.time()-t0:.1f}s", flush=True)
    return stl_path

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "edmund"
    out = f"/home/z/my-project/work/v3/{name}_head"
    if name == "edmund":
        m = HeadMorph()
    build_head(m, out)
