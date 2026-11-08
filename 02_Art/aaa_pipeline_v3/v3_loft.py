#!/usr/bin/env python3
"""v3 head BASE via profile lofting (sculptor method):
mid-sagittal profile curve + coronal half-width table -> lofted base mesh.
Features (brow/nose/lips/sockets/cheeks/jaw) are smooth-masked local passes.
Coordinate: +Z up, face toward -Y, menton at z=0. All meters."""
import numpy as np, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---- mid-sagittal profile: (z, y_front) front and (z, y_back) ---------------
PROFILE_F = [  # front of face, chin->vertex
    (-0.020, -0.010), (0.000, -0.033), (0.010, -0.040),
    (0.021, -0.0425), (0.032, -0.0455), (0.048, -0.0445), (0.060, -0.0488),
    (0.066, -0.0475), (0.0715, -0.0488), (0.079, -0.0470), (0.084, -0.0495),
    (0.0955, -0.0595), (0.102, -0.0510), (0.1155, -0.0415), (0.1235, -0.0435),
    (0.132, -0.0430), (0.150, -0.0390), (0.170, -0.0340), (0.195, -0.0230),
    (0.215, -0.0060), (0.232, +0.0100), (0.243, +0.0200), (0.250, +0.0240)]
PROFILE_B = [  # back of head / nape, chin->vertex
    (-0.020, +0.062), (0.000, +0.042), (0.040, +0.032),
    (0.080, +0.058), (0.120, +0.078), (0.160, +0.086), (0.195, +0.074),
    (0.220, +0.050), (0.238, +0.030), (0.246, +0.022), (0.250, +0.022)]
HALF_W = [  # (z, half_width)
    (-0.020, 0.050), (0.000, 0.044), (0.029, 0.0530), (0.060, 0.0600),
    (0.090, 0.0665), (0.1005, 0.0690), (0.115, 0.0730), (0.140, 0.0755),
    (0.170, 0.0730), (0.200, 0.0640), (0.222, 0.0600), (0.234, 0.0520),
    (0.243, 0.0360), (0.248, 0.0180), (0.2515, 0.0060)]

def _interp(table, zs):
    ts = np.array([t[0] for t in table]); vs = np.array([t[1] for t in table])
    o = np.argsort(ts); ts, vs = ts[o], vs[o]
    # monotone cubic-ish: use PCHIP if scipy, else linear
    from scipy.interpolate import PchipInterpolator
    return PchipInterpolator(ts, vs)(zs)

def loft_base(m, nz=150, nring=64):
    """Return verts, faces of the lofted base head (crown capped at apex)."""
    zs = np.linspace(-0.020, 0.245, nz)
    yf = _interp(PROFILE_F, zs); yb = _interp(PROFILE_B, zs); hw = _interp(HALF_W, zs)
    # superellipse exponent per z: rounder (2.6) at cranium, squarer at jaw (3.2)
    e = 2.55 + 0.5*np.clip((0.09 - zs)/0.12, 0, 1)
    t = np.linspace(0, 2*np.pi, nring, endpoint=False)
    ct, st = np.cos(t), np.sin(t)
    V = np.zeros((nz, nring, 3), dtype=np.float32)
    for i, z in enumerate(zs):
        yc, a = (yf[i]+yb[i])/2, (yf[i]-yb[i])/2
        x = hw[i]*np.sign(st)*(np.abs(st)**(2.0/e[i]))
        y = yc + a*np.sign(ct)*(np.abs(ct)**(2.0/e[i]))
        V[i,:,0] = x; V[i,:,1] = y; V[i,:,2] = z
    # crown apex cap: rings keep fullness; final fan to apex vertex
    apex = np.array([[0.0, (yf[-1]+yb[-1])/2 + 0.002, 0.2535]], dtype=np.float32)
    V = np.concatenate([V.reshape(-1,3), apex], axis=0)
    F = []
    for i in range(nz-1):
        for j in range(nring):
            j2 = (j+1) % nring
            F.append((i*nring+j, i*nring+j2, (i+1)*nring+j))
            F.append((i*nring+j2, (i+1)*nring+j2, (i+1)*nring+j))
    last = (nz-1)*nring
    for j in range(nring):
        j2 = (j+1) % nring
        F.append((last+j, last+j2, nz*nring))   # fan to apex
    return V, np.array(F, dtype=np.int64)

# ---- feature passes ---------------------------------------------------------
def mask_sphere(V, c, r, feather=0.008):
    d = np.linalg.norm(V - np.array(c), axis=1)
    m = np.clip((r - d)/feather, 0, 1)
    return m*m*(3-2*m)

