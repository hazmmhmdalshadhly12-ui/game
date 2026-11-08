#!/usr/bin/env python3
"""TLS pipeline v3 — anatomical SDF core.
Heads are built from anthropometric landmark volumes (Farkas ratios, Rhine&Moore
tissue depths), polygonized with marching cubes, then refined by deformation
passes. Coordinate frame: +Z up, face looks toward -Y, +X = character's LEFT.
Units: meters. All dims for a 1.75-1.80m adult."""
import numpy as np

def sd_ellipsoid(p, c, r):
    q = (p - c) / r
    k0 = np.sqrt((q*q).sum(-1))
    k1 = np.sqrt(((q*q/r).sum(-1)))
    return k0*(k0-1.0)/np.maximum(k1,1e-8)

def sd_ball(p, c, r):     return np.sqrt(((p-c)**2).sum(-1)) - r
def sd_capsule(p, a, b, r):
    pa, ba = p-a, b-a
    h = np.clip((pa*ba).sum(-1)/ (ba*ba).sum(), 0, 1)[..., None]
    return np.sqrt(((pa - ba*h)**2).sum(-1)) - r

def smin(a, b, k=0.02):
    h = np.clip(0.5 + 0.5*(b-a)/k, 0, 1)
    return b*(1-h) + a*h - k*h*(1-h)
def smax(a, b, k=0.015):
    return -smin(-a, -b, k)

# ----------------------------------------------------------------------------
class HeadMorph:
    """All dims meters. Defaults = Edmund Vale (35y male, lean)."""
    def __init__(self, **kw):
        self.cranW   = 1.00   # cranial width factor (0.94 dolicho .. 1.06 brachy)
        self.faceW   = 1.00   # bizygomatic width factor
        self.jawW    = 1.00   # bigonial factor
        self.chinH   = 1.00   # chin height factor
        self.chinP   = 0.0    # chin projection (+ forward)
        self.browP   = 1.00   # brow ridge prominence
        self.eyeW    = 1.00   # palpebral fissure width
        self.eyeTilt = 0.0    # canthus tilt radians (+ = down-out)
        self.eyeD    = 1.00   # eye socket depth/sink
        self.noseL   = 1.00   # nose length factor
        self.noseW   = 1.00   # alar width factor
        self.noseP   = 1.00   # nose projection factor
        self.noseB   = 0.0    # nose bridge bump (aquiline +)
        self.lipU    = 1.00   # upper lip volume
        self.lipL    = 1.00   # lower lip volume
        self.mouthW  = 1.00
        self.cheek   = 1.00   # malar fat fullness
        self.templeH = 0.0    # temple hollowing (age)
        self.cheekHk = 0.0    # cheekbone height offset (z)
        self.asym    = 0.015  # natural asymmetry amplitude
        self.asymSeed= 7
        self.age     = 35.0   # drives wrinkle/sag params
        self.fem     = 0.0    # 0 male .. 1 female
        for k, v in kw.items():
            if not hasattr(self, k): raise KeyError(k)
            setattr(self, k, v)

    # -- derived sagittal profile anchors (z from menton=0) -------------------
    def anchors(self):
        f = self.fem
        return dict(
            vertex_z  = 0.235 + 0.004*f,
            nasion    = np.array([0, -0.0415*self.browP, 0.1155]),
            glabella  = np.array([0, -0.0435*self.browP, 0.1235]),
            pronasale = np.array([0, -0.0455 - 0.0140*self.noseP, 0.0955 + 0.010*(self.noseL-1)]),
            rhinion   = np.array([0, -0.0485*self.browP - 0.003, 0.0985]),
            subnasale = np.array([0, -0.0415, 0.0800]),
            stomion   = np.array([0, -0.0470, 0.0660]),
            mentolab  = np.array([0, -0.0420, 0.0430]),
            pogonion  = np.array([0, -0.0425 - self.chinP, 0.0210]),
            menton    = np.array([0, -0.0330 - self.chinP, 0.0000]),
            gonion    = np.array([0.0515*self.jawW, -0.0020, 0.0290]),
            zygion    = np.array([0.0665*self.faceW, -0.0280, 0.1005 + self.cheekHk]),
            pupil     = np.array([0.0315, -0.0405, 0.1085]),
            canthus_i = np.array([0.0155, -0.0415, 0.1080]),
            canthus_o = np.array([0.0475, -0.0370, 0.1080 - self.eyeTilt*0.008]),
            tragion   = np.array([0.0710, 0.0060, 0.1060]),
        )

