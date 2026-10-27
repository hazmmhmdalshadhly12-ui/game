#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE LAST SIN - ready-made PBR material factory for M4 assets.
Texture sets live in 02_Art/textures/materials/<tag>/tls_tex_<tag>_{BaseColor,Normal,ORM}.png
Alpha cards live in 02_Art/textures/nature/tls_tex_card_<tag>.png
"""
import os
import tls_lib as L

_TEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "textures")
SETS = os.path.join(_TEX, "materials")
NAT = os.path.join(_TEX, "nature")

_cache = {}

def pbr(name, tag, base=(1, 1, 1), override_rough=None, override_metal=None,
        ao=0.9, normal_strength=1.0):
    """Material wired to a saved texture set (BaseColor/Normal/ORM)."""
    key = (name, tag)
    if key in _cache:
        return _cache[key]
    d = os.path.join(SETS, tag)
    bc_p = os.path.join(d, f"tls_tex_{tag}_BaseColor.png")
    nm_p = os.path.join(d, f"tls_tex_{tag}_Normal.png")
    orm_p = os.path.join(d, f"tls_tex_{tag}_ORM.png")
    for p in (bc_p, nm_p, orm_p):
        if not os.path.exists(p):
            raise FileNotFoundError(f"texture set missing: {p}")
    m = L.new_mat(name, base=base, rough=override_rough or 0.7,
                  metallic=override_metal or 0.0)
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    orm_img = L.load_png(orm_p, f"{name}_ORM", 'Non-Color')
    bc_img = L.load_png(bc_p, f"{name}_BC", 'sRGB')
    nm_img = L.load_png(nm_p, f"{name}_NM", 'Non-Color')
    L.add_orm(m, orm_img, ao_strength=ao)
    # base color image chained under AO multiply
    mul = None
    for l in nt.links:
        if l.to_socket == bsdf.inputs['Base Color'] and l.from_node.type == 'MIX_RGB':
            mul = l.from_node
            break
    if mul:
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = bc_img
        nt.links.new(tex.outputs['Color'], mul.inputs['Color1'])
    nm_node = nt.nodes.new('ShaderNodeNormalMap')
    nm_node.inputs['Strength'].default_value = normal_strength
    nm_tex = nt.nodes.new('ShaderNodeTexImage')
    nm_tex.image = nm_img
    nt.links.new(nm_tex.outputs['Color'], nm_node.inputs['Color'])
    nt.links.new(nm_node.outputs['Normal'], bsdf.inputs['Normal'])
    if override_rough is not None:
        L.set_principled(bsdf, roughness=override_rough)
    if override_metal is not None:
        L.set_principled(bsdf, metallic=override_metal)
    _cache[key] = m
    return m

def card(name, tag, base=(1, 1, 1), backface=True):
    """Alpha-card material for foliage (uses PNG alpha channel)."""
    p = os.path.join(NAT, f"tls_tex_card_{tag}.png")
    if not os.path.exists(p):
        raise FileNotFoundError(p)
    m = L.new_mat(name, base=base, rough=0.75)
    img = L.load_png(p, f"{name}_Card", 'sRGB')
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
    try:
        m.blend_method = 'CLIP'
    except Exception:
        pass
    try:
        m.use_backface_culling = backface
    except Exception:
        pass
    return m

def plain(name, base, rough=0.6, metal=0.0, **extra):
    return L.new_mat(name, base=base, rough=rough, metal=metal, **extra)

def emissive(name, base, strength=3.0):
    m = L.new_mat(name, base=base, rough=0.5)
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    L.set_principled(bsdf, emission=base, emission_strength=strength)
    return m