def dir_profile(V, c):
    dv = V - np.array(c); return dv/ (np.linalg.norm(dv, axis=1, keepdims=True)+1e-9)

def apply_features(V, m):
    A = m.anchors()
    disp = np.zeros_like(V)
    def add(c, r, amount, feather=0.008, direction=None):
        w = mask_sphere(V, c, r, feather) * amount
        dv = dir_profile(V, c) if direction is None else np.array(direction)[None,:].repeat(len(V),0)
        disp[:] += w[:,None]*dv
    # brow ridge bar (both sides + glabella) — fill the nasion notch too
    add(list(A['glabella']), 0.016, +0.0042, 0.010)
    for s in (-1,1):
        add([s*0.030, -0.042, 0.1215], 0.020, +0.0048, 0.012)
        add([s*0.020, -0.0415, 0.1180], 0.014, +0.0030, 0.009)
    # nasal bridge graduated (no stair-step)
    for (zz, amt, rr) in [(0.104, 0.0036, 0.015), (0.097, 0.0062, 0.013), (0.0915, 0.0078, 0.011)]:
        add([0, -0.050, zz], rr, amt, 0.009, direction=(0,-1,0))
    add(list(A['pronasale']), 0.0120, +0.0068, 0.007, direction=(0,-1,0))
    for s in (-1,1):
        add([s*0.0155*m.noseW, -0.052, 0.0905], 0.010, +0.0040, 0.007, direction=(0,-1,0.15))
    # zygomatic cheekbones
    for s in (-1,1):
        add([s*0.054*m.faceW, -0.030, 0.1005+m.cheekHk], 0.021, +0.0064, 0.014)
        add([s*0.040*m.faceW, -0.038, 0.0905], 0.020, +0.0050*m.cheek, 0.013)
    # lips (torus bumps, forward)
    mW = 0.0165*m.mouthW
    for s in (-1,1):
        add([s*mW*0.7, -0.0475, 0.0715], 0.0085, +0.0036*m.lipU, 0.006, direction=(0,-1,0))
        add([s*mW*0.6, -0.0480, 0.0602], 0.0085, +0.0042*m.lipL, 0.006, direction=(0,-1,0))
    add([0, -0.0470, 0.0645], 0.006, -0.0020, 0.004, direction=(0,-1,0))  # stomion crease
    # chin: mental protuberance
    add([0, -0.041, 0.024], 0.015, +0.0040, 0.010, direction=(0,-1,0.1))
    # gonial angles (jaw corners)
    for s in (-1,1):
        add([s*0.0495*m.jawW, -0.004, 0.0290], 0.018, +0.0055, 0.013)
        # masseter plane
        add([s*0.055*m.jawW, -0.008, 0.046], 0.022, +0.0048, 0.015)
    # temporal hollows (gentle inward above zygomatic)
    for s in (-1,1):
        add([s*0.068*m.cranW, -0.006, 0.145], 0.025, -0.0026*m.cranW, 0.014)
    # EARS: side protrusion masses (helix detail via wrinkle paths)
    for s in (-1,1):
        add([s*0.0700, 0.0065, 0.1130], 0.016, +0.0075, 0.010, direction=(s,0,0.05))
        add([s*0.0720, 0.0040, 0.0890], 0.009, +0.0045, 0.007, direction=(s,0.2,-0.3))  # lobe
    # orbital socket carve (inward) around pupils
    for s in (-1,1):
        pup = A['pupil'].copy(); pup[0]=s*pup[0]
        add(list(pup - [0,0.004,0]), 0.0160*m.eyeD, -0.0065, 0.008)
    # palpebral aperture: deeper carve between canthi
    for s in (-1,1):
        io_ = A['canthus_i'].copy(); io_[0]=s*io_[0]
        oo_ = A['canthus_o'].copy(); oo_[0]=s*oo_[0]
        n=7
        for k in range(n):
            tt = k/(n-1); p = io_*(1-tt)+oo_*tt
            add(list(p+[0,0.001,0]), 0.0068*m.eyeW, -0.0055, 0.004)
    # nostril wings carve
    for s in (-1,1):
        add([s*0.0082*m.noseW, -0.054, 0.0840], 0.0060, -0.0032, 0.004, direction=(0,-1,0))
    # philtrum groove
    add([0, -0.049, 0.0745], 0.0050, -0.0018, 0.005, direction=(0,-1,0))
    # mentolabial sulcus
    add([0, -0.044, 0.0430], 0.010, -0.0020, 0.007, direction=(0,-1,0))
    # under-jaw / throat inward to keep jawline crisp
    add([0, 0.004, 0.002], 0.028, -0.0035, 0.014, direction=(0,0,-1))
    V = V + disp
    return V