def head_sdf(m: HeadMorph, p):
    """Vectorized head SDF. p: (...,3) numpy array."""
    A = m.anchors()
    f, cw = m.fem, m.cranW
    d = None
    def uni(d, nd, k=0.022):
        return nd if d is None else smin(d, nd, k)

    # CRANIUM (braincase bottom must sit at ear-top level ~z=0.10, NOT mouth level)
    d = uni(d, sd_ellipsoid(p, np.array([0, 0.006, 0.1700 + 0.004*f]), np.array([0.0755*cw*(1-0.03*f), 0.0930, 0.0680])), 0.03)
    d = uni(d, sd_ellipsoid(p, np.array([0, 0.038, 0.1520]), np.array([0.0680, 0.0580, 0.0520])), 0.04)
    # forehead plate
    d = uni(d, sd_ellipsoid(p, np.array([0, -0.0200, 0.1750]), np.array([0.0600*(1-0.015*f), 0.0400, 0.0440])), 0.03)
    # NOTE: temple flattening omitted — a plain smax slab decapitates the cranium;
    # side flattening is instead handled by cranium width factor.

    # BROW RIDGE
    bR = 0.0062 + 0.0022*(1-f) + (m.browP-1)*0.004
    for s in (-1, 1):
        a = A['glabella'] + np.array([s*0.006, 0, -0.001])
        b = A['canthus_o'] + np.array([s*0.004, -0.006, 0.0125])
        b[0] = s*b[0]
        d = uni(d, sd_capsule(p, a, b, bR), 0.012)
    d = uni(d, sd_ball(p, A['glabella'], 0.0082 + 0.0018*(1-f)), 0.010)

    # ZYGOMATIC + cheek fat
    for s in (-1, 1):
        zy = A['zygion'].copy(); zy[0] = s*zy[0]
        d = uni(d, sd_ball(p, zy, 0.0135*(1-0.10*f)), 0.020)
        chk = np.array([s*0.0405*m.faceW, -0.0370, 0.0905 + m.cheekHk])
        d = uni(d, sd_ball(p, chk, 0.0150*m.cheek*(1-0.12*f)), 0.028)
        tr = A['tragion'].copy(); tr[0] = s*tr[0]
        d = uni(d, sd_capsule(p, zy + np.array([0,0,0.004]), tr + np.array([-s*0.010,0,0.002]), 0.0090), 0.020)

    # NOSE
    nas, rhi, pro = A['nasion'], A['rhinion'], A['pronasale']
    rhi2 = rhi + np.array([0, -m.noseB*0.006, m.noseB*0.004])
    d = uni(d, sd_capsule(p, nas, rhi2, 0.0085*(1-0.25*f)), 0.012)
    d = uni(d, sd_capsule(p, rhi2, pro, 0.0090*(1-0.2*f)*(1+0.12*m.noseW)), 0.010)
    tipR = 0.0105*(1-0.28*f)*(0.85+0.3*m.noseW)
    d = uni(d, sd_ball(p, pro, tipR), 0.010)
    for s in (-1, 1):
        al = np.array([s*0.0165*m.noseW, pro[1]+0.0060, pro[2]-0.0050])
        d = uni(d, sd_ball(p, al, 0.0078*m.noseW*(1-0.15*f)), 0.012)
        d = uni(d, sd_capsule(p, al, np.array([s*0.0075, pro[1]+0.0020, pro[2]-0.0098]), 0.0038), 0.010)
    d = uni(d, sd_ball(p, A['subnasale'] + np.array([0,-0.001,0.001]), 0.0060), 0.012)

    # MOUTH: lips + maxilla muzzle block connecting lips to face (prevents
    # a detached 'muzzle' blob after negative cuts)
    mW = 0.0165*m.mouthW
    d = uni(d, sd_ellipsoid(p, np.array([0, -0.0280, 0.0640]), np.array([0.0310*m.faceW, 0.0190, 0.0230])), 0.030)
    lipU_c = np.array([0, A['stomion'][1]-0.0005, 0.0715]); lipL_c = np.array([0, A['stomion'][1]-0.0010, 0.0602])
    d = uni(d, sd_capsule(p, lipU_c + np.array([-mW,0.0012,-0.0018]), lipU_c + np.array([mW,0.0012,-0.0018]),
                          0.0058*m.lipU*(1-0.10*f)), 0.014)
    d = uni(d, sd_capsule(p, lipL_c + np.array([-mW*0.92,0.0016,0.0006]), lipL_c + np.array([mW*0.92,0.0016,0.0006]),
                          0.0064*m.lipL*(1-0.05*f)), 0.014)
    d = uni(d, sd_capsule(p, np.array([-0.0035, A['subnasale'][1]-0.004, 0.0800]), np.array([-0.0042, lipU_c[1]+0.002, 0.0720]), 0.0022), 0.008)
    d = uni(d, sd_capsule(p, np.array([ 0.0035, A['subnasale'][1]-0.004, 0.0800]), np.array([ 0.0042, lipU_c[1]+0.002, 0.0720]), 0.0022), 0.008)
    for s in (-1,1):
        d = uni(d, sd_ball(p, np.array([s*mW*1.06, lipU_c[1]+0.001, 0.0658]), 0.0042), 0.012)

    # CHIN + MANDIBLE
    d = uni(d, sd_ball(p, A['pogonion'] + np.array([0,0,0.004]), 0.0112*(1-0.12*f)), 0.016)
    d = uni(d, sd_ball(p, A['menton'] + np.array([0,0,0.006]), 0.0095*(1-0.1*f)), 0.012)
    for s in (-1, 1):
        gon = A['gonion'].copy(); gon[0] = s*gon[0]
        go_u = np.array([s*0.0520*m.jawW, 0.0060, 0.0700])
        d = uni(d, sd_capsule(p, go_u, gon, 0.0092*(1-0.05*f)), 0.022)
        d = uni(d, sd_capsule(p, gon, A['pogonion'] + np.array([s*0.010,0,0.002]), 0.0115*(1-0.08*f)), 0.026)
        ms = np.array([s*0.0550*m.jawW*(1+0.04*(1-f)), -0.005, 0.0480])
        d = uni(d, sd_ball(p, ms, 0.0155*(1-0.18*f)), 0.030)

    # EARS (raised to cranium-bottom level; helix near z=0.142)
    for s in (-1, 1):
        ear_c = np.array([s*0.0700, 0.0065, 0.1130])
        d = uni(d, sd_ellipsoid(p, ear_c, np.array([0.0045, 0.0125, 0.0290])), 0.012)

    # EYE LID volumes
    for s in (-1, 1):
        pup = A['pupil'].copy(); pup[0]=s*pup[0]
        a = pup + np.array([-0.019*m.eyeW, 0.0015, 0.0140]); b = pup + np.array([0.019*m.eyeW, 0.0015, 0.0128])
        d = uni(d, sd_capsule(p, a, b, 0.0048*(1-0.15*f)), 0.012)
        a = pup + np.array([-0.017*m.eyeW, 0.0010, -0.0128]); b = pup + np.array([0.017*m.eyeW, 0.0008, -0.0118])
        d = uni(d, sd_capsule(p, a, b, 0.0036), 0.010)

    # NECK STUB
    d = uni(d, sd_capsule(p, np.array([0, 0.014, -0.050]), np.array([0, 0.016, -0.110]), 0.0530*(1-0.06*f)), 0.05)
    d = uni(d, sd_ball(p, np.array([0, 0.012, -0.022]), 0.043), 0.03)

    # ---- NEGATIVES -----------------------------------------------------------
    for s in (-1, 1):
        pup = A['pupil'].copy(); pup[0]=s*pup[0]
        neg = sd_ball(p, pup - np.array([0, 0.0050, 0.000]), 0.0150*m.eyeD)
        d = smax(d, -neg, 0.008)
        io_ = A['canthus_i'].copy(); io_[0]=s*io_[0]
        oo_ = A['canthus_o'].copy(); oo_[0]=s*oo_[0]
        slit = sd_capsule(p, io_ + np.array([0,0.0025,-0.0002]), oo_ + np.array([0,0.0025,-0.0002]), 0.0060*m.eyeW)
        d = smax(d, -slit, 0.004)
    for s in (-1, 1):
        n = np.array([s*0.0082*m.noseW, A['pronasale'][1]+0.0055, A['pronasale'][2]-0.0115])
        d = smax(d, -sd_ball(p, n, 0.0048*m.noseW), 0.005)
    for s in (-1, 1):
        c = np.array([s*0.0685, 0.0055, 0.1060])
        d = smax(d, -sd_capsule(p, c, c + np.array([s*0.014, 0.002, 0]), 0.0042), 0.004)
    d = smax(d, -sd_capsule(p, A['mentolab']+np.array([-0.008,0,0]), A['mentolab']+np.array([0.008,0,0]), 0.0045), 0.006)
    # NOTE: mouth-slit SDF cut removed — it severed lips/jaw from the face;
    # the lip seam is now a shallow wrinkle pass instead.

    return d

