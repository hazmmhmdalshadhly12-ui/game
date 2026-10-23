#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Edmund Vale - PBR materials + generated texture set.
Textures are generated procedurally (numpy) and saved as real PNG files that
ship with the character (also packed into the .blend).
"""
import math, os
import numpy as np
from edmund_lib import (new_mat, set_principled, add_image_tex, add_bump,
                        img_from_array, gen_cloth_weave, gen_leather_grain,
                        gen_skin_micro, gen_iris, _find_socket)

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
    return out

def _load(path):
    return bpy.data.images.load(path, check_existing=True) if (bpy := __import__("bpy")) else None

def build_materials(texs):
    import bpy
    M = {}

    # ---- skin (head/body): subsurface + pore micro bump
    m = new_mat("TLS_Edmund_Skin", base=(0.545, 0.390, 0.300), rough=0.46,
                sss_weight=0.14, sss_radius=(0.011, 0.0035, 0.0022),
                sss_scale=0.016, spec=0.35)
    img = bpy.data.images.load(texs["skin"], check_existing=True)
    add_bump(m, img, scale=0.22, distance=0.0012)
    # subtle roughness breakup
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 28.0
    noise.inputs['Detail'].default_value = 6.0
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = 0.0
    mr.inputs['From Max'].default_value = 1.0
    mr.inputs['To Min'].default_value = 0.40
    mr.inputs['To Max'].default_value = 0.55
    nt.links.new(noise.outputs['Fac'], mr.inputs['Value'])
    nt.links.new(mr.outputs['Result'], _find_socket(bsdf, ["Roughness"]))
    # slight color variation (cheeks/lips redder via AO-less noise)
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.50, 0.36, 0.28, 1)
    ramp.color_ramp.elements[1].color = (0.60, 0.42, 0.33, 1)
    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    mixc = nt.nodes.new('ShaderNodeMixRGB')
    mixc.blend_type = 'MULTIPLY'
    mixc.inputs['Fac'].default_value = 0.25
    nt.links.new(ramp.outputs['Color'], mixc.inputs['Color1'])
    bsdf_bc = _find_socket(bsdf, ["Base Color"])
    # pull existing base color into mix Color2
    try:
        base_val = bsdf_bc.default_value
        mixc.inputs['Color2'].default_value = base_val
        nt.links.new(mixc.outputs['Color'], bsdf_bc)
    except Exception:
        pass
    M["skin"] = m

    # ---- left hand skin with permanent ink stains (CHR-01 detail)
    m2 = m.copy()
    m2.name = "TLS_Edmund_Skin_InkedL"
    nt = m2.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs['Vector'])
    # mask around back of left hand (object coords == world, object at origin)
    sub = nt.nodes.new('ShaderNodeVectorMath')
    sub.operation = 'SUBTRACT'
    sub.inputs[1].default_value = (-0.338, -0.108, 0.862)
    nt.links.new(tc.outputs['Object'], sub.inputs[0])
    ln = nt.nodes.new('ShaderNodeVectorMath')
    ln.operation = 'LENGTH'
    nt.links.new(sub.outputs['Vector'], ln.inputs[0])
    mr2 = nt.nodes.new('ShaderNodeMapRange')
    mr2.inputs['From Min'].default_value = 0.030
    mr2.inputs['From Max'].default_value = 0.055
    mr2.inputs['To Min'].default_value = 1.0
    mr2.inputs['To Max'].default_value = 0.0
    nt.links.new(ln.outputs['Value'], mr2.inputs['Value'])
    noise2 = nt.nodes.new('ShaderNodeTexNoise')
    noise2.inputs['Scale'].default_value = 55.0
    noise2.inputs['Detail'].default_value = 8.0
    nt.links.new(tc.outputs['Object'], noise2.inputs['Vector'])
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    nt.links.new(mr2.outputs['Result'], mul.inputs[0])
    nt.links.new(noise2.outputs['Fac'], mul.inputs[1])
    mr3 = nt.nodes.new('ShaderNodeMapRange')
    mr3.inputs['From Min'].default_value = 0.25
    mr3.inputs['From Max'].default_value = 0.75
    mr3.inputs['To Min'].default_value = 0.0
    mr3.inputs['To Max'].default_value = 1.0
    mr3.clamp = True
    nt.links.new(mul.outputs['Value'], mr3.inputs['Value'])
    mixi = nt.nodes.new('ShaderNodeMixRGB')
    mixi.blend_type = 'MIX'
    mixi.inputs['Color2'].default_value = (0.018, 0.020, 0.030, 1.0)
    nt.links.new(mr3.outputs['Result'], mixi.inputs['Fac'])
    bc = _find_socket(bsdf, ["Base Color"])
    # chain: current base (already linked from mixc on the copy) -> mixi -> base
    src = bc.links[0].from_socket if bc.links else None
    if src:
        nt.links.new(src, mixi.inputs['Color1'])
    nt.links.new(mixi.outputs['Color'], bc)
    # ink areas less rough/glossy
    M["skin_ink"] = m2

    # ---- eyes
    m = new_mat("TLS_Edmund_Eye", base=(0.85, 0.85, 0.85), rough=0.08, spec=0.6)
    img = bpy.data.images.load(texs["iris"], check_existing=True)
    try:
        img.colorspace_settings.name = 'sRGB'
    except Exception:
        pass
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nt.links.new(tc.outputs['UV'], tex.inputs['Vector'])
    nt.links.new(tex.outputs['Color'], _find_socket(bsdf, ["Base Color"]))
    M["eye"] = m

    # ---- hair (dark unkempt brown per CHR-01)
    m = new_mat("TLS_Edmund_Hair", base=(0.026, 0.0155, 0.0095), rough=0.45, spec=0.25)
    M["hair"] = m
    M["brow"] = m.copy(); M["brow"].name = "TLS_Edmund_Brow"
    set_p = None
    M["stubble"] = m.copy(); M["stubble"].name = "TLS_Edmund_Stubble"
    # stubble slightly lighter than scalp hair (2-week beard shadow)
    st_bsdf = next(n for n in M["stubble"].node_tree.nodes
                   if n.type == 'BSDF_PRINCIPLED')
    set_principled(st_bsdf, base_color=(0.045, 0.028, 0.018))

    # ---- wool coat (London gray)
    m = new_mat("TLS_Edmund_CoatWool", base=(0.148, 0.155, 0.168), rough=0.88,
                sheen=0.35, sheen_rough=0.4)
    img = bpy.data.images.load(texs["weave"], check_existing=True)
    bump = add_bump(m, img, scale=0.35, distance=0.0018)
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    add_image_tex(m, img, coords='UV', scale=(9, 9, 1), vector_sock="Roughness",
                  color2=(1.6, 1.6, 1.6), blend_mode='MULTIPLY', noncolor=True)
    M["coat"] = m

    # ---- waistcoat (dark brown-charcoal wool)
    m = new_mat("TLS_Edmund_Waistcoat", base=(0.075, 0.062, 0.050), rough=0.85,
                sheen=0.25)
    img = bpy.data.images.load(texs["weave"], check_existing=True)
    add_bump(m, img, scale=0.30, distance=0.0015)
    M["waistcoat"] = m

    # ---- linen shirt (cream)
    m = new_mat("TLS_Edmund_ShirtLinen", base=(0.62, 0.585, 0.520), rough=0.80)
    img = bpy.data.images.load(texs["weave"], check_existing=True)
    add_bump(m, img, scale=0.22, distance=0.0012)
    M["shirt"] = m

    # ---- neckcloth (black silk)
    M["neckcloth"] = new_mat("TLS_Edmund_Neckcloth", base=(0.022, 0.022, 0.024),
                             rough=0.42, sheen=0.2)

    # ---- trousers (dark gray-brown wool)
    m = new_mat("TLS_Edmund_TrousersWool", base=(0.068, 0.062, 0.056), rough=0.88)
    img = bpy.data.images.load(texs["weave"], check_existing=True)
    add_bump(m, img, scale=0.28, distance=0.0015)
    M["trousers"] = m

    # ---- boots (black-brown leather)
    m = new_mat("TLS_Edmund_BootLeather", base=(0.032, 0.024, 0.018), rough=0.42,
                coat=0.15, coat_rough=0.3)
    img = bpy.data.images.load(texs["leather"], check_existing=True)
    add_bump(m, img, scale=0.30, distance=0.0022)
    M["boot"] = m

    # ---- satchel leather (mid brown, engraved)
    m = new_mat("TLS_Edmund_SatchelLeather", base=(0.105, 0.062, 0.034), rough=0.50,
                coat=0.10)
    img = bpy.data.images.load(texs["leather"], check_existing=True)
    add_bump(m, img, scale=0.45, distance=0.0030)
    M["satchel"] = m

    # ---- brass fittings
    M["brass"] = new_mat("TLS_Edmund_Brass", base=(0.62, 0.42, 0.16), rough=0.34,
                         metallic=1.0)

    # ---- boot sole
    M["sole"] = new_mat("TLS_Edmund_SoleLeather", base=(0.015, 0.013, 0.011),
                        rough=0.65)

    # ---- studio + cinematic helpers (not part of character export)
    M["backdrop"] = new_mat("TLS_Studio_Backdrop", base=(0.52, 0.52, 0.53),
                            rough=0.9)
    M["ground_cine"] = new_mat("TLS_Cine_Ground", base=(0.020, 0.021, 0.024),
                               rough=0.35, spec=0.6)
    return M