def apply_age_face(V, m):
    """Jowl sag + cheek hollow + lid hooding by age."""
    A = m.anchors()
    ak = max(0.0, m.age-30)/35.0
    disp = np.zeros_like(V)
    def add(c, r, amount, feather=0.012, direction=None):
        w = mask_sphere(V, c, r, feather)*amount
        dv = dir_profile(V, c) if direction is None else np.array(direction)[None,:].repeat(len(V),0)
        disp[:] += w[:,None]*dv
    if ak > 0:
        for s in (-1,1):
            add([s*0.030, -0.030, 0.045], 0.022, +0.0028*ak, 0.014)         # jowl
            add([s*0.052, -0.018, 0.062], 0.020, -0.0020*ak, 0.014)         # cheek hollow (buccal)
            add([s*0.028, -0.040, 0.1225], 0.016, +0.0012*ak, 0.010)        # upper-lid hood
        add([0, -0.020, 0.028], 0.028, +0.0015*ak, 0.016)                    # submental fullness
    if m.fem > 0.5:
        for s in (-1,1):
            add([s*0.036, -0.040, 0.095], 0.020, +0.0018, 0.014)             # feminine cheek apple
    V = V + disp
    return V

def ear_mesh(m, side, seg=28):
    """Parametric ear: helix C-curve + antihelix + lobe, as small lofted shell."""
    A = m.anchors()
    ec = A['tragion'].copy(); ec[0] = side*0.0700; ec[1] = 0.0065; ec[2] = 0.1130
    t = np.linspace(-0.55, 2.5, seg)
    helix = np.stack([ec[0]+side*0.0038*np.sin(t), ec[1]-0.0068*np.cos(t*1.15), ec[2]+0.0265*np.sin(t*0.92)], axis=1)
    anti = np.stack([ec[0]+side*0.0010*np.sin(t*1.05+0.9), ec[1]-0.0032, ec[2]+0.0130*np.sin(t*0.85)], axis=1)
    V = np.concatenate([helix, anti], axis=0)
    return V

def build_head_loft(morph, out_prefix):
    t0 = time.time()
    V, F = loft_base(morph)
    print(f"[loft] {len(V)} verts {len(F)} tris", flush=True)
    # 1) smooth FIRST (round crown, remove loft ridges) — never after features
    from v3_headbuild import laplacian_smooth
    V = laplacian_smooth(V, F, iters=3, lam=0.55)
    # 2) features at full strength
    V = apply_features(V, morph)
    V = apply_age_face(V, morph)
    from v3_anatomy import wrinkle_paths
    from v3_headbuild import apply_crease, apply_asymmetry, apply_skin_undulation
    center = np.array([0.0, 0.02, 0.10])
    total = np.zeros(len(V), dtype=np.float32)
    for wp in wrinkle_paths(morph):
        for path in wp['pts']:
            total += apply_crease(V, path, wp['depth'], wp['width'], wp['bulge'])
    dirv = V - center; dirv /= (np.linalg.norm(dirv, axis=1, keepdims=True)+1e-9)
    V = V + dirv*total[...,None]
    print("[wrinkles] applied", flush=True)
    V = apply_asymmetry(V, morph)
    V = apply_skin_undulation(V, morph)
    os.makedirs(os.path.dirname(out_prefix), exist_ok=True)
    import trimesh
    mesh = trimesh.Trimesh(vertices=V, faces=F, process=True)
    mesh.export(out_prefix + ".stl")
    lm = {k: (float(v) if np.isscalar(v) else [float(vv) for vv in v]) for k, v in morph.anchors().items()}
    with open(out_prefix + "_landmarks.json", "w") as f:
        json.dump(dict(landmarks=lm, morph={k: getattr(morph, k) for k in vars(morph)},
                       stats=dict(verts=int(len(mesh.vertices)), tris=int(len(mesh.faces)),
                                  bounds=mesh.bounds.tolist())), f, indent=1)
    print(f"[done] {out_prefix}.stl {len(mesh.vertices)}v {len(mesh.faces)}t in {time.time()-t0:.1f}s", flush=True)
    return out_prefix + ".stl"

if __name__ == "__main__":
    from v3_anatomy import HeadMorph
    name = sys.argv[1] if len(sys.argv) > 1 else "edmund"
    m = HeadMorph()
    build_head_loft(m, f"/home/z/my-project/work/v3/{name}_loft")