def wrinkle_paths(m: HeadMorph):
    """Anatomical wrinkle/crease paths. Each: dict(name, pts list[Nx3 arrays],
    depth, width, bulge). Muscle-anchored, mirrored where appropriate."""
    A = m.anchors()
    age_k = max(0.0, (m.age - 24.0)) / 40.0
    P = []
    def pair(rows):
        a = np.array(rows); b = a.copy(); b[:,0] *= -1
        return [a, b]

    def naso(s):
        al = np.array([s*0.0165*m.noseW, A['pronasale'][1]+0.007, A['pronasale'][2]-0.006])
        mc = np.array([s*0.0175*m.mouthW, A['stomion'][1]+0.004, 0.0645])
        jw = np.array([s*0.0260, A['stomion'][1]+0.006, 0.0430])
        return np.array([al, (al+mc)/2 + np.array([0,0.001,0.001]), mc + np.array([0,0.0025,0]), jw])
    P.append(dict(name='nasolabial', pts=[naso(1), naso(-1)], depth=0.0022*(0.45+0.9*age_k), width=0.0090, bulge=0.0016*(0.4+age_k)))

    io_i = np.array(A['canthus_i']); oo_o = np.array(A['canthus_o'])
    P.append(dict(name='teartrough', pts=pair([[io_i[0], io_i[1]-0.001, io_i[2]-0.004],
                                               [(io_i[0]+oo_o[0])/2, (io_i[1]+oo_o[1])/2-0.0015, (io_i[2]+oo_o[2])/2-0.0105],
                                               [oo_o[0], oo_o[1]+0.001, oo_o[2]-0.006]]),
                  depth=0.0013*(0.5+0.8*age_k), width=0.0060, bulge=0.0004))

    def crow(s):
        oo_ = np.array(A['canthus_o']); oo_[0]=s*oo_[0]
        out=[oo_ - [s*0.001,0,0.001]]
        for k in range(4):
            a2 = 0.35 + k*0.22
            out.append(oo_ + np.array([s*np.cos(a2)*0.016, -np.sin(a2)*0.006, -np.sin(a2)*0.014]))
        return np.array(out)
    P.append(dict(name='crowsfeet', pts=[crow(1), crow(-1)], depth=0.0012*(0.3+0.9*age_k), width=0.0050, bulge=0.0002))

    for i, zz in enumerate([0.1450, 0.1560, 0.1670][:3 if m.age>40 else 2]):
        arc = []
        for xx in np.linspace(-0.030, 0.030, 7):
            sag = -0.0415 - 0.0035*np.cos(xx/0.045*np.pi/2)
            arc.append([xx, sag, zz + 0.001*np.abs(xx)])
        P.append(dict(name=f'forehead{i}', pts=[np.array(arc)], depth=0.0009*(0.4+0.8*age_k), width=0.0068, bulge=0.0003))

    g = A['glabella']
    for s in (-0.004, 0.004):
        P.append(dict(name='glabella', pts=[np.array([[s, g[1]-0.002, 0.1215],[s*1.4, g[1]-0.002, 0.1140]])],
                      depth=0.0011*(0.2+0.9*age_k), width=0.0050, bulge=0.0002))

    def marion(s):
        mc = np.array([s*0.0180*m.mouthW, A['stomion'][1]+0.004, 0.0640])
        jw = np.array([s*0.0240, A['stomion'][1]+0.008, 0.0360])
        return np.array([mc, (mc+jw)/2 + np.array([s*0.001,0.002,0]), jw])
    P.append(dict(name='marionette', pts=[marion(1), marion(-1)], depth=0.0014*age_k, width=0.0075, bulge=0.0005))

    ml = A['mentolab']
    P.append(dict(name='mentolabial', pts=[np.array([[-0.010, ml[1]+0.001, ml[2]+0.001],[0, ml[1]-0.0005, ml[2]+0.0005],[0.010, ml[1]+0.001, ml[2]+0.001]])],
                  depth=0.0010*(0.5+0.6*age_k), width=0.0060, bulge=0.0004))

    for s in (-1,1):
        P.append(dict(name='philtrum', pts=[np.array([[s*0.0042, A['subnasale'][1]-0.0045, 0.0795],[s*0.0044, A['stomion'][1]+0.003, 0.0725]])],
                      depth=0.0006, width=0.0040, bulge=0.0))
    # lip seam (stomion) — shallow surface crease, all ages
    mW2 = 0.0165*m.mouthW
    seam = np.array([[-mW2*1.02, A['stomion'][1]-0.0010, 0.0660],
                     [0, A['stomion'][1]-0.0022, 0.0656],
                     [mW2*1.02, A['stomion'][1]-0.0010, 0.0660]])
    P.append(dict(name='lipseam', pts=[seam], depth=0.0009, width=0.0038, bulge=0.0))

    for i, zz in enumerate([0.010, -0.012, -0.034]):
        ring = np.array([[np.cos(t)*0.055, 0.010 - 0.012*np.cos(t)**2, zz + 0.002*np.sin(3*t)] for t in np.linspace(0, 2*np.pi, 18)])
        P.append(dict(name=f'neckring{i}', pts=[ring], depth=0.0011*(0.4+0.7*age_k), width=0.0090, bulge=0.0004))

    for s in (-1,1):
        ec = np.array([s*0.0700, 0.0065, 0.1130])
        helix = np.array([[ec[0]+s*0.0035*np.sin(t), ec[1]-0.0066*np.cos(t*1.2), ec[2]+0.0260*np.sin(t*0.9)] for t in np.linspace(-0.8, 2.4, 10)])
        P.append(dict(name='earhelix', pts=[helix], depth=0.0016, width=0.0055, bulge=0.0008))
        anti = np.array([[ec[0]+s*0.0012*np.sin(t*1.1+1), ec[1]-0.0040, ec[2]+0.0140*np.sin(t*0.8)] for t in np.linspace(0, 2.2, 8)])
        P.append(dict(name='earantihelix', pts=[anti], depth=0.0012, width=0.0045, bulge=0.0006))
        pup = A['pupil'].copy(); pup[0]=s*pup[0]
        lid = np.array([pup + [-0.018*m.eyeW, 0.0030, 0.0090], pup + [0, 0.0025, 0.0095], pup + [0.018*m.eyeW, 0.0030, 0.0080]])
        P.append(dict(name='lidcrease', pts=[lid], depth=0.0009*(0.7+0.5*(1-m.fem)), width=0.0045, bulge=0.0))
    return P
