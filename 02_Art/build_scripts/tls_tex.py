#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE LAST SIN - procedural texture generation (numpy, headless-safe).
All textures are original, generated here; palette per GAME_BIBLE §7.2:
  SLT #3A4550 | MSS #5A6B4A | BRF #6E5340 | CDL #E8A34D | SBL #7FA8C9 | INK #1C2226 | PPR #D9CBB2
Outputs per material set: _BaseColor (sRGB), _Normal (linear, OpenGL Y+), _ORM (R=AO G=Rough B=Metal).
"""
import math
import numpy as np

SLT = (0.227, 0.271, 0.314)   # slate stone
MSS = (0.353, 0.420, 0.290)   # wet moss
BRF = (0.431, 0.325, 0.251)   # oak wood
CDL = (0.910, 0.639, 0.302)   # candle flame / warm light
SBL = (0.498, 0.659, 0.788)   # mist/moon blue
INK = (0.110, 0.133, 0.149)   # register ink
PPR = (0.851, 0.796, 0.698)   # paper

def _tiled_fbm(res, octaves=5, seed=1, base_freq=4):
    """Tileable value-noise fBM in [0,1]."""
    rng = np.random.default_rng(seed)
    out = np.zeros((res, res), dtype=np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        f = base_freq * (2 ** o)
        g = rng.random((f, f)).astype(np.float32)
        # tileable upsample via np.interp grid
        xi = np.linspace(0, f, res, endpoint=False)
        gx, gy = np.meshgrid(xi, xi)
        x0 = np.floor(gx).astype(int) % f
        x1 = (x0 + 1) % f
        y0 = np.floor(gy).astype(int) % f
        y1 = (y0 + 1) % f
        tx = gx - np.floor(gx)
        ty = gy - np.floor(gy)
        tx = tx * tx * (3 - 2 * tx)
        ty = ty * ty * (3 - 2 * ty)
        v = (g[y0, x0] * (1 - tx) * (1 - ty) + g[y0, x1] * tx * (1 - ty) +
             g[y1, x0] * (1 - tx) * ty + g[y1, x1] * tx * ty)
        out += amp * v
        total += amp
        amp *= 0.55
    return out / total

def _voronoi(res, cells, seed, jitter=0.9):
    """Tileable voronoi: returns (edge01, cellid)."""
    rng = np.random.default_rng(seed)
    pts = rng.random((cells, 2)) * res
    yy, xx = np.mgrid[0:res, 0:res]
    d1 = np.full((res, res), 1e18, np.float32)
    d2 = np.full((res, res), 1e18, np.float32)
    cid = np.zeros((res, res), np.int32)
    for i in range(cells):
        px, py = pts[i]
        dx = np.abs(xx - px); dx = np.minimum(dx, res - dx)
        dy = np.abs(yy - py); dy = np.minimum(dy, res - dy)
        d = dx * dx + dy * dy
        m2 = d < d2
        d2[m2] = d[m2]
        m1 = d < d1
        d2[m1] = d1[m1]
        d1[m1] = d[m1]
        cid[m1] = i
    edge = np.clip((np.sqrt(d2) - np.sqrt(d1)) / 5.0, 0, 1)
    return edge.astype(np.float32), cid

def height_to_normal(height, strength=1.6):
    """Height (HxW float) -> OpenGL Y+ tangent normal, HxWx3 float."""
    h = height.astype(np.float32)
    gx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5 * strength
    gy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * 0.5 * strength
    nz = np.ones_like(h)
    ln = np.sqrt(gx * gx + gy * gy + nz * nz)
    n = np.dstack([-gx / ln, gy / ln, nz / ln])
    return (n * 0.5 + 0.5).astype(np.float32)

def pack_orm(ao, rough, metal):
    return np.dstack([np.clip(ao, 0, 1), np.clip(rough, 0, 1),
                      np.clip(metal, 0, 1)]).astype(np.float32)

def to_rgb(a, col):
    return np.clip(a[..., None] * np.array(col, np.float32)[None, None, :], 0, 1).astype(np.float32)

# ------------------------------------------------------------------ materials
def uv_checker(res=1024):
    """TLS-TEX-001: rainbow quadrant checker with sector numbers per quadrant."""
    yy, xx = np.mgrid[0:res, 0:res]
    u = xx / res; v = 1.0 - yy / res
    grid = 8
    gu = (u * grid).astype(int); gv = (v * grid).astype(int)
    checker = ((gu + gv) % 2) * 0.55 + 0.25
    hues = np.array([[0.85, 0.30, 0.25], [0.30, 0.75, 0.30],
                     [0.25, 0.40, 0.90], [0.90, 0.80, 0.20]], np.float32)
    qi = (np.dstack([u, v]) * 2).astype(int)
    qid = np.clip(qi[..., 0], 0, 1) * 2 + np.clip(qi[..., 1], 0, 1)
    col = hues[qid]
    out = col * checker[..., None]
    # sector index lines every 1/8
    lines = ((np.abs((u * grid) % 1 - 0.5) > 0.47) | (np.abs((v * grid) % 1 - 0.5) > 0.47))
    out = out * (1 - lines[..., None] * 0.4)
    return out.astype(np.float32)

def gen_slate(res=1024, seed=41):
    """TLS-MAT-001: wet Blackthorne slate - layered stone, damp variation, moss tint in crevices."""
    rock = _tiled_fbm(res, octaves=6, seed=seed, base_freq=6)
    strata = np.sin((np.linspace(0, res, res, endpoint=False) / res) * res * 0.20 +
                    rock * 6.0) * 0.5 + 0.5
    grain = _tiled_fbm(res, octaves=4, seed=seed + 1, base_freq=48)
    wet = _tiled_fbm(res, octaves=3, seed=seed + 2, base_freq=3)
    height = np.clip(rock * 0.55 + strata * 0.25 + grain * 0.2, 0, 1)
    base = 0.42 + height * 0.30 - wet * 0.18
    col = to_rgb(np.clip(base, 0, 1), SLT)
    moss_mask = np.clip((1 - height) * wet - 0.45, 0, 1) * 1.6
    col = col * (1 - moss_mask[..., None] * 0.55) + \
        to_rgb(moss_mask * 0.5, MSS) * (moss_mask[..., None] * 0.55)
    rough = np.clip(0.62 + wet * 0.25 - (wet > 0.62) * 0.28, 0, 1)
    ao = np.clip(0.55 + height * 0.45, 0, 1)
    return col, height_to_normal(height, 2.2), pack_orm(ao, rough, np.zeros_like(height))

def gen_oak(res=1024, seed=57):
    """TLS-MAT-002: freshly cut oak planks with nail line, per GAME_BIBLE BRF."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:res, 0:res]
    planks = 5
    ph = res // planks
    col = np.zeros((res, res, 3), np.float32)
    height = np.zeros((res, res), np.float32)
    rough = np.zeros((res, res), np.float32)
    for p in range(planks):
        m0, m1 = p * ph, (p + 1) * ph
        tone = 0.85 + rng.uniform(-0.12, 0.12)
        gfreq = rng.uniform(14, 22)
        rings = (np.sin((yy[m0:m1] / res * gfreq + _tiled_fbm(res, 4, seed + p, 8)[m0:m1] * 3.0)) * 0.5 + 0.5)
        fib = _tiled_fbm(res, 5, seed + 10 + p, 60)[m0:m1]
        h = rings * 0.6 + fib * 0.4
        c = to_rgb(np.clip(h * 0.5 + 0.35, 0, 1) * tone, BRF)
        col[m0:m1] = c
        height[m0:m1] = h
        rough[m0:m1] = np.clip(0.55 + fib * 0.2 - rings * 0.08, 0, 1)
    # plank gaps
    for p in range(1, planks):
        height[p * ph - 2:p * ph + 2] *= 0.25
        col[p * ph - 2:p * ph + 2] *= 0.45
    # knots
    for _ in range(3):
        px, py = rng.integers(0, res, 2)
        r = rng.integers(res // 40, res // 25)
        d = np.sqrt(((xx - px) % res) ** 2 + ((yy - py) % res) ** 2)
        knot = np.clip(1 - d / r, 0, 1)
        col = col * (1 - knot[..., None] * 0.5) + to_rgb(knot, INK) * (knot[..., None] * 0.5)
        height += knot * 0.25
    ao = np.clip(0.5 + height * 0.5, 0, 1)
    return col, height_to_normal(height, 1.8), pack_orm(ao, rough, np.zeros_like(height))

def gen_wool(res=1024, seed=71, col_in=(0.32, 0.30, 0.27)):
    """TLS-MAT-003: coarse Welsh working wool twill."""
    res2 = res
    yy, xx = np.mgrid[0:res2, 0:res2]
    threads = 110
    wx = np.sin(xx / res2 * math.pi * threads * 2) * 0.5 + 0.5
    wy = np.sin(yy / res2 * math.pi * threads * 2) * 0.5 + 0.5
    twill = ((xx // (res2 // threads) + yy // (res2 // threads)) % 2)
    weave = wx * 0.45 + wy * 0.45 + twill * 0.10
    fuzz = _tiled_fbm(res2, 4, seed, 90)
    n = np.random.default_rng(seed + 1).normal(0, 0.05, (res2, res2)).astype(np.float32)
    height = np.clip(weave * 0.8 + fuzz * 0.2 + n, 0, 1)
    tone = 0.72 + height * 0.42
    col = to_rgb(np.clip(tone, 0, 1), col_in)
    rough = np.full((res2, res2), 0.85, np.float32) - fuzz * 0.08
    ao = np.clip(0.45 + height * 0.55, 0, 1)
    return col, height_to_normal(height, 1.2), pack_orm(ao, rough, np.zeros_like(height))

def gen_brass(res=1024, seed=83):
    """TLS-MAT-004: aged brass with patina in crevices (lantern/plates)."""
    pat = _voronoi(res, 130, seed)[0]
    blotch = _tiled_fbm(res, 5, seed + 1, 6)
    polish = _tiled_fbm(res, 4, seed + 2, 24)
    height = np.clip(0.6 + polish * 0.4 - pat * 0.3, 0, 1)
    bright = to_rgb(np.clip(0.55 + polish * 0.45, 0, 1), (0.83, 0.66, 0.33))
    verd = to_rgb(np.clip(blotch, 0, 1) * 0.9, (0.34, 0.52, 0.42))
    pmask = np.clip(blotch - 0.44, 0, 1) * 1.8 + pat * 0.25
    col = bright * (1 - np.clip(pmask, 0, 1)[..., None]) + verd * np.clip(pmask, 0, 1)[..., None]
    metal = np.clip(1.0 - np.clip(pmask, 0, 1) * 0.9, 0, 1)
    rough = np.clip(0.28 + pat * 0.35 + blotch * 0.25, 0, 1)
    ao = np.clip(0.55 + height * 0.45, 0, 1)
    return col, height_to_normal(height, 0.9), pack_orm(ao, rough, metal)

def gen_stone_wall(res=1024, seed=97, mortar_dark=True):
    """KIT-A wall: coursed rubble stone + lime mortar (W-01 base)."""
    edge, cid = _voronoi(res, 46, seed, jitter=1.0)
    rng = np.random.default_rng(seed + 1)
    cell_tone = rng.uniform(0.55, 1.0, cid.max() + 1)[cid]
    rock = _tiled_fbm(res, 5, seed + 2, 10)
    wet = _tiled_fbm(res, 3, seed + 3, 3)
    mortar = np.clip(1.0 - edge * 1.2, 0, 1)
    height = np.clip(cell_tone * 0.5 + rock * 0.35, 0, 1) * edge + mortar * 0.25
    stone_col = to_rgb(np.clip(0.45 + cell_tone * 0.35 + rock * 0.2, 0, 1), (0.55, 0.56, 0.53))
    mortar_col = to_rgb(np.clip(0.5 + wet * 0.3, 0, 1), (0.47, 0.46, 0.42))
    col = stone_col * edge[..., None] + mortar_col * (1 - edge[..., None])
    moss = np.clip(wet - 0.55, 0, 1) * np.clip(1 - height, 0, 1) * 2.2
    col = col * (1 - moss[..., None] * 0.4) + to_rgb(moss * 0.6, MSS) * (moss[..., None] * 0.4)
    damp = np.clip(wet * 0.5 - 0.15, 0, 1)
    col *= (1 - damp[..., None] * 0.25)
    rough = np.clip(0.55 + mortar * 0.3 - wet * 0.25, 0, 1)
    ao = np.clip(0.35 + edge * 0.5 + height * 0.25, 0, 1)
    return col, height_to_normal(height, 2.6), pack_orm(ao, rough, np.zeros_like(height))

def gen_slate_roof(res=1024, seed=113):
    """Slate roof tiles - coursed overlapping slates, wet sheen."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:res, 0:res]
    rows = 10; cols = 8
    rh = res / rows; cw = res / cols
    ry = (yy // rh).astype(int); cx = (xx // cw).astype(int)
    off = (ry % 2) * 0.5
    tone = rng.uniform(0.7, 1.05, (rows, cols + 1))[(ry, cx + 0)]
    micro = _tiled_fbm(res, 5, seed + 1, 40)
    gap_y = np.abs((yy % rh) - rh / 2) > rh / 2 - 3
    gap_x = np.abs(((xx + off * cw) % cw) - cw / 2) > cw / 2 - 3
    height = tone * (0.55 + micro * 0.3)
    height[gap_y] *= 0.3; height[gap_x] *= 0.35
    col = to_rgb(np.clip(0.35 + tone * 0.35 + micro * 0.18, 0, 1), SLT)
    lichen = np.clip(_tiled_fbm(res, 4, seed + 2, 8) - 0.5, 0, 1) * (gap_y == False)
    col = col * (1 - lichen[..., None] * 0.35) + to_rgb(lichen, (0.62, 0.63, 0.48)) * (lichen[..., None] * 0.35)
    wet = _tiled_fbm(res, 3, seed + 3, 3)
    rough = np.clip(0.45 + wet * 0.3 - micro * 0.1, 0, 1)
    ao = np.clip(0.4 + (1 - gap_y * 0.7) * 0.5, 0, 1)
    return col, height_to_normal(height, 2.4), pack_orm(ao, rough, np.zeros_like(height))

def gen_bark(res=1024, seed=131):
    """Oak/ash bark: deep vertical fissures (TLS-MAT-005 layer + trees)."""
    fiss = _voronoi(res, 90, seed, jitter=1.3)[0]
    vnoise = _tiled_fbm(res, 5, seed + 1, 7)
    yy = np.linspace(0, 1, res, endpoint=False)[:, None]
    streak = _tiled_fbm(res, 4, seed + 2, 5) * 0.6 + 0.4
    height = np.clip(fiss * 0.45 + vnoise * 0.35 + streak * 0.2, 0, 1)
    col = to_rgb(np.clip(0.35 + height * 0.4, 0, 1), (0.30, 0.27, 0.23))
    moss = np.clip(vnoise - 0.55, 0, 1) * 2.0 * np.clip(streak - 0.4, 0, 1)
    col = col * (1 - moss[..., None] * 0.45) + to_rgb(moss * 0.7, MSS) * (moss[..., None] * 0.45)
    rough = np.clip(0.7 + fiss * 0.2, 0, 1)
    ao = np.clip(0.3 + fiss * 0.6, 0, 1)
    return col, height_to_normal(height, 2.8), pack_orm(ao, rough, np.zeros_like(height))

def gen_peat(res=1024, seed=149):
    """Moor peat soil - wet, fibrous, dark (TLS-MAT-005 layer)."""
    fib = _tiled_fbm(res, 5, seed, 30)
    clumps = _voronoi(res, 70, seed + 1)[0]
    wet = _tiled_fbm(res, 3, seed + 2, 3)
    height = np.clip(fib * 0.6 + clumps * 0.4, 0, 1)
    col = to_rgb(np.clip(0.22 + height * 0.28, 0, 1), (0.21, 0.18, 0.14))
    pool = np.clip(wet - 0.62, 0, 1) * 2.5
    col = col * (1 - pool[..., None] * 0.6) + to_rgb(pool, SBL) * (pool[..., None] * 0.6)
    rough = np.clip(0.75 - pool * 0.6 + fib * 0.1, 0, 1)
    ao = np.clip(0.4 + height * 0.5, 0, 1)
    return col, height_to_normal(height, 2.0), pack_orm(ao, rough, np.zeros_like(height))

def gen_heather(res=1024, seed=163):
    """Moor heather ground cover (TLS-MAT-005 layer)."""
    clump, cid = _voronoi(res, 120, seed)
    rng = np.random.default_rng(seed + 1)
    tone = rng.uniform(0.6, 1.1, cid.max() + 1)[cid]
    n = _tiled_fbm(res, 5, seed + 2, 24)
    height = np.clip(clump * 0.5 + n * 0.5, 0, 1)
    base = to_rgb(np.clip(0.3 + tone * 0.3 + n * 0.2, 0, 1), (0.29, 0.31, 0.22))
    purple = to_rgb(np.clip(n, 0, 1), (0.38, 0.24, 0.30))
    mask = np.clip(tone - 0.75, 0, 1)[..., None]
    col = base * (1 - mask) + purple * mask
    rough = np.full((res, res), 0.8, np.float32)
    ao = np.clip(0.4 + height * 0.5, 0, 1)
    return col, height_to_normal(height, 1.6), pack_orm(ao, rough, np.zeros_like(height))

def gen_iron(res=1024, seed=181, rust=0.55):
    """Rusted wrought iron (gate key, Y Porth door, fences)."""
    r1 = _tiled_fbm(res, 5, seed, 8)
    r2 = _voronoi(res, 100, seed + 1)[0]
    ham = _tiled_fbm(res, 4, seed + 2, 30)
    height = np.clip(ham * 0.4 + r1 * 0.4, 0, 1)
    dark = to_rgb(np.clip(0.25 + height * 0.25, 0, 1), (0.23, 0.23, 0.24))
    rust_col = to_rgb(np.clip(0.4 + r1 * 0.35, 0, 1), (0.45, 0.28, 0.16))
    rmask = np.clip(r1 * 0.7 + r2 * 0.5 - (1 - rust), 0, 1)
    col = dark * (1 - rmask[..., None]) + rust_col * rmask[..., None]
    metal = np.clip(1.0 - rmask * 1.1, 0, 1)
    rough = np.clip(0.45 + rmask * 0.4 + ham * 0.1, 0, 1)
    ao = np.clip(0.5 + height * 0.4, 0, 1)
    return col, height_to_normal(height, 1.4), pack_orm(ao, rough, metal)

def gen_leather(res=1024, seed=193, col_in=(0.30, 0.22, 0.15)):
    """Old leather (ledger cover, satchels, boots)."""
    edge, cid = _voronoi(res, 160, seed)
    grain = _tiled_fbm(res, 4, seed + 1, 50)
    creases = _tiled_fbm(res, 4, seed + 2, 5)
    height = np.clip(edge * 0.4 + grain * 0.35 + creases * 0.25, 0, 1)
    tone = 0.55 + height * 0.5
    col = to_rgb(np.clip(tone, 0, 1), col_in)
    wear = np.clip(creases * 1.4 - 0.65, 0, 1)
    col = col * (1 - wear[..., None] * 0.4) + to_rgb(wear, (0.62, 0.55, 0.44)) * (wear[..., None] * 0.4)
    rough = np.clip(0.5 + edge * 0.25 + creases * 0.15, 0, 1)
    ao = np.clip(0.45 + edge * 0.35 + height * 0.2, 0, 1)
    return col, height_to_normal(height, 1.1), pack_orm(ao, rough, np.zeros_like(height))

def gen_paper(res=1024, seed=211):
    """Register paper PPR with fiber and foxing stains."""
    fib = _tiled_fbm(res, 5, seed, 60)
    fox = _voronoi(res, 26, seed + 1)[0]
    blotch = _tiled_fbm(res, 3, seed + 2, 4)
    height = np.clip(0.5 + fib * 0.5, 0, 1)
    col = to_rgb(np.clip(0.75 + fib * 0.2, 0, 1), PPR)
    fmask = np.clip(blotch * 0.8 + (1 - fox) * 0.2 - 0.55, 0, 1) * 1.5
    col = col * (1 - fmask[..., None] * 0.5) + to_rgb(fmask, (0.52, 0.42, 0.28)) * (fmask[..., None] * 0.5)
    rough = np.full((res, res), 0.72, np.float32) - fib * 0.08
    ao = np.ones((res, res), np.float32)
    return col, height_to_normal(height, 0.4), pack_orm(ao, rough, np.zeros_like(height))

def gen_thatch(res=1024, seed=227):
    """Weathered straw thatch (Nan's cottage roof later)."""
    yy, xx = np.mgrid[0:res, 0:res]
    strands = 150
    ang = _tiled_fbm(res, 4, seed, 6) * 0.8 + 0.4
    s = np.sin(xx / res * strands * math.pi + yy / res * 6) * 0.5 + 0.5
    n = _tiled_fbm(res, 5, seed + 1, 40)
    height = np.clip(s * 0.5 + n * 0.5, 0, 1)
    col = to_rgb(np.clip(0.45 + height * 0.4, 0, 1), (0.55, 0.47, 0.30))
    dark = np.clip(n - 0.55, 0, 1) * 1.6
    col = col * (1 - dark[..., None] * 0.45) + to_rgb(dark, (0.28, 0.24, 0.16)) * (dark[..., None] * 0.45)
    rough = np.full((res, res), 0.82, np.float32)
    ao = np.clip(0.4 + height * 0.55, 0, 1)
    return col, height_to_normal(height, 2.0), pack_orm(ao, rough, np.zeros_like(height))

def gen_leaf_card(res=512, seed=241, col_in=(0.28, 0.33, 0.18)):
    """Hawthorn leaf cluster alpha card: RGB + alpha channel."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:res, 0:res]
    a = np.zeros((res, res), np.float32)
    for _ in range(9):
        cx, cy = rng.uniform(0.2, 0.8, 2) * res
        rot = rng.uniform(0, math.pi)
        ln = rng.uniform(res * 0.12, res * 0.22)
        wd = ln * rng.uniform(0.35, 0.55)
        ca, sa = math.cos(rot), math.sin(rot)
        dx = xx - cx; dy = yy - cy
        u = (dx * ca + dy * sa); v = (-dx * sa + dy * ca)
        m = (np.abs(u) < ln / 2) & (np.abs(v) < wd * (1 - np.abs(u) / (ln / 2)) ** 0.5)
        a[m] = np.maximum(a[m], 0.9)
    n = _tiled_fbm(res, 4, seed + 1, 30)
    col = to_rgb(np.clip(0.5 + n * 0.5, 0, 1), col_in)
    rgba = np.dstack([col, np.clip(a + n * 0.1, 0, 1) * (a > 0)]).astype(np.float32)
    return rgba, rgba[..., 3]

def gen_grass_card(res=512, seed=257, col_in=(0.30, 0.36, 0.20)):
    """Grass tuft alpha card."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:res, 0:res]
    a = np.zeros((res, res), np.float32)
    for i in range(22):
        bx = res * (0.15 + 0.7 * (i % 11) / 11) + rng.uniform(-8, 8)
        bend = rng.uniform(-0.5, 0.5)
        h = rng.uniform(res * 0.4, res * 0.9)
        w = rng.uniform(2.5, 5.0)
        for y in range(res):
            t = 1 - y / res
            if t > 1 or y > h:
                continue
            x = bx + bend * (h - y) ** 1.4 / h ** 0.4
            lo, hi = x - w * t, x + w * t
            m = (xx[y] >= lo) & (xx[y] <= hi)
            a[y, m] = 1.0
    n = _tiled_fbm(res, 3, seed + 1, 20)
    col = to_rgb(np.clip(0.45 + n * 0.4 + (yy / res) * 0.25, 0, 1), col_in)
    rgba = np.dstack([col, a]).astype(np.float32)
    return rgba, a

def gen_fern_card(res=512, seed=271):
    """Bracken frond alpha card (moor/marsh)."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:res, 0:res]
    a = np.zeros((res, res), np.float32)
    spine_x = res * 0.5
    a[:, int(spine_x) - 3:int(spine_x) + 3] = 1.0
    for i in range(14):
        t = i / 14
        y = res * 0.08 + t * res * 0.85
        ln = (1 - t) * res * 0.42 + res * 0.06
        for side in (-1, 1):
            x0 = spine_x + side * 3
            x1 = x0 + side * ln
            for t2 in np.linspace(0, 1, 30):
                xk = x0 + (x1 - x0) * t2
                yk = y - abs(side) * 0 + t2 * res * 0.03
                w = 3.5 * (1 - t2) + 1
                m = (np.abs(xx - xk) < w) & (np.abs(yy - yk) < 4)
                a[m] = 1.0
    n = _tiled_fbm(res, 3, seed + 1, 24)
    col = to_rgb(np.clip(0.4 + n * 0.45, 0, 1), (0.33, 0.34, 0.20))
    rgba = np.dstack([col, a]).astype(np.float32)
    return rgba, a

def gen_wax(res=256, seed=283):
    """Candle wax / drips + flame-ready emissive color helper."""
    n = _tiled_fbm(res, 4, seed, 18)
    height = np.clip(0.4 + n * 0.6, 0, 1)
    col = to_rgb(np.clip(0.7 + n * 0.25, 0, 1), (0.88, 0.84, 0.74))
    rough = np.full((res, res), 0.45, np.float32) - n * 0.1
    ao = np.clip(0.5 + height * 0.5, 0, 1)
    return col, height_to_normal(height, 0.8), pack_orm(ao, rough, np.zeros_like(height))
