#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Edmund Vale - PBR materials + generated texture set.
Textures are generated procedurally (numpy) and saved as real PNG files that
ship with the character (also packed into the .blend).

M3.6 quality pass (measured against M3.5 renders):
- skin: paler Welsh-clerk complexion, real subsurface weight/radius, tighter
  roughness band, beard-region blue-gray shadow so stubble roots read as skin
- ink stain: tightened radius (was drowning the whole hand)
- hair/stubble/brows: strand-card RGBA texture (root-to-tip gradient +
  tapered alpha) so cards stop reading as plastic ribbons
- garments: historically separated palette (charcoal coat / brown wool
  trousers / dark-brown waistcoat / ivory linen / black silk stock)
- coat: rain-damp hem darkening (Blackthorne weather)
- brass: roughness breakup + mild patina in the recesses
"""
import math, os
import numpy as np
from edmund_lib import (new_mat, set_principled, add_image_tex, add_bump,
                        img_from_array, gen_cloth_weave, gen_leather_grain,
                        gen_skin_micro, gen_iris, gen_hair_alpha, _find_socket)

# head center constants duplicated from edmund_body (kept in sync manually;
# body module imports lib only, materials must not import body -> no cycle)
_HEAD_C = (0.0, -0.004, 1.665)
_INK_HAND_C = (0.338, -0.108, 0.862)  # anatomical LEFT hand (CHR-01)

def build_textures(tex_dir):
    os.makedirs(tex_dir, exist_ok=True)
    out = {}
    weave = gen_cloth_weave(512, threads=44)
    p = os.path.join(tex_dir, "tls_chr_001_tex_cloth_weave.png")
    img_from_array("tls_tex_cloth_weave", weave, filepath=p)
    out["weave"] = p
    leather = gen_leather_grain(512)
    p = os.path.join(tex_dir, "tls_chr_001_tex_leather_grain.png")
    img_from_array("tls_tex_leather_grain", leather, filepath=p)
    out["leather"] = p
    micro = gen_skin_micro(512)
    p = os.path.join(tex_dir, "tls_chr_001_tex_skin_micro.png")
    img_from_array("tls_tex_skin_micro", micro, filepath=p)
    out["skin"] = p
    iris = gen_iris(512, base=(0.26, 0.29, 0.33))
    p = os.path.join(tex_dir, "tls_chr_001_tex_iris_gray.png")
    img_from_array("tls_tex_iris_gray", iris, filepath=p, colorspace='sRGB')
    out["iris"] = p
    hair = gen_hair_alpha(512)
    p = os.path.join(tex_dir, "tls_chr_001_tex_hair_alpha.png")
    img_from_array("tls_tex_hair_alpha", hair, filepath=p, colorspace='sRGB')
    out["hair_alpha"] = p
    return out

def _load(path):
    return bpy.data.images.load(path, check_existing=True) if (bpy := __import__("bpy")) else None

def _principled(m):
    return next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')

def _object_coord_chain(m):
    """TexCoord(Object) node pair reused by region masks."""
    nt = m.node_tree
    tc = nt.nodes.new('ShaderNodeTexCoord')
    return tc

def _region_mask(m, tc, center, r_in, r_out):
    """1 at distance<=r_in from center, fading to 0 at r_out (object space)."""
    nt = m.node_tree
    sub = nt.nodes.new('ShaderNodeVectorMath')
    sub.operation = 'SUBTRACT'
    sub.inputs[1].default_value = center
    nt.links.new(tc.outputs['Object'], sub.inputs[0])
    ln = nt.nodes.new('ShaderNodeVectorMath')
    ln.operation = 'LENGTH'
    nt.links.new(sub.outputs['Vector'], ln.inputs[0])
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = r_in
    mr.inputs['From Max'].default_value = r_out
    mr.inputs['To Min'].default_value = 1.0
    mr.inputs['To Max'].default_value = 0.0
    mr.clamp = True
    nt.links.new(ln.outputs['Value'], mr.inputs['Value'])
    return mr

def _mix_over_base(m, mask_out, tint, fac=1.0, blend='MIX'):
    """Chain mask->tint on top of the current Base Color input."""
    nt = m.node_tree
    bsdf = _principled(m)
    bc = _find_socket(bsdf, ["Base Color"])
    src = bc.links[0].from_socket if bc.links else None
    base_val = bc.default_value
    mix = nt.nodes.new('ShaderNodeMixRGB')
    mix.blend_type = blend
    mix.inputs['Fac'].default_value = fac
    mix.inputs['Color2'].default_value = (tint + (1.0,)) if len(tint) == 3 else tint
    if src:
        nt.links.new(src, mix.inputs['Color1'])
    else:
        mix.inputs['Color1'].default_value = base_val
    if mask_out is not None:
        nt.links.new(mask_out, mix.inputs['Fac'])
    nt.links.new(mix.outputs['Color'], bc)
    return mix

def _apply_card_texture(m, img):
    """M3.6 NOTE - DISABLED IN PRODUCTION: the strand RGBA texture renders
    clean on isolated test quads at every scale, but on the character every
    card develops hard-edged dark "chips" (8 isolation renders: not alpha
    wiring, not UVs, not EdgeSplit, not Subsurf, not shadows, not specular,
    not mip/minification). Root cause NOT identified within this milestone;
    the geometric-taper route (solid cards, width taper to 25%) is proven
    clean by the red-material isolation render, so that ships instead.
    Kept for the next grooming pass."""
    import bpy
    nt = m.node_tree
    bsdf = _principled(m)
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nt.links.new(tc.outputs['UV'], tex.inputs['Vector'])
    # base color = tint * card value gradient
    bc = _find_socket(bsdf, ["Base Color"])
    base_val = tuple(bc.default_value)[:3]
    mix = nt.nodes.new('ShaderNodeMixRGB')
    mix.blend_type = 'MULTIPLY'
    mix.inputs['Fac'].default_value = 1.0
    mix.inputs['Color1'].default_value = (base_val + (1.0,))
    nt.links.new(tex.outputs['Color'], mix.inputs['Color2'])
    nt.links.new(mix.outputs['Color'], bc)
    # tapered alpha
    alpha = _find_socket(bsdf, ["Alpha"])
    if alpha is not None:
        nt.links.new(tex.outputs['Alpha'], alpha)
    try:
        m.blend_method = 'BLEND'
    except Exception:
        pass
    return tex

def build_materials(texs):
    import bpy
    M = {}

    # ---- skin (head/body): subsurface + pore micro bump + beard shadow
    # M3.6: paler/desaturated complexion, SSS weight 0.14->0.26 with warmer
    # radius, roughness band 0.46-0.55 -> 0.42-0.62 (was reading as plastic)
    m = new_mat("TLS_Edmund_Skin", base=(0.470, 0.330, 0.252), rough=0.52,
                sss_weight=0.26, sss_radius=(0.0145, 0.0062, 0.0036),
                sss_scale=0.020, spec=0.42)
    img = bpy.data.images.load(texs["skin"], check_existing=True)
    add_bump(m, img, scale=0.13, distance=0.0008)
    nt = m.node_tree
    bsdf = _principled(m)
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 28.0
    noise.inputs['Detail'].default_value = 6.0
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = 0.0
    mr.inputs['From Max'].default_value = 1.0
    mr.inputs['To Min'].default_value = 0.42
    mr.inputs['To Max'].default_value = 0.62
    nt.links.new(noise.outputs['Fac'], mr.inputs['Value'])
    nt.links.new(mr.outputs['Result'], _find_socket(bsdf, ["Roughness"]))
    # subtle color variation (cheeks/lips redder via AO-less noise)
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.44, 0.30, 0.24, 1)
    ramp.color_ramp.elements[1].color = (0.52, 0.35, 0.28, 1)
    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    mixc = nt.nodes.new('ShaderNodeMixRGB')
    mixc.blend_type = 'MULTIPLY'
    mixc.inputs['Fac'].default_value = 0.25
    nt.links.new(ramp.outputs['Color'], mixc.inputs['Color1'])
    bsdf_bc = _find_socket(bsdf, ["Base Color"])
    try:
        base_val = bsdf_bc.default_value
        mixc.inputs['Color2'].default_value = base_val
        nt.links.new(mixc.outputs['Color'], bsdf_bc)
    except Exception:
        pass
    # M3.6 beard-region shadow: blue-gray darkening under the stubble cards so
    # the jaw reads as skin-with-stubble instead of pink-with-dots
    # (radius band 0.085..0.145 covers the actual lower-face surface shell)
    tc = _object_coord_chain(m)
    mask = _region_mask(m, tc, _HEAD_C, 0.085, 0.145)
    # keep it to the lower-front head region only
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs['Vector'])
    zok = nt.nodes.new('ShaderNodeMath')
    zok.operation = 'GREATER_THAN'
    zok.inputs[1].default_value = _HEAD_C[2] - 0.125
    nt.links.new(sep.outputs['Z'], zok.inputs[0])
    yok = nt.nodes.new('ShaderNodeMath')
    yok.operation = 'LESS_THAN'
    yok.inputs[1].default_value = _HEAD_C[1] - 0.020
    nt.links.new(sep.outputs['Y'], yok.inputs[0])
    andn = nt.nodes.new('ShaderNodeMath')
    andn.operation = 'MINIMUM'
    nt.links.new(mask.outputs['Result'], andn.inputs[0])
    nt.links.new(zok.outputs['Value'], andn.inputs[1])
    and2 = nt.nodes.new('ShaderNodeMath')
    and2.operation = 'MINIMUM'
    nt.links.new(andn.outputs['Value'], and2.inputs[0])
    nt.links.new(yok.outputs['Value'], and2.inputs[1])
    # unevenness
    nshadow = nt.nodes.new('ShaderNodeTexNoise')
    nshadow.inputs['Scale'].default_value = 42.0
    nshadow.inputs['Detail'].default_value = 5.0
    nt.links.new(tc.outputs['Object'], nshadow.inputs['Vector'])
    smul = nt.nodes.new('ShaderNodeMath')
    smul.operation = 'MULTIPLY'
    nt.links.new(and2.outputs['Value'], smul.inputs[0])
    nt.links.new(nshadow.outputs['Fac'], smul.inputs[1])
    _mix_over_base(m, smul.outputs['Value'], (0.33, 0.31, 0.30), blend='MULTIPLY')
    # M3.6: cavity shading via Pointiness - concave skin (eye sockets, nostrils,
    # lip line, pores) darkens subtly; kills the uniform plastic look
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    pt = nt.nodes.new('ShaderNodeMapRange')
    pt.inputs['From Min'].default_value = 0.50
    pt.inputs['From Max'].default_value = 0.56
    pt.inputs['To Min'].default_value = 0.30
    pt.inputs['To Max'].default_value = 0.0
    pt.clamp = True
    nt.links.new(geo.outputs['Pointiness'], pt.inputs['Value'])
    cav = nt.nodes.new('ShaderNodeMixRGB')
    cav.blend_type = 'MULTIPLY'
    cav.inputs['Color2'].default_value = (0.72, 0.68, 0.66, 1.0)
    nt.links.new(pt.outputs['Result'], cav.inputs['Fac'])
    bc2 = _find_socket(bsdf, ["Base Color"])
    src2 = bc2.links[0].from_socket if bc2.links else None
    if src2:
        nt.links.new(src2, cav.inputs['Color1'])
    else:
        cav.inputs['Color1'].default_value = tuple(bc2.default_value)
    nt.links.new(cav.outputs['Color'], bc2)
    M["skin"] = m

    # ---- left hand skin with permanent ink stains (CHR-01 detail)
    # M3.6: stain radius 0.012-0.038 -> 0.006-0.024 (was flooding the hand)
    m2 = m.copy()
    m2.name = "TLS_Edmund_Skin_InkedL"
    nt = m2.node_tree
    bsdf = _principled(m2)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mask = _region_mask(m2, tc, _INK_HAND_C, 0.006, 0.024)
    noise2 = nt.nodes.new('ShaderNodeTexNoise')
    noise2.inputs['Scale'].default_value = 55.0
    noise2.inputs['Detail'].default_value = 8.0
    nt.links.new(tc.outputs['Object'], noise2.inputs['Vector'])
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    nt.links.new(mask.outputs['Result'], mul.inputs[0])
    nt.links.new(noise2.outputs['Fac'], mul.inputs[1])
    mr3 = nt.nodes.new('ShaderNodeMapRange')
    mr3.inputs['From Min'].default_value = 0.25
    mr3.inputs['From Max'].default_value = 0.75
    mr3.inputs['To Min'].default_value = 0.0
    mr3.inputs['To Max'].default_value = 1.0
    mr3.clamp = True
    nt.links.new(mul.outputs['Value'], mr3.inputs['Value'])
    bc = _find_socket(bsdf, ["Base Color"])
    src = bc.links[0].from_socket if bc.links else None
    mixi = nt.nodes.new('ShaderNodeMixRGB')
    mixi.blend_type = 'MIX'
    mixi.inputs['Color2'].default_value = (0.014, 0.015, 0.024, 1.0)
    nt.links.new(mr3.outputs['Result'], mixi.inputs['Fac'])
    if src:
        nt.links.new(src, mixi.inputs['Color1'])
    nt.links.new(mixi.outputs['Color'], bc)
    M["skin_ink"] = m2

    # ---- eyes (wetter cornea kept from M3.5; sclera/iris from v2 texture)
    m = new_mat("TLS_Edmund_Eye", base=(0.85, 0.85, 0.85), rough=0.07, spec=0.7,
                coat=0.28, coat_rough=0.12)
    img = bpy.data.images.load(texs["iris"], check_existing=True)
    try:
        img.colorspace_settings.name = 'sRGB'
    except Exception:
        pass
    nt = m.node_tree
    bsdf = _principled(m)
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nt.links.new(tc.outputs['UV'], tex.inputs['Vector'])
    nt.links.new(tex.outputs['Color'], _find_socket(bsdf, ["Base Color"]))
    M["eye"] = m

    # ---- hair / brow / stubble: strand-card materials with alpha taper
    img = bpy.data.images.load(texs["hair_alpha"], check_existing=True)
    try:
        img.colorspace_settings.name = 'sRGB'
    except Exception:
        pass
    # M3.6 v5: SOLID card material (no alpha texture - see _apply_card_texture
    # note). Value breakup comes from geometry: tapered widths + length variance.
    m = new_mat("TLS_Edmund_Hair", base=(0.021, 0.013, 0.008), rough=0.55,
                spec=0.06, sheen=0.10, sheen_rough=0.5)
    M["hair"] = m
    # M3.6: SOLID variant for the scalp cap - the cap's UV spans the whole
    # dome, so the strand-card alpha texture on it produced huge blocky
    # transparent rectangles on the crown (found on iter-2 render)
    M["hair_cap"] = new_mat("TLS_Edmund_HairCap", base=(0.040, 0.024, 0.014),
                            rough=0.50, spec=0.25)
    M["brow"] = m.copy(); M["brow"].name = "TLS_Edmund_Brow"
    set_principled(_principled(M["brow"]), base_color=(0.034, 0.021, 0.012))
    M["stubble"] = m.copy(); M["stubble"].name = "TLS_Edmund_Stubble"
    # stubble slightly lighter than scalp hair (2-week beard shadow)
    set_principled(_principled(M["stubble"]), base_color=(0.070, 0.046, 0.030),
                   roughness=0.52)

    # ---- wool coat (charcoal London gray - darker than M3.5, reads 1847)
    m = new_mat("TLS_Edmund_CoatWool", base=(0.034, 0.037, 0.043), rough=0.90,
                sheen=0.35, sheen_rough=0.4)
    img = bpy.data.images.load(texs["weave"], check_existing=True)
    add_bump(m, img, scale=0.38, distance=0.0018)
    add_image_tex(m, img, coords='UV', scale=(9, 9, 1), vector_sock="Roughness",
                  color2=(1.6, 1.6, 1.6), blend_mode='MULTIPLY', noncolor=True)
    # M3.6: rain-damp hem - darker + slightly glossier toward the hem
    nt = m.node_tree
    bsdf = _principled(m)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs['Vector'])
    hem = nt.nodes.new('ShaderNodeMapRange')
    hem.inputs['From Min'].default_value = 0.80
    hem.inputs['From Max'].default_value = 0.56
    hem.inputs['To Min'].default_value = 0.0
    hem.inputs['To Max'].default_value = 0.55
    hem.clamp = True
    nt.links.new(sep.outputs['Z'], hem.inputs['Value'])
    _mix_over_base(m, hem.outputs['Result'], (0.024, 0.025, 0.028), blend='MIX')
    M["coat"] = m

    # ---- waistcoat (dark brown wool - separated from coat & trousers)
    m = new_mat("TLS_Edmund_Waistcoat", base=(0.082, 0.062, 0.041), rough=0.86,
                sheen=0.25)
    img = bpy.data.images.load(texs["weave"], check_existing=True)
    add_bump(m, img, scale=0.30, distance=0.0015)
    M["waistcoat"] = m

    # ---- linen shirt (ivory)
    m = new_mat("TLS_Edmund_ShirtLinen", base=(0.545, 0.508, 0.442), rough=0.82)
    img = bpy.data.images.load(texs["weave"], check_existing=True)
    add_bump(m, img, scale=0.22, distance=0.0012)
    M["shirt"] = m

    # ---- neckcloth (black silk stock)
    M["neckcloth"] = new_mat("TLS_Edmund_Neckcloth", base=(0.022, 0.022, 0.024),
                             rough=0.40, sheen=0.35)

    # ---- trousers (warm dark-brown wool - clearly not the coat's gray)
    m = new_mat("TLS_Edmund_TrousersWool", base=(0.048, 0.039, 0.030), rough=0.88)
    img = bpy.data.images.load(texs["weave"], check_existing=True)
    add_bump(m, img, scale=0.28, distance=0.0015)
    M["trousers"] = m

    # ---- boots (black-brown leather)
    m = new_mat("TLS_Edmund_BootLeather", base=(0.032, 0.024, 0.018), rough=0.38,
                coat=0.28, coat_rough=0.25)
    img = bpy.data.images.load(texs["leather"], check_existing=True)
    add_bump(m, img, scale=0.30, distance=0.0022)
    M["boot"] = m

    # ---- satchel leather (mid brown, engraved)
    m = new_mat("TLS_Edmund_SatchelLeather", base=(0.105, 0.062, 0.034), rough=0.52,
                coat=0.10)
    img = bpy.data.images.load(texs["leather"], check_existing=True)
    add_bump(m, img, scale=0.45, distance=0.0030)
    M["satchel"] = m

    # ---- brass fittings with roughness breakup + mild patina (M3.6)
    m = new_mat("TLS_Edmund_Brass", base=(0.62, 0.42, 0.16), rough=0.34,
                metallic=1.0)
    nt = m.node_tree
    bsdf = _principled(m)
    nb = nt.nodes.new('ShaderNodeTexNoise')
    nb.inputs['Scale'].default_value = 18.0
    nb.inputs['Detail'].default_value = 4.0
    mrb = nt.nodes.new('ShaderNodeMapRange')
    mrb.inputs['From Min'].default_value = 0.0
    mrb.inputs['From Max'].default_value = 1.0
    mrb.inputs['To Min'].default_value = 0.22
    mrb.inputs['To Max'].default_value = 0.48
    nt.links.new(nb.outputs['Fac'], mrb.inputs['Value'])
    nt.links.new(mrb.outputs['Result'], _find_socket(bsdf, ["Roughness"]))
    pat = nt.nodes.new('ShaderNodeMixRGB')
    pat.blend_type = 'MULTIPLY'
    pat.inputs['Fac'].default_value = 0.35
    pat.inputs['Color2'].default_value = (0.55, 0.50, 0.42, 1.0)
    nt.links.new(nb.outputs['Fac'], pat.inputs['Fac'])
    nt.links.new(pat.outputs['Color'], _find_socket(bsdf, ["Base Color"]))
    M["brass"] = m

    # ---- boot sole
    M["sole"] = new_mat("TLS_Edmund_SoleLeather", base=(0.015, 0.013, 0.011),
                        rough=0.65)

    # ---- studio + cinematic helpers (not part of character export)
    M["backdrop"] = new_mat("TLS_Studio_Backdrop", base=(0.52, 0.52, 0.53),
                            rough=0.9)
    M["ground_cine"] = new_mat("TLS_Cine_Ground", base=(0.020, 0.021, 0.024),
                               rough=0.35, spec=0.6)
    return M
