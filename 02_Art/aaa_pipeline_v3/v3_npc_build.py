#!/usr/bin/env python3
"""Build the 4 named NPCs with DISTINCT identities via HeadMorph parameters."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v3_anatomy import HeadMorph
from v3_loft import build_head_loft

NPCS = {
    "gwendolyn": dict(fem=1.0, age=41.0, faceW=1.04, jawW=0.92, browP=0.70,
                      lipU=1.15, lipL=1.20, cheek=1.15, noseW=0.95, noseP=0.90,
                      noseL=0.96, chinP=-0.002, eyeTilt=0.15, cranW=1.02,
                      asym=0.018, asymSeed=21),
    "crane":     dict(fem=0.0, age=58.0, faceW=0.97, jawW=0.95, browP=1.10,
                      lipU=0.92, lipL=0.90, cheek=0.80, noseL=1.08, noseW=1.00,
                      noseP=1.05, noseB=0.5, chinP=0.001, eyeD=1.08, templeH=1.0,
                      asym=0.020, asymSeed=33),
    "mair":      dict(fem=1.0, age=19.0, faceW=0.98, jawW=0.88, browP=0.55,
                      lipU=1.25, lipL=1.30, cheek=1.25, noseW=0.90, noseP=0.85,
                      noseL=0.92, chinP=-0.004, eyeW=1.05, cranW=1.03,
                      asym=0.012, asymSeed=5),
    "tom":       dict(fem=0.0, age=63.0, faceW=1.05, jawW=1.08, browP=1.15,
                      lipU=0.95, lipL=1.02, cheek=0.90, noseW=1.12, noseP=1.00,
                      noseL=1.02, chinP=0.003, eyeTilt=-0.10, asym=0.025, asymSeed=44),
}

if __name__ == "__main__":
    for name, params in NPCS.items():
        m = HeadMorph(**params)
        build_head_loft(m, f"/home/z/my-project/work/v3/{name}_loft")
        print("BUILT", name, flush=True)
