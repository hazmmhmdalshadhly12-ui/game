#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE LAST SIN - procedural PBR texture generator v2 (numpy + PIL).
Produces real PNG map sets (BaseColor / Roughness / Normal / Alpha) saved to disk.
"""
import os
import numpy as np
from PIL import Image
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sculpt_lib import value_noise3, fbm3, _hash3

def _norm(h):
    """height (H,W) -> tangent-space normal RGB."""
    gx = np.gradient(h, axis=1) * 4.0
    gy = np.gradient(h, axis=0) * 4.0
    n = np.dstack([-gx, -gy, np.ones_like(h)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return ((n * 0.5 + 0.5) * 255).astype(np.uint8)

def save(name, outdir, base=None, rough=None, normal_h=None, alpha=None, metal=None, size=1024):
    os.makedirs(outdir, exist_ok=True)
    paths = []
    def _sv(arr, suf):
        p = os.path.join(outdir, f"{name}_{suf}.png")
        Image.fromarray(arr).save(p)
        paths.append(p)
    if base is not None: _sv(np.clip(base, 0, 255).astype(np.uint8), "BC")
    if rough is not None: _sv(np.clip(rough * 255, 0, 255).astype(np.uint8), "R")
    if normal_h is not None: _sv(_norm(normal_h), "N")
    if metal is not None: _sv(np.clip(metal * 255, 0, 255).astype(np.uint8), "M")
    if alpha is not None:
        bc = base if base.ndim == 3 else np.dstack([base] * 3)
        rgba = np.dstack([np.clip(bc[..., 0], 0, 255).astype(np.uint8),
                          np.clip(bc[..., 1], 0, 255).astype(np.uint8),
                          np.clip(bc[..., 2], 0, 255).astype(np.uint8),
                          np.clip(alpha * 255, 0, 255).astype(np.uint8)])
        p = os.path.join(outdir, f"{name}_RGBA.png")
        Image.fromarray(rgba, "RGBA").save(p)
        paths.append(p)
    return paths

def _uv_grid(size):
    v, u = np.mgrid[0:size, 0:size]
    return u / size, v / size

# ------------------------------------------------------------- characters
def skin_maps(outdir, prm=None, size=1024):
    """Weathered 1840s male skin: tone + redness + stubble zone + blemishes."""
    prm = prm or {}
    u, v = _uv_grid(size)
    hue = prm.get("tone", (198, 168, 148))  # pale weathered
    base = np.zeros((size, size, 3), np.float64)
    base[..., 0] = hue[0]; base[..., 1] = hue[1]; base[..., 2] = hue[2]
    n1 = fbm3(u * 24, v * 24, 0.5, 3, seed=11)
    base *= (0.88 + 0.24 * n1)[..., None]
    # redness zones: cheeks/nose/ears (u bands), v mid
    red = np.exp(-(((u - 0.5) / 0.38) ** 2)) * np.exp(-(((v - 0.55) / 0.30) ** 2))
    red += 0.5 * np.exp(-(((u - 0.15) / 0.08) ** 2)) + 0.5 * np.exp(-(((u - 0.85) / 0.08) ** 2))
    base[..., 0] += 22 * red
    base[..., 1] -= 6 * red
    # darker eye band + brow band
    base *= (1.0 - 0.16 * np.exp(-(((v - 0.40) / 0.035) ** 2)))[..., None]
    # stubble zone (lower face): dark gray-brown speckle
    stub = np.clip((v - 0.60) / 0.25, 0, 1) * np.exp(-(((u - 0.5) / 0.42) ** 2))
    speck = (value_noise3(u * size / 3.0, v * size / 3.0, 3.7, 21) > 0.62).astype(np.float64)
    base = base * (1 - 0.38 * stub * speck)[..., None] + np.dstack([70, 58, 48]) * (0.38 * stub * speck)[..., None] * 0.9
    # freckles/blemishes
    fr = (value_noise3(u * size / 9.0, v * size / 9.0, 8.1, 33) > 0.78).astype(np.float64)
    base[..., 0] -= 12 * fr; base[..., 1] -= 14 * fr; base[..., 2] -= 12 * fr
    rough = 0.56 + 0.10 * fbm3(u * 8, v * 8, 2.2, 2, seed=5)
    rough -= 0.10 * np.exp(-(((u - 0.5) / 0.06) ** 2) + -((v - 0.52) / 0.18) ** 2)  # T-zone
    rough = np.clip(rough, 0.32, 0.78)
    h = fbm3(u * size / 2.2, v * size / 2.2, 1.0, 2, seed=3) * 0.5
    return save("tls_tex_101_skin", outdir, base, rough, normal_h=h, size=size)

def cloth_maps(outdir, name, color, weave=6.0, fuzz=0.5, rough=0.72, size=1024, seed=1):
    """Woven wool: twill weave + fuzz."""
    u, v = _uv_grid(size)
    tw = ((np.floor(u * size / weave) + np.floor(v * size / weave)) % 2)
    thread = 0.82 + 0.18 * np.sin(u * size / weave * np.pi) ** 2
    base = np.zeros((size, size, 3), np.float64)
    for i in range(3):
        base[..., i] = color[i] * (0.80 + 0.26 * fbm3(u * 14, v * 14, 1.5, 3, seed=seed))
    base *= (0.90 + 0.14 * tw)[..., None] * thread[..., None]
    h = 0.5 * np.sin(u * size / weave * np.pi) + 0.5 * np.sin(v * size / weave * np.pi)
    h = h * 0.6 + fbm3(u * 40, v * 40, 0.5, 2, seed=seed + 2) * fuzz
    r = np.clip(rough + 0.08 * (1 - tw) * fuzz, 0, 1)
    return save(name, outdir, base, r, normal_h=h, size=size)

def linen_maps(outdir, color=(226, 220, 202), size=1024):
    u, v = _uv_grid(size)
    w = 3.0
    base = np.zeros((size, size, 3), np.float64)
    for i in range(3):
        base[..., i] = color[i] * (0.90 + 0.14 * fbm3(u * 30, v * 30, 0.8, 2, seed=9))
    weave = 0.88 + 0.12 * (np.sin(u * size / w * np.pi) * np.sin(v * size / w * np.pi))
    base *= weave[..., None]
    h = np.sin(u * size / w * np.pi) * np.sin(v * size / w * np.pi) * 0.4
    r = np.clip(0.62 + 0.08 * fbm3(u * 6, v * 6, 0.4, 2, seed=4), 0, 1)
    return save("tls_tex_103_linen", outdir, base, r, normal_h=h, size=size)

def leather_maps(outdir, name="tls_tex_102_leather", color=(84, 58, 40), size=1024, worn=0.5):
    u, v = _uv_grid(size)
    grain = fbm3(u * size / 26, v * size / 26, 0.6, 4, seed=17)
    cell = np.abs(fbm3(u * size / 60, v * size / 60, 0.3, 3, seed=8) - 0.5) * 2
    base = np.zeros((size, size, 3), np.float64)
    for i in range(3):
        base[..., i] = color[i] * (0.78 + 0.30 * grain - 0.22 * cell)
    wear = fbm3(u * 5, v * 5, 0.2, 2, seed=25)
    base = base * (1 - 0.35 * worn * wear)[..., None] + np.dstack([150, 128, 104]) * (0.35 * worn * wear)[..., None]
    h = grain * 0.6 + cell * 0.4
    r = np.clip(0.58 + 0.15 * cell - 0.12 * wear, 0.3, 0.85)
    return save(name, outdir, base, r, normal_h=h, size=size)

def hair_alpha(outdir, name="tls_tex_104_hair", color=(52, 38, 30), size=1024, strands=140, seed=3):
    """Hair card alpha: vertical strands with tip fade."""
    u, v = _uv_grid(size)
    alpha = np.zeros((size, size))
    rng = np.random.default_rng(seed)
    for s in range(strands):
        x0 = rng.uniform(0.02, 0.98); w = rng.uniform(0.002, 0.006)
        curve = rng.uniform(-0.06, 0.06)
        thickness = rng.uniform(0.6, 1.0)
        d = np.abs(u - (x0 + curve * (0.5 - v) ** 2))
        strand = np.exp(-(d / w) ** 2) * np.clip((1.0 - v) * 1.4, 0, 1) ** 0.5
        alpha = np.maximum(alpha, strand * thickness)
    alpha = np.clip(alpha * 1.35, 0, 1)
    tone = np.zeros((size, size, 3), np.float64)
    for i in range(3):
        tone[..., i] = color[i] * (0.75 + 0.45 * fbm3(u * 20, v * 20, 0.7, 2, seed=seed + 5))
    tone *= (0.7 + 0.5 * alpha)[..., None]
    return save(name, outdir, tone, alpha=alpha, size=size)

def stubble_alpha(outdir, size=1024, name="tls_tex_105_stubble"):
    u, v = _uv_grid(size)
    n = value_noise3(u * size / 1.3, v * size / 1.3, 5.0, 41)
    a = (n > 0.58).astype(np.float64) * 0.9
    base = np.full((size, size, 3), 60.0)
    base[..., 0] -= 8; base[..., 1] -= 4
    return save(name, outdir, base, alpha=a, size=size)

# ------------------------------------------------------------- environment
def stone_maps(outdir, name="tls_tex_201_stone_rubble", courses=9, size=1024, seed=13,
               mortar=(122, 116, 102), stone=(128, 124, 116), moss=0.35):
    """Coursed rubble stone wall: per-stone jitter, recessed mortar, moss."""
    u, v = _uv_grid(size)
    rng = np.random.default_rng(seed)
    H, W = size, size
    stone_id = np.zeros((H, W), np.int64)
    course_h = 1.0 / courses
    vrow = np.floor(v / course_h).astype(np.int64)
    per_row = [{} for _ in range(courses + 2)]
    for row in range(courses):
        m = (vrow == row)
        nstones = int(1 / (course_h * 1.1)) + 3
        edges = np.sort(rng.uniform(0, 1, nstones)); edges[0], edges[-1] = 0.0, 1.0
        rid = rng.integers(1, 100000)
        row_ids = np.digitize(u, edges) + rid * 100
        for c in np.unique(row_ids[m]):
            per_row[row][c] = rng.uniform(-0.06, 0.06)
        stone_id[m] = row_ids[m]
    # simpler: per-cell depth via noise keyed by id
    idn = (stone_id % 10007) / 10007.0
    jitter = value_noise3(idn * 50, vrow * 7.3, 1.1, seed) * 2 - 1
    # mortar: near horizontal course edges + vertical joints
    dv = np.abs((v / course_h) - np.floor(v / course_h + 0.5) * 2) * course_h * 2  # 0..1
    du = np.abs(fbm3(u * 9, vrow * 3.0, 0.3, 2, seed=seed + 1) - 0.5) * 2
    joint = np.clip((dv - 0.72) / 0.28, 0, 1) * 0.7 + np.clip((du - 0.80) / 0.20, 0, 1) * 0.5
    joint = np.clip(joint, 0, 1)
    base = np.zeros((H, W, 3), np.float64)
    for i in range(3):
        base[..., i] = stone[i] * (0.86 + 0.22 * jitter + 0.10 * fbm3(u * 18, v * 18, 0.4, 3, seed=seed + 3))
    base *= (1 - 0.55 * joint)[..., None]
    base += np.asarray(mortar) * (0.55 * joint)[..., None]
    # moss on lower area + damp
    mn = fbm3(u * 6, v * 6, 0.3, 3, seed=seed + 7)
    mzone = np.clip((0.45 - v) * 3, 0, 1) * np.clip(mn * 1.6 - 0.25, 0, 1) * moss
    base = base * (1 - 0.65 * mzone)[..., None] + np.dstack([74, 92, 52]) * (0.65 * mzone)[..., None]
    h = (0.5 + 0.35 * jitter) * (1 - 0.85 * joint) + 0.15 * fbm3(u * 30, v * 30, 0.2, 2, seed=seed + 9)
    r = np.clip(0.62 + 0.20 * joint + 0.10 * mn - 0.10 * mzone, 0, 1)
    return save(name, outdir, base, r, normal_h=h, size=size)

def wood_maps(outdir, name="tls_tex_202_oak_planks", planks=5, color=(96, 70, 44), size=1024, seed=6):
    u, v = _uv_grid(size)
    ring = np.abs(((u * 3.0 + 0.2 * np.sin(v * 40)) % 1.0) - 0.5) * 2
    grain = fbm3(u * 60, v * 8, 0.5, 3, seed=seed)
    base = np.zeros((size, size, 3), np.float64)
    for i in range(3):
        base[..., i] = color[i] * (0.82 + 0.20 * grain - 0.18 * ring)
    pv = np.floor(v * planks)
    gap = np.clip((np.abs((v * planks) % 1.0 - 0.5) * 2 - 0.86) / 0.14, 0, 1)
    base *= (1 - 0.5 * gap)[..., None]
    pid = (pv * 7919) % 13 / 13.0
    base *= (0.9 + 0.2 * pid)[..., None]
    h = (0.4 * grain + 0.3 * (1 - ring)) * (1 - 0.7 * gap)
    r = np.clip(0.68 + 0.10 * grain, 0, 1)
    return save(name, outdir, base, r, normal_h=h, size=size)

def slate_maps(outdir, name="tls_tex_203_slate", rows=10, size=1024, color=(88, 92, 96), seed=4):
    """Staggered slate tiles with lap shadow."""
    u, v = _uv_grid(size)
    row = np.floor(v * rows)
    off = ((row % 2) * 0.5)
    cu = (u + off) % 1.0
    edge_u = np.clip((cu - 0.90) / 0.10, 0, 1)
    edge_v = np.clip((((v * rows) % 1.0) - 0.82) / 0.18, 0, 1)
    gap = np.maximum(edge_u, edge_v)
    idn = ((row * 13 + np.floor(cu * 2)) % 17) / 17.0
    base = np.zeros((size, size, 3), np.float64)
    for i in range(3):
        base[..., i] = color[i] * (0.86 + 0.20 * (idn - 0.5) + 0.08 * fbm3(u * 20, v * 20, 0.4, 2, seed=seed))
    base *= (1 - 0.45 * gap)[..., None]
    # damp lichen
    ln = fbm3(u * 7, v * 7, 0.3, 2, seed=seed + 2)
    base = base * (1 - 0.3 * np.clip(ln - 0.55, 0, 1) * 2)[..., None] + np.dstack([120, 124, 88]) * (0.3 * np.clip(ln - 0.55, 0, 1) * 2)[..., None]
    h = 0.45 + 0.2 * (idn - 0.5) - 0.5 * gap
    r = np.clip(0.55 + 0.15 * gap + 0.1 * ln, 0, 1)
    return save(name, outdir, base, r, normal_h=h, size=size)

def iron_maps(outdir, name="tls_tex_204_iron", color=(52, 50, 48), size=512, rust=0.5):
    u, v = _uv_grid(size)
    n = fbm3(u * 14, v * 14, 0.4, 3, seed=31)
    base = np.zeros((size, size, 3), np.float64)
    for i in range(3):
        base[..., i] = color[i] * (0.85 + 0.25 * n)
    rn = fbm3(u * 6, v * 6, 0.2, 2, seed=37)
    rm = np.clip(rn - (1 - rust), 0, 1) * 2
    base = base * (1 - rm)[..., None] + np.dstack([124, 62, 30]) * rm[..., None]
    r = np.clip(0.55 + 0.25 * rm, 0, 1)
    m = np.clip(1 - rm * 1.5, 0, 1)
    return save(name, outdir, base, r, normal_h=n * 0.5, metal=m, size=size)

def plaster_maps(outdir, name="tls_tex_205_limewash", color=(196, 190, 172), size=1024):
    u, v = _uv_grid(size)
    n = fbm3(u * 10, v * 10, 0.4, 3, seed=43)
    base = np.zeros((size, size, 3), np.float64)
    for i in range(3):
        base[..., i] = color[i] * (0.90 + 0.14 * n)
    # cracks
    cr = (value_noise3(u * 22, v * 22, 1.2, 47) > 0.80).astype(np.float64)
    base *= (1 - 0.5 * cr)[..., None]
    h = n * 0.5 - 0.6 * cr
    r = np.clip(0.78 + 0.10 * n, 0, 1)
    return save(name, outdir, base, r, normal_h=h, size=size)

def brass_maps(outdir, name="tls_tex_206_brass", color=(168, 130, 62), size=512, patina=0.35):
    u, v = _uv_grid(size)
    n = fbm3(u * 10, v * 10, 0.4, 3, seed=51)
    base = np.zeros((size, size, 3), np.float64)
    for i in range(3):
        base[..., i] = color[i] * (0.88 + 0.18 * n)
    pn = fbm3(u * 7, v * 7, 0.3, 2, seed=53)
    pm = np.clip(pn - (1 - patina), 0, 1) * 2
    base = base * (1 - pm)[..., None] + np.dstack([74, 118, 96]) * pm[..., None]
    r = np.clip(0.38 + 0.30 * pm, 0, 1)
    m = np.clip(1 - pm, 0, 1)
    return save(name, outdir, base, r, normal_h=n * 0.4, metal=m, size=size)

def dirt_maps(outdir, name="tls_tex_207_mud", size=1024):
    u, v = _uv_grid(size)
    n = fbm3(u * 12, v * 12, 0.4, 3, seed=61)
    base = np.zeros((size, size, 3), np.float64)
    for i in range(3):
        base[..., i] = (74, 60, 46)[i] * (0.80 + 0.30 * n)
    wet = np.clip(fbm3(u * 4, v * 4, 0.2, 2, seed=63) - 0.45, 0, 1) * 2
    base *= (1 - 0.35 * wet)[..., None]
    r = np.clip(0.80 - 0.25 * wet, 0.35, 1)
    return save(name, outdir, base, r, normal_h=n * 0.5, size=size)
